# Agent Kit

[Русский](README.md)

A shared skill library for Claude Code, Codex and other agents that read `SKILL.md`.
It contains engineering procedures, communication skills, a project harness example and a pinned-version installer.

## Layout

| Area | Contents |
| --- | --- |
| [skills/engineering](skills/README.md#engineering) | 28 skills for discussion, design, implementation, review and delivery |
| [skills/communication](skills/README.md#communication) | Writing style, recaps and style setup; `explain` remains internal work in progress |
| [examples/agent-harness](examples/agent-harness/AGENTS.md) | Example project policy: starts, worktrees, checks and owner acceptance |
| [tools/skills.py](tools/skills.py) | Version selection, diff preview, installation, verification and explicit exact-copy adoption |
| [provenance](provenance/sources.json) | Source history, licenses and frozen upstream comparison input |

A skill defines a procedure. Each target project keeps its commands, permissions, checks and merge/deploy gates. Select the skills the project needs rather than installing the entire catalog.

## Install into a project

Git and Python 3.11 or later are required. Clone the library and select its verified commit:

```bash
git clone https://github.com/KirillSachkov/agent-kit.git
cd agent-kit
git rev-parse HEAD
```

Substitute that full SHA and the target project path:

```bash
python3 tools/skills.py select --project /path/to/project --ref FULL_COMMIT_SHA --skill tdd --skill recap --client both --apply
python3 tools/skills.py preview --project /path/to/project
python3 tools/skills.py install --project /path/to/project
python3 tools/skills.py check --project /path/to/project
```

Without `--apply`, `select` previews its plan. Existing unmanaged folders are preserved. Use explicit `adopt` for exact copies; compare and reconcile adapted versions under their owning project's authority first. See [manifests and updates](docs/distribution.md).

## Sources and experiments

Agent Kit combines the public Agent Harness and Agent Clarity libraries while retaining both Git histories. Original commits and separate draft/research branches remain under `history/agent-harness/*` and `history/agent-clarity/*`. See [migration and boundaries](docs/migration.md).

Engineering skills include adaptations of Matt Pocock's work. Attribution and complete MIT notices remain in [NOTICE](NOTICE) and `provenance/engineering/`. See [upstream maintenance](docs/upstream.md).

## Checks

```bash
python3 scripts/check.py
```

Checks use synthetic projects. They do not authorize services or establish the correctness of an agent's eventual work in another project.
