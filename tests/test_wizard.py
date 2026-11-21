"""Run only the wizard library against synthetic files, never its setup stages."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "skills/engineering/wizard/template.sh"


class WizardEnvironment(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        self.target = self.root / "synthetic-config"
        self.library = TEMPLATE.read_text().split("# STAGES:", 1)[0]
        self.environment = dict(os.environ, ENV_FILE=str(self.target))

    def tearDown(self):
        self.temporary.cleanup()

    def run_library(self, commands, *arguments, input=""):
        return subprocess.run(["bash", "-c", self.library + "\n" + commands,
                               "wizard-test", *arguments], cwd=self.root,
                              env=self.environment, input=input, text=True,
                              capture_output=True)

    def test_values_round_trip_through_dotenv_and_existing(self):
        if not shutil.which("node"):
            self.skipTest("Node util.parseEnv is optional; shell tests still run")
        supported = subprocess.run(["node", "-e",
                                    "process.exit(typeof require('node:util').parseEnv === 'function' ? 0 : 1)"],
                                   capture_output=True)
        if supported.returncode:
            self.skipTest("Node util.parseEnv unavailable")
        values = ["", "plain", " leading # value = trailing ", 'a "double" and `backtick`',
                  r"literal\nvalue", "cost $5 \\ path", "$(touch sentinel)", "`touch sentinel`"]
        for value in values:
            with self.subTest(value=value):
                result = self.run_library('write_env SAMPLE "$1"; _existing SAMPLE > decoded', value)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual((self.root / "decoded").read_text(), value)
                parsed = subprocess.run(["node", "-e",
                                         "let t='';process.stdin.setEncoding('utf8');process.stdin.on('data',s=>t+=s);"
                                         "process.stdin.on('end',()=>process.stdout.write(JSON.stringify(require('node:util').parseEnv(t))));"],
                                        input=self.target.read_text(), text=True, capture_output=True, check=True)
                self.assertEqual(json.loads(parsed.stdout)["SAMPLE"], value)
                sourced = subprocess.run(["bash", "-c", '. "$1"; printf "%s" "$SAMPLE"', "bash", str(self.target)],
                                         cwd=self.root, text=True, capture_output=True, check=True)
                self.assertEqual(sourced.stdout, value)
                self.assertFalse((self.root / "sentinel").exists())

    def test_upsert_preserves_other_lines_and_file_mode(self):
        self.target.write_text("# preserved\nOTHER=keep\nSAMPLE=old\nSAMPLE=duplicate\n")
        self.target.chmod(0o640)
        result = self.run_library('write_env SAMPLE "$1"; write_env SAMPLE "$1"', "new")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.target.read_text(), "# preserved\nOTHER=keep\nSAMPLE='new'\n")
        self.assertEqual(self.target.stat().st_mode & 0o777, 0o640)
        self.assertEqual(list(self.root.glob("*.tmp.*")), [])

    def test_written_key_updates_the_callers_variable_without_local_name_collisions(self):
        for key in ("key", "value", "tmp", "target", "status", "quote"):
            with self.subTest(key=key):
                result = self.run_library(
                    'unset "$1"; write_env "$1" synthetic; printf "%s" "${!1}" > assigned', key)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual((self.root / "assigned").read_text(), "synthetic")

    def test_new_file_is_private_even_with_permissive_parent_umask(self):
        result = self.run_library("umask 022; write_env SAMPLE test")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.target.stat().st_mode & 0o777, 0o600)

    def test_invalid_or_unrepresentable_input_preserves_existing_file(self):
        self.target.write_bytes(b"OTHER=preserved\n")
        cases = [("INVALID-KEY", "test"), ("BAD\nKEY", "test"), ("SAMPLE", "line\nbreak"),
                 ("SAMPLE", "line\rbreak"), ("SAMPLE", "it's data"),
                 ("SAMPLE", "x'y'; touch sentinel")]
        for key, value in cases:
            with self.subTest(key=key, value=value):
                result = self.run_library('write_env "$1" "$2"', key, value)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(self.target.read_bytes(), b"OTHER=preserved\n")
                self.assertEqual(list(self.root.glob("*.tmp.*")), [])

    def test_unsupported_input_does_not_create_a_new_file(self):
        result = self.run_library('write_env SAMPLE "$1"', "line\nbreak")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.target.exists())

    def test_failed_copy_filter_or_rename_preserves_original(self):
        self.target.write_bytes(b"OTHER=preserved\n")
        for utility in ("cp", "grep", "mv"):
            with self.subTest(utility=utility):
                result = self.run_library(utility + '() { return 73; }; write_env SAMPLE new')
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(self.target.read_bytes(), b"OTHER=preserved\n")
                self.assertEqual(list(self.root.glob("*.tmp.*")), [])

    def test_relative_symlink_chain_and_parent_are_preserved(self):
        real = self.root / "real"
        real.mkdir()
        (self.root / "parent").symlink_to("real", target_is_directory=True)
        (real / "link").symlink_to("config")
        self.target.symlink_to("parent/link")
        result = self.run_library("write_env SAMPLE new")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(self.target.is_symlink())
        self.assertTrue((real / "link").is_symlink())
        self.assertTrue((self.root / "parent").is_symlink())
        self.assertEqual((real / "config").read_text(), "SAMPLE='new'\n")
        self.assertEqual((real / "config").stat().st_mode & 0o777, 0o600)

    def test_symlink_loop_is_rejected_without_modification(self):
        self.target.symlink_to("other")
        (self.root / "other").symlink_to("synthetic-config")
        result = self.run_library("write_env SAMPLE new")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(os.readlink(self.target), "other")
        self.assertEqual(os.readlink(self.root / "other"), "synthetic-config")


if __name__ == "__main__":
    unittest.main()
