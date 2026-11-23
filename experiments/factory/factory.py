#!/usr/bin/env python3
"""Lead tasks through a project's pipeline, one step command at a time.

Experimental. A step reads the task's stage, starts one fresh agent session with the
step's command, runs the step's check and moves the task to the next stage. The chain
lives in the project's docs/agents/pipeline.toml; this program only walks it.
"""
import argparse
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import time
import tomllib

STAGE = re.compile(r"^\*\*Stage:\*\* *(\S+) *$", re.M)
BLOCKED = "blocked"


class FactoryError(Exception):
    pass


def load_pipeline(project):
    path = project / "docs/agents/pipeline.toml"
    if not path.is_file():
        raise FactoryError(f"No pipeline at {path}")
    data = tomllib.loads(path.read_text())
    steps = data.get("step", [])
    names = [step.get("name") for step in steps]
    for step in steps:
        missing = [key for key in ("name", "when", "run", "check", "then") if not step.get(key)]
        if missing:
            raise FactoryError(f"Step {step.get('name', '?')} lacks: {', '.join(missing)}")
    if len(names) != len(set(names)) or len({step["when"] for step in steps}) != len(steps):
        raise FactoryError("Step names and their starting stages must be unique")
    return data.get("branch", "task/{name}"), steps


def stage(task):
    found = STAGE.search(task.read_text())
    return found[1] if found else None


def set_stage(task, value, note=None):
    text = task.read_text()
    line = f"**Stage:** {value}"
    text = STAGE.sub(line, text, count=1) if STAGE.search(text) else text.rstrip("\n") + f"\n\n{line}\n"
    if note:
        text = text.rstrip("\n") + f"\n\n> {note}\n"
    task.write_text(text)


def agent_argv(agent, model, prompt):
    custom = os.environ.get("FACTORY_AGENT")
    if custom:  # tests and other launchers: the prompt arrives as the last argument
        return [*shlex.split(custom), prompt]
    if agent == "claude":
        return ["claude", "-p", prompt, "--setting-sources", "project", "--model", model,
                "--no-session-persistence", "--output-format", "stream-json", "--verbose",
                "--dangerously-skip-permissions"]
    if agent == "codex":
        return ["codex", "exec", "--ignore-user-config", "--ephemeral", "--skip-git-repo-check",
                # A delivery pushes to a remote and calls the host CLI, both outside the checkout.
                "--sandbox", "danger-full-access", "--disable", "apps", "--disable", "plugins",
                "--enable", "skip_host_skill_discovery", "-c", 'web_search="disabled"',
                "-m", model, "--json", prompt]
    raise FactoryError(f"Unknown agent: {agent}")


def on_branch(project, branch):
    """Each task works on its own branch; create it from the current head the first time."""
    def git(*args):
        return subprocess.run(["git", "-C", str(project), *args], capture_output=True, text=True)
    if git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip() == branch:
        return
    exists = git("rev-parse", "--verify", "--quiet", "refs/heads/" + branch).returncode == 0
    switched = git("switch", branch) if exists else git("switch", "-c", branch)
    if switched.returncode:
        raise FactoryError(f"Cannot switch to {branch}: {switched.stderr.strip()}")


def run_step(project, task, steps, agent, model, timeout, branch="task/{name}"):
    """Run the step the task's stage calls for. Return the new stage, or None when no step applies."""
    current = stage(task)
    step = next((item for item in steps if item["when"] == current), None)
    if step is None:
        return None
    name = task.stem
    on_branch(project, branch.format(name=name))
    env = os.environ | {"FACTORY_TASK": str(task.relative_to(project)), "FACTORY_TASK_NAME": name,
                        "FACTORY_STEP": step["name"]}
    chosen = step.get("agent", agent)
    prompt = step["run"].format(task=task.relative_to(project), name=name,
                                invoke="$" if chosen == "codex" else "/")
    logs = project / ".factory/logs" / name
    logs.mkdir(parents=True, exist_ok=True)
    attempts = int(step.get("attempts", 1))
    reason = "the step's check did not pass"
    for attempt in range(1, attempts + 1):
        log = logs / f"{step['name']}-{attempt}.jsonl"
        started = time.monotonic()
        try:
            with log.open("w") as out, log.with_suffix(".stderr").open("w") as err:
                code = subprocess.run(agent_argv(chosen, step.get("model", model), prompt),
                                      cwd=project, env=env, stdin=subprocess.DEVNULL, stdout=out, stderr=err,
                                      timeout=timeout).returncode
        except subprocess.TimeoutExpired:
            code = 124
        check = subprocess.run(step["check"], shell=True, cwd=project, env=env, capture_output=True, text=True)
        record = dict(task=name, step=step["name"], attempt=attempt, agent_exit=code, check_exit=check.returncode,
                      seconds=round(time.monotonic() - started, 1))
        with (logs / "steps.jsonl").open("a") as journal:
            journal.write(json.dumps(record) + "\n")
        if check.returncode == 0:
            set_stage(task, step["then"])
            return step["then"]
        reason = (check.stdout + check.stderr).strip().splitlines()[-1:] or [reason]
        reason = reason[0] if isinstance(reason, list) else reason
        if check.returncode == 3:  # the check says a retry cannot help
            break
    set_stage(task, BLOCKED, f"Blocked at {step['name']}: {reason}")
    return BLOCKED


def tasks_in(project, pattern):
    return sorted(path for path in project.glob(pattern) if path.is_file() and stage(path))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=("status", "step", "run"))
    parser.add_argument("task", nargs="?", help="task file, relative to the project (step only)")
    parser.add_argument("--project", type=Path, default=Path.cwd())
    parser.add_argument("--tasks", default=".scratch/*/issues/*.md", help="glob of local task files")
    parser.add_argument("--agent", default="claude", choices=("claude", "codex"))
    parser.add_argument("--model", default="sonnet")
    parser.add_argument("--timeout", type=int, default=1800, help="seconds for one agent session")
    args = parser.parse_args(argv)
    try:
        project = args.project.resolve()
        branch, steps = load_pipeline(project)
        if args.command == "status":
            for task in tasks_in(project, args.tasks):
                print(f"{stage(task)}\t{task.relative_to(project)}")
            return 0
        if args.command == "step":
            if not args.task:
                raise FactoryError("step needs a task file")
            result = run_step(project, project / args.task, steps, args.agent, args.model, args.timeout, branch)
            print(result or "no step applies")
            return 0
        while True:  # run: every task advances until it reaches a stage no step starts from
            moved = False
            for task in tasks_in(project, args.tasks):
                result = run_step(project, task, steps, args.agent, args.model, args.timeout, branch)
                if result:
                    print(f"{task.relative_to(project)}: {result}", flush=True)
                    moved = True
            if not moved:
                return 0
    except FactoryError as error:
        print(f"factory: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
