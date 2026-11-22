"""Exercise full setup through its public entry point, using a local versioned provider."""
import json
import os
import re
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

    def setup(self, *flags, status=0, decide=True):
        # A project with its own instructions must state its delivery route. Fixtures choose local
        # on the first run; later runs reuse the recorded decision.
        if decide and "--decisions" not in flags and not (self.project / ".agents/setup-lock.json").exists():
            default = self.base / "default-decisions.json"
            default.write_text(json.dumps({"delivery": "local"}))
            flags = ("--decisions", default, *flags)
        run = subprocess.run([sys.executable, self.provider / "tools/setup.py", "--project", self.project,
                              "--ref", self.ref, *flags], capture_output=True, text=True, env=self.env)
        self.assertEqual(run.returncode, status, run.stdout[-3000:] + run.stderr)
        return run.stdout + run.stderr

    def decisions(self, **choices):
        path = self.base / "decisions.json"
        choices.setdefault("delivery", "local")
        path.write_text(json.dumps(choices))
        return ["--decisions", path]

    def test_fresh_preview_commit_and_noop_use_one_pin(self):
        (self.provider / "templates/project/WORKFLOW.md").write_text("Unselected workflow")
        (self.provider / "skills/engineering/probe/reference.txt").write_text("Unselected skill")
        new = self.release("New release")
        preview = self.setup("--client", "both", decide=False)
        self.assertEqual(list(self.project.iterdir()), [])
        self.assertIn("Observe a fixture", preview)
        self.assertRegex(preview, re.escape(f".agents/skills/probe: agent-kit@{self.ref} / probe, sha256 ")
                         + r"[0-9a-f]{12}, new\n")
        self.assertNotIn("selected/reference.txt", preview)
        self.assertIn("selected/WORKFLOW.md", preview)
        full = self.setup("--client", "both", "--full", decide=False)
        self.assertIn("current/.agents/skills-lock.json", full)
        self.assertIn("selected/reference.txt", full)
        self.assertEqual(list(self.project.iterdir()), [])
        self.setup("--client", "both", "--apply", decide=False)
        self.assertEqual(json.loads((self.project / ".agents/setup-lock.json").read_text())["decisions"], {})
        self.assertIn("WORKFLOW.md", (self.project / "AGENTS.md").read_text())
        self.assertIn("No testing strategy is agreed yet", (self.project / "docs/agents/testing.md").read_text())
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
        self.assertIn("State delivery in the decisions JSON", self.setup("--client", "both", status=1, decide=False))
        self.assertEqual({p.name for p in self.project.iterdir()},
                         {".claude", "CLAUDE.md", "docs", "Makefile", ".github"})
        route = self.decisions(delivery="pr")
        self.assertIn("fixture database", self.setup(*route, "--client", "both", "--full"))
        preview = self.setup(*route, "--client", "both", "--apply")
        for found in ("Existing project document: docs/checks.md", "make check", ".github/workflows/test.yaml"):
            self.assertIn(found, preview)
        self.assertNotIn("fixture database", preview)
        self.assertTrue((self.project / "CLAUDE.md").read_text().startswith(rules))
        self.assertIn("docs/checks.md", (self.project / "CLAUDE.md").read_text())
        self.assertIn("CLAUDE.md", (self.project / "AGENTS.md").read_text())
        self.assertFalse((self.project / "docs/agents/testing.md").exists())
        self.assertIn("Delivery route: pr", (self.project / "docs/agents/project-settings.md").read_text())
        self.assertEqual((self.project / ".claude/settings.json").read_text(), '{"private": true}')
        self.assertIn("No changes.", self.setup())

    def test_existing_documents_are_listed_without_assigning_them_settings(self):
        (self.project / "AGENTS.md").write_text("Read [domain](docs/domain.md) and [access](docs/mcp.md).\n")
        (self.project / "docs").mkdir()
        (self.project / "docs/domain.md").write_text("The ubiquitous language of orders. TDD is discussed here.\n")
        (self.project / "docs/mcp.md").write_text("Server authorization uses a token. Cleanup the worktree cache.\n")
        self.setup("--apply")
        settings = (self.project / "docs/agents/project-settings.md").read_text()
        self.assertIn("Documents reached from the existing instructions: `AGENTS.md`, `docs/domain.md`, `docs/mcp.md`.", settings)
        self.assertNotIn("Follow `", settings)
        self.assertIn("- Language: Use the language of the assignment.", settings)
        self.assertIn("No changes.", self.setup())

    def test_documents_keep_their_stored_spelling(self):
        (self.project / "GLOSSARY.md").write_text("Order: a purchase.\n")
        (self.project / "AGENTS.md").write_text("Read [domain](docs/agents/domain.md).\n")
        (self.project / "docs/agents").mkdir(parents=True)
        (self.project / "docs/agents/domain.md").write_text("Read `GLOSSARY.md` for terms.\n")
        (self.project / "docs/TESTING.md").write_text("Run the suite.\n")
        preview = self.setup()
        self.assertIn("Existing project document: GLOSSARY.md", preview)
        self.assertIn("Existing project document: docs/TESTING.md", preview)
        for wrong in ("docs/agents/GLOSSARY.md", "docs/testing.md"):
            self.assertNotIn("Existing project document: " + wrong, preview)

    def test_conflict_resolution_is_bound_to_discovered_difference(self):
        instructions = "Open a draft PR before implementation.\n"
        (self.project / "AGENTS.md").write_text(instructions)
        rejected = self.setup("--apply", status=1)
        self.assertIn("Open a draft PR", rejected)
        self.assertIn("after the local evidence", rejected)
        self.assertEqual([p.name for p in self.project.iterdir()], ["AGENTS.md"])
        resolution = "Use local Verify before opening a PR for this workflow."
        args = self.decisions(resolution=resolution, conflict_id=self.conflict_id(rejected))
        self.setup(*args, "--apply")
        self.assertIn("No changes.", self.setup(*args))
        self.assertIn("No changes.", self.setup())
        text = (self.project / "AGENTS.md").read_text()
        (self.project / "AGENTS.md").write_text("Repeat verification after every CI fix.\n" + text)
        self.assertIn("Resolve the displayed process conflict", self.setup("--apply", status=1))
        updated = self.setup(*args, "--apply", status=1)
        self.assertNotEqual(self.conflict_id(rejected), self.conflict_id(updated))
        self.setup(*self.decisions(resolution="Keep the original Verify through CI corrections.",
                                   conflict_id=self.conflict_id(updated)), "--apply")
        self.assertIn("No changes.", self.setup())

    def conflict_id(self, report):
        return re.search(r"conflict_id in the decisions JSON: ([0-9a-f]{64})", report)[1]

    def test_nested_policy_sources_negation_and_explicit_overrides(self):
        rules = self.project / "AGENTS.md"
        rules.write_text("Follow the [release guide](policy/release.md).\n")
        policy = self.project / "policy"
        policy.mkdir()
        (policy / "release.md").write_text("For delivery, read `gates/acceptance.md`.\n")
        gates = policy / "gates"
        gates.mkdir()
        contract = gates / "acceptance.md"
        external = self.base / "private.md"
        external.write_text("UNRELATED PRIVATE DATA")
        (gates / "linked.md").symlink_to(external)
        contract.write_text("Never open a PR. Deliver on main only.\n"
                            "Read [release](../release.md) and [external](../../../private.md).\n"
                            "Read [linked](linked.md).\n")
        preview = self.setup("--full")
        self.assertNotIn("UNRELATED PRIVATE DATA", preview)
        self.assertIn("Never open a PR", preview)
        self.assertIn("Delivery route: local", preview)
        self.assertNotIn("pull_request_template", preview)
        mixed = self.setup(*self.decisions(delivery="Small fixes land on main; larger changes use a PR."))
        self.assertIn("Delivery route: Small fixes land on main; larger changes use a PR.", mixed)
        self.assertIn("pull_request_template", mixed)
        contract.write_text("Every delivery requires the owner-attention classifier.\n"
                            "Its statuses are Owner signoff and No owner attention needed.\n")
        self.setup(*self.decisions(owner_attention=True), "--apply")
        settings = (self.project / "docs/agents/project-settings.md").read_text()
        self.assertIn("Enabled. Apply `policy/gates/acceptance.md`", settings)
        self.assertFalse((self.project / "docs/agents/owner-attention.md").exists())
        self.assertIn("No changes.", self.setup())
        contract.write_text("Do not use subagents.\n")
        report = self.setup("--apply", status=1)
        self.assertIn("parallel independent Standards and Spec reviewers", report)

    def test_instruction_owner_through_root_alias(self):
        for canonical, alias in (("AGENTS.md", "CLAUDE.md"), ("CLAUDE.md", "AGENTS.md")):
            self.project = self.base / canonical.removesuffix(".md")
            self.project.mkdir()
            (self.project / canonical).write_text("Project-owned rule.\n")
            link = self.project / alias
            link.symlink_to(canonical)
            args = self.decisions(instruction_owner=alias)
            self.setup(*args, "--client", "both", "--apply")
            self.assertTrue(link.is_symlink())
            self.assertIn("WORKFLOW.md", (self.project / canonical).read_text())
            lock = json.loads((self.project / ".agents/setup-lock.json").read_text())
            self.assertEqual(lock["instruction_owner"], canonical)
            self.assertIn("No changes.", self.setup(*args, "--apply"))
            self.assertIn("No changes.", self.setup())

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

    def test_project_decisions_and_discovered_commands(self):
        (self.project / "package.json").write_text(json.dumps({"packageManager": "pnpm@9",
                                "scripts": {"test:unit": "vitest run", "lint": "eslint src"}}))
        args = self.decisions(ci="No remote CI.", access="Use the synthetic fixture service.",
                              testing="Order rules are tested at the checkout API.",
                              delivery="pr", owner_attention=True)
        preview = self.setup(*args, "--apply")
        for fact in ("pnpm run test:unit", "vitest run", "pnpm run lint"):
            self.assertIn(fact, preview)
        testing = (self.project / "docs/agents/testing.md").read_text()
        self.assertIn("Order rules are tested at the checkout API.", testing)
        self.assertNotIn("pnpm", testing)
        settings = (self.project / "docs/agents/project-settings.md").read_text()
        for content in ("synthetic fixture service", "No remote CI.", "Delivery checks:"):
            self.assertIn(content, settings)
        self.assertNotIn("Tracker", settings)
        self.assertTrue((self.project / "docs/agents/owner-attention.md").is_file())
        self.assertTrue((self.project / ".github/pull_request_template.md").is_file())
        self.assertFalse((self.project / "evidence-manifest.json").exists())
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

    def test_known_backup_obstacle_blocks_preview_and_apply(self):
        root = self.project / "AGENTS.md"
        root.write_text("Project-owned instructions.\n")
        agents = self.project / ".agents"
        agents.mkdir()
        backup = agents / "skills-backups"
        backup.write_text("owned obstruction")
        self.assertIn("Backup destination must be a directory", self.setup(status=1))
        self.assertIn("Backup destination must be a directory", self.setup("--apply", status=1))
        self.assertEqual(root.read_text(), "Project-owned instructions.\n")
        self.assertEqual({p.name for p in self.project.iterdir()}, {".agents", "AGENTS.md"})
        self.assertEqual(list(agents.iterdir()), [backup])
        self.assertEqual(backup.read_text(), "owned obstruction")

    def test_obstructed_skill_parent_blocks_preview(self):
        agents = self.project / ".agents"
        agents.mkdir()
        (agents / "skills").write_text("Existing file")
        before = self.snapshot()
        self.assertIn("must be a directory", self.setup(status=1))
        self.assertIn("must be a directory", self.setup("--apply", status=1))
        self.assertEqual(self.snapshot(), before)

    def skill_command(self, *args, status=0):
        result = subprocess.run([sys.executable, self.provider / "tools/skills.py", *args,
                                 "--project", self.project], capture_output=True, text=True, env=self.env)
        self.assertEqual(result.returncode, status, result.stdout + result.stderr)
        return result.stdout + result.stderr

    def snapshot(self):
        return {str(path.relative_to(self.project)): path.readlink() if path.is_symlink() else
                path.read_bytes() if path.is_file() else None for path in self.project.rglob("*")}

    def test_retained_provider_identity_blocks_selection_install_and_setup(self):
        catalog = self.base / "third-party.json"
        catalog.write_text(json.dumps({"schema_version": 1, "providers": {"other": {
            "repository": str(self.provider), "skills_prefix": "skills/engineering"}},
            "skills": [{"provider": "other", "skill": "probe", "group": "engineering"}]}))
        self.skill_command("select", "--provider", "other", "--catalog", catalog,
                          "--ref", self.ref, "--all", "--apply")
        self.skill_command("install", "--catalog", catalog)
        manifest = self.project / ".agents/skills-manifest.json"
        selected = json.loads(manifest.read_bytes())
        manifest.unlink()
        before = self.snapshot()
        self.assertIn("identity conflict", self.setup("--apply", status=1))
        self.assertIn("identity conflict", self.skill_command("select", "--ref", self.ref,
                                                              "--all", "--apply", status=1))
        self.assertEqual(self.snapshot(), before)
        selected["skills"][0]["provider"] = "agent-kit"
        manifest.write_text(json.dumps(selected))
        before = self.snapshot()
        self.assertIn("identity conflict", self.skill_command("install", status=1))
        self.assertEqual(self.snapshot(), before)

    def test_full_setup_preserves_individual_features(self):
        catalog = self.provider / "skills/catalog.json"
        inventory = json.loads(catalog.read_bytes())
        inventory["skills"][0]["dependencies"] = [{"skill": "extra", "feature": "extended",
                                                  "reason": "A conditional practice."}]
        inventory["skills"].append({"provider": "agent-kit", "skill": "extra", "group": "engineering"})
        extra = self.provider / "skills/engineering/extra"
        extra.mkdir()
        (extra / "SKILL.md").write_text("# Extra\n")
        catalog.write_text(json.dumps(inventory))
        self.ref = self.release("Add conditional practice")
        self.skill_command("select", "--ref", self.ref, "--skill", "probe", "--feature", "extended", "--apply")
        self.skill_command("install")
        self.setup("--apply")
        manifest = json.loads((self.project / ".agents/skills-manifest.json").read_bytes())
        self.assertEqual(manifest["selection_features"], {".agents/skills/probe": ["extended"]})
        self.assertIn("No changes.", self.setup())

    def test_upgrade_names_pin_only_changed_and_retired_skills(self):
        catalog = self.provider / "skills/catalog.json"
        inventory = json.loads(catalog.read_bytes())
        inventory["skills"].append({"provider": "agent-kit", "skill": "retired", "group": "engineering"})
        retired = self.provider / "skills/engineering/retired"
        retired.mkdir()
        (retired / "SKILL.md").write_text("---\nname: retired\ndescription: Leaves the catalog.\n---\n")
        catalog.write_text(json.dumps(inventory))
        old = self.ref = self.release("Add a skill that later retires")
        self.setup("--apply")
        inventory["skills"].pop()
        catalog.write_text(json.dumps(inventory))
        self.ref = self.release("Retire it")
        preview = self.setup()
        self.assertIn(f".agents/skills/retired: not in this release, stays installed at {old}", preview)
        self.assertRegex(preview, r"/ probe, sha256 [0-9a-f]{12}, pin only\n")
        (self.provider / "skills/engineering/probe/reference.txt").write_text("v2\n")
        self.ref = self.release("Change one file")
        self.assertRegex(self.setup(), r"/ probe, sha256 [0-9a-f]{12}, 1 changed file\n")

    def test_upgrade_drops_retired_decisions_and_files_and_leaves_seeded_documents_to_the_project(self):
        templates = self.provider / "templates/project"
        defaults = json.loads((templates / "defaults.json").read_text())
        (templates / "defaults.json").write_text(json.dumps(defaults | {"tracker": "Old default."}))
        (templates / "evidence-manifest.json").write_text("{}\n")
        self.ref = self.release("Earlier release with a tracker setting and a manifest")
        self.setup(*self.decisions(tracker="Use Linear.", delivery="PR", owner_attention=True), "--apply")
        strategy = self.project / "docs/agents/testing.md"
        strategy.write_text(strategy.read_text() + "Orders are tested at the checkout API.\n")
        conditions = self.project / "docs/agents/owner-attention.md"
        conditions.write_text(conditions.read_text() + "Owner signoff for pricing.\n")
        self.assertIn("No changes.", self.setup())
        (templates / "defaults.json").write_text(json.dumps(defaults))
        (templates / "evidence-manifest.json").unlink()
        self.ref = self.release("Retire them")
        preview = self.setup("--apply")
        self.assertIn("no longer applies and is dropped: tracker", preview)
        self.assertIn("evidence-manifest.json: no longer part of the starter; left in place", preview)
        self.assertTrue((self.project / "evidence-manifest.json").is_file())
        self.assertIn("checkout API", strategy.read_text())
        self.assertIn("pricing", conditions.read_text())
        lock = json.loads((self.project / ".agents/setup-lock.json").read_text())
        self.assertEqual(lock["decisions"], {"delivery": "pr", "owner_attention": True})
        self.assertEqual(sorted(lock["files"]), [".github/pull_request_template.md", "WORKFLOW.md",
                                                 "docs/agents/project-settings.md"])
        self.assertEqual(lock["seeded"], ["docs/agents/owner-attention.md", "docs/agents/testing.md"])
        self.assertIn("No changes.", self.setup())

    def test_installer_failure_restores_setup_and_prior_backups(self):
        (self.project / "AGENTS.md").write_text("Keep project instructions.\n")
        self.setup("--apply")
        (self.provider / "skills/engineering/probe/reference.txt").write_text("v2\n")
        self.ref = self.release("Update installed skill")
        before = self.snapshot()
        for fault in ("before-copy", "after-lock"):
            script = """
import os, sys
from pathlib import Path
sys.path.insert(0, sys.argv.pop(1))
import setup
fault = sys.argv.pop(1)
replace = os.replace
def fail(source, destination):
    source = Path(source)
    if fault == 'before-copy' and source.parent.name.startswith('.skills-stage-') and source.name == '0':
        raise OSError('injected write failure')
    replace(source, destination)
    if fault == 'after-lock' and source.name == 'lock.json':
        raise KeyboardInterrupt('injected interrupt')
os.replace = fail
sys.exit(setup.main(sys.argv[1:]))
"""
            result = subprocess.run([sys.executable, "-c", script, self.provider / "tools", fault,
                                     "--project", self.project, "--ref", self.ref, "--client", "both",
                                     "--apply"], capture_output=True, text=True, env=self.env)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("injected", result.stderr)
            self.assertEqual(self.snapshot(), before)
