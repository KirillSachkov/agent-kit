---
name: deliver
description: "Deliver committed work for owner acceptance, authorized merge or local delivery. Use when asked to prepare a finished change for acceptance, open its PR, get CI green or complete delivery."
---

Deliver the committed work on the current branch.

The project's delivery route, required checks and merge authority should have been provided to you. If not, ask the user.

1. On a PR route, push the branch and open or reuse its PR so required CI can run. Use `pr` to mark verification pending in the PR body until evidence is available. Wait for the required checks on the pushed head. Fix failures caused by the change, run affected tests, push and wait again. Give a flaky check one rerun and diagnose a second failure from its log. On a local route, run the project's required checks. Stop on an unresolved failure.

2. Once the required checks pass, record the full commit SHA. If the project requires verification, use the passing report for that SHA if one exists. Otherwise have the designated verifier run the project's `verify-<app>` once on that commit. Accept `PASS` or `PASS+NOTES`. Stop on `FAIL` or `BLOCKED` and report the cause. If the skill is missing, the owner runs `create-verification-skill`.

3. On the PR route, use `pr` to update the existing PR body with the result and evidence. Attach evidence or use the project’s evidence store while keeping the verified PR head intact. Confirm that the head to hand over or merge is still the checked commit and that its required checks are green. If the head changed, take the new revision through checks and verification before acceptance. In a pipeline with completed CI and verification stages, use their results for the same head and finish the handoff.

4. Follow the project's merge authority. When the owner must act, hand over the checked revision and say what they decide. After an authorized PR merge, confirm the host merged the checked head. On a local merge, confirm the target points at the checked commit.

5. Close the task the way the issue tracker closes work.

6. After a merge, clear what the work left, as the project settings list it: typically the stands and processes it started, its worktree and its branches. Keep what the owner asked to keep. Stop a process by its PID and a stand by its exact name, never by a name pattern; leave anything you cannot tie to this work. Then check each item is gone and report what was cleared and what stays, with the command that clears it later. Before a merge clear nothing: the owner may still want the stand.
