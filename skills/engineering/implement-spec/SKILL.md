---
name: implement-spec
description: "Execute an assigned specification and its dependency graph under the target project's start, delegation and delivery rules. Use when the owner assigns a whole spec and the project's required start is satisfied."
---

Read root `AGENTS.md` and its requirements, worktree, testing, human-participation,
tracker and delivery pointers. Satisfy its start rule before writing. Confirm the
approved spec, its published tickets, criteria, blockers and human checkpoints.
If the ticket graph is missing, return the spec reference and the project's ticket-planning
entrypoint. Resume on assignment once the agreed tickets exist. An authorized
spec run covers its agreed child tasks, not new requirements.

The goal is the assigned spec delivered in the project's selected mode: ticket
PRs, an approved integration branch, or main-checkout delivery. Keep spec status,
review reports and verification evidence in the project-selected ticket, PR,
integration record or main-checkout evidence location; do not create a PR or branch
solely to hold evidence. Record an immutable review base against
the intended target. This procedure does not choose another acceptance mode.

Tickets form a **task graph** with blocking relationships and a ready **frontier**.
Start each native subagent with a fresh context. Communicate through short context
pointers to the spec, ticket, research and commits, rather than copying their bodies.
Run independent workers in the background where the client and project permit it.
A native subagent is not an independently assigned application session.

## Steps

1. Read the spec and ticket graph. Identify which tickets ship together and which
   deliver separately, the expected result of each delivery, and its dependency gates.
2. If exploration is needed, a fresh exploration subagent can write scoped notes
   at the location selected by the target project's exploration and evidence policy,
   accessible to later workers. If placement is unresolved, obtain the missing
   project decision before writing notes; do not assume an inside- or outside-repo
   location. Read-only exploration does not start another implementation beyond
   the approved graph.
3. Prepare the owned execution context under project policy. In integration mode,
   prepare its branch/worktree. In ticket-PR mode,
   each ticket follows its own delivery and dependency-merge gates. A main-checkout
   project keeps its prescribed context and serialized writers.
4. Use a fresh implementer for each ready ticket when native delegation is available.
   Use separate owned worktrees/branches when permitted; serialize writers where the
   project requires one main checkout. Each worker:
   - verifies ownership and required immutable base; reports mismatch without reset;
   - reads the project contract and task, uses `tdd` where required, and observes
     accepted testing seams and human checkpoints;
   - returns committed changes, checked revisions, evidence and blockers. Integration
     workers update from the integration tip only by the project's permitted procedure.
5. For tickets submitted together, have a fresh merger integrate their checked changes
   where project rules permit.
   If the owner requested a stop before review, return the assembled changes, review base
   and affected test results at that boundary. For a full delivery, follow [Prepare one delivery](../implement/SKILL.md#prepare-one-delivery)
   on the complete diff. For its single correction pass, use a fresh
   implementer in an owned context. Run affected tests and required local Verify,
   then hand the evidence to the delivery owner.
   Integrators and `ship` consume that record. For separate ticket PRs, do this for
   each PR and confirm its required acceptance/merge before unblocking dependents.
6. Recompute the frontier from proven dependency outcomes and start newly ready work.
   Keep independent authorized work moving while owner decisions are pending.
7. Clean only owned, integrated child resources with no active writer or unsaved work.
   Follow project rules for retained acceptance trees and unintegrated results.
