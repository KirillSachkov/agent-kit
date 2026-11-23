#!/usr/bin/env python3
"""Preview or install the pinned Agent Kit skills and root instructions in a project directory.

Project decisions belong to the setup skill, which runs inside the project.
"""
import argparse
from contextlib import contextmanager, redirect_stdout
from dataclasses import dataclass
import difflib
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile

import skills


KIT = Path(__file__).resolve().parents[1]
LOCK = ".agents/setup-lock.json"
MANIFEST = ".agents/skills-manifest.json"
# The setup skill writes and maintains these; an earlier starter installed them.
HANDED_OVER = ("docs/agents/project-settings.md",)
# The starter's templates and this tool change together; another starter needs its own tool.
STARTER_VERSION = 3
BEGIN = "<!-- agent-kit project instructions -->"
END = "<!-- end agent-kit project instructions -->"
ERROR = skills.SkillsError


def encoded(value):
    return (json.dumps(value, indent=2) + "\n").encode()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read_optional(project, name):
    path = skills.safe_path(project, name)
    if not path.exists():
        return None
    if not path.is_file():
        raise ERROR(f"Expected a regular file: {name}")
    return path.read_bytes()


def pinned_templates(ref):
    if not re.fullmatch(r"[0-9a-f]{40}", ref):
        raise ERROR("--ref must be a full lowercase commit SHA")
    prefix = "templates/project/"
    result = {}
    for row in skills.git(KIT, "ls-tree", "-rz", ref, "--", prefix).split(b"\0"):
        if not row:
            continue
        header, path = row.split(b"\t", 1)
        mode, kind, oid = header.decode().split()
        name = path.decode().removeprefix(prefix)
        if mode != "100644" or kind != "blob" or any(p.lower() == ".git" for p in Path(name).parts):
            raise ERROR(f"Unsupported project template: {name}")
        result[name] = skills.git(KIT, "cat-file", "blob", oid)
    if "AGENTS.md" not in result:
        raise ERROR(f"No project starter at {ref}")
    return result


def render(raw, settings):
    def replace(match):
        return str(settings[match[1]])
    return re.sub(r"@@([a-z_]+)@@", replace, raw.decode()).encode()


def root_documents(project):
    """Support the common root alias while refusing to follow other managed symlinks."""
    documents = {}
    for name, other in (("AGENTS.md", "CLAUDE.md"), ("CLAUDE.md", "AGENTS.md")):
        path = project / name
        if path.is_symlink():
            if path.resolve() != project / other or not (project / other).is_file():
                raise ERROR(f"Unsupported project instruction link: {name}")
            continue
        data = read_optional(project, name)
        if data is not None:
            documents[name] = data
    return documents


def root_parts(data):
    text = data.decode()
    if BEGIN not in text and END not in text:
        return text, ""
    if text.count(BEGIN) != 1 or text.count(END) != 1:
        raise ERROR("Conflicting Agent Kit instruction markers")
    first, block = text.split(BEGIN)
    managed, rest = block.split(END)
    if rest.strip():
        return first + rest, BEGIN + managed + END
    return first, BEGIN + managed + END


def instruction_owner(project, docs, previous, choice):
    # root_documents validated every root symlink. Canonicalize before checking delegation.
    if choice:
        choice = (project / choice).resolve().name
    if previous:
        previous = (project / previous).resolve().name
    delegates = {}
    for name, raw in docs.items():
        other = "CLAUDE.md" if name == "AGENTS.md" else "AGENTS.md"
        outside, _ = root_parts(raw)
        if re.search(r"(?:@|\b(?:read|see|follow|import|use|смотри|см\.|читай)\s+.{0,60})"
                     + re.escape(other) + r"\b", outside, re.I):
            delegates[name] = other
    if len(delegates) == 2:
        raise ERROR("Instruction cycle between AGENTS.md and CLAUDE.md; reconcile their project-owned pointers")
    if any((project / target).is_symlink() for target in delegates.values()):
        raise ERROR("Instruction cycle through the root instruction alias; reconcile its project-owned pointer")
    if delegates:
        owner = next(iter(delegates.values()))
        if choice and choice != owner:
            raise ERROR(f"Existing root instructions delegate to {owner}; reconcile the pointer before changing its owner")
    elif choice or previous:
        owner = choice or previous
    elif len(docs) > 1:
        raise ERROR("AGENTS.md and CLAUDE.md both contain project instructions. "
                    "Choose the owner with --instruction-owner.")
    else:
        owner = next(iter(docs), "AGENTS.md")
    return owner, delegates


@dataclass
class Edit:
    name: str
    before: bytes | None
    after: bytes | None  # None removes the file


@dataclass
class SetupPlan:
    edits: list
    items: list
    changed: list
    skill_lock: dict
    link: tuple | None
    notes: list

    def needs_link(self):
        return self.link and not self.link[1].is_symlink()


