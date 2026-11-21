# Portable procedures and project policy

AI-first Platform is the reference for separating engineering procedures from its
harness: [the reviewed main](https://github.com/KirillSachkov/ai-first-platform/tree/1ca63b8dbd8be327a3fd645e727573d539fe3c61).
Its compact procedures and native project pointers are the model, rather than the
product-specific adaptations in Inside Platform. The reference is not copied blindly:
contradictory lower steps about commit/review order, reset and cleanup are corrected.

The target project's `AGENTS.md` and its applicable pointers own:

- assignment and implementation start, including a named entrypoint when required;
- independence, delegation, main/worktree mode, base and environment preparation;
- test levels, accepted seams and authority for a new testing decision;
- requirements, domain/glossary filenames, human language and tracker conventions;
- human acceptance, delivery mode, current CI, merge, deployment and cleanup gates.

Resolve those rules from the target root and relevant descendants. Inline rules are
valid; consumers do not need to recreate the donor's `docs/agents` folder. A missing
required decision remains unresolved, but an absent optional filename is not a reason
to invent another approval, worktree or setup task.

## Native clients

Use the current client's mechanism to load a named skill. If there is no literal
Skill tool, read that skill's `SKILL.md` and relevant references. This changes the
loading mechanism, not the target project's permission to start or delegate.

`implement` and `implement-spec` are discoverable in both clients. Their availability
does not grant execution: a harness may still require the owner to name an entrypoint.
Other manual skills retain their deliberate manual invocation metadata.

## Shared invariants

The unit of review is the delivery. One PR containing several tickets gets one
review of their full diff. Separately delivered PRs each get their own review.
Both independent reviewers read the same immutable endpoints in parallel. The
author combines the findings into one fix pass, records dispositions and reruns
affected tests. For pre-commit review, record the reviewed snapshot separately,
freeze corrections and confirm that the delivered commit matches the final content.

## Verification and attention

After corrections, `implement` runs [local Verify](../skills/engineering/implement/VERIFICATION.md)
once if the project requires it, before opening a PR. The project decides scenarios,
environment, evidence storage and verifier independence. A failed or unavailable
required criterion keeps delivery open. `implement-spec` uses the same
[delivery steps](../skills/engineering/implement/SKILL.md#prepare-one-delivery)
on each complete deliverable.

`ship` takes the review reports, fixes, affected tests and local Verify evidence
from the author. It reuses them in acceptance and, for a PR, its description. CI
corrections receive affected tests and required CI on the new head. The local
Verify record stays attached to its original revision. The PR or local record
shows later changes, the final head and its check results.

After technical checks, `ship` invokes the optional [owner-attention classifier](../skills/engineering/owner-attention/SKILL.md)
once if configured. Project rules govern owner decisions and delivery authority.
Confirm the actual delivered revision before completing the task and cleaning
owned resources. The [starter](first-project.en.md) includes
copyable conditions, a PR body and an evidence manifest.

## Maintenance

The [reference record](../provenance/engineering-reference.json) records the source
commit and deliberate adaptations. Matt's pristine baseline, licenses and rename
map stay intact. Use the [three-way update workflow](upstream.md); commit and review
the library before a consumer explicitly selects the new full SHA. Shared source
updates never silently refresh installed copies or change project authority.
