"""Observable update safety using isolated Git histories, never the live library."""
import contextlib
import io
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_upstream import BASE, git, write
import upstream


class UpstreamTransaction(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name).resolve()
        self.source, self.root = self.base / "source", self.base / "library"
        for name in ("a", "b"):
            write(self.source / f"skills/group/{name}/SKILL.md", BASE)
        git(self.source, "init", "-q")
        git(self.source, "add", ".")
        git(self.source, "commit", "-qm", "baseline")
        self.old = git(self.source, "rev-parse", "HEAD")
        upstream.write_snapshot(self.root, self.source / "skills", self.old, "2026-01-01")
        write(self.root / "NOTICE", f"Derived from {upstream.REPOSITORY}/tree/{self.old}\n")
        for name in ("a", "b"):
            write(self.root / upstream.LOCAL / name / "SKILL.md", BASE.replace("intro", "intro\nlocal rule"))
            write(self.source / f"skills/group/{name}/SKILL.md", BASE.replace("end", "upstream improvement"))
        git(self.source, "commit", "-qam", "incoming")
        self.new = git(self.source, "rev-parse", "HEAD")
        git(self.root, "init", "-q")
        git(self.root, "add", ".")
        git(self.root, "commit", "-qm", "adaptation")

    def tearDown(self):
        self.temporary.cleanup()

    def image(self):
        return {str(p.relative_to(self.root)): (p.read_bytes(), p.stat().st_mode & 0o777)
                for p in self.root.rglob("*") if p.is_file() and ".git" not in p.relative_to(self.root).parts}

    def command(self, *arguments, revision=None):
        output, error = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(error):
            code = upstream.main(["update", revision or self.new, "--repository", str(self.source), *arguments], self.root)
        return code, output.getvalue(), error.getvalue()

    def preview(self):
        code, out, error = self.command()
        self.assertEqual(code, 0, error)
        token = re.search(r"Input fingerprint: ([0-9a-f]{64})", out)
        self.assertIsNotNone(token, out)
        return token.group(1)

    def test_preview_is_read_only_and_apply_preserves_adaptation(self):
        before = self.image()
        token = self.preview()
        self.assertEqual(self.image(), before)
        code, _, error = self.command("--apply", "--expected-input", token)
        self.assertEqual(code, 0, error)
        for name in ("a", "b"):
            text = (self.root / upstream.LOCAL / name / "SKILL.md").read_text()
            self.assertIn("local rule", text)
            self.assertIn("upstream improvement", text)
        self.assertEqual(upstream.read_source(self.root)["revision"], self.new)
        self.assertEqual(upstream.read_source(self.root)["repository"], str(self.source))
        self.assertIn(self.new, (self.root / "NOTICE").read_text())

    def test_apply_requires_the_reviewed_input_fingerprint(self):
        before = self.image()
        code, _, error = self.command("--apply")
        self.assertNotEqual(code, 0)
        self.assertIn("expected-input", error)
        self.assertEqual(self.image(), before)

    def test_conflict_never_changes_local_files_or_accepted_baseline(self):
        local = self.root / upstream.LOCAL / "a/SKILL.md"
        write(local, BASE.replace("end", "local end"))
        git(self.root, "commit", "-qam", "conflicting adaptation")
        before = self.image()
        code, out, _ = self.command()
        self.assertNotEqual(code, 0)
        self.assertIn("conflict", out.lower())
        token = re.search(r"Input fingerprint: ([0-9a-f]{64})", out).group(1)
        code, _, _ = self.command("--apply", "--expected-input", token)
        self.assertNotEqual(code, 0)
        self.assertEqual(self.image(), before)
        self.assertEqual(upstream.read_source(self.root)["revision"], self.old)

    def test_apply_refuses_local_drift_after_preview(self):
        token = self.preview()
        write(self.root / upstream.LOCAL / "a/SKILL.md", "new local decision\n")
        git(self.root, "commit", "-qam", "new decision")
        before = self.image()
        code, _, error = self.command("--apply", "--expected-input", token)
        self.assertNotEqual(code, 0)
        self.assertIn("changed", error)
        self.assertEqual(self.image(), before)

    def test_apply_refuses_a_different_library_revision_even_if_skill_bytes_match(self):
        token = self.preview()
        write(self.root / "README.md", "Changed maintenance contract\n")
        git(self.root, "add", "README.md")
        git(self.root, "commit", "-qm", "new library revision")
        before = self.image()
        code, _, error = self.command("--apply", "--expected-input", token)
        self.assertNotEqual(code, 0)
        self.assertIn("changed", error)
        self.assertEqual(self.image(), before)

    def test_moving_ref_is_rejected_before_fetch(self):
        before = self.image()
        with patch.object(upstream, "fetch") as fetch:
            code, _, error = self.command(revision="main")
        self.assertNotEqual(code, 0)
        self.assertIn("SHA", error)
        fetch.assert_not_called()
        self.assertEqual(self.image(), before)

    def test_preview_token_cannot_apply_another_incoming_revision(self):
        token = self.preview()
        write(self.source / "skills/group/a/SKILL.md", BASE.replace("end", "different upstream decision"))
        git(self.source, "commit", "-qam", "unreviewed incoming")
        other = git(self.source, "rev-parse", "HEAD")
        before = self.image()
        with patch.object(upstream, "fetch") as fetch:
            code, _, error = self.command("--apply", "--expected-input", token, revision=other)
        self.assertNotEqual(code, 0)
        self.assertIn("changed", error)
        fetch.assert_not_called()
        self.assertEqual(self.image(), before)

    def test_preview_token_cannot_apply_another_source_repository(self):
        token = self.preview()
        before = self.image()
        with patch.object(upstream, "fetch") as fetch:
            code, _, error = self.command("--repository", str(self.source) + "-other",
                                           "--apply", "--expected-input", token)
        self.assertNotEqual(code, 0)
        self.assertIn("changed", error)
        fetch.assert_not_called()
        self.assertEqual(self.image(), before)

    def test_failure_installing_second_section_restores_the_whole_batch(self):
        token = self.preview()
        before = self.image()
        original = upstream.os.replace
        failed = False
        def fail_once(source, destination):
            nonlocal failed
            if Path(destination) == self.root / upstream.UPSTREAM and not failed:
                failed = True
                raise OSError("injected replacement failure")
            return original(source, destination)
        with patch.object(upstream.os, "replace", side_effect=fail_once):
            code, _, error = self.command("--apply", "--expected-input", token)
        self.assertTrue(failed)
        self.assertNotEqual(code, 0)
        self.assertIn("injected", error)
        self.assertEqual(self.image(), before)

    def test_failure_writing_staged_provenance_does_not_touch_library(self):
        before = self.image()
        original = upstream._atomic
        def fail_archive(path, content):
            if path.name == "ARCHIVE.json":
                raise OSError("injected provenance failure")
            return original(path, content)
        with patch.object(upstream, "_atomic", side_effect=fail_archive):
            code, _, error = self.command()
        self.assertNotEqual(code, 0)
        self.assertIn("injected", error)
        self.assertEqual(self.image(), before)

    def test_failed_rollback_retains_recovery_instead_of_deleting_the_backup(self):
        token = self.preview()
        original = upstream.os.replace
        def refuse_provenance_install_and_restore(source, destination):
            if Path(destination) == self.root / upstream.UPSTREAM:
                raise OSError("persistent provenance write failure")
            return original(source, destination)
        with patch.object(upstream.os, "replace", side_effect=refuse_provenance_install_and_restore):
            code, _, error = self.command("--apply", "--expected-input", token)
        self.assertNotEqual(code, 0)
        self.assertIn("recovery retained", error)
        recovery = list(self.root.glob(".upstream-apply-*/old/provenance/upstream/mattpocock/SOURCE"))
        self.assertEqual(len(recovery), 1)
        self.assertIn(self.old, recovery[0].read_text())
        self.assertIn("local rule", (self.root / upstream.LOCAL / "a/SKILL.md").read_text())


if __name__ == "__main__":
    unittest.main()
