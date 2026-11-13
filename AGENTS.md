# Agent Kit

Public library of agent skills, distribution tools and a project harness example.
Session mode: main

## Ownership

- Editable skill sources live in `skills/engineering` and `skills/communication`. `skills/catalog.json` is the discoverable inventory. Preserve complete folders, native metadata, licenses and attribution.
- Before editing borrowed engineering skills, read `docs/upstream.md` and use `tools/upstream.py` to compare the adaptation with its frozen upstream source.
- `examples/agent-harness` owns an example project's policy. Its explicit implementation starts, worktree rules and owner acceptance apply to that example. Skills read the target project's policy when used elsewhere.
- `explain` is an internal work in progress. Preserve its status; installation requires an explicit selection.
- Private home data, account configuration, credentials and service caches belong outside this public repository.

## Work

Write code, agent instructions, skills and commit messages in English. Keep the Russian and English human entrypoints consistent. Read `CODING_STANDARDS.md` before implementation or review and `docs/distribution.md` before changing installation behavior.

For assigned work, preserve other writers, record a review base, run the affected behavioral tests and `python3 scripts/check.py`, commit, and obtain independent Standards and Spec review. The maintainer's assigned bootstrap and maintenance sessions may commit to `main`; contributors use a PR. Publication and archival require authority from the current assignment.
