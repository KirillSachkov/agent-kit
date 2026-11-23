"""The experimental step runner leads a task through the fixture pipeline with a scripted agent."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

KIT = Path(__file__).resolve().parents[1]
FACTORY = KIT / "experiments/factory"
sys.path.insert(0, str(FACTORY))
import bench  # noqa: E402
import factory  # noqa: E402


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
        run = subprocess.run([sys.executable, str(FACTORY / "factory.py"), "run", "--project", str(project)],
                             env=env, capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        return root, project, bench.grade(root, project, situation)

    def test_every_step_passing_reaches_the_owner_with_an_open_pull_request(self):
        root, project, facts = self.trial("happy")
        self.assertEqual(facts["final_stage"], "needs-owner")
        self.assertTrue(facts["pass"], facts)
        self.assertEqual((facts["sessions"], facts["ci_runs"], facts["merge_attempts"]), (3, [True], 0))
        journal = [json.loads(line) for line in (project / ".factory/logs/01-greet-by-name/steps.jsonl").read_text().splitlines()]
        self.assertEqual([(row["step"], row["attempt"], row["check_exit"]) for row in journal],
                         [("implement", 1, 0), ("verify", 1, 0), ("ship", 1, 0)])
        self.assertEqual(subprocess.check_output(["git", "-C", str(project), "rev-parse", "--abbrev-ref", "HEAD"], text=True).strip(),
                         "task/01-greet-by-name")

    def test_a_blocked_verification_stops_the_chain_before_delivery_without_a_retry(self):
        root, project, facts = self.trial("verify-blocked")
        self.assertEqual((facts["final_stage"], facts["pr_opened"], facts["verdict"]), ("blocked", False, "Verdict: BLOCKED"))
        self.assertTrue(facts["pass"], facts)
        self.assertIn("Blocked at verify: verification verdict: BLOCKED", (project / bench.TASK).read_text())
        self.assertEqual(facts["sessions"], 2)

    def test_a_fixable_ci_failure_is_fixed_and_an_outage_blocks_after_the_allowed_attempts(self):
        root, project, facts = self.trial("ci-fix")
        self.assertEqual((facts["final_stage"], facts["ci_runs"]), ("needs-owner", [False, True]))
        root, project, facts = self.trial("ci-outage")
        self.assertEqual((facts["final_stage"], facts["ci_runs"], facts["sessions"]), ("blocked", [False], 4))

    def test_a_task_in_a_stage_no_step_starts_from_is_left_alone(self):
        with tempfile.TemporaryDirectory() as temporary:
            task = Path(temporary) / "task.md"
            task.write_text("# Task\n\n**Stage:** needs-owner\n")
            self.assertIsNone(factory.run_step(Path(temporary), task, [], "claude", "sonnet", 5))
            factory.set_stage(task, "ready", "note")
            self.assertEqual(factory.stage(task), "ready")


if __name__ == "__main__":
    unittest.main()
