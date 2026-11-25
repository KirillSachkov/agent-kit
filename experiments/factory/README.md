# Factory experiment

An experiment in leading an agreed ticket or spec from "ready" to "PR waits for the owner" without a human in between. Nothing here is installed by the Kit yet.

## What it holds

- `skill/deliver/`: the `deliver` skill and `orchestrator.py`, the program that leads a ticket.
- `fixture/` and `spec-fixture/`: a tiny project with a ticket, a spec with three tickets, a verify skill, a CI script and the tasks in `docs/agents/pipeline.toml`.
- `bin/gh`: a local double of the GitHub CLI. It stores PRs, runs the fixture's CI on the pushed head and refuses every merge. `bin/orca` keeps trials away from the session application of the machine that runs them.
- `bench.py`, `matrix.py`: prepare a disposable copy of the fixture with the Kit installed, run one trial, and grade it from git, the ticket file and the double's state. Nothing is graded from what an agent said.
- `fake_agent.py`: a scripted agent, used by `tests/test_factory_experiment.py`.
- `results/`: one JSON line per trial.

## Words

The words are Matt Pocock's, from his `software-factory` skill. A **ticket** is the work to deliver: a ticket or a spec with tickets. A **task** is a kind of work defined once in the pipeline: implement, verify, ship, rework. A **run** is one execution of a task, a fresh headless session of the client. The **orchestrator** starts runs and records them. The **runner** is the machine the runs execute on, here the owner's own.

## The pipeline

`docs/agents/pipeline.toml` lists tasks. A task starts from the stage in `when`, gets one run with its instruction (`run`, or `run_spec` for a spec), and moves the ticket to `then` when its `check`, a shell command, exits 0. Exit 3 means a retry cannot help. The project's one command for all its checks is written once, as `checks` at the top, and a task's check names it as `{checks}`. The fixture's tasks are `implement` → `verify` → `ship`, with `rework` for the owner's feedback on the PR.

Two ways to work with the same skills and settings:

- **By hand:** the owner runs `/implement` or `/implement-spec`, then `/ship`, each in a session of their own.
- **Whole:** `/deliver <ticket>` starts the orchestrator. It gives the ticket a worktree, starts one run per task, runs each check and records the stage. The session that started it follows the run with `wait`, which returns at each finished attempt, and tells the owner what happened. The run itself is detached from that session; `status`, `stop` and a second `run` work from any session, and a trigger can start it with no session at all.

A third way was measured and removed: a session that led the chain itself and gave each task to a subagent (`conductor` in the results). A subagent receives `/implement` as plain text, so it wrote the code without the skill, and with it without the review; the leading session also lost track of the stage.

## Results, 2026-11-23

Six situations: every task passes, verification is blocked, CI fails on a fixable check, CI fails outside the repository, a spec with three tickets, and feedback on the open PR. A trial passes when the work ends in the expected stage with working behaviour, a review, a PR with green CI where one is due, no merge attempt and nothing touched outside the trial folder.

| Client | Model | orchestrator (`steps`) | leading session (`conductor`) |
| --- | --- | --- | --- |
| Claude Code | haiku | 18/18 | 11/18 |
| Claude Code | sonnet | 18/18 | 3/18 |
| Codex | gpt-6-luna | 17/18 | 1/18 |
| Codex | gpt-6.2-sol | 16/18 | 9/18 |
| OpenCode | deepseek/deepseek-flash | 6/8 | not run |

Cost per trial under the orchestrator: about $0.06 on haiku, $0.40 to $1.10 on sonnet, $0.02 on deepseek-flash. Codex reports no cost.

No trial tried to merge.

What failed under the orchestrator:

- Codex, once: the login shell found the system's Python 3.9 first and the program did not start. The program now says which Python it needs and the bench keeps its interpreter first.
- Codex, once: the verifier reported the environment missing when it was present. The chain stopped as it should; the verdict was wrong.
- Codex, twice on the spec (once in the matrix, once in a later control run): `implement-spec` put its ticket worktrees under the home folder, as the machine's own instructions say. Graded as reaching outside.
- OpenCode, twice: no review was seen in the session log.

What failed under the leading session: of 130 trials 43 passed; in 59 the work was delivered without a review, and in 28 the stage was wrong as well or instead. A partial rerun after that fix (`*-conductor-rerun-partial.jsonl`) changed little: 13/31 on Claude Code, 6/27 on Codex.

The bench reaches outside when the machine's global instructions tell agents to: two Codex conductor trials registered a worktree with the session application through a second copy of its command line. `bin/orca` now shadows it.

## Limits

- The fixture is a toy: one file, one command. It measures whether the chain holds, not whether a model can build a feature.
- Three trials per cell, fewer for OpenCode.
- The result files use the words of their day: `executor` `steps` is the orchestrator, `task` is a ticket. The trials before the review fixes used the same tasks but an earlier program; `2026-11-23-codex-steps-control.jsonl` and the OpenCode trials ran on the current one.
- `2026-11-23-codex-deliver-matrix-invalid-path.jsonl` is kept as a record of a bench fault, not a result.

## Run it

```
python3 -m unittest tests.test_factory_experiment          # scripted agent, no model
python3 experiments/factory/bench.py /tmp/trial --situation happy --agent codex --model <model>
python3 experiments/factory/matrix.py /tmp/matrix --agent codex --models <model> --repeats 1
```
