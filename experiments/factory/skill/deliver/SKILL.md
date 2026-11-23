---
name: deliver
description: "Lead an agreed ticket or spec through the project's pipeline until it waits for the owner."
disable-model-invocation: true
---

Lead the work the user named through the pipeline in `docs/agents/pipeline.toml`, from its current stage to a stage no step starts from.

The pipeline should have been provided to you. If the file is missing, tell the user to run `/setup-agent-kit`.

A step starts from the stage in its `when`. Its `run` is the instruction for one session; `run_spec` replaces it when the work is a spec with tickets. Its `check` is a shell command that decides whether the step is done. `then` is the next stage.

`factory.py` is the program in this skill's folder. Run it from the project root. Read `executor` in the pipeline and follow that section only.

## steps

The program leads the chain: it gives the task a worktree, starts one fresh session per step, runs each check and moves the stage. You start it, answer for it and pass the owner's words on. Do none of the steps yourself.

- **Start or continue:** `python3 factory.py run <task> --detach`, then `python3 factory.py wait <task>` in the background. A task the tracker holds is named by its reference; add `--spec` when it is a spec with tickets. Tell the user the run has started and end your turn. A blocked task continues from the step that blocked it.
- **Status:** when asked, run `python3 factory.py status` and say each task's stage, the running step and the last result.
- **Stop:** `python3 factory.py stop <task>`.
- **Feedback on the result:** post the owner's words as a comment on the task's PR, then start the task with `--stage rework`.
- **A changed task:** stop the run, let the owner change the task in the tracker, then start it again.

## conductor

Run `python3 factory.py place <task>` and work in the folder it prints. Then, for each step from the task's current stage:

1. Start a subagent with a fresh context window and give it the step's instruction, word for word.
2. When the subagent returns, run the step's `check` yourself.
3. Exit 0: set the `**Stage:**` line of the task file in the project root to the step's `then` and go on.
4. Any other exit: start the step again, up to its `attempts`. On exit 3, or when the attempts are spent, set the stage to `blocked`, add a line to the task saying which step and why, and stop.

You lead and check; the subagents do the work. A step is done when its check passes, never when a subagent says so.

## Report

When a run ends, say the stage the work ended in. For a stage that waits for the owner, give the PR link and what the owner decides. For `blocked`, give the step, the reason and the session to reopen from the status line.
