"""Behavioral checks of the distribution CLI, using local Git providers."""
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

CLI = pathlib.Path(__file__).resolve().parents[1] / "tools" / "skills.py"


class SkillsCLI(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = pathlib.Path(self.temp.name)
        self.provider = self.base / "provider"
        self.provider.mkdir()
        self.git("init", "-q")
        self.skill = self.provider / "skills" / "example"
        self.skill.mkdir(parents=True)
        (self.skill / "SKILL.md").write_text("# Example\nRead reference.md.\n")
        (self.skill / "reference.md").write_text("version one\n")
        self.ref = self.commit()
        self.project = self.base / "consumer"
        (self.project / ".agents").mkdir(parents=True)
        self.catalog = self.base / "catalog.json"
        self.catalog.write_text(json.dumps({"schema_version": 1, "providers": {
            "test": {"repository": str(self.provider), "skills_prefix": "skills"}
        }}))
        self.manifest = self.project / ".agents" / "skills-manifest.json"
        self.select(self.ref)

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.provider), *args], text=True).strip()

    def commit(self):
        self.git("add", ".")
        self.git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                 "commit", "-qm", "fixture")
        return self.git("rev-parse", "HEAD")

    def select(self, ref, destination=".agents/skills/example"):
        self.manifest.write_text(json.dumps({"schema_version": 1, "skills": [
            {"provider": "test", "ref": ref, "skill": "example", "destination": destination}
        ]}))

    def run_cli(self, command, success=True):
        result = subprocess.run([sys.executable, str(CLI), command, "--project", str(self.project),
                                 "--catalog", str(self.catalog)], capture_output=True, text=True)
        self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
        return result

    def test_preview_is_read_only_and_install_copies_whole_pinned_skill(self):
        # A dirty provider file must not silently become the selected revision.
        (self.skill / "reference.md").write_text("uncommitted source edit\n")
        result = self.run_cli("preview")
        self.assertIn("version one", result.stdout)
        self.assertFalse((self.project / ".agents/skills").exists())
        self.run_cli("install")
        installed = self.project / ".agents/skills/example"
        self.assertEqual((installed / "reference.md").read_text(), "version one\n")
        self.assertTrue((installed / "SKILL.md").exists())
        lock = json.loads((self.project / ".agents/skills-lock.json").read_text())
        self.assertEqual(lock["skills"][".agents/skills/example"]["ref"], self.ref)
        self.run_cli("check")

    def test_provider_can_store_skills_at_its_repository_root(self):
        self.skill.rename(self.provider / "example")
        self.select(self.commit())
        catalog = json.loads(self.catalog.read_text())
        catalog["providers"]["test"]["skills_prefix"] = ""
        self.catalog.write_text(json.dumps(catalog))

        self.run_cli("install")

        self.assertTrue((self.project / ".agents/skills/example/SKILL.md").is_file())

    def test_manifest_skill_removed_from_catalog_names_the_missing_skill(self):
        catalog = json.loads(self.catalog.read_text())
        provider = catalog["providers"]["test"]
        del provider["skills_prefix"]
        provider["skill_paths"] = {}
        self.catalog.write_text(json.dumps(catalog))

        result = self.run_cli("install", success=False)

        self.assertIn("Skill is not in the provider catalog: example", result.stderr)
        self.assertFalse((self.project / ".agents/skills").exists())

    def test_relative_provider_and_notices_resolve_from_the_catalog_directory(self):
        (self.provider / "LICENSE").write_text("Fixture permission notice\n")
        self.select(self.commit())
        catalog = json.loads(self.catalog.read_text())
        catalog["providers"]["test"].update({
            "repository": "provider", "notices": {"LICENSE": {"source_path": "LICENSE"}},
        })
        self.catalog.write_text(json.dumps(catalog))
        self.run_cli("install")
        self.assertEqual((self.project / ".agents/skills/example/PROVIDER-NOTICES/LICENSE").read_text(),
                         "Fixture permission notice\n")
        self.run_cli("check")

    def test_edited_installed_copy_blocks_update_and_is_preserved(self):
        self.run_cli("install")
        target = self.project / ".agents/skills/example/reference.md"
        target.write_text("consumer adaptation\n")
        (self.skill / "reference.md").write_text("version two\n")
        self.select(self.commit())
        self.run_cli("preview")
        failed = self.run_cli("install", success=False)
        self.assertIn("locally edited", failed.stderr)
        self.assertEqual(target.read_text(), "consumer adaptation\n")
        self.run_cli("check", success=False)

    def test_unsafe_paths_and_symlinks_are_refused_without_writing(self):
        for destination in ["../outside", ".agents/skills/../outside", str(self.base / "outside"),
                            ".agents/skills/example/nested", ".git/hooks/example"]:
            with self.subTest(destination=destination):
                self.select(self.ref, destination)
                self.run_cli("install", success=False)
        self.select(self.ref)
        outside = self.base / "outside"
        outside.mkdir()
        (self.project / ".agents/skills").symlink_to(outside, target_is_directory=True)
        self.run_cli("install", success=False)
        self.assertEqual(list(outside.iterdir()), [])

    def test_source_symlink_is_rejected_and_named_branch_is_not_a_pin(self):
        self.select("main")
        self.run_cli("install", success=False)
        (self.skill / "outside").symlink_to("../../outside")
        self.select(self.commit())
        self.run_cli("install", success=False)
        self.assertFalse((self.project / ".agents/skills").exists())

    def test_explicit_update_replaces_whole_folder_and_keeps_previous_copy(self):
        self.run_cli("install")
        (self.skill / "reference.md").unlink()
        (self.skill / "guide.md").write_text("version two\n")
        executable = self.skill / "run.sh"
        executable.write_text("#!/bin/sh\nexit 0\n")
        executable.chmod(0o755)
        self.select(self.commit())
        self.run_cli("install")
        installed = self.project / ".agents/skills/example"
        self.assertFalse((installed / "reference.md").exists())
        self.assertTrue((installed / "run.sh").stat().st_mode & 0o111)
        previous = list((self.project / ".agents/skills-backups").glob("*/example/reference.md"))
        self.assertEqual(len(previous), 1)
        self.assertEqual(previous[0].read_text(), "version one\n")
        self.run_cli("check")

    def test_batch_conflict_never_partly_installs_and_policy_is_untouched(self):
        policy = self.project / "AGENTS.md"
        policy.write_text("Project acceptance remains here.\n")
        unmanaged = self.project / ".agents/skills/custom"
        unmanaged.mkdir(parents=True)
        (unmanaged / "SKILL.md").write_text("local skill\n")
        manifest = json.loads(self.manifest.read_text())
        manifest["skills"].append({"provider": "test", "ref": self.ref, "skill": "example",
                                   "destination": ".agents/skills/custom"})
        self.manifest.write_text(json.dumps(manifest))
        self.run_cli("install", success=False)
        self.assertFalse((self.project / ".agents/skills/example").exists())
        self.assertEqual(policy.read_text(), "Project acceptance remains here.\n")
        self.assertEqual((unmanaged / "SKILL.md").read_text(), "local skill\n")

    def test_check_verifies_lock_content_identity_not_only_revision(self):
        self.run_cli("install")
        lock_path = self.project / ".agents/skills-lock.json"
        lock = json.loads(lock_path.read_text())
        lock["skills"][".agents/skills/example"]["sha256"] = "wrong"
        lock_path.write_text(json.dumps(lock))
        self.run_cli("check", success=False)

    def test_source_links_are_checkable_but_installer_never_writes_through_them(self):
        self.run_cli("install")
        source_hash = json.loads((self.project / ".agents/skills-lock.json").read_text())["skills"][".agents/skills/example"]["sha256"]
        snapshot = self.base / "snapshot/example"
        snapshot.mkdir(parents=True)
        for source in self.skill.iterdir():
            (snapshot / source.name).write_bytes(source.read_bytes())
        catalog = json.loads(self.catalog.read_text())
        catalog["providers"]["test"]["snapshot_directory"] = "snapshot"
        catalog["providers"]["test"]["snapshot_ref"] = self.ref
        catalog["providers"]["test"]["snapshot_sha256"] = {"example": source_hash}
        self.catalog.write_text(json.dumps(catalog))
        manifest = json.loads(self.manifest.read_text())
        manifest["installation"] = "source-links"
        self.manifest.write_text(json.dumps(manifest))
        import shutil
        shutil.rmtree(self.project / ".agents/skills/example")
        (self.project / ".agents/skills/example").symlink_to(snapshot, target_is_directory=True)
        self.provider.rename(self.base / "provider-not-cloned-here")
        self.run_cli("check")
        self.run_cli("install", success=False)
        (snapshot / "reference.md").write_text("changed snapshot\n")
        self.run_cli("check", success=False)

    def test_another_installer_lock_refuses_mutation(self):
        (self.project / ".agents/skills-sync.lock").write_text("another writer\n")
        self.run_cli("install", success=False)
        self.assertFalse((self.project / ".agents/skills").exists())
        self.assertEqual((self.project / ".agents/skills-sync.lock").read_text(), "another writer\n")

    def test_provider_notices_travel_with_installed_copies(self):
        (self.provider / "LICENSE").write_text("Fixture provider notice\n")
        self.select(self.commit())
        catalog = json.loads(self.catalog.read_text())
        catalog["providers"]["test"]["notices"] = {"LICENSE.provider": {"source_path": "LICENSE"}}
        self.catalog.write_text(json.dumps(catalog))
        self.run_cli("install")
        notice = self.project / ".agents/skills/example/PROVIDER-NOTICES/LICENSE.provider"
        self.assertEqual(notice.read_text(), "Fixture provider notice\n")
        self.run_cli("check")

    def test_one_provider_can_verify_grouped_offline_snapshots(self):
        self.run_cli("install")
        source_hash = json.loads((self.project / ".agents/skills-lock.json").read_text())["skills"][".agents/skills/example"]["sha256"]
        snapshot = self.base / "snapshots/engineering/example"
        snapshot.mkdir(parents=True)
        for source in self.skill.iterdir():
            (snapshot / source.name).write_bytes(source.read_bytes())
        catalog = json.loads(self.catalog.read_text())
        catalog["providers"]["test"].update({"snapshot_ref": self.ref,
            "snapshot_paths": {"example": "snapshots/engineering/example"},
            "snapshot_sha256": {"example": source_hash}})
        self.catalog.write_text(json.dumps(catalog))
        manifest = json.loads(self.manifest.read_text())
        manifest["installation"] = "source-links"
        self.manifest.write_text(json.dumps(manifest))
        import shutil
        shutil.rmtree(self.project / ".agents/skills/example")
        (self.project / ".agents/skills/example").symlink_to(snapshot, target_is_directory=True)
        self.provider.rename(self.base / "provider-not-cloned")
        self.run_cli("check")
        (snapshot / "reference.md").write_text("modified distribution\n")
        self.run_cli("check", success=False)

    def test_explicit_adoption_locks_an_exact_copy_and_adds_notices(self):
        import shutil
        (self.provider / "LICENSE").write_text("Fixture license\n")
        self.select(self.commit())
        catalog = json.loads(self.catalog.read_text())
        catalog["providers"]["test"]["notices"] = {"LICENSE.fixture": {"source_path": "LICENSE"}}
        self.catalog.write_text(json.dumps(catalog))
        destination = self.project / ".agents/skills/example"
        shutil.copytree(self.skill, destination)
        policy = self.project / "AGENTS.md"
        policy.write_text("Project approval rules\n")
        unrelated = self.project / ".agents/skills/third-party"
        unrelated.mkdir()
        (unrelated / "SKILL.md").write_text("Existing provider\n")
        self.run_cli("install", success=False)
        self.run_cli("adopt")
        self.assertEqual((destination / "reference.md").read_text(), "version one\n")
        self.assertEqual((destination / "PROVIDER-NOTICES/LICENSE.fixture").read_text(), "Fixture license\n")
        self.assertEqual(policy.read_text(), "Project approval rules\n")
        self.assertEqual((unrelated / "SKILL.md").read_text(), "Existing provider\n")
        self.run_cli("check")

    def test_adoption_refuses_variants_before_changing_an_exact_copy(self):
        import shutil
        exact = self.project / ".agents/skills/example"
        variant = self.project / ".agents/skills/custom"
        shutil.copytree(self.skill, exact)
        shutil.copytree(self.skill, variant)
        (variant / "project-note.md").write_text("Intentional adaptation\n")
        manifest = json.loads(self.manifest.read_text())
        manifest["skills"].append({"provider": "test", "ref": self.ref,
            "skill": "example", "destination": ".agents/skills/custom"})
        self.manifest.write_text(json.dumps(manifest))
        failed = self.run_cli("adopt", success=False)
        self.assertIn("exact complete pinned copy", failed.stderr)
        self.assertEqual((variant / "project-note.md").read_text(), "Intentional adaptation\n")
        self.assertEqual((exact / "reference.md").read_text(), "version one\n")
        self.assertFalse((self.project / ".agents/skills-lock.json").exists())
        self.assertFalse((self.project / ".agents/skills-backups").exists())

    def test_select_previews_then_creates_a_pinned_manifest_without_installing(self):
        import shutil
        catalog = json.loads(self.catalog.read_text())
        catalog["skills"] = [{"provider": "test", "skill": "example", "group": "engineering"}]
        self.catalog.write_text(json.dumps(catalog))
        listed = self.run_cli("list")
        self.assertIn("engineering/example", listed.stdout)
        shutil.rmtree(self.project / ".agents")
        arguments = [sys.executable, str(CLI), "select", "--project", str(self.project),
            "--catalog", str(self.catalog), "--provider", "test", "--ref", self.ref,
            "--skill", "example", "--client", "both"]
        preview = subprocess.run(arguments, capture_output=True, text=True)
        self.assertEqual(preview.returncode, 0, preview.stderr)
        self.assertIn(self.ref, preview.stdout)
        self.assertFalse((self.project / ".agents").exists())
        selected = subprocess.run(arguments + ["--apply"], capture_output=True, text=True)
        self.assertEqual(selected.returncode, 0, selected.stderr)
        manifest = json.loads(self.manifest.read_text())
        self.assertEqual(manifest["skills"], [{"provider": "test", "ref": self.ref,
            "skill": "example", "destination": ".agents/skills/example"}])
        self.assertEqual(manifest["clients"], ["codex", "claude"])
        self.assertFalse((self.project / ".agents/skills").exists())

    def test_both_clients_share_one_index_and_leave_other_skills_installed(self):
        manifest = json.loads(self.manifest.read_text())
        manifest["clients"] = ["codex", "claude"]
        self.manifest.write_text(json.dumps(manifest))
        unrelated = self.project / ".agents/skills/third-party"
        unrelated.mkdir(parents=True)
        (unrelated / "SKILL.md").write_text("Provider-owned skill\n")
        preview = self.run_cli("preview")
        self.assertIn("WOULD LINK", preview.stdout)
        self.assertFalse((self.project / ".claude").exists())
        self.run_cli("install")
        link = self.project / ".claude/skills"
        self.assertTrue(link.is_symlink())
        self.assertEqual(link.resolve(), (self.project / ".agents/skills").resolve())
        self.assertEqual((unrelated / "SKILL.md").read_text(), "Provider-owned skill\n")
        self.run_cli("install")
        self.run_cli("check")

    def test_claude_conflict_blocks_selection_and_install_before_mutation(self):
        manifest = json.loads(self.manifest.read_text())
        manifest["clients"] = ["codex", "claude"]
        self.manifest.write_text(json.dumps(manifest))
        other = self.project / ".claude/skills/installed-provider"
        other.mkdir(parents=True)
        (other / "SKILL.md").write_text("Keep installed provider\n")
        before = self.manifest.read_bytes()
        self.run_cli("install", success=False)
        self.assertFalse((self.project / ".agents/skills").exists())
        self.assertFalse((self.project / ".agents/skills-sync.lock").exists())
        catalog = json.loads(self.catalog.read_text())
        catalog["skills"] = [{"provider": "test", "skill": "example", "group": "engineering"}]
        self.catalog.write_text(json.dumps(catalog))
        result = subprocess.run([sys.executable, str(CLI), "select", "--project", str(self.project),
            "--catalog", str(self.catalog), "--provider", "test", "--ref", self.ref,
            "--skill", "example", "--client", "both", "--apply"], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.manifest.read_bytes(), before)
        self.assertEqual((other / "SKILL.md").read_text(), "Keep installed provider\n")

    def pinned_catalog(self, graph):
        # The consumer catalog locates the provider. Only the committed inventory describes a release.
        catalog = {"schema_version": 1, "providers": {"test": {
            "repository": str(self.provider), "skills_prefix": "skills", "catalog_path": "release.json"}},
            "skills": [{"provider": "test", "skill": name, "group": "engineering", "dependencies": edges}
                       for name, edges in graph.items()]}
        for name in graph:
            folder = self.provider / "skills" / name
            folder.mkdir(exist_ok=True)
            (folder / "SKILL.md").write_text(f"---\nname: {name}\ndescription: When asked to {name}.\n---\n# {name}\n")
        (self.provider / "release.json").write_text(json.dumps(catalog))
        self.catalog.write_text(json.dumps(catalog))
        return self.commit()

    def invoke(self, command, *options, success=True):
        result = subprocess.run([sys.executable, str(CLI), command, "--project", str(self.project),
                                 "--catalog", str(self.catalog), "--provider", "test", *options],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
        return result

    def test_dependency_reasons_features_and_reference_through_all_commands(self):
        ref = self.pinned_catalog({
            "implement": [{"skill": "review", "reason": "Review the delivery."},
                          {"skill": "tdd", "feature": "tdd", "reason": "Work test-first."}],
            "review": [{"skill": "guide", "reference": True, "reason": "Terminology."}],
            "tdd": [], "guide": [], "grilling": []})
        self.manifest.unlink()
        listing = self.invoke("list", "--ref", ref).stdout
        self.assertIn("When asked to grilling.", listing)
        self.assertIn("reference: guide", listing)
        self.assertIn("feature tdd", listing)
        options = ("--skill", "implement", "--ref", ref)
        result = self.invoke("select", *options)
        self.assertIn("Review the delivery.", result.stdout)
        self.assertNotIn("Work test-first.", result.stdout)
        self.assertFalse(self.manifest.exists())
        self.invoke("select", *options, "--feature", "tdd", "--apply")
        expected = {"implement", "review", "tdd"}
        before = self.manifest.read_bytes()
        self.assertEqual({e["skill"] for e in json.loads(before)["skills"]}, expected)
        for command in ["preview", "install", "check"]:
            with self.subTest(command=command):
                out = self.invoke(command).stdout
                self.assertIn("implement (required): Review the delivery.", out)
                self.assertIn("implement (feature tdd): Work test-first.", out)
        self.assertEqual({p.name for p in (self.project / ".agents/skills").iterdir()}, expected)
        self.assertNotIn("selected-manifest", self.invoke("select", *options, "--feature", "tdd", "--apply").stdout)
        self.assertEqual(before, self.manifest.read_bytes())

    def test_complete_selection_and_removed_skills_follow_the_pin(self):
        old = self.pinned_catalog({"recap": [], "grilling": []})
        new = self.pinned_catalog({"grilling": [], "implement": []})
        self.manifest.unlink()
        self.assertNotIn("recap", self.invoke("list", "--ref", new).stdout)
        self.assertIn("recap", self.invoke("list", "--ref", old).stdout)
        self.invoke("select", "--all", "--ref", old, "--apply")
        self.invoke("install")
        self.invoke("check")
        self.assertIn("# recap\n", (self.project / ".agents/skills/recap/SKILL.md").read_text())
        self.assertFalse((self.project / ".agents/skills/implement").exists())
        self.manifest.unlink()
        self.invoke("select", "--skill", "grilling", "--ref", new, "--apply")
        self.assertEqual([e["skill"] for e in json.loads(self.manifest.read_text())["skills"]], ["grilling"])
        self.invoke("select", "--skill", "recap", "--ref", new, success=False)

    def test_dependency_cycles_missing_skills_and_unknown_features_stop_selection(self):
        self.manifest.unlink()
        for graph, term in [
            ({"implement": [{"skill": "review", "reason": "Review it."}]}, "Missing dependency review"),
            ({"implement": [{"skill": "review", "reason": "Review it."}],
              "review": [{"skill": "implement", "reason": "Implement it."}]}, "implement -> review -> implement")]:
            ref = self.pinned_catalog(graph)
            result = self.invoke("select", "--ref", ref, "--skill", "implement", "--apply", success=False)
            self.assertIn(term, result.stderr)
            self.assertFalse(self.manifest.exists())
        result = self.invoke("select", "--ref", ref, "--all", "--feature", "typo", "--apply", success=False)
        self.assertIn("Unknown feature", result.stderr)
        self.assertFalse(self.manifest.exists())

    def test_conflicting_dependency_pins_preserve_manifest_and_local_edits_before_selection(self):
        old = self.pinned_catalog({"review": []})
        new = self.pinned_catalog({"implement": [{"skill": "review", "reason": "Review it."}], "review": []})
        self.manifest.unlink()
        self.invoke("select", "--ref", old, "--skill", "review", "--apply")
        self.invoke("install")
        before = self.manifest.read_bytes()
        result = self.invoke("select", "--ref", new, "--skill", "implement", "--apply", success=False)
        self.assertIn("Version conflict", result.stderr)
        self.assertEqual(self.manifest.read_bytes(), before)
        installed = self.project / ".agents/skills/review/SKILL.md"
        installed.write_text("consumer adaptation\n")
        result = self.invoke("select", "--ref", new, "--all", "--apply", success=False)
        self.assertIn("locally edited", result.stderr)
        self.assertEqual(self.manifest.read_bytes(), before)
        self.assertEqual(installed.read_text(), "consumer adaptation\n")
        self.assertFalse((self.project / ".agents/skills/implement").exists())

    def test_manually_selected_roots_resolve_dependencies_and_conflicts_on_install(self):
        graph = {"example": [{"skill": "review", "reason": "Review it."}], "review": []}
        old = self.pinned_catalog(graph)
        graph["grilling"] = []
        ref = self.pinned_catalog(graph)
        self.select(ref)
        self.invoke("install")
        self.invoke("check")
        self.assertTrue((self.project / ".agents/skills/review/SKILL.md").exists())
        lock = self.project / ".agents/skills-lock.json"
        before = lock.read_bytes()
        manifest = json.loads(self.manifest.read_text())
        manifest["skills"].append({"provider": "test", "ref": old, "skill": "review",
                                   "destination": ".agents/skills/review"})
        self.manifest.write_text(json.dumps(manifest))
        for command in ("preview", "install", "check"):
            self.assertIn("Version conflict", self.invoke(command, success=False).stderr)
        self.assertEqual(lock.read_bytes(), before)

    def test_existing_claude_index_alias_is_preserved(self):
        manifest = json.loads(self.manifest.read_text())
        manifest["clients"] = ["claude"]
        self.manifest.write_text(json.dumps(manifest))
        (self.project / ".claude").mkdir()
        link = self.project / ".claude/skills"
        link.symlink_to("../.agents/skills", target_is_directory=True)
        self.run_cli("install")
        import os
        self.assertEqual(os.readlink(link), "../.agents/skills")
        self.run_cli("check")


if __name__ == "__main__":
    unittest.main()
