# Agent Kit parts map

[Русский](parts.ru.md)

The Kit has eight parts. Each part works alone: it has its own skills, input and result. A project enables the parts it wants in its settings. Matt Pocock's skills are the base; the tables below name every edit to them. The Kit adds its own skills only where Matt has none.

“You” under “Who starts it” means invoking by name: `/name` in Claude Code, `$name` in Codex. “Agent” means either the agent or you can invoke it.

## Parts

| Part | What it hands on | Required |
| --- | --- | --- |
| 1. Intake | A clear task or an answer | no |
| 2. Design | A spec and tickets with dependencies | no |
| 3. Execution | A committed change with tests | core |
| 4. Review | Two reports: Standards and Spec | part of execution |
| 5. Verification | An observation per criterion at a revision | no |
| 6. Evidence | Verification artifacts and the PR section | no |
| 7. Delivery and acceptance | The delivered revision and the owner's decision | no |
| 8. Improvement | Changes to instructions, checks and architecture | no |

## Skills by part

“Setup skill name” in the Source column marks one mechanical edit: the original sends the user to `/setup-matt-pocock-skills`, ours to `/setup-agent-kit`.

### 1. Intake

| Skill | Who starts it | Purpose | Reads | Writes | Calls | Source |
| --- | --- | --- | --- | --- | --- | --- |
| `ask` | you | Suggest which skill and what size of work fits | root instructions, the SKILL.md of the skill in question | nothing | none | Matt: the main flow is his; added reading the project's situation, working with `/deliver` and the references |
| `triage` | you | Sort incoming issues and PRs into readiness roles | tracker, labels, `.out-of-scope/` | labels, comments, `.out-of-scope/` | `grilling`, `domain-modeling` | Matt, setup skill name |
| `diagnosing-bugs` | agent | Find the cause on a reproducible case, then fix it with a regression test | `GLOSSARY.md`, ADRs | code and a test | none | Matt |

### 2. Design

| Skill | Who starts it | Purpose | Reads | Writes | Calls | Source |
| --- | --- | --- | --- | --- | --- | --- |
| `grill-me` | you | An interview to settle a decision, saving nothing | the conversation | nothing | `grilling` | Matt |
| `grill-with-docs` | you | The same, recording terms and decisions | `GLOSSARY.md`, ADRs | `GLOSSARY.md`, ADRs | `grilling`, `domain-modeling` | Matt |
| `grilling` | agent | The interview method: rounds of questions with a recommendation | conversation, environment | nothing | none | Matt |
| `domain-modeling` | agent | Sharpen terms and record decisions | `GLOSSARY.md`, ADRs, code | `GLOSSARY.md`, `docs/adr/` | none | Matt |
| `research` | agent | Gather facts from primary sources with a background agent | external sources | a Markdown file in the project | none | Matt |
| `prototype` | agent | Throwaway code that answers a design question | nearby code | a prototype on its own branch, a verdict | none | Matt |
| `wayfinder` | you | A decision map for a large, unclear effort | tracker | the map and decision tickets | `grilling`, `domain-modeling`, `research`, `prototype` | Matt, setup skill name |
| `to-spec` | you | Write what was agreed into a spec | conversation, tracker, testing strategy | a spec in the tracker | none | Matt, setup skill name |
| `to-tickets` | you | Split a spec into vertical tickets with dependencies | spec, tracker | tickets in the tracker | none | Matt, one edit |

The edit in `to-tickets`: after publishing it shows the ready tickets and stops. Implementation is a separate assignment.

### 3. Execution

| Skill | Who starts it | Purpose | Reads | Writes | Calls | Source |
| --- | --- | --- | --- | --- | --- | --- |
| `implement` | you | Implement one task, commit it and review it | the task or ticket | code, tests, commits | `tdd`, `code-review` | Matt, one edit |
| `implement-spec` | you | Implement a whole spec along its ticket graph on one branch | spec, tickets | a branch, commits, a draft PR | `tdd`, `code-review`, subagents | Matt, setup skill name |
| `tdd` | agent | The red-green loop at pre-agreed seams | `GLOSSARY.md`, testing strategy | tests and code | `codebase-design` | Matt |

