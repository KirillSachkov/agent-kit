---
name: implement
description: "Implement an assigned task, spec or ticket after the target project's start rule is satisfied. Use for implementation requests; the harness decides whether ordinary assignment or a named entrypoint is required."
---

Implement the assigned work. First read target root `AGENTS.md`, applicable instructions and its implementation pointers. Satisfy its start rule before writing: a request, readiness label or this skill's discovery does not override that rule.

For a whole specification, use the project's spec execution route and its ticket graph. If the user passes a ticket reference, fetch it from the configured issue tracker and state its title. If the reference is ambiguous, ask.

Prepare or reuse the execution context under project instructions. Record starting HEAD and an immutable review base covering the complete assigned change, including earlier commits when resuming.

Before implementation, state the expected observable result from the task or spec. Read `testing.md` or the testing contract named by root instructions for the accepted boundaries, environment, development and delivery commands. Use `tdd` where the project requires it. Invoke skills through the current client's mechanism; when unavailable, read the named skill's `SKILL.md` and relevant references and follow them. Run targeted tests during implementation. Before preparing the diff, pass the project's pre-review checks. At an assigned stop before review, return the tested diff, review base and results.

## Prepare one delivery

Review everything submitted together. Several tickets in one PR share this step. For separately delivered PRs, complete this step for each PR. A worker contributing a part returns its changes and test results to the author of the combined delivery.

Follow the project's review/commit order. For commit-first review, commit the assigned changes and pass immutable base/head to `code-review`. For required pre-commit review, freeze scoped content as an immutable Git tree using the project helper or a temporary index; preserve the real index and branch. Pass that snapshot and base to `code-review`, then verify the delivered commit tree matches the frozen final content, recording any review corrections separately. Include the requirement source.

Use the existing Standards and Spec reports when a separate review already covers this delivery’s base, snapshot and requirements. Otherwise invoke `code-review` once for the delivery. Its independent Standards and Spec reviewers read the same immutable diff in parallel. Combine their findings into one fix pass, record each disposition, rerun affected tests and freeze the corrected content. Give a reason for any optional suggestion left open.

Before opening the PR or waiting for CI, run [local Verify](VERIFICATION.md) once on the corrected revision if the target requires it. Record the project-based reason when it is inapplicable. A failed or unavailable required criterion keeps delivery open.

Pass the task, review endpoints and both reports, fixes and dispositions, test results, and local Verify verdict, revision, artifacts and limits to `ship` for Kit-managed delivery, or to the handoff named by the project.
