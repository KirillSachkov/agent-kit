"""The experimental step runner leads a task through the fixture pipeline with a scripted agent."""
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
from bench import factory  # noqa: E402


class StepRunnerTest(unittest.TestCase):
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
        bench.execute(project, env, "steps-direct", "claude", "sonnet", 60, bench.work(situation), situation)
        return root, project, bench.grade(root, project, situation)

    def program(self, project, *args):
        return subprocess.run([sys.executable, str(project / ".agents/skills/deliver/factory.py"), *args, "--project", str(project)],
                              env=self.env, capture_output=True, text=True)

    def test_every_step_passing_reaches_the_owner_with_an_open_pull_request(self):
        root, project, facts = self.trial("happy")
        self.assertEqual(facts["final_stage"], "needs-owner")
        self.assertTrue(facts["pass"], facts)
        self.assertEqual((facts["sessions"], facts["ci_runs"], facts["merge_attempts"], facts["outside"]), (4, [True], 0, []))
        journal = [json.loads(line) for line in (project / ".factory/01-greet-by-name/steps.jsonl").read_text().splitlines()]
        self.assertEqual([(row["step"], row["attempt"], row["check_exit"]) for row in journal],
                         [("implement", 1, 0), ("verify", 1, 0), ("ship", 1, 0)])

    def test_the_work_happens_in_a_worktree_of_its_own_and_the_project_stays_on_its_branch(self):
        root, project, facts = self.trial("happy")
        self.assertEqual((facts["own_worktree"], facts["branch"]), (True, "task/01-greet-by-name"))
        self.assertTrue((root / "project-worktrees/01-greet-by-name/greet.py").is_file())
        self.assertEqual(subprocess.check_output(["git", "-C", str(project), "branch", "--show-current"], text=True).strip(), "main")
        status = self.program(project, "status").stdout
        self.assertIn("01-greet-by-name\tneeds-owner\tnot running\tlast: ship attempt 1 passed", status)

    def test_a_blocked_verification_stops_the_chain_before_delivery_without_a_retry(self):
        root, project, facts = self.trial("verify-blocked")
        self.assertEqual((facts["final_stage"], facts["pr_opened"], facts["verdict"]), ("blocked", False, "Verdict: BLOCKED"))
        self.assertTrue(facts["pass"], facts)
        self.assertIn("Blocked at verify: verification verdict: BLOCKED", (project / bench.TICKET).read_text())
        self.assertEqual(facts["sessions"], 3)

    def test_a_blocked_task_continues_from_the_step_that_blocked_it(self):
        root, project, facts = self.trial("verify-blocked")
        (root / "project-worktrees/01-greet-by-name/.verify-env").write_text("ready\n")
        self.assertEqual(self.program(project, "run", bench.TICKET).returncode, 0)
        facts = bench.grade(root, project, "happy")
        self.assertEqual((facts["final_stage"], facts["pr_opened"]), ("needs-owner", True))
        journal = [json.loads(line)["step"] for line in (project / ".factory/01-greet-by-name/steps.jsonl").read_text().splitlines()]
        self.assertEqual(journal, ["implement", "verify", "verify", "ship"])

    def test_a_fixable_ci_failure_is_fixed_and_an_outage_blocks_after_the_allowed_attempts(self):
        root, project, facts = self.trial("ci-fix")
        self.assertEqual((facts["final_stage"], facts["ci_runs"]), ("needs-owner", [False, True]))
        root, project, facts = self.trial("ci-outage")
        self.assertEqual((facts["final_stage"], facts["ci_runs"], facts["sessions"]), ("blocked", [False], 5))

    def test_the_owners_feedback_on_the_pull_request_takes_the_work_through_the_chain_again(self):
        root, project, facts = self.trial("rework")
        self.assertTrue(facts["pass"], facts)
        journal = [json.loads(line)["step"] for line in (project / ".factory/01-greet-by-name/steps.jsonl").read_text().splitlines()]
        self.assertEqual(journal, ["implement", "verify", "ship", "rework", "verify", "ship"])

    def test_later_steps_follow_the_branch_the_implementing_skill_moved_the_work_to(self):
        root = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve() / "trial"
        root.mkdir()
        project, env = bench.prepare(root, "happy")
        mover = root / "mover.py"
        mover.write_text("import os, subprocess, sys\n"
                         "if os.environ['FACTORY_STEP'] == 'implement':\n"
                         "    subprocess.run(['git', 'switch', '-qc', 'integration/greeting'], check=True)\n"
                         f"raise SystemExit(subprocess.run([sys.executable, {str(FACTORY / 'fake_agent.py')!r}, *sys.argv[1:]]).returncode)\n")
        self.env = env | {"FACTORY_AGENT": f"{sys.executable} {mover}"}
        self.assertEqual(self.program(project, "run", bench.TICKET).returncode, 0)
        facts = bench.grade(root, project, "happy")
        self.assertEqual((facts["final_stage"], facts["branch"]), ("needs-owner", "integration/greeting"))
        self.assertEqual(json.loads((root / "gh-state.json").read_text())["prs"][0]["head"], "integration/greeting")

    def test_a_run_started_off_the_base_branch_works_in_that_checkout(self):
        root = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve() / "trial"
        root.mkdir()
        project, self.env = bench.prepare(root, "happy")
        subprocess.run(["git", "-C", str(project), "switch", "-qc", "mine"], check=True)
        self.assertEqual(self.program(project, "place", bench.TICKET).stdout.strip(), str(project))

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
        self.assertIn("Stopped 01-greet-by-name", self.program(project, "stop", bench.TICKET).stdout)
        status = self.program(project, "wait", bench.TICKET).stdout
        self.assertIn("01-greet-by-name\tready\tnot running\tlast: implement attempt 1 stopped", status)

    def test_a_tracker_reference_keeps_its_stage_in_the_run_state_and_each_client_spells_the_skill_its_way(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary).resolve()
            task = factory.Task(project, "#42")
            self.assertEqual((task.name, task.stage()), ("42", None))
            task.set_stage("verify")
            self.assertEqual(factory.Task(project, "#42").stage(), "verify")
            self.assertEqual((project / ".factory/.gitignore").read_text(), "*\n")
            self.assertIsNone(factory.run_step({}, [], task, 5))
        pipeline = {"agents": {"opencode": {"command": "opencode run -m {model} {prompt}", "skill": "@"}}}
        saved = os.environ.pop("FACTORY_AGENT", None)
        self.addCleanup(lambda: saved and os.environ.update(FACTORY_AGENT=saved))
        self.assertEqual(factory.agent_argv(pipeline, "opencode", "x/y", "/implement 42"), ["opencode", "run", "-m", "x/y", "@implement 42"])
        self.assertEqual(factory.agent_argv(pipeline, "codex", "m", "/ship")[-1], "$ship")
        with self.assertRaises(factory.FactoryError):
            factory.agent_argv({}, "unknown", "m", "hello")


if __name__ == "__main__":
    unittest.main()
