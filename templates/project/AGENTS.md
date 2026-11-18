# Project instructions

Fill in **Project decisions** before assigning the first implementation. Keep these instructions
in the project repository. Installed skills supply procedures and follow the decisions below.

## Project decisions

- Instructions and tracker: `<language, task tracker, and references to project rules>`
- Start and context: `<what authorizes implementation, where it runs, and who owns each worktree>`
- Checks: `<local commands, permitted test inputs, and how to identify the required CI run>`
- Evidence: `<where to keep review, verification, and links the owner can inspect>`
- Delivery: `<PR or main, who accepts the result, and who may push, merge, or deploy>`
- Cleanup: `<who can retire task branches and worktrees, and what history to retain>`

## Task workflow

1. Record the requested outcome, scope, acceptance scenarios, and any decisions reserved for the
   owner. Check for existing work before editing. Record the exact base and the assigned context.
2. Implement within the assignment. Run the affected checks. Use independent Standards and Spec
   review on an immutable diff. Record the findings, make one correction pass, and repeat the
   affected checks.
3. When the task requires an observed scenario, use a fresh verifier on the corrected revision.
   Record the actor, action, expected and observed result, source revision, and evidence location.
   Record unmet or unavailable scenarios explicitly. Keep these observations separate from review
   and CI results. Use synthetic data for shareable examples.
4. Deliver according to the project decisions. Check the required CI at the delivered revision.
   If the project uses a merge queue, record its checks and the actual merged revision separately.
   If the project requires a classifier, run it last and read-only. Present the outcome and any
   remaining decisions to the owner. Keep acceptance and authority for publication distinct.
5. Before any authorized retirement, confirm integration or explicit disposition, retain the
   needed evidence and recovery references, and check for active writers and unpublished changes.
   Retire only the task's identified resources and verify the outcome.
