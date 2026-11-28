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
valid; the `setup-project` interview records them in `docs/agents/project-settings.md`. A missing
required decision remains unresolved, but an absent optional filename is not a reason
to invent another approval, worktree or setup task.

## Parts and assembly

The Kit is a set of parts that each work alone; the [parts map](parts.en.md) lists
every skill and project file with its part. Matt Pocock's skills are the base, and the
parts map names every edit to them. The Kit adds its own skills only where he has none: `deliver`, `owner-gate`
and the pstack `create-verification-skill`. A rule about how parts connect lives in a
skill the Kit owns, never inside a borrowed one: `deliver` holds the rule that behaviour is
verified on the final revision after required checks pass.

## Native clients

Borrowed skills keep Matt's “call the Skill tool” wording. The starter's root
instructions tell a client without that tool to read the named `SKILL.md`.

Human-invoked skills keep their invocation metadata as Matt and pstack set it, and
`scripts/check.py` holds every borrowed skill to its original. The flags are the whole
protection: the root instructions add no rule of their own.

## Review, verification and delivery

`implement` and `implement-spec` call `code-review` once on the finished work.
`implement` commits first, so the review has a diff to read, and commits the fixes.
Its two reviewers read the same diff in parallel.

`create-verification-skill` generates a project-local `verify-<app>` skill that
launches the app, drives it as a user, captures evidence and writes a short report
with a verdict beside it. The project settings say when verification is needed and
who runs it; run it once after required PR CI (or local delivery checks) passes on the final head. A CI fix happens before this run. The PR receives the report before owner handoff or merge. `pr` is the only writer of
the PR body: it takes the report and attaches the evidence the way the project says.

`deliver` takes committed work to a merged PR or a local delivery: it opens the PR,
gets the required checks green and confirms that the merge really happened. It reads
the route, checks and merge authority from the project. [owner-gate](../skills/engineering/owner-gate/SKILL.md)
judges whether the owner is needed before delivery. The “Owner gate” line in the project
settings chooses the level: always the owner (the default), by a conditions page, or
never.

## Maintenance

The [reference record](../provenance/engineering-reference.json) records the source
commits and deliberate adaptations. Matt's pristine baseline, licenses and rename
map stay intact; use the [three-way update workflow](upstream.md) for it. The pstack
baseline and its revision are kept under `provenance/upstream/pstack`. Commit and
review the library before a consumer explicitly selects the new full SHA. Shared
source updates never silently refresh installed copies or change project authority.
