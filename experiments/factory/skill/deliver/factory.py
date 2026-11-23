#!/usr/bin/env python3
"""Lead tasks through a project's pipeline, one step command at a time.

Experimental. A step reads the task's stage, starts one fresh agent session with the
step's command, runs the step's check and moves the task to the next stage. The chain
lives in the project's docs/agents/pipeline.toml; this program only walks it.

State is the task's stage (a line in a task file, else state.json) and one folder per
task under .factory/: state.json, the step journal and each session's log. A run that
dies or is stopped loses nothing: the next run starts from the recorded stage.
"""
import argparse
import json
import os
from pathlib import Path
import re
import shlex
import signal
import subprocess
import sys
import time
import tomllib

STAGE = re.compile(r"^\*\*Stage:\*\* *(\S+) *$", re.M)
SESSION = re.compile(r'"(?:session_id|thread_id)"\s*:\s*"([^"]+)"')
BLOCKED = "blocked"
# How to start one headless session of a client, and the sign that invokes a skill in it.
# A pipeline adds or replaces clients in its [agents.<name>] tables.
CLIENTS = {
    "claude": {"command": "claude -p {prompt} --model {model} --output-format stream-json --verbose "
                          "--dangerously-skip-permissions", "skill": "/"},
    # A delivery pushes to a remote and calls the host CLI, both outside the checkout.
    "codex": {"command": "codex exec --sandbox danger-full-access -m {model} --json {prompt}", "skill": "$"},
}


class FactoryError(Exception):
    pass


class Stopped(BaseException):
    """The owner stopped the run."""


def load_pipeline(project):
    path = project / "docs/agents/pipeline.toml"
    if not path.is_file():
        raise FactoryError(f"No pipeline at {path}")
    data = tomllib.loads(path.read_text())
    steps = data.get("step", [])
    for step in steps:
        missing = [key for key in ("name", "when", "run", "check", "then") if not step.get(key)]
        if missing:
            raise FactoryError(f"Step {step.get('name', '?')} lacks: {', '.join(missing)}")
    if len({step["name"] for step in steps}) != len(steps) or len({step["when"] for step in steps}) != len(steps):
        raise FactoryError("Step names and their starting stages must be unique")
    return data, steps


def git(folder, *args):
    return subprocess.run(["git", "-C", str(folder), *args], capture_output=True, text=True)


class Task:
    """A ticket or spec file of the local tracker, or a reference the host tracker understands."""

    def __init__(self, project, ref, spec=False):
        path = project / ref
        self.project = project
        self.file = path if path.is_file() else None
        self.ref = str(path.relative_to(project)) if self.file else ref
        if self.file:  # a ticket is named by its file; a spec by its feature folder
            self.name = path.parent.name if path.name == "spec.md" else path.stem
        else:
            self.name = re.sub(r"[^A-Za-z0-9._-]+", "-", ref).strip("-")
        if not self.name:
            raise FactoryError(f"Cannot name the task: {ref}")
        self.folder = project / ".factory" / self.name
        self.spec = spec or bool(self.file and path.name == "spec.md") or bool(self.state().get("spec"))

    def state(self):
        path = self.folder / "state.json"
        return json.loads(path.read_text()) if path.is_file() else {}

    def update(self, **changes):
        state = self.state() | changes
        self.folder.mkdir(parents=True, exist_ok=True)
        ignore = self.project / ".factory/.gitignore"
        if not ignore.exists():
            ignore.write_text("*\n")
        (self.folder / "state.json").write_text(json.dumps(state, indent=2) + "\n")
        return state

    def stage(self):
        if self.file:
            found = STAGE.search(self.file.read_text())
            return found[1] if found else None
        return self.state().get("stage")

    def set_stage(self, value, note=None):
        if not self.file:
            self.update(stage=value, note=note)
            return
        text = self.file.read_text()
        line = f"**Stage:** {value}"
        text = STAGE.sub(line, text, count=1) if STAGE.search(text) else text.rstrip("\n") + f"\n\n{line}\n"
        if note:
            text = text.rstrip("\n") + f"\n\n> {note}\n"
        self.file.write_text(text)

    def journal(self, **record):
        self.folder.mkdir(parents=True, exist_ok=True)
        with (self.folder / "steps.jsonl").open("a") as out:
            out.write(json.dumps(dict(task=self.name) | record) + "\n")


def agent_argv(pipeline, agent, model, prompt):
    custom = os.environ.get("FACTORY_AGENT")
    if custom:  # tests and other launchers: the prompt arrives as the last argument
        return [*shlex.split(custom), prompt]
    client = CLIENTS.get(agent, {}) | pipeline.get("agents", {}).get(agent, {})
    if not client.get("command"):
        raise FactoryError(f"Unknown agent: {agent}. Add [agents.{agent}] with a command to the pipeline")
    if prompt.startswith("/"):
        prompt = client.get("skill", "/") + prompt[1:]  # the same skill command in this client's spelling
    return [prompt if part == "{prompt}" else part.replace("{model}", model) for part in shlex.split(client["command"])]


