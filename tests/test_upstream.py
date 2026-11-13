"""Regression tests for tools/upstream.py and the frozen upstream checks.

Run from the repository root: python3 -m unittest discover -s tests
"""
from __future__ import annotations

import contextlib
import importlib.util
import sys
import os
import io
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import upstream
BASE = "intro\nkeep one\nmiddle\nkeep two\nend\n"


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def git(directory: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=directory, check=True, capture_output=True, text=True,
    ).stdout.strip()


class MergeSkill(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        base = Path(self.temporary.name)
        self.old, self.new, self.local = base / "old/skill", base / "new/skill", base / "local/skill"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def merge(self) -> list[str]:
        return upstream.merge_skill(self.old, self.new, self.local)

    def test_upstream_change_merges_beside_local_adaptation(self) -> None:
        write(self.old / "SKILL.md", BASE)
        write(self.new / "SKILL.md", BASE.replace("end", "end, improved upstream"))
        write(self.local / "SKILL.md", BASE.replace("intro", "intro\nlocal rule"))
        self.assertEqual(self.merge(), [])
        self.assertEqual(
            (self.local / "SKILL.md").read_text(),
            "intro\nlocal rule\nkeep one\nmiddle\nkeep two\nend, improved upstream\n",
        )

    def test_same_line_changed_on_both_sides_leaves_conflict_visible(self) -> None:
        write(self.old / "SKILL.md", BASE)
        write(self.new / "SKILL.md", BASE.replace("middle", "upstream middle"))
        write(self.local / "SKILL.md", BASE.replace("middle", "local middle"))
        self.assertEqual(self.merge(), ["skill/SKILL.md: conflict markers left in the file"])
        text = (self.local / "SKILL.md").read_text()
        self.assertIn("<<<<<<< local", text)
        self.assertIn(">>>>>>> new upstream", text)

    def test_unchanged_local_file_takes_upstream_version(self) -> None:
        write(self.old / "SKILL.md", BASE)
        write(self.new / "SKILL.md", "rewritten\n")
        write(self.local / "SKILL.md", BASE)
        self.assertEqual(self.merge(), [])
        self.assertEqual((self.local / "SKILL.md").read_text(), "rewritten\n")

    def test_file_added_upstream_is_copied_with_its_mode(self) -> None:
        write(self.new / "REFERENCE.md", "new\n")
        write(self.new / "run.sh", "#!/bin/sh\n")
        (self.new / "run.sh").chmod(0o755)
        self.assertEqual(self.merge(), [])
        self.assertEqual((self.local / "REFERENCE.md").read_text(), "new\n")
        self.assertTrue(os.access(self.local / "run.sh", os.X_OK))

    def test_file_removed_upstream_is_removed_only_when_unadapted(self) -> None:
        write(self.old / "plain.md", "a\n")
        write(self.local / "plain.md", "a\n")
        write(self.old / "adapted.md", "a\n")
        write(self.local / "adapted.md", "a\nlocal\n")
        self.assertEqual(self.merge(), ["skill/adapted.md: removed upstream but changed locally; local file kept"])
        self.assertFalse((self.local / "plain.md").exists())
        self.assertTrue((self.local / "adapted.md").exists())


class Update(unittest.TestCase):
    def update(self, base: Path, local_name: str) -> tuple[int, Path, str]:
        """Merge a new upstream revision of `skill` into the local copy named `local_name`."""
        source = base / "source"
        write(source / "skills/group/skill/SKILL.md", BASE)
        git(source, "init", "-q")
        git(source, "add", ".")
        git(source, "commit", "-qm", "old")
        old_revision = git(source, "rev-parse", "HEAD")
        write(source / "skills/group/skill/SKILL.md", BASE.replace("end", "end, improved upstream"))
        git(source, "commit", "-qam", "new")
        new_revision = git(source, "rev-parse", "HEAD")

        root = base / "root"
        baseline = base / "baseline"
        write(baseline / "group/skill/SKILL.md", BASE)
        upstream.write_snapshot(root, baseline, old_revision, "2026-01-01")
        if local_name != "skill":
            write(root / "provenance/upstream/mattpocock/RENAMES", f"# upstream: local\nskill: {local_name}\n")
        write(root / f"skills/engineering/{local_name}/SKILL.md", BASE.replace("intro", "intro\nlocal rule"))
        git(root, "init", "-q")
        git(root, "add", ".")
        git(root, "commit", "-qm", "root")

        with contextlib.redirect_stdout(io.StringIO()):
            code = upstream.main(["update", new_revision, "--repository", str(source)], root)
        return code, root, new_revision

    def test_update_merges_new_revision_and_records_it(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            code, root, new_revision = self.update(Path(temporary), "skill")

            self.assertEqual(code, 0)
            self.assertIn("local rule", (root / "skills/engineering/skill/SKILL.md").read_text())
            self.assertIn("improved upstream", (root / "skills/engineering/skill/SKILL.md").read_text())
            source_file = upstream.read_source(root)
            self.assertEqual(source_file["revision"], new_revision)
            with upstream.pristine_skills(root) as baseline:
                self.assertEqual(source_file["sha256"], upstream.identity(baseline))

    def test_update_merges_into_renamed_local_skill(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            code, root, _ = self.update(Path(temporary), "renamed")

            self.assertEqual(code, 0)
            merged = (root / "skills/engineering/renamed/SKILL.md").read_text()
            self.assertIn("local rule", merged)
            self.assertIn("improved upstream", merged)
            self.assertFalse((root / "skills/engineering/skill").exists())
            self.assertTrue((root / "provenance/upstream/mattpocock/RENAMES").is_file())


class Pairs(unittest.TestCase):
    def test_renamed_skill_pairs_with_its_upstream_original_by_either_name(self) -> None:
        expected = [(Path("provenance/upstream/mattpocock/skills/engineering/ask-matt"), Path("skills/engineering/ask"))]
        self.assertEqual(upstream.pairs(ROOT, ["ask"]), expected)
        self.assertEqual(upstream.pairs(ROOT, ["ask-matt"]), expected)

    def test_unrenamed_skill_pairs_by_its_own_name(self) -> None:
        self.assertEqual(
            upstream.pairs(ROOT, ["grilling"]),
            [(Path("provenance/upstream/mattpocock/skills/productivity/grilling"), Path("skills/engineering/grilling"))],
        )


def check_copy(change) -> list[str]:
    """Check a safe public fixture without copying caches, Git objects or local state."""
    with tempfile.TemporaryDirectory() as temporary:
        copy = Path(temporary) / "repo"
        for folder in ("examples/agent-harness", "skills/engineering", "provenance/engineering", "provenance/upstream", "tools"):
            shutil.copytree(ROOT / folder, copy / folder, symlinks=True, ignore=shutil.ignore_patterns("__pycache__"))
        notice = ROOT / "NOTICE" if (ROOT / "NOTICE").is_file() else ROOT / "provenance/engineering/NOTICE"
        shutil.copyfile(notice, copy / "NOTICE")
        change(copy)
        spec = importlib.util.spec_from_file_location("example_harness_check", copy / "examples/agent-harness/scripts/check.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.check(copy)[0]


class CheckUpstreamCopy(unittest.TestCase):
    def errors(self, change) -> list[str]:
        return check_copy(change)

    def test_clean_repository_passes(self) -> None:
        self.assertEqual(self.errors(lambda copy: None), [])

    def test_edited_upstream_copy_fails(self) -> None:
        def edit(copy: Path) -> None:
            source = upstream.read_source(copy)
            original = (copy / upstream.UPSTREAM / "SOURCE").read_bytes()
            with upstream.pristine_skills(copy) as baseline:
                file = baseline / "productivity/grilling/SKILL.md"
                file.write_text(file.read_text() + "edit\n")
                upstream.write_snapshot(copy, baseline, source["revision"], source["date"])
            (copy / upstream.UPSTREAM / "SOURCE").write_bytes(original)

        self.assertIn(
            "provenance/upstream/mattpocock: pristine copy differs from SOURCE; never edit it by hand",
            self.errors(edit),
        )

    def test_upstream_skill_without_local_copy_fails(self) -> None:
        def remove(copy: Path) -> None:
            shutil.rmtree(copy / "skills/engineering/grilling")

        self.assertIn(
            "provenance/upstream/mattpocock/skills/productivity/grilling: no local skill with this name",
            self.errors(remove),
        )

    def test_rename_to_missing_local_skill_fails(self) -> None:
        def rename(copy: Path) -> None:
            renames = copy / "provenance/upstream/mattpocock/RENAMES"
            renames.write_text(renames.read_text() + "grilling: no-such-skill\n")

        self.assertIn(
            "provenance/upstream/mattpocock/skills/productivity/grilling: no local skill with this name",
            self.errors(rename),
        )

    def test_rename_of_unknown_upstream_skill_fails(self) -> None:
        def rename(copy: Path) -> None:
            renames = copy / "provenance/upstream/mattpocock/RENAMES"
            renames.write_text(renames.read_text() + "gone: grilling\n")

        self.assertIn("provenance/upstream/mattpocock/RENAMES: gone is not a borrowed skill", self.errors(rename))

    def test_snapshot_link_naming_another_revision_fails(self) -> None:
        def repin(copy: Path) -> None:
            notice = copy / "NOTICE"
            notice.write_text(notice.read_text().replace("a496f5513d4a4cf889bc48e189e579f4b0bdf6aa", "0" * 40))

        self.assertIn(
            "NOTICE: Matt's snapshot link must name the SOURCE revision a496f5513d4a4cf889bc48e189e579f4b0bdf6aa",
            self.errors(repin),
        )

    def test_source_without_revision_fails(self) -> None:
        def strip(copy: Path) -> None:
            source = copy / "provenance/upstream/mattpocock/SOURCE"
            source.write_text("".join(l for l in source.read_text().splitlines(True) if not l.startswith("revision")))

        self.assertIn("provenance/upstream/mattpocock/SOURCE: revision must be a full commit SHA", self.errors(strip))

    def test_missing_source_is_reported(self) -> None:
        def delete(copy: Path) -> None:
            (copy / "provenance/upstream/mattpocock/SOURCE").unlink()

        self.assertEqual(self.errors(delete), ["provenance/upstream/mattpocock/SOURCE: missing"])


if __name__ == "__main__":
    unittest.main()
