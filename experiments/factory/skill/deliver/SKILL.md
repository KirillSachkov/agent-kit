---
name: deliver
description: "Lead an agreed ticket or spec through the project's pipeline until it waits for the owner."
disable-model-invocation: true
---

Lead the work the user named through the pipeline in `docs/agents/pipeline.toml`, from its current stage to a stage no step starts from. With nothing named, take every task whose stage is the first step's `when`.

The pipeline should have been provided to you. If the file is missing, tell the user to run `/setup-agent-kit`.

A step starts from the stage in its `when`. Its `run` is the instruction for one session; `run_spec` replaces it when the work is a spec with tickets. Its `check` is a shell command that decides whether the step is done. `then` is the next stage.

Read `executor` in the pipeline and follow that section only.

## steps

Run `python3 <this skill's folder>/factory.py run <task>` in the background from the project root and wait for it to exit. The program starts one fresh session per step, runs each check and moves the stage. Start nothing else and do none of the steps yourself.

## conductor

Work on the branch the pipeline's `branch` names; create it from the current head the first time. Then, for each step from the task's current stage:

1. Start a subagent with a fresh context window and give it the step's instruction, word for word. When the instruction names a skill, the owner has invoked that skill: the subagent loads it.
2. When the subagent returns, run the step's `check` yourself.
3. Exit 0: set the task's `**Stage:**` line to the step's `then` and go on.
4. Any other exit: start the step again, up to its `attempts`. On exit 3, or when the attempts are spent, set the stage to `blocked`, add a line to the task saying which step and why, and stop.

You lead and check; the subagents do the work. A step is done when its check passes, never when a subagent says so.

## Report

Say the stage the work ended in. For a stage that waits for the owner, give the PR link and what the owner decides. For `blocked`, give the step and the reason.
