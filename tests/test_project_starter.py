"""Exercise the starter on a disposable repository using the public installer."""

from pathlib import Path
import os
import subprocess
import sys
import tempfile
import unittest


KIT = Path(__file__).resolve().parents[1]
SKILLS = (
    "implement", "implement-spec", "code-review", "tdd", "ship", "pr", "recap",
    "diagnosing-bugs", "to-spec", "to-tickets", "setup-harness",
)


class ProjectStarterTest(unittest.TestCase):
    def setUp(self):
        local_git_vars = subprocess.check_output(["git", "rev-parse", "--local-env-vars"], text=True)
        self.fixture_env = os.environ.copy()
        for variable in local_git_vars.splitlines():
            self.fixture_env.pop(variable, None)
        self.fixture_env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")

    def run_command(self, args, cwd, *, status=0):
        result = subprocess.run(args, cwd=cwd, env=self.fixture_env, capture_output=True, text=True)
        self.assertEqual(result.returncode, status, result.stdout + result.stderr)
        return result.stdout.strip()

    def git(self, path, *args):
        return self.run_command([
            "git", "-c", "user.name=Starter exercise", "-c", "user.email=exercise@example.invalid",
            "-c", f"core.hooksPath={os.devnull}", "-c", "commit.gpgSign=false", *args,
        ], path)

    def check_status_command(self, path, source, *, status, message):
        self.assertEqual(
            self.run_command([sys.executable, "status.py", source], path, status=status), message,
        )

    def test_install_and_run_a_task_through_worktree_retirement(self):
        with tempfile.TemporaryDirectory(prefix="agent-kit-starter-") as temporary:
            root = Path(temporary)
            project = root / "project with spaces"
            project.mkdir()
            self.git(project, "init", "-q", "-b", "main", "--template=")
            ref = self.git(KIT, "rev-parse", "HEAD")
            starter = self.git(KIT, "show", f"{ref}:templates/project/AGENTS.md") + "\n"
            with (project / "AGENTS.md").open("x", encoding="utf-8") as instructions:
                instructions.write(starter)

            install = [sys.executable, str(KIT / "tools/skills.py")]
            selection = [argument for skill in SKILLS for argument in ("--skill", skill)]
            self.run_command([
                *install, "select", "--project", str(project), "--ref", ref,
                "--client", "both", *selection, "--apply",
            ], KIT)
            self.run_command([*install, "preview", "--project", str(project)], KIT)
            self.assertFalse((project / ".agents/skills").exists())
            self.run_command([*install, "install", "--project", str(project)], KIT)
            self.run_command([*install, "check", "--project", str(project)], KIT)
            self.assertEqual((project / "AGENTS.md").read_text(encoding="utf-8"), starter)
            self.assertIn("Owner attention: disabled.", starter)
            self.assertFalse((project / ".agents/skills/owner-attention").exists())
            for name in ("implement", "implement-spec", "setup-harness"):
                installed = project / ".agents/skills" / name
                self.assertIn("disable-model-invocation: true", (installed / "SKILL.md").read_text())
                self.assertIn("allow_implicit_invocation: false", (installed / "agents/openai.yaml").read_text())
            self.assertEqual(
                (project / ".claude/skills").resolve(), (project / ".agents/skills").resolve(),
            )
            self.assertEqual(
                (project / ".agents/skills/implement/VERIFICATION.md").read_text(),
                self.git(KIT, "show", f"{ref}:skills/engineering/implement/VERIFICATION.md") + "\n",
            )

            (project / "status.py").write_text('print("ready")\n', encoding="utf-8")
            (project / "input.txt").write_text("fixture\n", encoding="utf-8")
            self.git(project, "add", ".")
            self.git(project, "commit", "-qm", "Start fixture project")
            self.check_status_command(project, "missing.txt", status=0, message="ready")

            task = root / "task"
            self.git(project, "worktree", "add", "-qb", "task/missing-input", str(task))
            (task / "status.py").write_text(
                'from pathlib import Path\nimport sys\n\n'
                'if not Path(sys.argv[1]).is_file():\n'
                '    print("Input file is missing.")\n'
                '    raise SystemExit(2)\n'
                'print("ready")\n',
                encoding="utf-8",
            )
            self.git(task, "add", "status.py")
            self.git(task, "commit", "-qm", "Report missing input")
            checked_head = self.git(task, "rev-parse", "HEAD")

            verification = root / "verify"
            self.git(project, "worktree", "add", "-q", "--detach", str(verification), checked_head)
            self.check_status_command(verification, "missing.txt", status=2, message="Input file is missing.")
            self.check_status_command(verification, "input.txt", status=0, message="ready")
            self.git(project, "worktree", "remove", str(verification))

            self.git(project, "merge", "--ff-only", checked_head)
            self.assertEqual(self.git(project, "rev-parse", "HEAD"), checked_head)
            self.git(project, "worktree", "remove", str(task))
            self.git(project, "branch", "-d", "task/missing-input")
            self.assertFalse(task.exists())
            self.assertFalse(verification.exists())
            self.assertEqual(self.git(project, "status", "--porcelain"), "")
            self.check_status_command(project, "missing.txt", status=2, message="Input file is missing.")

    def test_installation_invocation_can_switch_both_clients_without_editing_project_rules(self):
        with tempfile.TemporaryDirectory(prefix="agent-kit-invocation-") as temporary:
            project = Path(temporary)
            rules = project / "AGENTS.md"
            instructions = "Existing project rules.\n"
            rules.write_text(instructions)
            cli = [sys.executable, str(KIT / "tools/skills.py")]
            target = ["--project", str(project)]
            ref = self.git(KIT, "rev-parse", "HEAD")
            select = [
                *cli, "select", *target, "--ref", ref, "--client", "both",
                "--skill", "implement", "--skill", "implement-spec", "--apply",
            ]

            for invocation in ("implicit", "manual"):
                with self.subTest(invocation=invocation):
                    self.run_command([*select, "--implementation-invocation", invocation], KIT)
                    self.run_command(select, KIT)
                    preview = self.run_command([*cli, "preview", *target], KIT)
                    self.assertIn(f"allow_implicit_invocation: {'true' if invocation == 'implicit' else 'false'}", preview)
                    self.run_command([*cli, "install", *target], KIT)
                    self.run_command([*cli, "check", *target], KIT)
                    for name in ("implement", "implement-spec"):
                        claude_skill = project / ".claude/skills" / name / "SKILL.md"
                        codex_policy = project / ".agents/skills" / name / "agents/openai.yaml"
                        self.assertEqual(
                            "disable-model-invocation: true" in claude_skill.read_text(), invocation == "manual",
                        )
                        self.assertIn(
                            f"allow_implicit_invocation: {'false' if invocation == 'manual' else 'true'}",
                            codex_policy.read_text(),
                        )
                    self.assertEqual(rules.read_text(), instructions)


if __name__ == "__main__":
    unittest.main()
