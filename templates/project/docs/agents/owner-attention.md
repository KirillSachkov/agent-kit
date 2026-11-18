# Owner attention

Enable this policy explicitly under **Project decisions** in the project's `AGENTS.md`. The
owner may adapt the statuses, conditions, and consequences below. State any standing merge
permission separately and name its scope.

## Conditions

Apply the first matching status. When in doubt, use the status that calls the owner.

| Status | When to use it | What the caller does |
| --- | --- | --- |
| Owner attention needed | The change departs from the agreed plan, has a material unresolved finding or risk, or has a required check or scenario that failed or remains unverified. | Keep delivery pending and ask the owner the concrete question. |
| Owner decision needed | The plan reserves a decision for the owner and the result and evidence are ready. | Present the requested evidence and wait for the decision. |
| No owner attention needed | The change follows the plan, required checks and scenarios passed, and no decision is reserved. | Continue under the project's ordinary delivery rules. |

When preparing the task, agree which consequences require an owner decision. Consider access,
money, personal data, irreversible changes, and visible changes without approved design.
Complete technical fixes and required checks before classification. Keep omitted optional
scenarios visible as limitations. A missing required scenario still calls for attention.

## Timing and authority

Run `owner-attention` once for the finished delivery, after review dispositions, required
verification, and checks on the delivered revision. Keep the exact revision, status, reason,
and required owner action. The caller applies the project's PR state or labels when configured.
If classification cannot be completed, keep the delivery pending.

A changed delivery candidate or a material change in its verification evidence invalidates the
result. Keep the original record, restore pending status, and handle the changed candidate as a
new delivery. Record owner approval with its source and the revision or scope it covers. This
template provides no automatic permission to merge or deploy.
