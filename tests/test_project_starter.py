"""Exercise the starter on a disposable repository using the public installer."""

from pathlib import Path
import os
import subprocess
import sys
import tempfile
import unittest


KIT = Path(__file__).resolve().parents[1]


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
            setup = [sys.executable, str(KIT / "tools/setup.py"), "--project", str(project),
                     "--ref", ref, "--client", "both"]
            self.run_command(setup, KIT)
            self.assertFalse((project / "AGENTS.md").exists())
            self.assertFalse((project / ".agents/skills").exists())
            self.run_command([*setup, "--apply"], KIT)
            self.run_command([sys.executable, str(KIT / "tools/skills.py"), "check",
                              "--project", str(project)], KIT)
            self.assertIn("No changes.", self.run_command(setup, KIT))
            self.assertIn("docs/agents/project-settings.md", (project / "AGENTS.md").read_text())
            self.assertEqual(
                (project / ".claude/skills").resolve(), (project / ".agents/skills").resolve(),
            )
            self.assertEqual(
                (project / ".agents/skills/create-verification-skill/SKILL.md").read_text(),
                self.git(KIT, "show", f"{ref}:skills/engineering/create-verification-skill/SKILL.md") + "\n",
            )
            self.assertFalse((project / "evidence-manifest.json").exists())
            instructions = (project / "AGENTS.md").read_text()
            for name in ("to-spec", "to-tickets", "implement", "implement-spec"):
                self.assertRegex(instructions, r"Human-invoked skills: [^.]*`" + name + "`")
            self.assertNotRegex(instructions, r"Human-invoked skills: [^.]*`(code-review|tdd|ship)`")

            for skill in ("grill-me", "to-spec", "to-tickets", "implement", "implement-spec",
                          "create-verification-skill"):
                installed = project / ".agents/skills" / skill
                frontmatter = (installed / "SKILL.md").read_text().split("---", 2)[1]
                self.assertIn("disable-model-invocation: true", frontmatter.splitlines())
                policy = (installed / "agents/openai.yaml").read_text().splitlines()
                self.assertIn("  allow_implicit_invocation: false", policy)

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


if __name__ == "__main__":
    unittest.main()
