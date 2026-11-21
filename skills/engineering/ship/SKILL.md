---
name: ship
description: "Deliver assigned and reviewed work under the target project's rules. Use after implementation or when asked to deliver; the harness selects PR or main-checkout delivery, checks, acceptance and merge authority."
---

Read the assignment, target root `AGENTS.md`, its delivery, tracker and acceptance
rules, and `testing.md` or the testing contract it names.

1. Read the implementation handoff. Match the task to its immutable review base and
   endpoint, Standards and Spec reports, dispositions, fixes and affected tests.
   Carry forward the local Verify revision, verdict, scenario evidence and limits,
   or the project-based reason it was inapplicable. A missing, failed or blocked
   required result keeps the delivery pending.
2. For a PR, push the owned branch and use `pr` to open or update its description
   with that evidence. For main-checkout delivery, prepare the checked commit locally
   and run the project's delivery checks. If a required check needs a remote run,
   use the project's authorized staging route. Reserve any push that publishes the
   change for the authorized delivery step.
3. Wait for the project's required CI using its script or the provider's watch CLI.
   For GitHub branch-protection checks, use `gh pr checks <pr> --required --watch`.
   Compare the named required checks and their run revisions with the candidate
   and confirm the PR still has that head (`gh pr view <pr> --json headRefOid`).
   Pending, missing or cancelled required checks keep delivery open. A project with
   local checks only proceeds once its required checks pass.

   - On failure, inspect the named check and relevant job log. For a change defect,
     fix it, run affected tests, push the correction under project rules and wait
     for required CI on the new head.
   - For a suspected transient environment failure, retry the failed check once on
     the same commit. If it fails again, diagnose the cause from the job log. Apply
     an in-scope fix or report the external blocker, affected check and needed action.
   - Preserve the original review and successful local Verify after every CI fix,
     including code changes. Update the PR or local record with the local Verify
     revision, subsequent edits, affected test results and final head with its CI
     evidence. Review and local Verify each stay complete.
4. After technical checks pass on the candidate, invoke the configured classifier
   once if enabled (for example, `owner-attention` as a fresh read-only subagent).
   Supply the task, original Spec notes, dispositions and unresolved findings,
   Verify revision and limits, later changes, final candidate, checks and target
   decision rules. Record its status, reason and owner action. Required classification
   that cannot run leaves delivery pending. When disabled, go directly to project
   acceptance. Obtain any required owner decision before the action it authorizes.
   Preserve the source and scope of existing permission.
5. Stop at the project's authorized endpoint. For authorized merge, push, deployment
   or publication, apply the project's head guard and acceptance rules. A queued
   merge remains pending. Read back the actual outcome and delivered revision from
   the destination. For a GitHub merge, confirm `state` is `MERGED`, the expected
   target and candidate head, and record the actual merge commit
   (`gh pr view <pr> --json state,baseRefName,headRefOid,mergeCommit`). For local
   delivery, confirm the target ref and commit. Run any required post-delivery
   checks on the delivered revision.
6. Record the observed result and revision in the project tracker. Close the task
   when its completion conditions hold. Clean only owned resources under the project
   lifecycle rules, preserving active writers, unsaved work and unintegrated results.
