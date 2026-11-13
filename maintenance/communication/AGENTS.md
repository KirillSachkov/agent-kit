# Communication skill maintenance

Skills that make a coding agent's work easy to understand. Write skills, code and commits in English.

Session mode: main

## Layout

- Canonical source: `../../skills/communication/`. Skills marked `metadata.internal: true` remain in progress and require explicit selection.
- Each skill folder is self-contained: `SKILL.md`, `references/`, `examples/`, `assets/`, so it installs on its own. Name another skill in backticks; never link into its folder.
- `tests/` and `scripts/check.py` verify the shared source from this maintenance directory; run before relevant commits.

## Rules

- A skill stays thin: steps, one format reference, good examples. Edit a skill by the principles of [writing-for-agents](https://github.com/mattpocock/skills/tree/main/skills/productivity/writing-for-agents).
- Add a rule only after a real failure, and first check which existing rule it replaces.
- Pages use the host's theme. `recap` pages load Mermaid from cdn.jsdelivr.net; `explain` draws diagrams at build time.

## Checks

```bash
python3 scripts/check.py   # skill frontmatter, links in docs and examples, tests
```

Done: `scripts/check.py` prints OK. Contributors open a PR; the maintainer's sessions (`Session mode: main`) commit to `main`.