def place(pipeline, task):
    """The folder the task's sessions work in: the checkout the owner chose by leaving the base
    branch, else a worktree of the task's own, created once."""
    state = task.state()
    if state.get("worktree") and Path(state["worktree"]).is_dir():
        return Path(state["worktree"])
    project = task.project
    current = git(project, "branch", "--show-current").stdout.strip()
    if current != pipeline.get("base", "main"):
        task.update(worktree=str(project), branch=current, spec=task.spec)
        return project
    root = Path(os.path.expanduser(pipeline.get("worktrees", "../{project}-worktrees").format(project=project.name)))
    work = (project / root).resolve() / task.name
    branch = pipeline.get("branch", "task/{name}").format(name=task.name)
    exists = git(project, "rev-parse", "--verify", "--quiet", "refs/heads/" + branch).returncode == 0
    added = git(project, "worktree", "add", str(work), branch) if exists else git(project, "worktree", "add", "-b", branch, str(work))
    if added.returncode:
        raise FactoryError(f"Cannot create the worktree {work}: {added.stderr.strip()}")
    task.update(worktree=str(work), branch=branch, spec=task.spec)
    if pipeline.get("setup"):
        done = subprocess.run(pipeline["setup"], shell=True, cwd=work, capture_output=True, text=True)
        if done.returncode:
            raise FactoryError(f"The worktree setup failed: {(done.stdout + done.stderr).strip()[-300:]}")
    return work


