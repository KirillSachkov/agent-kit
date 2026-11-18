# Start a project with Agent Kit

[Русский](first-project.ru.md)

This walkthrough uses a new or existing Git repository. Git and Python 3.11 or newer are required.
The [starter instructions](../templates/project/AGENTS.md) are designed to live in that repository.
If it already has `AGENTS.md`, compare the two and keep the project's established decisions.

To configure a project interactively, explicitly invoke `setup-harness`. From a fresh Agent Kit
checkout, you can explicitly ask the agent to follow [the setup skill](../skills/engineering/setup-harness/SKILL.md).

## Install the workflow

Run the commands from the Agent Kit checkout. Set `project` to the absolute path of the target
repository and `kit_ref` to the full SHA you reviewed. In a new repository with no instructions,
copy the starter from that revision. Fill in its project decisions before assigning work.

```bash
project=/absolute/path/to/project
kit_ref=FULL_COMMIT_SHA
git show "$kit_ref:templates/project/AGENTS.md"
# After checking the output, for a project without AGENTS.md:
starter=$(git show "$kit_ref:templates/project/AGENTS.md") &&
  (set -C; printf '%s\n' "$starter" > "$project/AGENTS.md")
```

Choose the skill set, preview the proposed changes, then install and check the complete folders.
The same installed files are available to Codex and Claude Code with `--client both`.

```bash
python3 tools/skills.py select --project "$project" --ref "$kit_ref" --client both \
  --skill implement --skill implement-spec --skill code-review --skill tdd \
  --skill ship --skill pr --skill recap --skill diagnosing-bugs \
  --skill to-spec --skill to-tickets --skill setup-harness --apply &&
  python3 tools/skills.py preview --project "$project"
```

After a successful preview, review the changes before proceeding.

```bash
python3 tools/skills.py install --project "$project" &&
  python3 tools/skills.py check --project "$project"
```

See [pinned distribution](distribution.md) for updates and existing skill folders.

The starter requires the owner to choose `implement` or `implement-spec` explicitly.
If the owner opts in to implicit skill selection after an ordinary implementation assignment,
set the Start rule in `AGENTS.md` accordingly and select both skills with
`--implementation-invocation implicit`. Use `--implementation-invocation manual`
to restore explicit selection and update the Start rule to match.

## Set up delivery

- For GitHub PRs, copy the [PR template](../templates/project/.github/pull_request_template.md)
  to `.github/pull_request_template.md` in the target and point `AGENTS.md` to it. Compare with
  any existing PR template before changing it.
- Classification starts disabled. To enable it, add `--skill owner-attention` to the selection above. Copy the
  [conditions](../templates/project/docs/agents/owner-attention.md) into the target and set the
  **Owner attention** decision in `AGENTS.md` to the conditions path and `owner-attention`.
  Agree on the conditions and authority before using them. `ship` runs a fresh, read-only
  classifier once on the finished delivery after review, required verification, and checks.
- Start each verification record with the [manifest template](../templates/project/evidence-manifest.json)
  in the evidence location declared by the target. Record the verified commit or tree SHA. Give each
  scenario its expected and observed outcome and mark it `pass`, `fail` or `not_exercised`.
  For each artifact fill in `kind`, `file` (relative to the manifest), `source` and `caption`.
  Add `url` only after publishing it under the target's rules.

Use a screenshot for a visible state, a short recording for an interaction, and a table for data
or access. Open the files before attaching them and confirm what they show and which data they
use. Use synthetic data for files published publicly. Keep private evidence in the project's
chosen store and use links the intended readers can open. Show each scenario and any important
limit in the body of the PR. Keep technical details in its disclosure.

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

For the verification row, have a fresh verifier who did not implement the change run the regular
command at the corrected revision and capture its exit status and output. Follow the installed
`implement/VERIFICATION.md`. For a bug fix, retain the failure on the old revision and the
pass on the corrected one. If a check requires an unavailable account, browser, or service, keep
that scenario open in the report.

One test in the library provisions a disposable Git repository, installs the pinned workflow, runs
a local task from a worktree, and verifies its result after integration and retirement:

```bash
python3 -m unittest discover -s tests -p test_project_starter.py
```

That test uses local Git and command output. To exercise real CI, agent review, or owner approval,
run the first task under the target project's configured workflow and record those outcomes.
