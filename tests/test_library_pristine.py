import io
import os
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import upstream


class FrozenBaselineTests(unittest.TestCase):
    def test_windows_escape_in_archive_is_rejected_on_every_platform(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "kit"
            source = Path(temporary) / "source"
            file = source / "group/skill/SKILL.md"
            file.parent.mkdir(parents=True)
            file.write_text("original\n")
            upstream.write_snapshot(root, source, "a" * 40, "2026-01-01")
            with tarfile.open(root / upstream.UPSTREAM / "skills.tar.gz", "w:gz") as archive:
                member = tarfile.TarInfo("C:\\escape")
                member.size = 1
                archive.addfile(member, io.BytesIO(b"x"))
            errors = upstream.check_pristine(root)
            self.assertTrue(any("unsafe pristine archive member" in error for error in errors), errors)

    def test_packed_baseline_preserves_diff_and_is_not_a_discoverable_skill(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "kit"
            source = Path(temporary) / "source"
            original = source / "productivity/grilling/SKILL.md"
            original.parent.mkdir(parents=True)
            original.write_text("original\n")
            executable = original.parent / "run.sh"
            executable.write_text("#!/bin/sh\n")
            executable.chmod(0o755)
            local = root / "skills/engineering/grilling/SKILL.md"
            local.parent.mkdir(parents=True)
            local.write_text("original\nlocal adaptation\n")
            upstream.write_snapshot(root, source, "a" * 40, "2026-01-01")
            (root / "NOTICE").write_text("https://github.com/mattpocock/skills/tree/" + "a" * 40)
            self.assertEqual(upstream.check_pristine(root), [])
            self.assertEqual(list((root / "provenance").rglob("SKILL.md")), [])
            with tarfile.open(root / upstream.UPSTREAM / "skills.tar.gz") as archive:
                self.assertEqual(archive.getmember("productivity/grilling/run.sh").mode, 0o755)
            self.assertEqual(upstream.pairs(root, ["grilling"])[0][1], Path("skills/engineering/grilling"))
            process = subprocess.run(
                [sys.executable, "-c", "import sys; from pathlib import Path; import upstream; raise SystemExit(upstream.main(['diff', 'grilling'], Path(sys.argv[1])))", str(root)],
                env=dict(os.environ, PYTHONPATH=str(ROOT / "tools")), capture_output=True, text=True,
            )
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertIn("+local adaptation", process.stdout)


if __name__ == "__main__":
    unittest.main()
