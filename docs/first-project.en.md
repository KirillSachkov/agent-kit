# Start a project with Agent Kit

[Русский](first-project.ru.md)

Use an empty local Git repository for the first trial. Setup succeeds when a fresh session can explain the first task and the point where the owner decides. Have Git, Python 3.11+ and a Kit checkout available.

## Set up the project

From the Kit checkout, choose an existing project directory and an immutable revision:

```bash
project=/absolute/path/to/project
kit_ref=$(git rev-parse HEAD)
python3 tools/setup.py --project "$project" --ref "$kit_ref"
```

Inspect the proposed settings, skills and diff. Full setup includes all skills released at that revision. The task activates each practice: a question can end with an answer, while a large delivery can use `to-spec`, `to-tickets` and `implement-spec`. Project policy determines when to apply TDD, local Verify or an owner decision.

For an existing project, inspect the sources of instructions, tracker, tests, CI and delivery rules. Reconcile material differences before applying. For example, a project requiring another Verify after CI selects a different workflow. Local checks can cover a project with no external CI.

```bash
python3 tools/setup.py --project "$project" --ref "$kit_ref" --apply
python3 tools/skills.py check --project "$project"
python3 tools/setup.py --project "$project" --ref "$kit_ref"
```

The same SHA and decisions produce an empty diff on the second preview. Run `python3 tools/setup.py --help` for settings. To take just one skill, use [selection with dependencies](distribution.md).

## Start work in a fresh session

| What you want | What you say | Where the agent stops |
| --- | --- | --- |
| Understand one issue | “Why does #42 lose the discount?” | Reproduction and explanation. |
| Prepare a spec | `$grill-me` to discuss the idea, then `$to-spec` to save the decision | A link to the saved spec. |
| Accept and split the spec | “I accept the spec. `$to-tickets <spec>`” | Proposed tickets with their dependencies. Approve the breakdown to save them. |
| Execute the agreed graph | `$implement-spec <spec>` | The project's delivery endpoint. Add “stop before review” for just the tested change. |
| Implement one assigned issue | “Implement #42” or `$implement <issue>` | The assigned endpoint. A standalone issue can go straight to implementation. |

After a plain “I accept the spec”, the next command is `$to-tickets`. After ticket publication, start implementation separately. To require a named start for implementation too, set `start` in the setup decisions to “Only begin when the owner explicitly invokes implement or implement-spec for the assigned work.”

## Existing project decisions

Pass `--decisions /path/to/decisions.json` to preview and apply. For example, a project using PRs with its own testing guide can select:

```json
{"language": "en", "delivery": "pr", "testing_file": "docs/TESTING.md"}
```

The testing file must already exist at that project-relative path. Inspect the final diff and any access, start or acceptance decisions that setup reports. Project authority controls merge and publication.

The supported decisions are listed in the [pinned defaults](../templates/project/defaults.json). Set `instruction_owner` when both root files carry independent rules. When preview reports differences, agree their disposition with the project owner. Put that decision in `resolution` and copy the displayed `conflict_id` into the same JSON object. A changed set of differences requires agreement on the new preview and its ID. Setup preserves unmanaged files and reports edits to managed material before writing. For both clients, pass `--client both` on the first preview and apply.

## What the agent reads

- Root instructions identify start authority, checkout, delivery mode and owner decisions. The [two workflow maps](../templates/project/WORKFLOW.md) show the branches.
- The spec describes the expected outcome. The project's `testing.md` or existing equivalent names boundaries, commands, data and environment. A discovered command and a successful run have distinct statuses. A separate skill for choosing and configuring test types, static analysis and CI is **in development**.
- One PR or local delivery gets one `code-review` call. Parallel Standards and Spec reviews feed one correction pass, affected tests and, if required, local Verify. A product failure or unavailable environment leaves a required criterion open.
- When local Verify passed on A and CI needs a fix on B, retain the observation on A, later edits, affected tests and CI on B. An enabled classifier runs once to identify the owner decision. The agent confirms the actual revision after authorized delivery.

Open a fresh project session and ask: “The command should explain why an input file is missing. Which files tell you when to start, how to check that behavior and when you need me?” The first trial is complete when the agent can point to the answers and repeating setup gives an empty diff.
