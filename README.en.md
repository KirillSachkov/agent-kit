# Agent Kit

[Русский](README.md)

Agent Kit brings a development workflow to a new or existing project. Set up the complete set of practices or select one skill with its dependencies. Each project owns its start rules, checks and acceptance authority.

## First installation

From the Kit checkout, substitute your project path and select a full commit SHA. The first command previews the composition and diff. The second applies that selection.

```bash
kit_ref=$(git rev-parse HEAD)
python3 tools/setup.py --project /path/to/project --ref "$kit_ref"
python3 tools/setup.py --project /path/to/project --ref "$kit_ref" --apply
```

After setup, a fresh agent can read the project instructions and explain how to take the first task through the owner's decision. Requires Git and Python 3.11+. [Start a project](docs/first-project.en.md) · [Workflow diagrams](templates/project/WORKFLOW.md)

## Select one skill

```bash
python3 tools/skills.py select --project /path/to/project --ref "$kit_ref" --skill implement --apply
python3 tools/skills.py preview --project /path/to/project
python3 tools/skills.py install --project /path/to/project
python3 tools/skills.py check --project /path/to/project
```

Selection shows why each dependency is included. For example, `implement` includes `code-review`, and `grilling` works on its own. [Skill catalog](skills/README.md) · [Versions, updates and existing copies](docs/distribution.md)

## Inside the Kit

- [Delivery routing experiment](experiments/delivery-routing/README.md) compares skill handoffs with a project-owned workflow on paired model runs.
- The [parts map](docs/parts.en.md) shows the Kit's eight parts, the skills in each and the project files they read and write.
- [Engineering skills](skills/README.md) supply procedures. The [example project harness](examples/agent-harness/README.en.md) shows a project using worktrees, pull requests and owner approval of a specific commit.
- The [migration record](docs/migration.md) covers the preserved Agent Harness and Agent Clarity histories. Matt Pocock's skills retain their licenses, frozen source revision and adaptation diff. [Upstream maintenance](docs/upstream.md)
- Run `python3 scripts/check.py` to check the catalog, source integrity and tool behavior on disposable projects.