The edit in `implement`: the work is committed before review, and the review reads the changes since the starting commit. The original has the opposite order, which hands `code-review` an empty diff ([Matt's bug #511](https://github.com/mattpocock/skills/issues/511)).

### 4. Review

| Skill | Who starts it | Purpose | Reads | Writes | Calls | Source |
| --- | --- | --- | --- | --- | --- | --- |
| `code-review` | agent | Two independent axes: coding standards and fidelity to the spec | the diff from a fixed point, project standards, the spec | a report | two subagents | Matt, setup skill name |

`implement` and `implement-spec` call it themselves, once, on the finished work.

### 5. Verification

| Skill | Who starts it | Purpose | Reads | Writes | Calls | Source |
| --- | --- | --- | --- | --- | --- | --- |
| `create-verification-skill` | you | Create the project's verification skill once | project code, ways to run it | `verify-<app>` in the project | none | pstack, three edits |
| `verify-<app>` | agent | Launch the app, walk a scenario as a user and capture evidence | its own sections: launch, doctor, drive, evidence, report, cleanup | evidence files and a `report.md` with the verdict | none | generated in the project |

The edits in `create-verification-skill`: the feature-map and maintenance steps are removed and a Report section with a verdict (`PASS`, `PASS+NOTES`, `FAIL`, `BLOCKED`) and one line per scenario is added. There is no generic verification skill. The project settings say when verification is needed and who runs it: by default when user-visible behaviour changes, by a fresh agent, once before delivery.

### 6. Evidence

| Skill | Who starts it | Purpose | Reads | Writes | Calls | Source |
| --- | --- | --- | --- | --- | --- | --- |
| `pr` | agent | Write a PR body the owner reads in a minute: what is needed from them, what changed, what was verified, merge danger | the diff, the verification report, the evidence storage setting, the project's PR template | the PR text and attachments | none | Matt and Inside Platform |

The `pr` format joins two sources. From Matt: the visuals of the change and the merge danger section. From Inside Platform: the owner's action first, one line and one attachment per scenario, the 70-word limit and collapsed Details for agents. The project's PR template takes priority. `verify-<app>` produces the evidence: screenshots, recordings and a short `report.md` beside them. `pr` attaches them the way the project settings say, by default with `gh --attach`.

### 7. Delivery and acceptance

| Skill | Who starts it | Purpose | Reads | Writes | Calls | Source |
| --- | --- | --- | --- | --- | --- | --- |
| `ship` | agent | Take committed work to a merged PR or a local delivery: make sure behaviour is verified when the settings call for it, open the PR, get checks green, confirm the merge | the route, required checks and merge authority from the project settings | the PR, the merge, the closed task | `pr` | Kit |
| `owner-gate` | agent | Decide whether the owner is needed before delivery: a status, a reason and the questions for them | the task, the diff, the verification report, the project's conditions page | nothing, only its answer | none | Kit, after Inside Platform |

Acceptance has three levels, set by the “Owner gate” line in the project settings. `owner`: every delivery waits for the owner and the agent never merges; this is the default and the skill does not run. `conditions`: a fresh agent judges the change once against the conditions page and returns a status; a status that needs no owner permits the merge. `none`: the agent merges by itself. The conditions page has a “Cases from history” section where the owner adds examples of a status that turned out wrong.

### 8. Improvement

| Skill | Who starts it | Purpose | Reads | Writes | Calls | Source |
| --- | --- | --- | --- | --- | --- | --- |
| `retro` | you | After the work, suggest changes to instructions and checks | the session log | suggestions | `writing-for-agents` | Matt |
| `improve-codebase-architecture` | you | Find where to deepen modules and show an HTML report | commit history, code, `GLOSSARY.md`, ADRs | a report in the temp directory | `codebase-design`, `grilling`, `domain-modeling` | Matt, one edit |
| `codebase-design` | agent | The shared vocabulary of deep modules and seams | nothing | nothing | none | Matt |

The edit in `improve-codebase-architecture`: the report language comes from the project instructions. It touches a line each in `SKILL.md` and `HTML-REPORT.md`.

### Outside the parts

| Skill | Who starts it | Purpose | Reads | Writes | Calls | Source |
| --- | --- | --- | --- | --- | --- | --- |
| `setup-agent-kit` | you | One project setup by interview: language, tracker, labels, domain docs, delivery and workplace, verification, owner gate, testing strategy, existing rules, the shape of the root instructions | the remote, root instructions, check commands and CI, `docs/agents/` | everything in `docs/agents/`, a block in the root instructions | none | Matt, extended with Kit sections |
| `handoff` | you | Hand work to another session | the conversation | a file in the temp directory | none | Matt |
| `wait-what` | you | Ask for a plainer restatement | `GLOSSARY.md` | nothing | none | Matt |
| `wizard` | agent | A script for steps only a human can take | `.env`, config, CI workflows | a bash script, and through it `.env` and secrets | none | Matt, template changed |
| `teach` | you | Learn a topic over several sessions | the current directory | materials in the current directory | none | Matt |
| `to-questionnaire` | you | A questionnaire for the person who holds the knowledge | the conversation | a questionnaire | none | Matt |
| `writing-for-agents` | agent | How to write skills and instructions | nothing | nothing | none | Matt |

The change in `wizard`: `SKILL.md` matches the original and only `template.sh` differs. It writes only single-quoted values, so `source` and dotenv parsers read them alike.

## Project files

| File | Written by | Read by | Part |
| --- | --- | --- | --- |
| The Kit block in `AGENTS.md` | `tools/setup.py` | every session | pointer to the rest |
| `docs/agents/project-settings.md` | `setup-agent-kit` from your answers | `ship`, the verify step, `pr`, test choice; settings are grouped by reader | verification, evidence, delivery |
| `docs/agents/testing.md` | `setup-agent-kit` creates it, then you and the agent | `to-spec`, `tdd` through the root pointer | design, execution |
| `verify-<app>` | `create-verification-skill` | the agent at the verify step | verification |
| `docs/agents/owner-gate.md` | `setup-agent-kit` creates it at the “conditions” level, then only you | `owner-gate` | acceptance |
| `.github/pull_request_template.md` | the project, when it has its own | `pr` | evidence |
| `docs/agents/issue-tracker.md`, `triage-labels.md`, `domain.md` | `setup-agent-kit` | `to-spec`, `to-tickets`, `triage`, `implement-spec`, `code-review` | intake, design, execution |
| `GLOSSARY.md`, `docs/adr/` | `domain-modeling` | most of Matt's skills | design |
| `CODING_STANDARDS.md` | the project | `code-review` | review |

`testing.md` holds only the testing strategy: for each kind of change the seam and kind of test, what stays untested, and the data and services tests may use. Run commands stay in `package.json` or the `Makefile`. Required delivery checks and CI are recorded in the project settings.

## Where a rule lives

The split is Matt's (`code-review` and `retro` are his originals here), extended with two Kit files.

| File | What it holds | When it is read |
| --- | --- | --- |
| `AGENTS.md` | pointers and what every session needs | every session |
| `CODING_STANDARDS.md` | judgement rules about code | at review, by the Standards axis |
| Linter, hooks, CI | mechanical rules | automatically |
| `docs/agents/testing.md` | the seam and kind of test to use | when choosing tests |
| `GLOSSARY.md` | the project's terms | in design and in code |

The reviewer reads the standards, not the implementer: the implementer's context is busy with exploration and debugging, while the reviewer receives a finished diff. A violation is classified first. A mechanical one (a banned API, an import shape, a file location) gets a deterministic check. `CODING_STANDARDS.md` takes only judgement calls no tool can replace. Even with no documents the Standards axis applies a baseline of Fowler's code smells; a project rule overrides the baseline, and the reviewer skips whatever tooling enforces.

Setup does not create `CODING_STANDARDS.md`. It grows through `retro`: a review missed a mistake, and `retro` proposes a check or a rule.

The Kit block inside `AGENTS.md` takes only what neither a skill nor a check can carry. Today the root block says where the settings are and what to do without them, how to take test seams, how to load a named skill and where implementation may start. `ship` itself carries the rule that behaviour is verified before delivery; the Kit installs no separate workflow file.

## Who can start a skill

The “Who starts it” column repeats the skills' own flags. A skill marked “you” is closed to the agent by two flags: `disable-model-invocation: true` for Claude Code and `allow_implicit_invocation: false` for Codex. `scripts/check.py` verifies that the two flags agree and that every borrowed skill is marked as its original is. The flags are the whole protection, as in Matt's original: the root instructions add nothing to them, so a pipeline the owner set up can name such a skill in a step.

## Still undecided

- Moving `deliver` and the orchestrator from the [experiment](../experiments/factory/README.md) into the Kit: after a trial on a real project.
- Starting the orchestrator from tracker events or a schedule.

## Candidates from pstack

Source: [pstack](https://github.com/backnotprop/pstack/tree/c3464c11c60b1352d5e8f5f0428a3a6943837568), MIT. Each candidate is added only after the test bench shows a gap.

| Mechanic | Part | From |
| --- | --- | --- |
| A review finding counts only with a command and its output | review | `skills/interrogate` |
| A new check must fail on a past mistake | improvement | `skills/correct` |
| Sorting bot comments on a PR: fix, dismiss with disproof, ask | delivery | `playbooks/babysit.md` |
| Seven questions before trusting a performance number | evidence | `skills/benchmark-checklist` |
| A decision log with an evidence pointer on every row | evidence | `skills/show-me-your-work` |
| Blinded comparison of skill variants | test bench | `playbooks/eval.md` |
