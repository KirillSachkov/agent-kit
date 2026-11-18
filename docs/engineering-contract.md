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

Record immutable review endpoints and preserve complete full-diff review coverage.
Run one independent Standards/Spec review, then one fix pass for blocking defects;
optional suggestions may be left with a one-line reason. Rerun affected checks and
retain correction evidence. Do not send corrections back to reviewers unless the
target explicitly requires another round. For required pre-commit review, keep the reviewed
snapshot tree separate from the later delivered commit, record corrections, and
verify the delivered commit matches the frozen final content. A done status, green
CI, or an agent's review is not a substitute for project-required human acceptance. Never reset a
foreign context or clean unintegrated work because a generic example says to do so.

`recap` supplies readable narrative; `pr` owns the final PR description and tracker
contract; `ship` follows the project's actual delivery mode. A main-checkout flow
does not acquire a mandatory PR.

## Verification and attention

After review corrections, `implement` routes required independent verification through
[its portable handoff](../skills/engineering/implement/VERIFICATION.md). `implement-spec` and
`ship` include their handoff steps locally so independently pinned installations remain complete.
The target owns applicability, scenarios, verdicts, environment limitations, evidence storage and
freshness. `ship` can call the optional [owner-attention skill](../skills/engineering/owner-attention/SKILL.md)
once after review dispositions, required verification and final checks. The target supplies
consequences, statuses, invalidation and approval scope. No shared status creates merge or
deployment authority. The [starter](first-project.en.md#set-up-delivery) includes copyable
conditions, a PR body and an evidence manifest.
`pr` and `recap` report observed outcomes and limits separately from regression checks.

## Maintenance

The [reference record](../provenance/engineering-reference.json) records the source
commit and deliberate adaptations. Matt's pristine baseline, licenses and rename
map stay intact. Use the [three-way update workflow](upstream.md); commit and review
the library before a consumer explicitly selects the new full SHA. Shared source
updates never silently refresh installed copies or change project authority.
