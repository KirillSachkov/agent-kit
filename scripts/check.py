#!/usr/bin/env python3
"""Verify the public library, retained histories and synthetic behavioral tests."""
import ast
import json
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]


def git(*args):
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True)


def check_structure():
    errors = []
    catalog = json.loads((ROOT / "skills/catalog.json").read_text())
    items = catalog["skills"]
    names = [item["skill"] for item in items]
    if len(names) != len(set(names)):
        errors.append("duplicate skill names")
    if set(catalog["providers"]) != {"agent-kit"}:
        errors.append("public catalog must have one provider")
    found = set()
    for item in items:
        source = ROOT / "skills" / item["source"]
        if source.is_symlink() or not source.resolve().is_relative_to((ROOT / "skills").resolve()):
            errors.append(f"unsafe canonical source: {source}")
            continue
        skill = source / "SKILL.md"
        if not skill.is_file():
            errors.append(f"missing skill: {source}")
            continue
        found.add(source.relative_to(ROOT))
        metadata = skill.read_text().split("---", 2)
        if len(metadata) != 3 or not re.search(r"^name:\s*" + re.escape(item["skill"]) + r"\s*$", metadata[1], re.M):
            errors.append(f"invalid skill frontmatter: {skill}")
        internal = len(metadata) == 3 and "internal: true" in metadata[1]
        if bool(item.get("internal")) != internal:
            errors.append(f"internal status mismatch: {skill}")
        if not internal:
            runtime = ROOT / ".agents/skills" / item["skill"]
            if not runtime.is_symlink() or runtime.resolve() != source.resolve():
                errors.append(f"canonical discovery mismatch: {item['skill']}")
        for path in source.rglob("*"):
            if path.is_symlink():
                errors.append(f"symlink inside distributable folder: {path}")
    actual = {p.parent.relative_to(ROOT) for group in ("engineering", "communication") for p in (ROOT / "skills" / group).glob("*/SKILL.md")}
    if actual != found:
        errors.append("canonical catalog coverage mismatch")
    alias = ROOT / ".claude/skills"
    if not alias.is_symlink() or alias.resolve() != (ROOT / ".agents/skills").resolve():
        errors.append("Claude discovery must share the canonical index")
    sources = json.loads((ROOT / "provenance/sources.json").read_text())
    for source in sources["sources"]:
        if git("merge-base", "--is-ancestor", source["main"], "HEAD").returncode:
            errors.append(f"original main history missing: {source['repository']}")
        for reference in source["preserved_refs"]:
            if git("cat-file", "-e", reference["sha"] + "^{commit}").returncode:
                errors.append(f"original branch history missing: {reference['ref']}")
                continue
            candidates = [reference["ref"], reference["ref"].replace("refs/heads/", "refs/remotes/origin/", 1)]
            if not any(git("rev-parse", "--verify", candidate).stdout.strip() == reference["sha"] for candidate in candidates):
                errors.append(f"retained branch ref missing: {reference['ref']}")
    docs = [ROOT / name for name in ("README.md", "README.en.md", "AGENTS.md", "CODING_STANDARDS.md", "skills/README.md")]
    docs.extend((ROOT / "docs").glob("*.md"))
    for doc in docs:
        if not doc.is_file():
            errors.append(f"missing entrypoint: {doc}")
            continue
        for link in re.findall(r"\[[^\]]*\]\(([^)]+)\)", doc.read_text()):
            link = link.strip("<>").split("#", 1)[0]
            if not link or urlsplit(link).scheme or link.startswith(("/", "~")):
                continue
            if not (doc.parent / unquote(link)).exists():
                errors.append(f"broken navigation: {doc.relative_to(ROOT)} -> {link}")
    for folder in ("tools", "scripts"):
        for path in (ROOT / folder).rglob("*.py"):
            try:
                ast.parse(path.read_text(), filename=str(path))
            except SyntaxError as error:
                errors.append(str(error))
    return errors


def main():
    errors = check_structure()
    if errors:
        print("\n".join(errors))
        return 1
    commands = [
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"],
        [sys.executable, "examples/agent-harness/scripts/check.py"],
        [sys.executable, "maintenance/communication/scripts/check.py"],
    ]
    for command in commands:
        print("CHECK " + " ".join(command[1:]), flush=True)
        result = subprocess.run(command, cwd=ROOT)
        if result.returncode:
            return result.returncode
    print("OK public catalog, histories, canonical discovery and behavioral checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
