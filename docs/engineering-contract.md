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

## Parts and assembly

The Kit is a set of parts that each work alone; the [parts map](parts.en.md) lists
every skill and project file with its part. Matt Pocock's skills are the unedited
base. The Kit adds its own skills only where he has none: `ship`, `owner-attention`
and the pstack `create-verification-skill`. The [starter workflow](../templates/project/WORKFLOW.md)
connects the parts a project enables. A rule about how parts connect lives in that
workflow, never inside a borrowed skill.

## Native clients

Borrowed skills keep Matt's “call the Skill tool” wording. The starter's root
instructions tell a client without that tool to read the named `SKILL.md`.

Human-invoked skills keep their invocation metadata as Matt and pstack set it, and
`scripts/check.py` holds every borrowed skill to its original. The starter's root
instructions tell the agent to name such a command and stop, never to read the skill
file and follow it.

## Review, verification and delivery

`implement` and `implement-spec` call `code-review` once on the finished work.
`implement` commits first, so the review has a diff to read, and commits the fixes.
Its two reviewers read the same diff in parallel.

`create-verification-skill` generates a project-local `verify-<app>` skill that
launches the app and drives it as a user. When the project requires verification,
the workflow runs that skill once on the corrected revision before a PR, checks
every acceptance criterion and records the action, observation and revision. A
product failure or an unavailable environment keeps delivery open.

`ship` takes the review reports, fixes, test results and verification record from
the author. It reuses them in acceptance and, for a PR, its description. CI
corrections receive affected tests and required CI on the new head. The
verification record stays attached to its original revision.

After technical checks, `ship` invokes the optional [owner-attention](../skills/engineering/owner-attention/SKILL.md)
skill once if configured. Project rules govern owner decisions and delivery
authority. Confirm the actual delivered revision before completing the task and
cleaning owned resources.

## Maintenance

The [reference record](../provenance/engineering-reference.json) records the source
commits and deliberate adaptations. Matt's pristine baseline, licenses and rename
map stay intact; use the [three-way update workflow](upstream.md) for it. The pstack
baseline and its revision are kept under `provenance/upstream/pstack`. Commit and
review the library before a consumer explicitly selects the new full SHA. Shared
source updates never silently refresh installed copies or change project authority.
