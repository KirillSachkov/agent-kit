"""Exercise full setup through its public entry point, using a local versioned provider."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


KIT = Path(__file__).resolve().parents[1]


class SetupTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.project = self.base / "project"
        self.project.mkdir()
        self.provider = self.base / "kit"
        self.provider.mkdir()
        self.env = os.environ.copy()
        for name in subprocess.check_output(["git", "rev-parse", "--local-env-vars"], text=True).splitlines():
            self.env.pop(name, None)
        self.env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1", PYTHONDONTWRITEBYTECODE="1")
        self.git("init", "-q", "--template=")
        (self.provider / "tools").mkdir()
        for name in ("setup.py", "skills.py"):
            shutil.copy(KIT / "tools" / name, self.provider / "tools" / name)
        shutil.copytree(KIT / "templates", self.provider / "templates")
        skill = self.provider / "skills/engineering/probe"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("---\nname: probe\ndescription: Observe a fixture.\n---\nProbe contents\n")
        (skill / "reference.txt").write_text("v1\n")
        (self.provider / "skills/catalog.json").write_text(json.dumps({
            "schema_version": 1, "providers": {"agent-kit": {"repository": "..",
            "catalog_path": "skills/catalog.json", "skills_prefix": "skills/engineering"}},
            "skills": [{"provider": "agent-kit", "skill": "probe", "group": "engineering"}],
        }))
        self.ref = self.release("Initial release")

    def git(self, *args):
        return subprocess.check_output(["git", "-c", "user.name=Fixture", "-c", "user.email=test@example.invalid",
                                      "-c", "commit.gpgSign=false", "-c", f"core.hooksPath={os.devnull}",
                                      *args], cwd=self.provider, env=self.env, text=True).strip()

    def release(self, title):
        self.git("add", ".")
        self.git("commit", "-qm", title)
        return self.git("rev-parse", "HEAD")

    def setup(self, *flags, status=0):
        run = subprocess.run([sys.executable, self.provider / "tools/setup.py", "--project", self.project,
                              "--ref", self.ref, *flags], capture_output=True, text=True, env=self.env)
        self.assertEqual(run.returncode, status, run.stdout[-3000:] + run.stderr)
        return run.stdout + run.stderr

    def decisions(self, **choices):
        path = self.base / "decisions.json"
        path.write_text(json.dumps(choices))
        return ["--decisions", path]

    def test_fresh_preview_commit_and_noop_use_one_pin(self):
        (self.provider / "templates/project/WORKFLOW.md").write_text("Unselected workflow")
        (self.provider / "skills/engineering/probe/reference.txt").write_text("Unselected skill")
        new = self.release("New release")
        preview = self.setup("--client", "both")
        self.assertEqual(list(self.project.iterdir()), [])
        self.assertIn("Observe a fixture", preview)
        self.assertIn("current/.agents/skills-lock.json", preview)
        self.assertIn("selected/WORKFLOW.md", preview)
        self.setup("--client", "both", "--apply")
        self.assertIn("WORKFLOW.md", (self.project / "AGENTS.md").read_text())
        self.assertIn("No local test command", (self.project / "docs/agents/testing.md").read_text())
        self.assertNotIn("Unselected", (self.project / "WORKFLOW.md").read_text())
        self.assertEqual((self.project / ".agents/skills/probe/reference.txt").read_text(), "v1\n")
        self.assertTrue((self.project / ".claude/skills").is_symlink())
        before = {p: p.stat().st_mtime_ns for p in self.project.rglob("*") if p.is_file()}
        self.assertIn("No changes.", self.setup("--apply"))
        self.assertEqual(before, {p: p.stat().st_mtime_ns for p in before})
        self.ref = new
        self.setup("--apply")
        self.assertEqual((self.project / "WORKFLOW.md").read_text(), "Unselected workflow")
        self.assertEqual((self.project / ".agents/skills/probe/reference.txt").read_text(), "Unselected skill")

    def test_existing_policy_equivalent_testing_and_ci(self):
        (self.project / ".claude").mkdir()
        (self.project / ".claude/settings.json").write_text('{"private": true}')
        rules = "Use [testing](docs/checks.md). Submit a pull request for delivery.\n"
        (self.project / "CLAUDE.md").write_text(rules)
        (self.project / "docs").mkdir()
        (self.project / "docs/checks.md").write_text("Run `make verify` from src using the fixture database.\n")
        (self.project / "Makefile").write_text("check:\n\t@true\n")
        workflows = self.project / ".github/workflows"
        workflows.mkdir(parents=True)
        (workflows / "test.yaml").write_text("name: Sample CI\n")
        preview = self.setup("--client", "both", "--apply")
        for found in ("docs/checks.md", "fixture database", "make check", ".github/workflows/test.yaml"):
            self.assertIn(found, preview)
        self.assertTrue((self.project / "CLAUDE.md").read_text().startswith(rules))
        self.assertIn("docs/checks.md", (self.project / "CLAUDE.md").read_text())
        self.assertIn("CLAUDE.md", (self.project / "AGENTS.md").read_text())
        self.assertFalse((self.project / "docs/agents/testing.md").exists())
        self.assertIn("Delivery route: pr", (self.project / "docs/agents/project-settings.md").read_text())
        self.assertEqual((self.project / ".claude/settings.json").read_text(), '{"private": true}')
        self.assertIn("No changes.", self.setup())

    def test_conflict_resolution_is_bound_to_discovered_difference(self):
        instructions = "Open a draft PR before implementation.\n"
        (self.project / "AGENTS.md").write_text(instructions)
        rejected = self.setup("--apply", status=1)
        self.assertIn("Open a draft PR", rejected)
        self.assertIn("after the local evidence", rejected)
        self.assertEqual([p.name for p in self.project.iterdir()], ["AGENTS.md"])
        self.setup(*self.decisions(resolution="Use local Verify before opening a PR for this workflow."), "--apply")
        self.assertIn("No changes.", self.setup())
        text = (self.project / "AGENTS.md").read_text()
        (self.project / "AGENTS.md").write_text("Repeat verification after every CI fix.\n" + text)
        self.assertIn("Resolve the displayed process conflict", self.setup("--apply", status=1))

    def test_preserves_local_edits_and_unmanaged_destinations(self):
        self.setup("--apply")
        path = self.project / ".agents/skills/probe/reference.txt"
        path.write_text("local skill edit")
        settings = self.project / "docs/agents/project-settings.md"
        old = settings.read_bytes()
        self.setup(*self.decisions(language="French"), "--apply", status=1)
        self.assertEqual(settings.read_bytes(), old)
        self.assertEqual(path.read_text(), "local skill edit")
        path.write_text("v1\n")
        settings.write_text("local policy edit")
        self.assertIn("locally changed starter document", self.setup("--apply", status=1))
        self.assertEqual(settings.read_text(), "local policy edit")

    def test_existing_client_conflict_invalid_options_and_writer_lock_do_not_write(self):
        (self.project / ".claude/skills").mkdir(parents=True)
        self.assertIn("unmanaged", self.setup("--client", "both", "--apply", status=1))
        self.assertIn("Unknown decisions", self.setup(*self.decisions(unrecognized=True), "--apply", status=1))
        self.assertFalse((self.project / ".agents").exists())
        agents = self.project / ".agents"
        agents.mkdir()
        lock = agents / "skills-sync.lock"
        lock.write_text("another installer\n")
        self.assertIn("Another installation", self.setup("--apply", status=1))
        self.assertTrue(lock.exists())
        self.assertFalse((self.project / "AGENTS.md").exists())

    def test_generated_check_inventory_and_project_decisions(self):
        (self.project / "package.json").write_text(json.dumps({"packageManager": "pnpm@9",
                                "scripts": {"test:unit": "vitest run", "lint": "eslint src"}}))
        args = self.decisions(ci="No remote CI.", access="Use the synthetic fixture service.",
                              development_checks="Run the unit suite.", delivery="pr", owner_attention=True)
        self.setup(*args, "--apply")
        testing = (self.project / "docs/agents/testing.md").read_text()
        for content in ("pnpm run test:unit", "vitest run", "pnpm run lint", "project root",
                        "synthetic fixture service", "No remote CI.", "Run the unit suite."):
            self.assertIn(content, testing)
        self.assertTrue((self.project / "docs/agents/owner-attention.md").is_file())
        self.assertTrue((self.project / ".github/pull_request_template.md").is_file())
        self.assertIn("No changes.", self.setup())

    def test_two_instruction_roots_delegate_or_require_an_explicit_owner(self):
        wrapper = self.project / "AGENTS.md"
        canonical = self.project / "CLAUDE.md"
        canonical.write_text("Use the project tracker.\n")
        wrapper.write_text("Implement in the assigned worktree.\n")
        self.assertIn("instruction_owner", self.setup("--apply", status=1))
        self.assertFalse((self.project / ".agents").exists())
        source = "Read [the canonical instructions](CLAUDE.md).\n"
        wrapper.write_text(source)
        self.setup("--apply")
        self.assertEqual(wrapper.read_text(), source)
        self.assertIn("WORKFLOW.md", canonical.read_text())
        self.assertIn("No changes.", self.setup())
        altered = canonical.read_text() + "\nLocal addition after the Kit section.\n"
        canonical.write_text(altered)
        self.setup("--apply")
        self.assertEqual(canonical.read_text(), altered)

    def test_russian_ci_rules_and_compatible_negations(self):
        rules = self.project / "AGENTS.md"
        rules.write_text("Не открывай PR до локального Verify.\nПосле CI не нужен повторный Verify.\n"
                         "Do not repeat Verify after CI fixes.\n")
        self.assertNotIn("Project workflow difference", self.setup())
        rules.write_text("Открывай черновой PR до начала работы.\nПосле исправления CI нужен повторный Verify.\n")
        preview = self.setup("--apply", status=1)
        self.assertEqual(preview.count("Project workflow difference:"), 2)
        self.assertFalse((self.project / ".agents").exists())

    def test_runtime_failure_restores_existing_documents_and_manifest(self):
        root = self.project / "AGENTS.md"
        root.write_text("Project-owned instructions.\n")
        agents = self.project / ".agents"
        agents.mkdir()
        backup = agents / "skills-backups"
        backup.write_text("owned obstruction")
        self.setup("--apply", status=1)
        self.assertEqual(root.read_text(), "Project-owned instructions.\n")
        self.assertEqual({p.name for p in self.project.iterdir()}, {".agents", "AGENTS.md"})
        self.assertEqual(list(agents.iterdir()), [backup])
        self.assertEqual(backup.read_text(), "owned obstruction")
