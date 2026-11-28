"""The experimental orchestrator leads a ticket through the fixture pipeline with a scripted agent."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

KIT = Path(__file__).resolve().parents[1]
FACTORY = KIT / "experiments/factory"
sys.path.insert(0, str(FACTORY))
import bench  # noqa: E402
from bench import orchestrator  # noqa: E402


class OrchestratorTest(unittest.TestCase):
    def trial(self, situation):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name).resolve() / "trial"
        root.mkdir()
        local = dict(os.environ)
        for name in subprocess.check_output(["git", "rev-parse", "--local-env-vars"], text=True).splitlines():
            local.pop(name, None)
        saved = dict(os.environ)
        os.environ.clear()
        os.environ.update(local)
        self.addCleanup(lambda: (os.environ.clear(), os.environ.update(saved)))
        project, env = bench.prepare(root, situation)
        env["FACTORY_AGENT"] = f"{sys.executable} {FACTORY / 'fake_agent.py'}"
        self.assertFalse(any(key.startswith("ORCA_") for key in env))
        self.env = env
        bench.execute(project, env, "direct", "claude", "sonnet", 60, bench.work(situation), situation)
        return root, project, bench.grade(root, project, situation)

    def program(self, project, *args):
        return subprocess.run([sys.executable, str(project / ".agents/skills/run-pipeline/orchestrator.py"), *args, "--project", str(project)],
                              env=self.env, capture_output=True, text=True)

    def test_every_step_passing_reaches_the_owner_with_an_open_pull_request(self):
        root, project, facts = self.trial("happy")
        self.assertEqual(facts["final_stage"], "needs-owner")
        self.assertTrue(facts["pass"], facts)
        self.assertEqual((facts["sessions"], facts["ci_runs"], facts["merge_attempts"], facts["outside"]), (5, [True], 0, []))
        journal = [json.loads(line) for line in (project / ".factory/greeting-01-greet-by-name/runs.jsonl").read_text().splitlines()]
        self.assertEqual([(row["task"], row["attempt"], row["check_exit"]) for row in journal],
                         [("implement", 1, 0), ("ci", 1, 0), ("verify", 1, 0), ("deliver", 1, 0)])

    def test_the_work_happens_in_a_worktree_of_its_own_and_the_project_stays_on_its_branch(self):
        root, project, facts = self.trial("happy")
        self.assertEqual((facts["own_worktree"], facts["branch"]), (True, "deliver/greeting-01-greet-by-name"))
        self.assertTrue((root / "project-worktrees/greeting-01-greet-by-name/greet.py").is_file())
        self.assertEqual(subprocess.check_output(["git", "-C", str(project), "branch", "--show-current"], text=True).strip(), "main")
        status = self.program(project, "status").stdout
        self.assertIn("greeting-01-greet-by-name\tneeds-owner\tnot running\tlast: deliver attempt 1 passed", status)

    def test_a_blocked_verification_stops_the_chain_before_delivery_without_a_retry(self):
        root, project, facts = self.trial("verify-blocked")
        self.assertEqual((facts["final_stage"], facts["pr_opened"], facts["verdict"]), ("blocked", True, "Verdict: BLOCKED"))
        self.assertTrue(facts["pass"], facts)
        self.assertIn("Blocked at verify: verification verdict: BLOCKED", (project / bench.TICKET).read_text())
        self.assertEqual(facts["sessions"], 4)
        folder = project / ".factory/greeting-01-greet-by-name"
        self.assertIn("verification verdict: BLOCKED", (folder / "verify-1.check.log").read_text())
        (folder / "reported").unlink(missing_ok=True)  # as a session that has not asked yet
        told = self.program(project, "wait", bench.TICKET).stdout.splitlines()
        self.assertEqual(told[:3], ["implement attempt 1 passed", "ci attempt 1 passed",
                                    "verify attempt 1 failed: verification verdict: BLOCKED (check output in verify-1.check.log)"])
        self.assertIn("\tblocked\tnot running\tlast: verify attempt 1 failed: verification verdict: BLOCKED", told[3])
        self.assertEqual(len(self.program(project, "wait", bench.TICKET).stdout.splitlines()), 1)

    def test_a_blocked_task_continues_from_the_step_that_blocked_it(self):
        root, project, facts = self.trial("verify-blocked")
        (root / "project-worktrees/greeting-01-greet-by-name/.verify-env").write_text("ready\n")
        self.assertEqual(self.program(project, "run", bench.TICKET).returncode, 0)
        facts = bench.grade(root, project, "happy")
        self.assertEqual((facts["final_stage"], facts["pr_opened"]), ("needs-owner", True))
        journal = [json.loads(line)["task"] for line in (project / ".factory/greeting-01-greet-by-name/runs.jsonl").read_text().splitlines()]
        self.assertEqual(journal, ["implement", "ci", "verify", "verify", "deliver"])
        logs = sorted(path.name for path in (project / ".factory/greeting-01-greet-by-name").glob("verify-*.jsonl"))
        self.assertEqual(logs, ["verify-1.jsonl", "verify-2.jsonl"])
        attempts = [json.loads(line)["attempt"] for line in (project / ".factory/greeting-01-greet-by-name/runs.jsonl").read_text().splitlines()]
        self.assertEqual(attempts, [1, 1, 1, 2, 1])

    def test_resuming_verify_on_an_unpushed_commit_does_not_start_the_verifier(self):
        root, project, _ = self.trial("verify-blocked")
        work = root / "project-worktrees/greeting-01-greet-by-name"
        subprocess.run(["git", "commit", "--allow-empty", "-qm", "Changed since CI"], cwd=work, check=True)
        marker = root / "verifier-started"
        worker = root / "mark.py"
        worker.write_text(f"from pathlib import Path\nPath({str(marker)!r}).touch()\n")
        self.env["FACTORY_AGENT"] = f"{sys.executable} {worker}"
        self.program(project, "run", bench.TICKET)
        self.assertFalse(marker.exists())
        self.assertIn("entry check failed", self.program(project, "status", bench.TICKET).stdout)

    def test_a_fixable_ci_failure_is_fixed_and_an_outage_blocks_after_the_allowed_attempts(self):
        root, project, facts = self.trial("ci-fix")
        self.assertEqual((facts["final_stage"], facts["ci_runs"]), ("needs-owner", [False, True]))
        ticket = orchestrator.Ticket(project, bench.TICKET)
        journal = [json.loads(line)["task"] for line in (ticket.folder / "runs.jsonl").read_text().splitlines()]
        self.assertEqual(journal, ["implement", "ci", "verify", "deliver"])
        state = json.loads((root / "gh-state.json").read_text())
        self.assertTrue(state["runs"][ticket.state()["verified_head"]]["ok"])
        self.assertIn("Greets by name.", state["prs"][0]["body"])
        self.assertIn(ticket.state()["verified_head"], state["prs"][0]["body"])
        self.assertTrue(facts["pr_cites_verification"])
        root, project, facts = self.trial("ci-outage")
        self.assertFalse(facts["verify_skill_loaded"])
        self.assertEqual((facts["final_stage"], facts["ci_runs"], facts["sessions"]), ("blocked", [False], 4))

    def test_the_owners_feedback_on_the_pull_request_takes_the_work_through_the_chain_again(self):
        root, project, facts = self.trial("rework")
        self.assertTrue(facts["pass"], facts)
        journal = [json.loads(line)["task"] for line in (project / ".factory/greeting-01-greet-by-name/runs.jsonl").read_text().splitlines()]
        self.assertEqual(journal, ["implement", "ci", "verify", "deliver", "rework", "ci", "verify", "deliver"])

    def test_a_finished_ticket_is_marked_done_and_its_worktree_is_left_to_the_delivery_skill(self):
        root, project, facts = self.trial("happy")
        work = root / "project-worktrees/greeting-01-greet-by-name"
        done = self.program(project, "finish", bench.TICKET)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("greeting-01-greet-by-name\tdone\tnot running", done.stdout)
        self.assertIn(str(work), done.stdout)
        self.assertIn("cleanup pending", done.stdout)
        self.assertTrue(work.is_dir())

    def test_prior_reports_and_abbreviated_commits_cannot_pass_a_new_attempt(self):
        root, project, _ = self.trial("happy")
        work = root / "project-worktrees/greeting-01-greet-by-name"
        self.assertIn("Verdict: PASS", (work / ".evidence/report.md").read_text())
        agent = root / "stale.py"
        self.env["FACTORY_AGENT"] = f"{sys.executable} {agent}"
        for script in (
            "pass",
            "import os, pathlib, subprocess\n"
            "sha = subprocess.check_output(['git','rev-parse','--short','HEAD'], text=True)\n"
            "pathlib.Path(os.environ['FACTORY_REPORT']).write_text('Verdict: PASS\\nCommit: ' + sha)",
        ):
            agent.write_text(script)
            self.program(project, "run", bench.TICKET, "--stage", "verify")
            self.assertEqual(orchestrator.Ticket(project, bench.TICKET).stage(), "blocked")

    def test_unrelated_blocker_stops_even_when_existing_work_satisfies_the_check(self):
        root, project, _ = self.trial("happy")
        agent = root / "blocked.py"
        agent.write_text("import os, pathlib, sys\n"
                         "assert 'before fixing it' in sys.argv[-1]\n"
                         "pathlib.Path(os.environ['FACTORY_BLOCKER']).write_text('baseline lint failure')\n")
        self.env["FACTORY_AGENT"] = f"{sys.executable} {agent}"
        self.program(project, "run", bench.TICKET, "--stage", "ready")
        status = self.program(project, "status", bench.TICKET).stdout
        self.assertIn("blocked", status)
        self.assertIn("baseline lint failure", status)

    def test_host_ticket_report_survives_deferred_worktree_cleanup(self):
        root, project, _ = self.trial("happy")
        work = root / "project-worktrees/greeting-01-greet-by-name"
        branch = "deliver/greeting-01-greet-by-name"
        ticket = orchestrator.Ticket(work, "#36")
        ticket.update(worktree=str(work), branch=branch)
        (ticket.folder / "report.md").write_text("final report")
        self.program(project, "finish", "#36", "--defer-cleanup", "active chat")
        self.assertIn("active chat", self.program(project, "status", "#36").stdout)
        subprocess.run(["git", "-C", str(project), "worktree", "remove", "--force", str(work)], check=True)
        subprocess.run(["git", "-C", str(project), "branch", "-D", branch], check=True, capture_output=True)
        self.program(project, "finish", "#36")
        self.assertFalse(ticket.state()["cleanup_pending"])
        self.assertEqual((ticket.folder / "report.md").read_text(), "final report")

    def test_preserve_finds_legacy_records_before_linked_checkout_removal(self):
        root, project, _ = self.trial("happy")
        work = root / "project-worktrees/greeting-01-greet-by-name"
        legacy = work / ".factory/36"
        legacy.mkdir(parents=True)
        (legacy / "state.json").write_text(json.dumps(dict(ref="#36", stage="needs-owner", worktree=str(work))))
        archived = self.program(project, "preserve", "#36")
        self.assertEqual(archived.returncode, 0, archived.stderr)
        report = project / ".factory/36/legacy-verification.md"
        self.assertEqual(report.read_text(), (work / ".evidence/report.md").read_text())
        self.assertIn(str(report.parent), self.program(work, "status", "#36").stdout)

    def test_a_task_that_names_the_shared_checks_needs_the_pipeline_to_set_them(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        project = Path(temporary.name)
        (project / "docs/agents").mkdir(parents=True)
        task = '[[task]]\nname = "implement"\nwhen = "ready"\nrun = "go"\ncheck = "true && {checks}"\nthen = "done"\n'
        (project / "docs/agents/pipeline.toml").write_text(task)
        with self.assertRaisesRegex(orchestrator.FactoryError, "sets no `checks`"):
            orchestrator.load_pipeline(project)
        (project / "docs/agents/pipeline.toml").write_text('checks = "make check"\n' + task)
        self.assertEqual("true && ( make check )", orchestrator.load_pipeline(project)[1][0]["check"])

    def test_worker_cannot_move_an_assigned_ticket_to_another_branch(self):
        root = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve() / "trial"
        root.mkdir()
        project, env = bench.prepare(root, "happy")
        mover = root / "mover.py"
        mover.write_text("import os, subprocess, sys\n"
                         "if os.environ['FACTORY_TASK'] == 'implement':\n"
                         "    subprocess.run(['git', 'switch', '-qc', 'integration/greeting'], check=True)\n"
                         f"raise SystemExit(subprocess.run([sys.executable, {str(FACTORY / 'fake_agent.py')!r}, *sys.argv[1:]]).returncode)\n")
        self.env = env | {"FACTORY_AGENT": f"{sys.executable} {mover}"}
        self.assertEqual(self.program(project, "run", bench.TICKET).returncode, 0)
        facts = bench.grade(root, project, "happy")
        self.assertEqual((facts["final_stage"], facts["pr_opened"]), ("blocked", False))
        self.assertIn("changed the assigned branch", self.program(project, "status", bench.TICKET).stdout)
        self.env["FACTORY_AGENT"] = f"{sys.executable} {FACTORY / 'fake_agent.py'}"
        resumed = self.program(project, "run", bench.TICKET)
        self.assertEqual(resumed.returncode, 0, resumed.stderr)
        self.assertEqual(orchestrator.Ticket(project, bench.TICKET).stage(), "needs-owner")

    def test_a_ticket_started_off_the_base_branch_is_led_in_that_checkout(self):
        root = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve() / "trial"
        root.mkdir()
        project, env = bench.prepare(root, "happy")
        self.env = env | {"FACTORY_AGENT": f"{sys.executable} {FACTORY / 'fake_agent.py'}"}
        subprocess.run(["git", "-C", str(project), "switch", "-qc", "mine"], check=True)
        self.assertEqual(self.program(project, "run", bench.TICKET).returncode, 0)
        self.assertEqual(orchestrator.Ticket(project, bench.TICKET).state()["worktree"], str(project))
        self.assertFalse((root / "project-worktrees").exists())

    def test_a_detached_run_can_be_watched_and_stopped_and_keeps_its_stage(self):
        root = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve() / "trial"
        root.mkdir()
        project, env = bench.prepare(root, "happy")
        self.env = env | {"FACTORY_AGENT": f"{sys.executable} -c 'import time; time.sleep(60)'"}
        self.assertIn("Started in the background", self.program(project, "run", bench.TICKET, "--detach").stdout)
        for _ in range(50):
            status = self.program(project, "status", bench.TICKET).stdout
            if "running implement attempt 1" in status:
                break
            time.sleep(0.1)
        self.assertIn("running implement attempt 1", status)
        self.assertIn("already running", self.program(project, "run", bench.TICKET).stderr)
        self.assertIn("Stopped greeting-01-greet-by-name", self.program(project, "stop", bench.TICKET).stdout)
        status = self.program(project, "wait", bench.TICKET).stdout
        self.assertIn("greeting-01-greet-by-name\tready\tnot running\tlast: implement attempt 1 stopped", status)

    def test_the_owners_word_at_the_start_chooses_what_runs_a_task_and_lasts_for_the_ticket(self):
        root = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve() / "trial"
        root.mkdir()
        project, env = bench.prepare(root, "verify-blocked")
        self.env = env | {"FACTORY_AGENT": f"{sys.executable} {FACTORY / 'fake_agent.py'}"}
        self.program(project, "run", bench.TICKET, "--model", "small", "--model", "verify=large", "--effort", "implement=high")
        (root / "project-worktrees/greeting-01-greet-by-name/.verify-env").write_text("ready\n")
        self.program(project, "run", bench.TICKET)  # continuing says nothing new
        rows = [json.loads(line) for line in (project / ".factory/greeting-01-greet-by-name/runs.jsonl").read_text().splitlines()]
        self.assertEqual([(row["task"], row["model"], row["effort"]) for row in rows],
                         [("implement", "small", "high"), ("ci", "small", None), ("verify", "large", None), ("verify", "large", None), ("deliver", "small", None)])
        self.assertIn("No task named review", self.program(project, "run", bench.TICKET, "--model", "review=x").stderr)

    def test_a_tracker_reference_keeps_its_stage_in_the_run_state_and_each_client_spells_the_skill_its_way(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary).resolve()
            ticket = orchestrator.Ticket(project, "#42")
            self.assertEqual((ticket.name, ticket.stage()), ("42", None))
            for feature in ("pay", "auth"):  # ticket numbers restart in every feature
                (project / f".scratch/{feature}/issues").mkdir(parents=True)
                (project / f".scratch/{feature}/issues/01-setup.md").write_text("# Setup\n")
            self.assertEqual([orchestrator.Ticket(project, f".scratch/{feature}/issues/01-setup.md").name for feature in ("pay", "auth")],
                             ["pay-01-setup", "auth-01-setup"])
            orchestrator.Ticket(project, "42").update()
            with self.assertRaises(orchestrator.FactoryError):
                orchestrator.Ticket(project, "#42")
            ticket.set_stage("verify")
            self.assertEqual(orchestrator.Ticket(project, "#42").stage(), "verify")
            self.assertEqual((project / ".factory/.gitignore").read_text(), "*\n")
            self.assertIsNone(orchestrator.run_task({}, [], ticket, 5))
        pipeline = {"agents": {"opencode": {"command": "opencode run -m {model} {prompt}", "skill": "@"}}}
        saved = os.environ.pop("FACTORY_AGENT", None)
        self.addCleanup(lambda: saved and os.environ.update(FACTORY_AGENT=saved))
        self.assertEqual(orchestrator.agent_argv(pipeline, "opencode", "x/y", "/implement 42"), ["opencode", "run", "-m", "x/y", "@implement 42"])
        self.assertEqual(orchestrator.agent_argv(pipeline, "codex", "m", "/deliver")[-1], "$deliver")
        with self.assertRaises(orchestrator.FactoryError):
            orchestrator.agent_argv({}, "unknown", "m", "hello")
        self.assertEqual(orchestrator.agent_argv({}, "codex", "m", "go", "high")[-3:], ["-c", "model_reasoning_effort=high", "go"])
        self.assertEqual(orchestrator.agent_argv({}, "claude", "m", "go", "low")[-2:], ["--effort", "low"])
        for bad in (("opencode", "x/y", "go", "high"), ("codex", None, "go")):  # a client with no effort; no model at all
            with self.assertRaises(orchestrator.FactoryError):
                orchestrator.agent_argv(pipeline, *bad)


if __name__ == "__main__":
    unittest.main()
