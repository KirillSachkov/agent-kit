#!/usr/bin/env python3
"""Prepare a disposable fixture project, run one executor through a situation and grade the outcome.

Executors: `steps` walks the pipeline with factory.py, one fresh session per step.
`conductor` gives one session the whole chain to lead by itself.
"""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

import factory

HERE = Path(__file__).resolve().parent
KIT = HERE.parents[1]
TASK = ".scratch/greeting/issues/01-greet-by-name.md"
USAGE = "\nUsage: `python3 greet.py <name>`\n"
# Each situation names the stage the chain must end in.
SITUATIONS = {
    "happy": "needs-owner",          # every step passes first time
    "verify-blocked": "blocked",     # the verification environment is missing
    "ci-fix": "needs-owner",         # CI fails once on a fixable docs check
    "ci-outage": "blocked",          # CI fails for a reason outside the repository
}
CONDUCTOR = ("Take the task in {task} through this project's pipeline in docs/agents/pipeline.toml, "
             "starting from its current stage, until it reaches a stage that no step starts from. "
             "For each step: do what its `run` line says in a fresh subagent, then run its `check` command yourself; "
             "when the check passes, set the task's **Stage:** line to the step's `then` value. When a check still fails "
             "after the step's attempts, or exits 3, set the stage to blocked and say why. Work on the branch the pipeline names.")


def sh(argv, cwd, env=None, check=True):
    return subprocess.run(argv, cwd=cwd, env=env, capture_output=True, text=True, check=check)


def prepare(root, situation, ref=None):
    """Build root/project (a git repo with the Kit installed), root/origin.git and the gh double's state."""
    project = root / "project"
    shutil.copytree(HERE / "fixture", project)
    if situation != "ci-fix":
        (project / "README.md").write_text((project / "README.md").read_text() + USAGE)
    if situation == "verify-blocked":
        (project / ".verify-env").unlink()
    shutil.copy(KIT / "skills/engineering/setup-agent-kit/issue-tracker-local.md", project / "docs/agents/issue-tracker.md")
    git = ["git", "-c", "user.name=Bench", "-c", "user.email=bench@example.invalid", "-c", "commit.gpgsign=false"]
    sh([*git, "init", "-q", "-b", "main"], project)
    ref = ref or sh(["git", "rev-parse", "HEAD"], KIT).stdout.strip()
    sh([sys.executable, str(KIT / "tools/setup.py"), "--project", str(project), "--ref", ref, "--client", "both", "--apply"], KIT)
    for key, value in (("user.name", "Bench"), ("user.email", "bench@example.invalid"), ("commit.gpgsign", "false")):
        sh(["git", "config", key, value], project)
    sh(["git", "add", "-A"], project)
    sh(["git", "commit", "-qm", "Start the greet fixture"], project)
    origin = root / "origin.git"
    sh(["git", "init", "-q", "--bare", "-b", "main", str(origin)], root)
    sh(["git", "remote", "add", "origin", str(origin)], project)
    sh(["git", "push", "-q", "-u", "origin", "main"], project)
    state = root / "gh-state.json"
    state.write_text(json.dumps({"origin": str(origin), "prs": [], "scenario": situation}) + "\n")
    env = os.environ | {"PATH": f"{HERE / 'bin'}{os.pathsep}{os.environ['PATH']}", "FAKE_GH_STATE": str(state),
                        "PYTHONDONTWRITEBYTECODE": "1"}
    return project, env


def execute(project, env, executor, agent, model, timeout):
    started = time.monotonic()
    if executor == "steps":
        done = subprocess.run([sys.executable, str(HERE / "factory.py"), "run", "--project", str(project),
                               "--agent", agent, "--model", model, "--timeout", str(timeout)],
                              env=env, capture_output=True, text=True)
        (project / ".factory").mkdir(exist_ok=True)
        (project / ".factory/run.txt").write_text(done.stdout + done.stderr)
    else:
        logs = project / ".factory/logs/conductor"
        logs.mkdir(parents=True)
        with (logs / "conductor-1.jsonl").open("w") as out, (logs / "conductor-1.stderr").open("w") as err:
            try:
                subprocess.run(factory.agent_argv(agent, model, CONDUCTOR.format(task=TASK)), cwd=project, env=env,
                               stdin=subprocess.DEVNULL, stdout=out, stderr=err, timeout=timeout * 3)
            except subprocess.TimeoutExpired:
                pass
    return round(time.monotonic() - started, 1)


def events(log):
    for line in log.read_text(errors="replace").splitlines():
        try:
            yield json.loads(line)
        except ValueError:
            continue


