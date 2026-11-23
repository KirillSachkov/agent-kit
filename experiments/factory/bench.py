#!/usr/bin/env python3
"""Prepare a disposable fixture project, lead one ticket through a situation and grade the outcome.

Entries: `deliver` says /deliver to one session, which starts the orchestrator.
`direct` starts the orchestrator from a terminal.
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


HERE = Path(__file__).resolve().parent
KIT = HERE.parents[1]
sys.path.insert(0, str(HERE / "skill/deliver"))
import orchestrator  # noqa: E402

TICKET = ".scratch/greeting/issues/01-greet-by-name.md"
SPEC = ".scratch/greeting/spec.md"
USAGE = "\nUsage: `python3 greet.py <name>`\n"
# Each situation names the stage the chain must end in.
SITUATIONS = {
    "happy": "needs-owner",          # every task passes first time
    "verify-blocked": "blocked",     # the verification environment is missing
    "ci-fix": "needs-owner",         # CI fails once on a fixable docs check
    "ci-outage": "blocked",          # CI fails for a reason outside the repository
    "spec": "needs-owner",           # a spec with three tickets, one blocked by another, delivered together
    "rework": "needs-owner",         # the owner comments on the open PR and the chain takes the work again
}
FEEDBACK = "Trim the name: `python3 greet.py ' Ada '` must print `Hello, Ada!`."
# A trial leaves no session history and reads no personal client settings.
CLIENTS = """
[agents.claude]
command = 'claude -p {prompt} --setting-sources project --model {model} --no-session-persistence --output-format stream-json --verbose --dangerously-skip-permissions'

[agents.codex]
command = '''codex exec --ignore-user-config --ephemeral --skip-git-repo-check --sandbox danger-full-access --disable apps --disable plugins --enable skip_host_skill_discovery -c 'web_search="disabled"' -m {model} --json {prompt}'''

[agents.opencode]
command = 'opencode run --standalone --archived --auto --format json -m {model} {prompt}'
skill = "@"
"""
ENTRIES = ("deliver", "direct")


def work(situation):
    return SPEC if situation == "spec" else TICKET


def sh(argv, cwd, env=None, check=True):
    return subprocess.run(argv, cwd=cwd, env=env, capture_output=True, text=True, check=check)


def prepare(root, situation, ref=None, agent="claude", model="sonnet"):
    """Build root/project (a git repo with the Kit installed), root/origin.git and the gh double's state."""
    project = root / "project"
    shutil.copytree(HERE / "fixture", project)
    scratch = HERE / ("spec-fixture" if situation == "spec" else "fixture") / "scratch"
    shutil.rmtree(project / "scratch")
    shutil.copytree(scratch, project / ".scratch")  # the Kit ignores .scratch, so the fixture stores it as scratch
    shutil.copytree(HERE / "skill/deliver", project / ".agents/skills/deliver")
    if situation != "ci-fix":
        (project / "README.md").write_text((project / "README.md").read_text() + USAGE)
    if situation == "verify-blocked":
        (project / ".verify-env").unlink()
    shutil.copy(KIT / "skills/engineering/setup-project/issue-tracker-local.md", project / "docs/agents/issue-tracker.md")
    pipeline = project / "docs/agents/pipeline.toml"
    text = pipeline.read_text()
    for key, value in (("agent", agent), ("model", model)):
        text, count = re.subn(rf'^{key} = "[^"]*"', f'{key} = "{value}"', text, count=1, flags=re.M)
        assert count == 1, key
    pipeline.write_text(text + CLIENTS)
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
    # A trial must not reach the session application that started the bench: no Orca variables, no orca command.
    env = {key: value for key, value in os.environ.items() if not key.startswith("ORCA_")}
    path = [part for part in env["PATH"].split(os.pathsep) if not (Path(part) / "orca").exists()]
    env |= {"PATH": os.pathsep.join([str(HERE / "bin"), *path]), "FAKE_GH_STATE": str(state), "PYTHONDONTWRITEBYTECODE": "1"}
    # Codex runs commands in a login shell, which rebuilds PATH from the profile: keep the gh double first there too.
    profile = root / "zsh"
    profile.mkdir()
    # The same shell would also find the system's older python3 first; keep this interpreter ahead of it.
    (profile / ".zprofile").write_text(f'export PATH="{HERE / "bin"}:{Path(sys.executable).parent}:$PATH"\n')
    env["ZDOTDIR"] = str(profile)
    return project, env


def execute(project, env, entry, agent, model, timeout, ticket, situation="happy"):
    """Lead the ticket to the end of its chain through the named entry."""
    started = time.monotonic()
    logs = project / ".factory/_session"
    logs.mkdir(parents=True)
    program = [sys.executable, str(project / ".agents/skills/deliver/orchestrator.py")]
    tail = [ticket, "--project", str(project), "--timeout", str(timeout)]
    if entry == "direct":
        argv = [*program, "run", *tail]
    else:
        argv = orchestrator.agent_argv(orchestrator.load_pipeline(project)[0], agent, model, "/deliver " + ticket)
    def call(argv, name):
        with (logs / f"{name}.jsonl").open("w") as out, (logs / f"{name}.stderr").open("w") as err:
            try:
                subprocess.run(argv, cwd=project, env=env | {"PWD": str(project)}, stdin=subprocess.DEVNULL, stdout=out,
                               stderr=err, timeout=timeout * 4)
            except subprocess.TimeoutExpired:
                pass
    call(argv, "session-1")
    call([*program, "wait", *tail], "wait-1")  # the session may end while the run it started goes on
    if situation == "rework" and orchestrator.Ticket(project, ticket).stage() == "needs-owner":
        state = json.loads((project.parent / "gh-state.json").read_text())
        state["prs"][0].setdefault("comments", []).append(FEEDBACK)
        (project.parent / "gh-state.json").write_text(json.dumps(state) + "\n")
        call([*program, "run", *tail, "--stage", "rework"], "rework-run")
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
        part = event.get("part") or {}
        if event.get("type") == "tool_use":  # OpenCode, which loads a mentioned skill without a visible call
            given = (part.get("state") or {}).get("input") or {}
            if part.get("tool") == "skill":
                used.append(str(given.get("id") or given.get("name")))
            if part.get("tool") == "subagent" and re.search(r"code.?review|standards axis|spec axis", str(given.get("description")), re.I):
                used.append("code-review")
            actions.append(json.dumps(given))
        for action in actions:
            used += re.findall(r"skills/([a-z0-9-]+)/SKILL\.md", action)
            for group in re.findall(r"skills/\{([a-z0-9,-]+)\}/SKILL\.md", action):  # a shell brace list
                used += group.split(",")
    return list(dict.fromkeys(used))


