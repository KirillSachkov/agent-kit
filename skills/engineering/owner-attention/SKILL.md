---
name: owner-attention
description: "Classify whether a finished change needs an owner decision. Use once, explicitly from ship, when the target enables classification."
disable-model-invocation: true
---

Read the target's conditions and the final delivery packet as a fresh, read-only subagent. Decide
whether the owner must look before delivery. Do not edit files, request fixes, review code quality,
post to a tracker, approve a merge, or take any delivery action.

## Inputs

The caller supplies the task or specification and its requested scenarios; original Spec notes;
review dispositions, local Verify revision, observations and limits, subsequent changes,
unresolved findings, final candidate revision and check results; and the target's
status rules and authority. Read the conditions and plan first. Use the full diff only if needed
to decide a consequence the supplied evidence cannot settle.

Treat an explicit, in-scope decision as evidence only when the project accepts its source and
scope. A proposed outcome, a caller's reassurance, and an unexercised scenario are not proof.

## Decide and return

Use the exact status names and precedence in the target's conditions. Apply its uncertainty rule
when required evidence is missing. If the conditions or status rules themselves are unavailable,
report that classification is unavailable to the caller. The caller retains the pending state.

Return only the status, a short reason, and the owner action if the status calls for one. Make
each owner question concrete and state what its answer would authorize where that is unclear.
Do not attach permissions to a status beyond the target's express rules.

Classify the completed delivery once. The caller treats later changes under the target's
invalidation policy and records the result on its reviewed evidence and final revision.