def build_plan(project, ref, client, owner_choice):
    templates = pinned_templates(ref)
    starter = json.loads(templates.pop("starter.json", b"{}")).get("starter_version", 1)
    if starter != STARTER_VERSION:
        raise ERROR(f"The starter at {ref} is version {starter}; this tool installs version {STARTER_VERSION}. "
                    f"Run the tool of that revision: git -C {KIT} show {ref}:tools/setup.py")
    if "WORKFLOW.md" not in templates:
        raise ERROR(f"Missing pinned workflow template at {ref}")
    old_state = read_optional(project, LOCK)
    state = json.loads(old_state) if old_state else {}
    if old_state is not None and (state.get("schema_version") != 1 or not isinstance(state.get("files"), dict)):
        raise ERROR(f"Invalid setup lock: {LOCK}")
    notes = []
    if state.get("decisions"):
        notes.append("Decisions an earlier release recorded now live in docs/agents/project-settings.md; "
                     "run the setup-agent-kit skill to bring that file to its current form")
    edits = []
    managed = dict(state.get("files", {}))
    def add(name, before, after):
        skills.safe_path(project, name)
        if before != after:
            edits.append(Edit(name, before, after))
    docs = root_documents(project)
    roots = dict(state.get("roots", {}))
    canonical, delegates = instruction_owner(project, docs, state.get("instruction_owner"), owner_choice)
    catalog_dir = KIT / "skills"
    catalog = skills.read_json(catalog_dir / "catalog.json")
    manifest = skills.select_manifest(project, catalog, catalog_dir, "agent-kit", ref, None, client)
    items, skill_lock, _ = skills.plan(project, catalog, catalog_dir, manifest=manifest)
    changed = skills.preflight_changed(project, items, skill_lock)
    link = skills.client_discovery(project, manifest)
    manual = [entry["skill"] for entry, _, _, files in items
              if re.search(rb"\A---\n(?:.*\n)*?disable-model-invocation:\s*true\s*\n(?:.*\n)*?---", files["SKILL.md"][0])]
    details = {"human_invoked": ", ".join(f"`{name}`" for name in manual) or "none"}
    root_template = render(templates.pop("AGENTS.md"), details).decode().rstrip()
    requested_roots = {canonical, "AGENTS.md"}
    if "claude" in manifest.get("clients", []) or "CLAUDE.md" in docs:
        requested_roots.add("CLAUDE.md")
    for name in sorted(requested_roots):
        if (project / name).is_symlink() or (name in delegates and name not in roots):
            continue
        before = docs.get(name)
        outside, old_block = root_parts(before or b"")
        if roots.get(name) != (sha(old_block.encode()) if old_block else None):
            raise ERROR(f"Reconcile edited Agent Kit instruction block in {name}")
        snippet = root_template if name == canonical else f"Read [{canonical}]({canonical}) for the project workflow and settings."
        block = f"{BEGIN}\n{snippet}\n{END}"
        if old_block:
            after = before.decode().replace(old_block, block).encode()
        else:
            separator = "" if not outside or outside.endswith("\n\n") else "\n" if outside.endswith("\n") else "\n\n"
            after = (outside + separator + block + "\n").encode()
        add(name, before, after)
        roots[name] = sha(block.encode())
    for name, raw in sorted(templates.items()):
        before = read_optional(project, name)
        after = render(raw, details)
        if name not in managed and before is not None:
            raise ERROR(f"Unmanaged project document already exists: {name}")
        if name in managed and (before is None or sha(before) != managed[name]):
            raise ERROR(f"Reconcile locally changed starter document: {name}")
        add(name, before, after)
        managed[name] = sha(after)
    for name in sorted(set(managed) - set(templates)):
        current = read_optional(project, name)
        if name in HANDED_OVER:
            if current is not None:
                notes.append(f"{name}: now the project's own file; the setup-agent-kit skill maintains it")
        elif current is not None and sha(current) == managed[name]:
            edits.append(Edit(name, current, None))
            notes.append(f"{name}: no longer part of the starter; removed, as the project never edited it")
        elif current is not None:
            notes.append(f"{name}: no longer part of the starter; the project edited it, so it stays")
        del managed[name]
    add(MANIFEST, read_optional(project, MANIFEST), encoded(manifest))
    state = dict(schema_version=1, ref=ref, roots=roots, instruction_owner=canonical, files=managed)
    add(LOCK, old_state, encoded(state))
    return SetupPlan(edits, items, changed, skill_lock, link, notes)


