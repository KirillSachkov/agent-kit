# Start a project with Agent Kit

[Русский](first-project.ru.md)

This walkthrough uses a new or existing Git repository. Git and Python 3.11 or newer are required.
The [starter instructions](../templates/project/AGENTS.md) are designed to live in that repository.
If it already has `AGENTS.md`, compare the two and keep the project's established decisions.

## Install the workflow

Run the commands from the Agent Kit checkout. Set `project` to the absolute path of the target
repository and `kit_ref` to the full SHA you reviewed. In a new repository with no instructions,
copy the starter from that revision. Fill in its project decisions before assigning work.

```bash
project=/absolute/path/to/project
kit_ref=FULL_COMMIT_SHA
git show "$kit_ref:templates/project/AGENTS.md"
# After checking the output, for a project without AGENTS.md:
(set -C; git show "$kit_ref:templates/project/AGENTS.md" > "$project/AGENTS.md")
```

Choose the skill set, preview the proposed changes, then install and check the complete folders.
The same installed files are available to Codex and Claude Code with `--client both`.

```bash
python3 tools/skills.py select --project "$project" --ref "$kit_ref" --client both \
  --skill implement --skill implement-spec --skill code-review --skill tdd \
  --skill ship --skill pr --skill recap --skill diagnosing-bugs \
  --skill to-spec --skill to-tickets --apply
python3 tools/skills.py preview --project "$project"
python3 tools/skills.py install --project "$project"
python3 tools/skills.py check --project "$project"
```

See [pinned distribution](distribution.md) for updates and existing skill folders.

## Run the first task

Pick a small change with a result you can see through the project's regular entry point. A fictional
example is a local status command that should report a missing input file with exit status 2 and a
specific message. Write the expected behavior before implementation.

| Step | What to keep |
| --- | --- |
| Assign and start | Task, acceptance scenario, exact base, assigned checkout or worktree |
| Change and review | Test result, reviewed revision, independent Standards and Spec findings, corrections |
| Verify the result | Corrected revision, expected and observed behavior, evidence and any limits |
| Deliver | Delivered revision, check results, decision requested from the owner if needed, actual merged revision when applicable |
| Retire | Evidence location, integrated or recoverable task revision, exact resources removed or retained |

For the verification row, run the regular command in a fresh context at the corrected revision.
Capture the exit status and output. For a bug fix, retain the failure on the old revision and the
pass on the corrected one. If a check requires an unavailable account, browser, or service, keep
that scenario open in the report.

One test in the library provisions a disposable Git repository, installs the pinned workflow, runs
a local task from a worktree, and verifies its result after integration and retirement:

```bash
python3 -m unittest discover -s tests -p test_project_starter.py
```

That test uses local Git and command output. To exercise real CI, agent review, or owner approval,
run the first task under the target project's configured workflow and record those outcomes.
