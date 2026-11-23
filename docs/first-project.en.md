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

Inspect the proposed settings, skills and the project file diff. Skill changes take one line each; `--full` prints their complete diff. Full setup includes all skills released at that revision. The task activates each practice: a question can end with an answer, while a large delivery can use `to-spec`, `to-tickets` and `implement-spec`. Project settings determine whether a behaviour check or an owner decision is required.

In a project with its own instructions, setup asks you to state the delivery route: `local`, `main`, `pr`, or the project's rule in words. It does not infer it. Inspect the listed documents and CI files and reconcile material differences before applying. For example, a project requiring another Verify after CI selects a different workflow. Local checks can cover a project with no external CI.

```bash
python3 tools/setup.py --project "$project" --ref "$kit_ref" --apply
python3 tools/skills.py check --project "$project"
python3 tools/setup.py --project "$project" --ref "$kit_ref"
```

The same SHA and decisions produce an empty diff on the second preview. Then invoke `$setup-matt-pocock-skills` once in the project: it configures the tracker, labels and domain docs that `to-spec`, `to-tickets` and `triage` expect. If the project needs behaviour checks, invoke `$create-verification-skill`: it generates the project's `verify-<app>` skill. Run `python3 tools/setup.py --help` for settings. To take just one skill, use [selection with dependencies](distribution.md).

## Start work in a fresh session

The table uses Codex commands. In Claude Code, start the message with a slash command such as `/to-tickets <spec>`. You can accept the spec and request the breakdown in that same message.

| What you want | What you say | Where the agent stops |
| --- | --- | --- |
| Understand one issue | “Why does #42 lose the discount?” | Reproduction and explanation. |
| Prepare a spec | `$grill-me` to discuss the idea, then `$to-spec` to save the decision | A link to the saved spec. |
| Accept and split the spec | “I accept the spec. `$to-tickets <spec>`” | Proposed tickets with their dependencies. Approve the breakdown to save them. |
| Execute the agreed graph | `$implement-spec <spec>` | Implements the tickets on one branch and reviews it once. |
| Implement one assigned issue | `$implement <issue>` | Implements, commits and reviews the work. |

After a plain “I accept the spec”, the agent names the next command, `$to-tickets`, and stops. After ticket publication, start implementation separately. The agent does not start human-invoked skills itself: the skill flags and a line in the project's root instructions say so.

## Existing project decisions

Pass `--decisions /path/to/decisions.json` to preview and apply. For example, a project using PRs with its own testing guide can select:

```json
{"language": "en", "delivery": "pr", "testing_file": "docs/TESTING.md"}
```

The testing file must already exist at that project-relative path. Inspect the final diff. By default every delivery waits for you and the agent never merges; only the `owner_gate` setting, set to `conditions` or `none`, lets it merge.

The supported decisions are listed in the [pinned defaults](../templates/project/defaults.json). Set `instruction_owner` when both root files carry independent rules. When preview reports differences, agree their disposition with the project owner. Put that decision in `resolution` and copy the displayed `conflict_id` into the same JSON object. A changed set of differences requires agreement on the new preview and its ID. Setup preserves unmanaged files and reports edits to managed material before writing. For both clients, pass `--client both` on the first preview and apply.

## What the agent reads

- Root instructions identify start authority, checkout, delivery mode and owner decisions. The short [workflow](../templates/project/WORKFLOW.md) holds the rules that connect skills, and the [parts map](parts.en.md) shows what each skill is for.
- The spec describes the expected outcome. The project's `testing.md` or existing equivalent holds the testing strategy: the seam and kind of test for each kind of change. `to-spec` and `tdd` read it. The agent takes run commands from the project itself.
- One PR or local delivery gets one `code-review` call. Parallel Standards and Spec reviews feed one correction pass, affected tests and, if required, one pass of the project's `verify-<app>` skill. A `FAIL` or `BLOCKED` verdict keeps delivery open.
- `ship` opens the PR, gets the required checks green and confirms the merge really happened. It merges only when the project lets it. Verification evidence is stored the way the `evidence` setting says: as PR attachments (the default on GitHub), in a repository folder, in external storage, or as text only.
- The review reads the coding standards, not the implementer. Setup does not create `CODING_STANDARDS.md`: when a review misses a mistake, invoke `$retro`, and it proposes either an automated check or a rule for that file.

Open a fresh project session and ask: “The command should explain why an input file is missing. Which files tell you which tests to write, how to check that behavior and when you need me?” The first trial is complete when the agent can point to the answers and repeating setup gives an empty diff.
