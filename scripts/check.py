#!/usr/bin/env python3
"""Verify the public library, retained histories and synthetic behavioral tests."""
import ast
import hashlib
import json
import re
import subprocess
import sys
import tarfile
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import upstream  # noqa: E402


def git(*args):
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True)


def frontmatter_errors(text):
    """Hold SKILL.md frontmatter to a conservative subset every strict YAML parser reads alike.

    Clients and installers parse it as YAML and skip a skill that fails. Top-level values are
    one line each: plain, quoted, or a block scalar. Nested mappings are indented and unchecked.
    """
    lines = text.splitlines()
    if not lines or lines[0] != "---" or "---" not in lines[1:]:
        return ["no frontmatter block"]
    found = {}
    errors = []
    scalar = None
    for line in lines[1:lines.index("---", 1)]:
        if not line.strip() or line[0] == "#":
            continue
        if line[0] in " \t":
            if scalar:
                errors.append(f"{scalar}: keep the value on one line or use a block scalar")
                scalar = None
            continue
        key, separator, value = line.partition(":")
        value = value.strip()
        if not separator or (value and line[len(key) + 1] != " "):
            errors.append(f"not a key: value line: {line}")
            continue
        if key in found:
            errors.append(f"duplicate key: {key}")
        found[key] = value
        scalar = key if value and value.rstrip("+-") not in ("|", ">") else None
        if value[:1] == '"':
            try:
                json.loads(value)
            except ValueError:
                errors.append(f"{key}: invalid double-quoted value")
        elif value[:1] == "'":
            if len(value) < 2 or not value.endswith("'") or "'" in value[1:-1].replace("''", ""):
                errors.append(f"{key}: invalid single-quoted value")
        elif value and value.rstrip("+-") not in ("|", ">") and (
                ": " in value or " #" in value or value.endswith(":") or value[:1] in "[]{}>|*&!%@`,?-#"):
            errors.append(f"{key}: quote a value containing ': ', ' #' or a leading YAML indicator")
    for key in ("name", "description"):
        if not found.get(key):
            errors.append(f"missing {key}")
    return errors


def claude_human_invoked(skill_md):
    frontmatter = skill_md.split("---", 2)[1] if skill_md.startswith("---") else ""
    return bool(re.search(r"^disable-model-invocation:\s*true\s*$", frontmatter, re.M))


def codex_human_invoked(openai_yaml):
    return bool(re.search(r"^policy:[ \t]*\n(?:[ \t]+.*\n)*?[ \t]+allow_implicit_invocation:\s*false\s*$",
                          openai_yaml, re.M))


def invocation_errors(name, skill_md, openai_yaml, upstream_skill_md=None):
    """A skill is human-invoked in both clients or in neither, and as its upstream original is."""
    errors = []
    if claude_human_invoked(skill_md) != codex_human_invoked(openai_yaml):
        errors.append(f"{name}: invocation flags disagree between Claude Code and Codex")
    if upstream_skill_md is not None and claude_human_invoked(skill_md) != claude_human_invoked(upstream_skill_md):
        errors.append(f"{name}: invocation differs from the pristine upstream skill")
    return errors


def upstream_skill_files():
    """Map local skill names to the pristine SKILL.md text of the Matt and pstack baselines."""
    base = ROOT / "provenance/upstream"
    renames = upstream.local_names(ROOT)
    result = {}
    for archive_path in (base / "mattpocock/skills.tar.gz", base / "pstack/create-verification-skill.tar.gz"):
        with tarfile.open(archive_path) as archive:
            for member in archive.getmembers():
                parts = Path(member.name).parts
                if member.isfile() and len(parts) >= 3 and parts[-1] == "SKILL.md":
                    result[renames.get(parts[-2], parts[-2])] = archive.extractfile(member).read().decode()
    return result


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
    pristine = upstream_skill_files()
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
        text = skill.read_text()
        metadata = text.split("---", 2)
        errors.extend(f"{skill.relative_to(ROOT)}: {error}" for error in frontmatter_errors(text))
        policy = source / "agents/openai.yaml"
        errors.extend(invocation_errors(item["skill"], text, policy.read_text() if policy.is_file() else "",
                                        pristine.get(item["skill"])))
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
    actual = {p.parent.relative_to(ROOT) for p in (ROOT / "skills/engineering").glob("*/SKILL.md")}
    if actual != found:
        errors.append("canonical catalog coverage mismatch")
    alias = ROOT / ".claude/skills"
    if not alias.is_symlink() or alias.resolve() != (ROOT / ".agents/skills").resolve():
        errors.append("Claude discovery must share the canonical index")
    pstack = ROOT / "provenance/upstream/pstack"
    recorded = dict(line.split(": ", 1) for line in (pstack / "SOURCE").read_text().splitlines())
    archive = hashlib.sha256((pstack / "create-verification-skill.tar.gz").read_bytes()).hexdigest()
    if recorded.get("sha256") != archive or not re.fullmatch(r"[0-9a-f]{40}", recorded.get("revision", "")):
        errors.append("pstack baseline does not match its SOURCE record")
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
    docs = [ROOT / name for name in ("README.md", "README.en.md", "AGENTS.md", "CODING_STANDARDS.md", "skills/README.md", "provenance/engineering/README.md")]
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