def session(argv, work, env, log, timeout):
    """Run one agent session in its own process group, so a stop ends everything it started."""
    with log.open("w") as out, log.with_suffix(".stderr").open("w") as err:
        child = subprocess.Popen(argv, cwd=work, env=env, stdin=subprocess.DEVNULL, stdout=out, stderr=err,
                                 start_new_session=True)
        try:
            return child.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            code = 124
        except Stopped:
            code = None
        try:
            os.killpg(child.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        child.wait()
        if code is None:
            raise Stopped()
        return code


def run_step(pipeline, steps, task, timeout):
    """Run the step the task's stage calls for. Return the new stage, or None when no step applies."""
    step = next((item for item in steps if item["when"] == task.stage()), None)
    if step is None:
        return None
    work = place(pipeline, task)
    branch = task.state().get("branch")
    if branch and git(work, "branch", "--show-current").stdout.strip() != branch:
        switched = git(work, "switch", branch)
        if switched.returncode:
            raise FactoryError(f"Cannot switch to {branch}: {switched.stderr.strip()}")
    # A session reads the task where it works; a task file git does not carry stays in the project.
    ref = task.ref if not task.file or (work / task.ref).is_file() else str(task.file)
    env = os.environ | {"FACTORY_TASK": ref, "FACTORY_TASK_NAME": task.name, "FACTORY_STEP": step["name"]}
    agent = step.get("agent", pipeline.get("agent", "claude"))
    model = step.get("model", pipeline.get("model", "sonnet"))
    instruction = step.get("run_spec", step["run"]) if task.spec else step["run"]
    argv = agent_argv(pipeline, agent, model, instruction.format(task=ref, name=task.name))
    reason = "the step's check did not pass"
    for attempt in range(1, int(step.get("attempts", 1)) + 1):
        log = task.folder / f"{step['name']}-{attempt}.jsonl"
        task.update(running=dict(step=step["name"], attempt=attempt, started=int(time.time())))
        started = time.monotonic()
        try:
            code = session(argv, work, env, log, int(step.get("timeout", timeout)))
        except Stopped:
            task.journal(step=step["name"], attempt=attempt, stopped=True)
            raise
        finally:
            task.update(running=None)
        check = subprocess.run(step["check"], shell=True, cwd=work, env=env, capture_output=True, text=True)
        found = SESSION.search(log.read_text(errors="replace"))
        task.journal(step=step["name"], attempt=attempt, agent=agent, model=model, agent_exit=code,
                     check_exit=check.returncode, seconds=round(time.monotonic() - started, 1),
                     session=found[1] if found else None)
        if check.returncode == 0:
            # The skill may have moved the work to a branch of its own; later steps follow it.
            task.update(branch=git(work, "branch", "--show-current").stdout.strip() or branch, blocked_at=None)
            task.set_stage(step["then"])
            return step["then"]
        reason = ((check.stdout + check.stderr).strip().splitlines() or [reason])[-1]
        if check.returncode == 3:  # the check says a retry cannot help
            break
    task.update(blocked_at=step["when"])
    task.set_stage(BLOCKED, f"Blocked at {step['name']}: {reason}")
    return BLOCKED


def alive(pid):
    try:
        os.kill(pid, 0)
    except (OSError, TypeError):
        return False
    return True


def lead(pipeline, steps, task, timeout):
    """Advance one task until it reaches a stage no step starts from. Return whether it moved."""
    pid = task.state().get("pid")
    if pid != os.getpid() and alive(pid):
        raise FactoryError(f"{task.name} is already running (pid {pid})")
    task.update(pid=os.getpid())
    moved = False
    try:
        while True:
            result = run_step(pipeline, steps, task, timeout)
            if result is None:
                return moved
            print(f"{task.ref}: {result}", flush=True)
            moved = True
    finally:
        task.update(pid=None)


def tasks_in(project, pattern):
    found = set(project.glob(pattern)) | set(project.glob(".scratch/*/issues/*.md"))
    files = {path for path in found if path.is_file() and STAGE.search(path.read_text())}
    tasks = {task.name: task for task in (Task(project, str(path.relative_to(project))) for path in sorted(files))}
    for state in sorted(project.glob(".factory/*/state.json")):  # tasks of a host tracker have no file
        if state.parent.name not in tasks and "stage" in json.loads(state.read_text()):
            tasks[state.parent.name] = Task(project, state.parent.name)
    return list(tasks.values())


def status_line(task):
    state = task.state()
    running = state.get("running") if alive(state.get("pid")) else None
    journal = task.folder / "steps.jsonl"
    last = json.loads(journal.read_text().splitlines()[-1]) if journal.is_file() and journal.read_text().strip() else {}
    parts = [task.name, task.stage() or "-"]
    if running:
        minutes = (int(time.time()) - running["started"]) // 60
        parts.append(f"running {running['step']} attempt {running['attempt']} for {minutes} min")
    else:
        parts.append("not running")
    if last:
        result = "stopped" if last.get("stopped") else ("passed" if last.get("check_exit") == 0 else "failed")
        parts.append(f"last: {last['step']} attempt {last['attempt']} {result}")
        if last.get("session"):
            parts.append(f"session {last['session']}")
    if state.get("worktree"):
        parts.append(f"in {state['worktree']} on {state.get('branch')}")
    return "\t".join(parts)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=("run", "status", "stop", "wait", "place"))
    parser.add_argument("task", nargs="?", help="ticket or spec file relative to the project, or a tracker reference; "
                                                "run and status take every staged task without it")
    parser.add_argument("--project", type=Path, default=Path.cwd())
    parser.add_argument("--tasks", default=".scratch/*/*.md", help="glob of local task files that may carry a stage")
    parser.add_argument("--stage", help="run: start the named task from this stage, such as rework")
    parser.add_argument("--spec", action="store_true", help="run: the tracker reference is a spec with tickets")
    parser.add_argument("--detach", action="store_true", help="run: return at once and leave the run in the background")
    parser.add_argument("--timeout", type=int, default=1800, help="seconds for one agent session")
    args = parser.parse_args(argv)
    try:
        project = args.project.resolve()
        pipeline, steps = load_pipeline(project)
        task = Task(project, args.task, args.spec) if args.task else None
        if args.command != "run" and args.command != "status" and task is None:
            raise FactoryError(f"{args.command} needs a task")
        if args.command == "status":
            for item in [task] if task else tasks_in(project, args.tasks):
                print(status_line(item))
            return 0
        if args.command == "place":  # for a session that leads the chain itself
            print(place(pipeline, task))
            return 0
        if args.command == "stop":
            pid = task.state().get("pid")
            if not alive(pid):
                print(f"{task.name} is not running")
                return 0
            os.kill(pid, signal.SIGTERM)
            print(f"Stopped {task.name}; run it again to continue from {task.stage()}")
            return 0
        if args.command == "wait":
            while alive(task.state().get("pid")):
                time.sleep(5)
            print(status_line(task))
            return 0
        if args.detach:
            if alive(task.state().get("pid") if task else None):
                raise FactoryError(f"{task.name} is already running")
            again = [sys.executable, str(Path(__file__).resolve()), *[arg for arg in (argv or sys.argv[1:]) if arg != "--detach"]]
            folder = task.folder if task else project / ".factory"
            folder.mkdir(parents=True, exist_ok=True)
            with (folder / "run.log").open("a") as out:
                child = subprocess.Popen(again, cwd=Path.cwd(), stdin=subprocess.DEVNULL, stdout=out, stderr=out,
                                         start_new_session=True)
            if task:
                task.update(pid=child.pid)
            print(f"Started in the background (pid {child.pid}); follow it with status")
            return 0

        def stop(*_):
            raise Stopped()
        signal.signal(signal.SIGTERM, stop)
        if task:
            if alive(task.state().get("pid")) and task.state()["pid"] != os.getpid():
                raise FactoryError(f"{task.name} is already running (pid {task.state()['pid']})")
            current = task.stage()
            if args.stage:
                task.set_stage(args.stage)
            elif current == BLOCKED and task.state().get("blocked_at"):
                task.set_stage(task.state()["blocked_at"])  # the owner dealt with the block; take the step again
            elif current is None and steps:
                task.set_stage(steps[0]["when"])
            lead(pipeline, steps, task, args.timeout)
            return 0
        while any([lead(pipeline, steps, item, args.timeout) for item in tasks_in(project, args.tasks)]):
            pass
        return 0
    except Stopped:
        print("factory: stopped", file=sys.stderr)
        return 130
    except FactoryError as error:
        print(f"factory: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
