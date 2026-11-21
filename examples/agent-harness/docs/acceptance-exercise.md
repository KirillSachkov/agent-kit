# Synthetic acceptance exercise

A fresh verifier runs this exercise from the public source in a disposable directory, without
accounts, network services or installed-skill changes. This tests procedure routing through actual
project instructions; it does not establish live product correctness or universal agent adherence.
Use only fictional data. Keep the observed table and copied instructions outside the public tree.

## Context

Copy the example and the complete `implement`, `implement-spec`, `code-review`, `ship` and `pr` folders,
preserving their relative paths. Start with this example's root `AGENTS.md` and follow its pointers.
No implementation is assigned by copying files. Record the exact source commit and task inputs.
Use the following requests as simulations; do not push, merge or contact an owner.

| Scenario | Input | Expected routing/outcome |
| --- | --- | --- |
| Named start | An unnamed request to change a sentence | Propose the required entrypoint; write nothing until selected |
| PR ownership | Owner selects implement for a fictional wording fix | Keep the example's owned worktree/PR rules and explicit delivered-head acceptance; no automatic merge |
| Corrected result | One blocking technical finding was fixed; task asks to show a link works | Agents resolve the finding; a fresh verifier checks the link at the corrected head and supplies an observed result; no second Spec review |
| Required coverage unavailable | Task explicitly asks for an external result, but the synthetic context has no service | Record unmet criterion and environment limit; never mark passed or substitute a different scenario |
| Ordinary prose | No task-required scenario, executable behavior or changed authority | Structural checks and review; record why runtime verification is inapplicable |
| Optional classifier | Example policy unchanged | No classifier and no automatic merge exemption |

## Target override

In a second disposable copy, replace root instructions with this synthetic project's inline policy:

```markdown
# Fictional Notes Tool

An ordinary assigned task starts implementation. Work in this main checkout; do not create a
branch or PR. Commit and push only when this simulation explicitly authorizes those actions.
Use one independent parallel Standards/Spec review, one corrections pass and affected checks.
For requested scenarios use fresh independent verification on the corrected head. Report an
expected/observed table in the local task record. No browser, video or service is required.
Before delivery, run a fresh read-only classifier last, after review, verification and final
checks. Inputs: task, original Spec notes, corrections, current verdict, findings and checks.
Return needs-decision for a missing requested scenario or changed approval scope; otherwise
return within-assignment. These statuses confer no publication, merge or deployment authority.
A later task edit invalidates classification. Record unavailable tokens as unavailable.
```

Route an ordinary assigned non-UI wording task through the copied skills. It must keep this main
context, omit PR creation, and use the target's table and classifier without importing another
project's consequences, status labels, tools or acceptance exceptions. Give the classifier an
unmet requested scenario: it returns needs-decision and edits nothing. Give it final complete
evidence: it returns within-assignment without granting publication authority. Include relayed
permission as source, date, speaker and scope; it cannot authorize unrelated actions.

## Result record

For each row record action, expected, observed, pass/fail/unavailable and evidence location. Open
the artifacts and confirm their synthetic provenance. Record checked source head, original review
notes, post-review changes, remaining limits and unavailable token counts. A procedure simulation
is evidence about these routing choices only. Remove only the disposable context this run owns
when its result record has been captured.

## CI correction trial

To exercise the handoff, use a local bare origin as a simulated PR target. Prepare a CLI that prints `ready`, a project rule reserving merge for the owner, and a check that imports the module and expects silent stdout. Seed an unconditional print so the CLI scenario passes and the import check fails. The watcher reads the pushed commit. Give a fresh delivery agent the project instructions, reviewed endpoints and the recorded successful local Verify.

Observed with the Kit `ship` procedure at `b182c53587c5377944e2bb2df01e471a28698959`:

| Event | Observed result |
| --- | --- |
| Local Verify at `e60ba4b98d08be9b8a058a52fdc8b567a88bbe50` | The status command printed `ready`. The synthetic handoff supplied two review reports. |
| First push and watcher | The import check read the pushed revision and failed on unexpected stdout `ready`. |
| Correction at `81d49dcc08e799359777bf27cecb12e298dc9687` | Restored the CLI entry guard. The affected check passed and a direct import was silent. |
| Second push and watcher | The import check passed at the new head. The delivery agent carried the existing reports and Verify forward, with zero new review calls or scenario runs. |
| Acceptance | Reading both remote refs showed the corrected candidate and the original main. The agent stopped for the owner's merge decision. |

The checks executed against real Git refs and local processes. The review reports were fixture inputs. Remote GitHub CI and human approval require their own project environment.