@contextmanager
def write_documents(project, edits):
    applied = []
    created_dirs = []
    with tempfile.TemporaryDirectory(prefix=".setup-stage-", dir=project / ".agents") as temporary:
        stage = Path(temporary)
        try:
            for i, edit in enumerate(edits):
                target = skills.safe_path(project, edit.name)
                if read_optional(project, edit.name) != edit.before:
                    raise ERROR(f"Project document changed during setup: {edit.name}")
                staged = stage / f"{i}.new"
                if edit.after is not None:
                    staged.write_bytes(edit.after)
                if edit.before is not None:
                    if edit.after is not None:
                        staged.chmod(stat.S_IMODE(target.stat().st_mode))
                    backup = stage / f"{i}.old"
                    os.link(target, backup)
            for i, edit in enumerate(edits):
                target = skills.safe_path(project, edit.name)
                missing = []
                for parent in target.parents:
                    if parent.exists():
                        break
                    missing.append(parent)
                for directory in reversed(missing):
                    directory.mkdir()
                    created_dirs.append(directory)
                applied.append((target, stage / f"{i}.old"))
                if edit.after is None:
                    target.unlink()
                else:
                    os.replace(stage / f"{i}.new", target)
            yield
        except BaseException:
            for target, backup in reversed(applied):
                if backup.exists():
                    os.replace(backup, target)
                else:
                    target.unlink(missing_ok=True)
            for directory in reversed(created_dirs):
                directory.rmdir()
            raise


def describe(result, project, ref, *, full):
    for note in result.notes:
        print(note)
    print("Selected skills and activation conditions:")
    for entry, _, _, files in result.items:
        print(f"  {entry['skill']}: " + skills.skill_description(files["SKILL.md"][0]))
    for edit in result.edits:
        print("".join(difflib.unified_diff((edit.before or b"").decode().splitlines(True),
                                          (edit.after or b"").decode().splitlines(True),
                                          fromfile="current/" + edit.name, tofile="selected/" + edit.name)), end="")
    for entry, _, _, _ in result.items:
        if entry["ref"] != ref:
            print(f"{entry['destination']}: not in this release, stays installed at {entry['ref']}")
    if result.changed and not full:
        for entry, _, current, wanted in result.changed:
            count = sum(current.get(name) != wanted.get(name) for name in current.keys() | wanted.keys())
            change = ("new" if not current else "pin only" if not count
                      else f"{count} changed file{'s' if count > 1 else ''}")
            print(f"{entry['destination']}: {entry['provider']}@{entry['ref']} / {entry['skill']}, "
                  f"sha256 {skills.digest(wanted)[:12]}, {change}")
        print("Pass --full for the complete skill file differences.")
    elif result.changed:
        skills.preview(result.changed)
        lock = result.skill_lock
        updated_lock = {**lock, "skills": dict(lock["skills"])}
        for entry, _, _, files in result.items:
            updated_lock["skills"][entry["destination"]] = {**entry, "sha256": skills.digest(files)}
        before = read_optional(project, ".agents/skills-lock.json") or b""
        print("".join(difflib.unified_diff(before.decode().splitlines(True),
                                          encoded(updated_lock).decode().splitlines(True),
                                          fromfile="current/.agents/skills-lock.json", tofile="selected/.agents/skills-lock.json")), end="")
    if result.needs_link():
        print("WOULD LINK .claude/skills -> ../.agents/skills")
    if not result.edits and not result.changed and not result.needs_link():
        print("No changes.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, type=Path, help="existing project directory (may be empty)")
    parser.add_argument("--ref", required=True, help="full locally available Agent Kit commit SHA")
    parser.add_argument("--client", choices=("codex", "claude", "both"), help="project skill discovery clients")
    parser.add_argument("--instruction-owner", choices=("AGENTS.md", "CLAUDE.md"),
                        help="the root file that owns shared instructions when both carry their own")
    parser.add_argument("--apply", action="store_true", help="write the complete setup after preflight")
    parser.add_argument("--full", action="store_true", help="print every skill file difference, not one line per skill")
    args = parser.parse_args(argv)
    try:
        project = args.project.resolve(strict=True)
        if not project.is_dir():
            raise ERROR("--project must be an existing directory")
        guard = skills.safe_path(project, ".agents/skills-sync.lock")
        if guard.exists():
            raise ERROR("Another installation holds skills-sync.lock; reconcile its owner before retrying")
        result = build_plan(project, args.ref, args.client, args.instruction_owner)
        describe(result, project, args.ref, full=args.full)
        if not args.apply:
            return 0
        agents = skills.safe_path(project, ".agents")
        created = False
        try:
            try:
                agents.mkdir()
                created = True
            except FileExistsError:
                pass
            with skills.installation_guard(project):
                latest = build_plan(project, args.ref, args.client, args.instruction_owner)
                if latest != result:
                    raise ERROR("Project changed during setup; preview the updated plan")
                if latest.edits or latest.changed or latest.needs_link():
                    with write_documents(project, latest.edits):
                        if latest.changed or latest.needs_link():
                            # Report only after the whole setup is committed, even if stdout closes.
                            with redirect_stdout(io.StringIO()):
                                skills.install(project, latest.items, latest.skill_lock, client_link=latest.link)
                    print(f"Applied complete setup at {args.ref}.")
        finally:
            if created:
                try:
                    agents.rmdir()
                except OSError:
                    pass
        return 0
    except (ERROR, OSError, KeyError, TypeError, ValueError, RuntimeError) as error:
        print(f"setup: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
