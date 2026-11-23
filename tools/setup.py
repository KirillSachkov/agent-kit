#!/usr/bin/env python3
"""Preview or install the pinned skills in a project directory.

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
STARTER_VERSION = 5
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
    if not result:
        raise ERROR(f"No project starter at {ref}")
    return result


def render(raw, settings):
    def replace(match):
        return str(settings[match[1]])
    return re.sub(r"@@([a-z_]+)@@", replace, raw.decode()).encode()


def handed_over(data):
    """An earlier release kept a marked block in the root instructions. The text is the project's now:
    return it without the marks, or None when there were none."""
    text = data.decode()
    if BEGIN not in text and END not in text:
        return None
    lines = [line for line in text.splitlines(keepends=True) if line.strip() not in (BEGIN, END)]
    return "".join(lines).encode()


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
    retired: list  # destinations of skills that left the Kit and that the project never edited

    def needs_link(self):
        return self.link and not self.link[1].is_symlink()


def build_plan(project, ref, client):
    templates = pinned_templates(ref)
    starter = json.loads(templates.pop("starter.json", b"{}")).get("starter_version", 1)
    if starter != STARTER_VERSION:
        raise ERROR(f"The starter at {ref} is version {starter}; this tool installs version {STARTER_VERSION}. "
                    f"Run the tool of that revision: git -C {KIT} show {ref}:tools/setup.py")
    old_state = read_optional(project, LOCK)
    state = json.loads(old_state) if old_state else {}
    if old_state is not None and (state.get("schema_version") != 1 or not isinstance(state.get("files"), dict)):
        raise ERROR(f"Invalid setup lock: {LOCK}")
    notes = []
    if state.get("decisions"):
        notes.append("Decisions an earlier release recorded now live in docs/agents/project-settings.md; "
                     "run the setup-project skill to bring that file to its current form")
    edits = []
    managed = dict(state.get("files", {}))
    def add(name, before, after):
        skills.safe_path(project, name)
        if before != after:
            edits.append(Edit(name, before, after))
    catalog_dir = KIT / "skills"
    catalog = skills.read_json(catalog_dir / "catalog.json")
    manifest = skills.select_manifest(project, catalog, catalog_dir, "agent-kit", ref, None, client)
    # A skill that left the Kit is removed when the project never edited it. An edited copy is refused
    # like any other edited skill, so the owner reconciles it first.
    recorded = json.loads(read_optional(project, ".agents/skills-lock.json") or b"{}").get("skills", {})
    retired = [entry["destination"] for entry in manifest["skills"]
               if entry["ref"] != ref and skills.safe_path(project, entry["destination"]).is_dir()
               and skills.digest(skills.folder_files(skills.safe_path(project, entry["destination"])))
               == recorded.get(entry["destination"], {}).get("sha256")]
    manifest["skills"] = [entry for entry in manifest["skills"] if entry["destination"] not in retired]
    for destination in retired:
        manifest.get("selection_features", {}).pop(destination, None)
    items, skill_lock, _ = skills.plan(project, catalog, catalog_dir, manifest=manifest)
    for destination in retired:
        skill_lock["skills"].pop(destination, None)
    changed = skills.preflight_changed(project, items, skill_lock)
    link = skills.client_discovery(project, manifest)
    for name in ("AGENTS.md", "CLAUDE.md"):
        before = None if (project / name).is_symlink() else read_optional(project, name)
        after = handed_over(before) if before is not None else None
        if after is not None:
            add(name, before, after)
            notes.append(f"{name}: the instruction block an earlier release managed is now the project's own text; "
                         "run the setup-project skill to shape it")
    for name, raw in sorted(templates.items()):
        before = read_optional(project, name)
        after = render(raw, {})
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
                notes.append(f"{name}: now the project's own file; the setup-project skill maintains it")
        elif current is not None and sha(current) == managed[name]:
            edits.append(Edit(name, current, None))
            notes.append(f"{name}: no longer part of the starter; removed, as the project never edited it")
        elif current is not None:
            notes.append(f"{name}: no longer part of the starter; the project edited it, so it stays")
        del managed[name]
    add(MANIFEST, read_optional(project, MANIFEST), encoded(manifest))
    state = dict(schema_version=1, ref=ref, files=managed)
    add(LOCK, old_state, encoded(state))
    notes += [f"{destination}: no longer in the Kit; removed, as the project never edited it" for destination in retired]
    return SetupPlan(edits, items, changed, skill_lock, link, notes, retired)


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
        result = build_plan(project, args.ref, args.client)
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
                latest = build_plan(project, args.ref, args.client)
                if latest != result:
                    raise ERROR("Project changed during setup; preview the updated plan")
                if latest.edits or latest.changed or latest.needs_link():
                    with write_documents(project, latest.edits):
                        if latest.changed or latest.needs_link() or latest.retired:
                            # Report only after the whole setup is committed, even if stdout closes.
                            with redirect_stdout(io.StringIO()):
                                skills.install(project, latest.items, latest.skill_lock, client_link=latest.link)
                        if latest.retired:  # kept beside the other previous copies, not deleted
                            backups = skills.safe_path(project, ".agents/skills-backups")
                            backups.mkdir(exist_ok=True)
                            kept = Path(tempfile.mkdtemp(prefix="retired-", dir=backups))
                            for destination in latest.retired:
                                os.replace(skills.safe_path(project, destination), kept / Path(destination).name)
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
