# Start a project with Agent Kit

[Русский](first-project.ru.md)

Use an empty local Git repository for the first trial. Setup succeeds when a fresh session can explain the first task and the point where the owner decides. Have Git, Python 3.11+ and a Kit checkout available.

## Install the skills

From the Kit checkout, name an existing project directory and a selected commit:

```bash
project=/absolute/path/to/project
kit_ref=$(git rev-parse HEAD)
python3 tools/setup.py --project "$project" --ref "$kit_ref"
python3 tools/setup.py --project "$project" --ref "$kit_ref" --apply
python3 tools/skills.py check --project "$project"
```

The first command shows what will change: one line per skill; `--full` prints the complete diff. The second applies it. The command installs the skills only. It makes no project decisions, and the setup skill writes `AGENTS.md` in the next step. It leaves your instructions and files alone, and repeating it with the same SHA gives an empty diff. Add `--client both` for two clients. To take just one skill, use [selection with dependencies](distribution.md).

## Configure the project

Open a session in the project and invoke `$setup-project`. The skill explores the project and runs a short interview, leading each section with an answer you can accept in a word:

| Section | What is decided |
| --- | --- |
| Language | the language the agent writes in for people |
| Tracker | where issues live: GitHub, GitLab, local files or your own |
| Labels | the names of the issue readiness roles |
| Domain docs | where `GLOSSARY.md` and ADRs live |
| Delivery | local, to `main`, through a PR, or your own rule in words; required checks and CI; whether implementation happens in a worktree |
| Verification | when it is needed, who runs it, where evidence is kept |
| Owner gate | every delivery waits for you, by a conditions page, or none |
| Testing strategy | where each kind of change is tested, when the project has no such document yet |
| Root instructions | what stays in `AGENTS.md`, what moves to the settings and what goes as a repeat or a broken pointer |
| Existing rules | what stays where the project's rules differ from the skills |

The skill shows a draft before writing. The result lives in `docs/agents/`: settings, tracker, labels, domain docs, testing strategy. Invoke the skill again to change a decision: it shows the current ones and asks only about what changes and about settings new in this Kit version. When the project needs behaviour checks, invoke `$create-verification-skill` afterwards.

## Start work in a fresh session

The table uses Codex commands. In Claude Code, start the message with a slash command such as `/to-tickets <spec>`. You can accept the spec and request the breakdown in that same message.

| What you want | What you say | Where the agent stops |
| --- | --- | --- |
| Understand one issue | “Why does #42 lose the discount?” | Reproduction and explanation. |
| Prepare a spec | `$grill-me` to discuss the idea, then `$to-spec` to save the decision | A link to the saved spec. |
| Accept and split the spec | “I accept the spec. `$to-tickets <spec>`” | Proposed tickets with their dependencies. Approve the breakdown to save them. |
| Execute the agreed graph | `$implement-spec <spec>` | Implements the tickets on one branch and reviews it once. |
| Implement one assigned issue | `$implement <issue>` | Implements, commits and reviews the work. |

After a plain “I accept the spec”, the agent names the next command, `$to-tickets`, and stops. After ticket publication, start implementation separately. The agent does not start human-invoked skills itself: the skill flags say so.

## What the agent reads

- Root instructions point at the project settings and say where implementation may start. The [parts map](parts.en.md) shows what each skill is for.
- The spec describes the expected outcome. The project's `testing.md` or existing equivalent holds the testing strategy: the seam and kind of test for each kind of change. `to-spec` and `tdd` read it. The agent takes run commands from the project itself.
- `implement` reviews each ticket it builds and `implement-spec` reviews the whole spec once. Parallel Standards and Spec reviews feed one correction pass, affected tests and, if required, one pass of the project's `verify-<app>` skill. A `FAIL` or `BLOCKED` verdict keeps delivery open.
- `ship` opens the PR, gets the required checks green and confirms the merge really happened. It merges only when the project lets it. Verification evidence is stored the way the project settings say: as PR attachments (the default on GitHub), in a repository folder, in external storage, or as text only.
- The review reads the coding standards, not the implementer. Setup does not create `CODING_STANDARDS.md`: when a review misses a mistake, invoke `$retro`, and it proposes either an automated check or a rule for that file.

Open a fresh project session and ask: “The command should explain why an input file is missing. Which files tell you which tests to write, how to check that behavior and when you need me?” The first trial is complete when the agent can point to the answers and repeating setup gives an empty diff.