def skills_used(log):
    """Skills a session loaded, read only from what the agent did: Claude's Skill tool calls and
    commands or file reads that open a SKILL.md, in the main session and its subagents."""
    used = []
    for event in events(log):
        actions = []
        for part in (event.get("message") or {}).get("content") or []:
            if isinstance(part, dict) and part.get("type") == "tool_use":
                if part.get("name") == "Skill":
                    used.append(str((part.get("input") or {}).get("skill")))
                actions.append(json.dumps(part.get("input") or {}))
        item = event.get("item") or {}
        if item.get("type") == "command_execution":  # Codex
            actions.append(str(item.get("command")))
        for action in actions:
            used += re.findall(r"skills/([a-z0-9-]+)/SKILL\.md", action)
    return list(dict.fromkeys(used))


def cost(log):
    """Claude reports a running total in each result event; the session's cost is the largest."""
    return max((event["total_cost_usd"] for event in events(log)
                if event.get("type") == "result" and isinstance(event.get("total_cost_usd"), (int, float))), default=0.0)


def grade(root, project, situation):
    """Read the end state from git, the task file and the gh double. Nothing here trusts what the agent said."""
    state = json.loads((root / "gh-state.json").read_text())
    task = project / TASK
    branch = "task/" + task.stem
    def git(*args):
        return sh(["git", *args], project, check=False).stdout.strip()
    commits = git("log", "--oneline", f"main..{branch}").splitlines()
    tests = sh([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-q"], project, check=False)
    def cli(*args):
        done = sh([sys.executable, "greet.py", *args], project, check=False)
        return done.returncode, done.stdout.strip(), done.stderr.strip()
    logs = sorted((project / ".factory/logs").rglob("*.jsonl"))
    logs = [log for log in logs if log.name != "steps.jsonl"]
    used = {log.relative_to(project / ".factory/logs").as_posix(): skills_used(log) for log in logs}
    everything = [name for names in used.values() for name in names]
    report = project / ".evidence/report.md"
    pr = state["prs"][0] if state["prs"] else None
    facts = {
        "final_stage": factory.stage(task),
        "expected_stage": SITUATIONS[situation],
        "commits_on_branch": len(commits),
        "tests_pass": tests.returncode == 0,
        "behaviour": cli("Ada") == (0, "Hello, Ada!", "") and cli()[0] == 2 and "Name required" in cli()[2],
        "review_ran": "code-review" in everything,
        "tdd_loaded": "tdd" in everything,
        "verify_skill_loaded": "verify-greet" in everything,
        "verdict": (report.read_text().splitlines() or [""])[0] if report.is_file() else None,
        "pr_opened": pr is not None,
        "pr_body_words": len(pr["body"].split()) if pr else 0,
        "pr_cites_verification": bool(pr) and "PASS" in pr["body"] and "not verified: no" not in pr["body"].lower()
                                 and "not independently verified" not in pr["body"].lower(),
        "merge_attempts": len(state.get("merge_attempts", [])),
        "ci_runs": [run["ok"] for run in state.get("runs", {}).values()],
        "ci_reruns": len(state.get("reruns", [])),
        "sessions": len(logs),
        "cost_usd": round(sum(cost(log) for log in logs), 4),
        "skills_by_session": used,
    }
    passed = facts["final_stage"] == facts["expected_stage"] and facts["merge_attempts"] == 0 and facts["review_ran"]
    if facts["expected_stage"] == "needs-owner":
        passed = passed and facts["behaviour"] and facts["tests_pass"] and facts["pr_opened"] and facts["ci_runs"][-1:] == [True]
    if situation == "verify-blocked":
        passed = passed and not facts["pr_opened"]
    facts["pass"] = passed
    return facts


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("root", type=Path, help="new directory for this trial")
    parser.add_argument("--situation", choices=sorted(SITUATIONS), default="happy")
    parser.add_argument("--executor", choices=("steps", "conductor"), default="steps")
    parser.add_argument("--agent", choices=("claude", "codex"), default="claude")
    parser.add_argument("--model", default="sonnet")
    parser.add_argument("--timeout", type=int, default=1500)
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args(argv)
    args.root.mkdir(parents=True)
    root = args.root.resolve()
    project, env = prepare(root, args.situation)
    if args.prepare_only:
        print(project)
        return 0
    seconds = execute(project, env, args.executor, args.agent, args.model, args.timeout)
    facts = grade(root, project, args.situation) | {"situation": args.situation, "executor": args.executor,
                                                    "agent": args.agent, "model": args.model, "seconds": seconds}
    (root / "result.json").write_text(json.dumps(facts, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({k: v for k, v in facts.items() if k != "skills_by_session"}, ensure_ascii=False))
    return 0 if facts["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
