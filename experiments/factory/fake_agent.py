#!/usr/bin/env python3
"""A scripted stand-in for an agent session, used to test the step runner without a model."""
import os
from pathlib import Path
import subprocess
import sys

step = os.environ.get("FACTORY_STEP")


def run(*argv, check=True):
    return subprocess.run(argv, capture_output=True, text=True, check=check)


if step == "implement":
    Path("greet.py").write_text('import sys\n\nif len(sys.argv) != 2:\n    print("Name required", file=sys.stderr)\n    raise SystemExit(2)\nprint(f"Hello, {sys.argv[1]}!")\n')
    Path("tests/test_greet.py").write_text('import subprocess, sys, unittest\n\n\nclass GreetTest(unittest.TestCase):\n    def test_greets(self):\n        done = subprocess.run([sys.executable, "greet.py", "Ada"], capture_output=True, text=True)\n        self.assertEqual((done.returncode, done.stdout.strip()), (0, "Hello, Ada!"))\n')
    run("git", "add", "greet.py", "tests")
    run("git", "commit", "-qm", "Greet by name")
    print('{"item":{"type":"command_execution","command":"cat .agents/skills/tdd/SKILL.md .agents/skills/code-review/SKILL.md"}}')
elif step == "verify":
    Path(".evidence").mkdir(exist_ok=True)
    verdict = "PASS" if Path(".verify-env").exists() else "BLOCKED"
    Path(".evidence/report.md").write_text(f"Verdict: {verdict}\nCommit: test\n")
    print('{"item":{"type":"command_execution","command":"cat .agents/skills/verify-greet/SKILL.md"}}')
elif step == "ship":
    run("git", "push", "-q", "-u", "origin", "HEAD")
    run("gh", "pr", "create", "--title", "Greet by name", "--body", "## What changed\n\nGreets by name.", check=False)
    if run("gh", "pr", "checks", "--required", check=False).returncode and "usage line" in run("gh", "run", "view", "--log-failed").stdout:
        readme = Path("README.md")
        readme.write_text(readme.read_text() + "\nUsage: `python3 greet.py <name>`\n")
        run("git", "commit", "-qam", "Document the usage line")
        run("git", "push", "-q")
elif step == "rework":
    assert "Trim the name" in run("gh", "pr", "view", "--json", "comments").stdout
    greet = Path("greet.py")
    greet.write_text(greet.read_text().replace("{sys.argv[1]}", "{sys.argv[1].strip()}"))
    run("git", "commit", "-qam", "Trim the name")
    print('{"item":{"type":"command_execution","command":"cat .agents/skills/code-review/SKILL.md"}}')
else:
    sys.exit(f"fake agent: no script for step {step}")
