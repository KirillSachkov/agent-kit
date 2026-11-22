# Agent Kit parts map

[Русский](parts.ru.md)

The Kit has eight parts. Each part works alone: it has its own skills, input and result. A project enables the parts it wants in its settings, and the [workflow](../templates/project/WORKFLOW.md) connects the enabled ones. Matt Pocock's skills are the base, unedited. The Kit adds its own skills only where Matt has none.

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

### 1. Intake

| Skill | Who starts it | Purpose | Reads | Writes | Calls | Source |
| --- | --- | --- | --- | --- | --- | --- |
| `ask` | you | Suggest which skill and what size of work fits | root instructions, the SKILL.md of the skill in question | nothing | none | Matt, reworked |
| `triage` | you | Sort incoming issues and PRs into readiness roles | tracker, labels, `.out-of-scope/` | labels, comments, `.out-of-scope/` | `grilling`, `domain-modeling` | Matt |
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
| `wayfinder` | you | A decision map for a large, unclear effort | tracker | the map and decision tickets | `grilling`, `domain-modeling`, `research`, `prototype` | Matt |
| `to-spec` | you | Write what was agreed into a spec | conversation, tracker, testing strategy | a spec in the tracker | none | Matt |
| `to-tickets` | you | Split a spec into vertical tickets with dependencies | spec, tracker | tickets in the tracker | none | Matt, one edit |

The edit in `to-tickets`: after publishing it shows the ready tickets and stops. Implementation is a separate assignment.

### 3. Execution

| Skill | Who starts it | Purpose | Reads | Writes | Calls | Source |
| --- | --- | --- | --- | --- | --- | --- |
| `implement` | you | Implement one task and commit it | the task or ticket | code, tests, a commit | `tdd`, `code-review` | Matt |
| `implement-spec` | you | Implement a whole spec along its ticket graph on one branch | spec, tickets | a branch, commits, a draft PR | `tdd`, `code-review`, subagents | Matt |
| `tdd` | agent | The red-green loop at pre-agreed seams | `GLOSSARY.md`, testing strategy | tests and code | `codebase-design` | Matt |

A plain assignment in chat (“Implement #42”) counts as invoking `implement` when the project's start rule allows it. The project workflow says so, not the skill.

### 4. Review

| Skill | Who starts it | Purpose | Reads | Writes | Calls | Source |
| --- | --- | --- | --- | --- | --- | --- |
| `code-review` | agent | Two independent axes: coding standards and fidelity to the spec | the diff from a fixed point, project standards, the spec | a report | two subagents | Matt |

`implement` and `implement-spec` call it themselves, once, on the finished work.

### 5. Verification

| Skill | Who starts it | Purpose | Reads | Writes | Calls | Source |
| --- | --- | --- | --- | --- | --- | --- |
| `create-verification-skill` | you | Create the project's verification skill once | project code, ways to run it | `verify-<app>` in the project | none | pstack, two edits |
| `verify-<app>` | agent | Launch the app and walk a scenario as a user | its own sections: launch, doctor, drive, evidence, cleanup | verification artifacts | none | generated in the project |

The edits in `create-verification-skill`: the feature-map and maintenance steps are removed. There is no generic verification skill. The project workflow decides what to verify for a task and when: every acceptance criterion, once before a PR, recording the action, the observation and the revision. `implement-spec` opens a draft PR itself, so for it verification runs before the draft is marked ready.

### 6. Evidence

| Skill | Who starts it | Purpose | Reads | Writes | Calls | Source |
| --- | --- | --- | --- | --- | --- | --- |
| `pr` | agent | Shape the PR body: a visual of the change, before and after, merge danger | the diff, check results, the project's PR template | the PR text | none | Matt, one edit |

The edit in `pr`: the project's PR template takes priority. `verify-<app>` produces the evidence itself; its Evidence section names where it is kept.

### 7. Delivery and acceptance

| Skill | Who starts it | Purpose | Reads | Writes | Calls | Source |
| --- | --- | --- | --- | --- | --- | --- |
| `ship` | agent | Take reviewed work to a local delivery or a PR, wait for CI, read back the outcome | delivery settings, review reports, the verification record | the PR, a tracker record | `pr`, `owner-attention` | Kit |
| `owner-attention` | agent | Decide whether the owner must look before delivery | project conditions, the delivery packet | status, reason, action | none | Kit |

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
| `setup-matt-pocock-skills` | you | Configure the tracker, labels, language and domain docs | the remote, root instructions, `docs/agents/` | `docs/agents/issue-tracker.md`, `triage-labels.md`, `domain.md`, a block in the root instructions | none | Matt, extended |
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
| `WORKFLOW.md` | `tools/setup.py` | the agent choosing its next step | workflow assembly |
| `docs/agents/project-settings.md` | `tools/setup.py` from your decisions | the agent at start, `ship`, `owner-attention` | execution, verification, delivery |
| `docs/agents/testing.md` | `tools/setup.py` seeds it once, then you and the agent | `to-spec`, `tdd` through the root pointer | design, execution |
| `verify-<app>` | `create-verification-skill` | the agent at the verify step | verification |
| `docs/agents/owner-attention.md` | `tools/setup.py` seeds it once, then you | `owner-attention` | acceptance |
| `.github/pull_request_template.md` | `tools/setup.py` or the project | `pr` | evidence |
| `docs/agents/issue-tracker.md`, `triage-labels.md`, `domain.md` | `setup-matt-pocock-skills` | `to-spec`, `to-tickets`, `triage`, `implement-spec`, `code-review` | intake, design, execution |
| `GLOSSARY.md`, `docs/adr/` | `domain-modeling` | most of Matt's skills | design |
| `CODING_STANDARDS.md` | the project | `code-review` | review |

`testing.md` holds only the testing strategy: for each kind of change the seam and kind of test, what stays untested, and the data and services tests may use. Run commands stay in `package.json` or the `Makefile`. Required delivery checks and CI are recorded in the project settings.

## Still undecided

- How the workflow is assembled. Today the `WORKFLOW.md` text connects the parts. Other options are compared on the test bench.
- One project setup skill in place of the `tools/setup.py` and `setup-matt-pocock-skills` pair ([#9](https://github.com/KirillSachkov/agent-kit/issues/9)).
- Reworking `ask` into a navigator of practices ([#8](https://github.com/KirillSachkov/agent-kit/issues/8)).
- Starting sessions from tracker events.

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
