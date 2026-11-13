#!/usr/bin/env python3
"""Repository check: skill frontmatter, links in docs, tests (Python 3.9+)."""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LINK = re.compile(r"\]\(([^)]+)\)")


def main() -> int:
    errors = []
    docs = [p for p in (ROOT / "AGENTS.md", ROOT / "README.md") if p.exists()]
    for card in sorted((ROOT / "skills").rglob("SKILL.md")):
        skill = card.parent
        head = card.read_text(encoding="utf-8").split("---", 2)
        if len(head) < 3 or f"\nname: {skill.name}\n" not in head[1] or "\ndescription:" not in head[1]:
            errors.append(f"{card.relative_to(ROOT)}: frontmatter needs name: {skill.name} and description")
        docs += [card, *sorted(skill.glob("references/*.md")), *sorted(skill.glob("*.md")), *sorted(skill.glob("examples/**/*.md"))]
    for doc in dict.fromkeys(docs):
        text = re.sub(r"(`{3,}).*?\1", "", doc.read_text(encoding="utf-8"), flags=re.S)  # links inside code fences are examples
        text = re.sub(r"`[^`\n]+`", "", text)  # and so are links inside inline code
        for target in LINK.findall(text):
            if re.match(r"[a-z]+:", target) or target.startswith("#"):
                continue
            if not (doc.parent / target.split("#", 1)[0]).exists():
                errors.append(f"{doc.relative_to(ROOT)}: broken link {target}")
    pythons = dict.fromkeys(p for p in (sys.executable, "/usr/bin/python3") if Path(p).exists())
    for python in pythons:
        tests = subprocess.run([python, "-m", "unittest", "discover", "-s", str(ROOT / "tests"), "-q"], capture_output=True, text=True)
        if tests.returncode:
            errors.append(f"tests failed ({python}):\n{tests.stderr.strip()}")
    for error in errors:
        print(error, file=sys.stderr)
    print("FAIL" if errors else "OK")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