def cost(log):
    """Claude reports a running total in each result event; the session's cost is the largest.
    OpenCode reports the cost of each step. Codex reports none."""
    steps = sum((event.get("part") or {}).get("cost") or 0 for event in events(log) if event.get("type") == "step_finish")
    return steps + max((event["total_cost_usd"] for event in events(log)
                        if event.get("type") == "result" and isinstance(event.get("total_cost_usd"), (int, float))), default=0.0)


def reached_outside(logs):
    """Commands that address the host's session application or the owner's worktrees."""
    hits = []
    for log in logs:
        for event in events(log):
            commands = [json.dumps(part.get("input") or {}) for part in (event.get("message") or {}).get("content") or []
                        if isinstance(part, dict) and part.get("type") == "tool_use"]
            item = event.get("item") or {}
            if item.get("type") == "command_execution":
                commands.append(str(item.get("command")))
            hits += [c[:120] for c in commands if re.search(r"\borca (orchestration|worktree|repo|agent)\b|/Worktrees/", c)]
    return hits


def grade(root, project, situation):
    """Read the end state from git, the ticket file and the gh double. Nothing here trusts what the agent said."""
    state = json.loads((root / "gh-state.json").read_text())
    ticket = orchestrator.Ticket(project, work(situation))
    place = Path(ticket.state().get("worktree") or project)  # where the work happened
    commits = sh(["git", "log", "--oneline", "main..HEAD"], place, check=False).stdout.splitlines()
    tests = sh([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-q"], place, check=False)
    def cli(*args):
        done = sh([sys.executable, "greet.py", *args], place, check=False)
        return done.returncode, done.stdout.strip(), done.stderr.strip()
    logs = sorted(log for log in (project / ".factory").rglob("*.jsonl")
                  if log.name != "runs.jsonl" and not log.name.startswith("wait-"))
    used = {log.relative_to(project / ".factory").as_posix(): skills_used(log) for log in logs}
    everything = [name for names in used.values() for name in names]
    report = place / ".evidence/report.md"
    pr = state["prs"][0] if state["prs"] else None
    facts = {
        "final_stage": ticket.stage(),
        "own_worktree": place != project,
        "branch": sh(["git", "branch", "--show-current"], place, check=False).stdout.strip(),
        "expected_stage": SITUATIONS[situation],
        "commits_on_branch": len(commits),
        "tests_pass": tests.returncode == 0,
        "behaviour": cli("Ada") == (0, "Hello, Ada!", "") and cli()[0] == 2 and "Name required" in cli()[2]
                     and (situation != "spec" or cli("--shout", "Ada")[:2] == (0, "HELLO, ADA!"))
                     and (situation != "rework" or cli(" Ada ")[:2] == (0, "Hello, Ada!")),
        "outside": reached_outside(logs),
        "review_ran": "code-review" in everything,
        "tdd_loaded": "tdd" in everything,
        "verify_skill_loaded": "verify-greet" in everything,
        "verdict": (report.read_text().splitlines() or [""])[0] if report.is_file() else None,
        "pr_opened": pr is not None,
        "pr_body_words": len(pr["body"].split()) if pr else 0,
        "pr_cites_verification": bool(pr) and "PASS" in pr["body"] and "not verified: no verification" not in pr["body"].lower()
                                 and "not independently verified" not in pr["body"].lower(),
        "merge_attempts": len(state.get("merge_attempts", [])),
        "ci_runs": [run["ok"] for run in state.get("runs", {}).values()],
        "ci_reruns": len(state.get("reruns", [])),
        "sessions": len(logs),
        "cost_usd": round(sum(cost(log) for log in logs), 4),
        "skills_by_session": used,
    }
    passed = (facts["final_stage"] == facts["expected_stage"] and facts["merge_attempts"] == 0 and facts["review_ran"]
              and not facts["outside"] and facts["own_worktree"])
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
    parser.add_argument("--entry", choices=ENTRIES, default="deliver")
    parser.add_argument("--agent", choices=("claude", "codex", "opencode"), default="claude")
    parser.add_argument("--model", default="sonnet")
    parser.add_argument("--timeout", type=int, default=1500)
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args(argv)
    args.root.mkdir(parents=True)
    root = args.root.resolve()
    project, env = prepare(root, args.situation, agent=args.agent, model=args.model)
    if args.prepare_only:
        print(project)
        return 0
    seconds = execute(project, env, args.entry, args.agent, args.model, args.timeout, work(args.situation), args.situation)
    facts = grade(root, project, args.situation) | {"situation": args.situation, "entry": args.entry,
                                                    "agent": args.agent, "model": args.model, "seconds": seconds}
    (root / "result.json").write_text(json.dumps(facts, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({k: v for k, v in facts.items() if k != "skills_by_session"}, ensure_ascii=False))
    return 0 if facts["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
