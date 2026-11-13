"""Regression tests for the client pointer checks in scripts/check.py.

Run from the repository root: python3 -m unittest discover -s tests
"""
from __future__ import annotations

import unittest
from pathlib import Path

from test_upstream import check_copy

import upstream

EXAMPLE = Path("examples/agent-harness")


class ClientPointers(unittest.TestCase):
    def test_root_claude_md_fails(self) -> None:
        self.assertIn(
            "CLAUDE.md: use native AGENTS.md instead of CLAUDE.md",
            check_copy(lambda copy: (copy / EXAMPLE / "CLAUDE.md").symlink_to("AGENTS.md")),
        )

    def test_nested_claude_md_fails(self) -> None:
        self.assertIn(
            "docs/CLAUDE.md: use native AGENTS.md instead of CLAUDE.md",
            check_copy(lambda copy: (copy / EXAMPLE / "docs/CLAUDE.md").write_text("# Notes\n")),
        )

    def test_claude_md_in_pristine_upstream_copy_is_not_reported_as_ours(self) -> None:
        def modify(copy):
            source = upstream.read_source(copy)
            with upstream.pristine_skills(copy) as baseline:
                (baseline / "productivity/grilling/CLAUDE.md").write_text("# Upstream\n")
                upstream.write_snapshot(copy, baseline, source["revision"], source["date"])
        errors = check_copy(modify)
        self.assertEqual([error for error in errors if "CLAUDE.md" in error], [])

    def test_broken_skills_pointer_fails(self) -> None:
        def unlink(copy: Path) -> None:
            (copy / EXAMPLE / ".claude/skills").unlink()

        self.assertIn(".claude/skills: incorrect client pointer", check_copy(unlink))


if __name__ == "__main__":
    unittest.main()
