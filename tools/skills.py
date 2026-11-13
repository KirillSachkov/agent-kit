#!/usr/bin/env python3
"""Pinned, agent-independent skill distribution. No network or global updates."""
import argparse
from contextlib import contextmanager
import difflib
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[1]


class SkillsError(Exception):
    pass


def safe_path(root, relative):
    parts = Path(relative).parts
    if Path(relative).is_absolute() or not parts or any(p in {".", ".."} for p in parts):
        raise SkillsError(f"Unsafe relative path: {relative}")
    target = root
    for part in parts:
        target = target / part
        if target.is_symlink():
            raise SkillsError(f"Symlink not allowed in managed path: {target}")
    if not target.resolve().is_relative_to(root.resolve()):
        raise SkillsError(f"Path escapes project: {relative}")
    return target


def read_json(path):
    try:
        value = json.loads(path.read_text())
        if not isinstance(value, dict):
            raise ValueError("expected a JSON object")
        return value
    except (OSError, ValueError) as error:
        raise SkillsError(f"Cannot read {path}: {error}") from error


@contextmanager
def installation_guard(project):
    guard = safe_path(project, ".agents/skills-sync.lock")
    try:
        descriptor = os.open(guard, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as error:
        raise SkillsError("Another installation holds skills-sync.lock; reconcile its owner before retrying") from error
    try:
        with os.fdopen(descriptor, "w") as file:
            file.write(str(os.getpid()) + "\n")
        yield
    finally:
        guard.unlink()


def list_skills(catalog):
    for entry in catalog.get("skills", []):
        state = " (internal)" if entry.get("internal") else ""
        print(f"{entry['group']}/{entry['skill']} [{entry['provider']}]{state}")


def select(project, catalog, catalog_dir, provider_name, ref, names, client, apply):
    if catalog.get("schema_version") != 1 or not isinstance(catalog.get("providers"), dict):
        raise SkillsError("Invalid catalog")
    if not names or not ref:
        raise SkillsError("select requires --ref and at least one --skill")
    provider = catalog["providers"].get(provider_name)
    if provider is None:
        raise SkillsError(f"Unknown provider: {provider_name}")
    available = {entry["skill"] for entry in catalog.get("skills", []) if entry["provider"] == provider_name}
    path = safe_path(project, ".agents/skills-manifest.json")
    before = path.read_text() if path.exists() else ""
    manifest = read_json(path) if path.exists() else {"schema_version": 1, "installation": "copies", "skills": []}
    if manifest.get("schema_version") != 1 or not isinstance(manifest.get("skills"), list):
        raise SkillsError("Invalid existing manifest")
    if manifest.get("installation", "copies") != "copies":
        raise SkillsError("Source-link selections belong to their source bootstrap")
    selections = {}
    for name in dict.fromkeys(names):
        if name not in available:
            raise SkillsError(f"Skill is not in this catalog: {name}")
        entry = {"provider": provider_name, "ref": ref, "skill": name,
                 "destination": ".agents/skills/" + name}
        source_files(provider, entry, catalog_dir)
        selections[entry["destination"]] = entry
    existing = []
    for entry in manifest["skills"]:
        if not isinstance(entry, dict) or "destination" not in entry:
            raise SkillsError("Invalid existing skill selection")
        if entry["destination"] in selections:
            existing.append(selections.pop(entry["destination"]))
        else:
            existing.append(entry)
    manifest["skills"] = existing + list(selections.values())
    if client is not None:
        manifest["clients"] = ["codex", "claude"] if client == "both" else [client]
    client_discovery(project, manifest)
    after = json.dumps(manifest, indent=2) + "\n"
    print("".join(difflib.unified_diff(before.splitlines(True), after.splitlines(True),
                                      fromfile="current-manifest", tofile="selected-manifest")), end="")
    if apply:
        path.parent.mkdir(parents=True, exist_ok=True)
        with installation_guard(project):
            if (path.read_text() if path.exists() else "") != before:
                raise SkillsError("Manifest changed while selecting; retry from its new version")
            descriptor, temporary = tempfile.mkstemp(prefix=".skills-manifest-", dir=path.parent)
            try:
                with os.fdopen(descriptor, "w") as stream:
                    stream.write(after)
                os.replace(temporary, path)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
        print("Selected pinned skills; run preview, then install or explicit adopt.")


def git(repo, *args):
    result = subprocess.run(["git", "-c", "core.fsmonitor=false", "-C", str(repo), *args],
                            capture_output=True, env={**os.environ, "GIT_OPTIONAL_LOCKS": "0",
                                                      "GIT_NO_LAZY_FETCH": "1"})
    if result.returncode:
        raise SkillsError("Pinned source unavailable locally: " + result.stderr.decode(errors="replace").strip())
    return result.stdout


def snapshot_folder(provider, entry, catalog_dir):
    if provider.get("snapshot_ref") != entry["ref"]:
        return None
    paths = provider.get("snapshot_paths")
    if paths is not None:
        if not isinstance(paths, dict) or not isinstance(paths.get(entry["skill"]), str):
            raise SkillsError(f"Missing snapshot path for skill: {entry['skill']}")
        relative = paths[entry["skill"]]
    elif provider.get("snapshot_directory"):
        relative = provider["snapshot_directory"] + "/" + entry["skill"]
    else:
        return None
    return safe_path(catalog_dir.resolve(), relative)


def source_files(provider, entry, catalog_dir):
    ref = entry["ref"]
    if not re.fullmatch(r"[0-9a-f]{40}", ref):
        raise SkillsError("ref must be a full lowercase 40-character commit SHA")
    repo = Path(provider["repository"]).expanduser()
    if not repo.is_absolute():
        repo = ROOT / repo
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", entry["skill"]):
        raise SkillsError("Unsafe skill name")
    snapshot = snapshot_folder(provider, entry, catalog_dir)
    if snapshot is not None:
        files = folder_files(snapshot)
        expected = provider.get("snapshot_sha256", {}).get(entry["skill"])
        if "SKILL.md" not in files or not expected or digest(files) != expected:
            raise SkillsError(f"Pinned snapshot failed content verification: {entry['skill']}")
        return files
    source_path = provider.get("skill_paths", {}).get(entry["skill"])
    prefix_path = Path(source_path) if source_path else Path(provider["skills_prefix"]) / entry["skill"]
    if prefix_path.is_absolute() or ".." in prefix_path.parts:
        raise SkillsError("Unsafe source prefix")
    prefix = str(prefix_path)
    git(repo, "cat-file", "-e", ref + "^{commit}")
    result = {}
    for record in git(repo, "ls-tree", "-rz", ref, "--", prefix + "/").split(b"\0"):
        if not record:
            continue
        header, name = record.split(b"\t", 1)
        mode, kind, blob = header.decode().split()
        relative = name.decode().removeprefix(prefix + "/")
        if mode not in {"100644", "100755"} or kind != "blob":
            raise SkillsError(f"Source contains symlink/submodule/unsupported mode: {relative}")
        if Path(relative).is_absolute() or ".." in Path(relative).parts:
            raise SkillsError("Unsafe source file path")
        result[relative] = (git(repo, "cat-file", "blob", blob), mode)
    if "SKILL.md" not in result:
        raise SkillsError(f"Missing SKILL.md at {prefix} in {ref}")
    return result


def folder_files(path):
    if not path.exists():
        return {}
    result = {}
    for p in sorted(path.rglob("*")):
        if p.is_symlink():
            raise SkillsError(f"Installed copy contains symlink: {p}")
        if p.is_file():
            result[str(p.relative_to(path))] = (p.read_bytes(), "100755" if p.stat().st_mode & 0o111 else "100644")
        elif not p.is_dir():
            raise SkillsError(f"Installed copy contains special file: {p}")
    return result


def digest(files):
    result = hashlib.sha256()
    for name in sorted(files):
        data, mode = files[name]
        result.update(name.encode() + b"\0" + mode.encode() + b"\0" + data + b"\0")
    return result.hexdigest()


def with_notices(provider, entry, files, catalog_dir):
    files = dict(files)
    for name, notice in provider.get("notices", {}).items():
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", name):
            raise SkillsError("Unsafe provider notice name")
        if provider.get("snapshot_ref") == entry["ref"] and notice.get("snapshot_path"):
            data = safe_path(catalog_dir.resolve(), notice["snapshot_path"]).read_bytes()
            if hashlib.sha256(data).hexdigest() != notice.get("sha256"):
                raise SkillsError(f"Provider notice failed content verification: {name}")
        else:
            source = Path(notice["source_path"])
            if source.is_absolute() or ".." in source.parts:
                raise SkillsError("Unsafe provider notice path")
            repository = Path(provider["repository"]).expanduser()
            if not repository.is_absolute():
                repository = ROOT / repository
            data = git(repository, "show", entry["ref"] + ":" + str(source))
        destination = "PROVIDER-NOTICES/" + name
        if destination in files:
            raise SkillsError("Provider notice collides with a source file")
        files[destination] = (data, "100644")
    return files


def client_discovery(project, manifest):
    clients = manifest.get("clients", ["codex"])
    if not isinstance(clients, list) or not clients or any(client not in {"codex", "claude"} for client in clients):
        raise SkillsError("clients must select codex, claude or both")
    if "claude" not in clients:
        return None
    source = safe_path(project, ".agents/skills")
    parent = safe_path(project, ".claude")
    if parent.exists() and not parent.is_dir():
        raise SkillsError("Claude discovery parent must be a directory")
    target = parent / "skills"
    if target.is_symlink():
        if target.resolve() != source.resolve():
            raise SkillsError("Conflicting Claude skill index; preserved")
    elif target.exists():
        raise SkillsError("Existing Claude skill directory/file is unmanaged; preserved")
    return source, target


def plan(project, catalog, catalog_dir):
    manifest = read_json(safe_path(project, ".agents/skills-manifest.json"))
    if manifest.get("schema_version") != 1 or catalog.get("schema_version") != 1:
        raise SkillsError("Unsupported schema_version")
    installation = manifest.get("installation", "copies")
    if installation not in {"copies", "source-links"}:
        raise SkillsError("installation must be copies or source-links")
    lock_path = safe_path(project, ".agents/skills-lock.json")
    lock = read_json(lock_path) if lock_path.exists() else {"schema_version": 1, "skills": {}}
    if lock.get("schema_version") != 1 or not isinstance(lock.get("skills"), dict):
        raise SkillsError("Invalid skills lock")
    if not isinstance(manifest.get("skills"), list) or not isinstance(catalog.get("providers"), dict):
        raise SkillsError("Manifest needs a skills array; catalog needs providers")
    items = []
    destinations = set()
    for entry in manifest["skills"]:
        if not isinstance(entry, dict):
            raise SkillsError("Skill entries must be objects")
        if not re.fullmatch(r"\.agents/skills/[a-z0-9][a-z0-9-]*", entry["destination"]):
            raise SkillsError(f"Unsafe destination: {entry['destination']}")
        if entry["destination"] in destinations:
            raise SkillsError("Duplicate destination")
        destinations.add(entry["destination"])
        provider = catalog["providers"].get(entry["provider"])
        if provider is None:
            raise SkillsError(f"Unknown provider: {entry['provider']}")
        wanted = source_files(provider, entry, catalog_dir)
        if installation == "source-links":
            destination = safe_path(project, str(Path(entry["destination"]).parent)) / Path(entry["destination"]).name
            expected = snapshot_folder(provider, entry, catalog_dir)
            if expected is None:
                raise SkillsError("Source link requires a catalog snapshot at the selected ref")
            if not destination.is_symlink() or destination.resolve() != expected.resolve():
                raise SkillsError(f"Expected runtime source link: {destination} -> {expected}")
            current = folder_files(expected)
        else:
            wanted = with_notices(provider, entry, wanted, catalog_dir)
            destination = safe_path(project, entry["destination"])
            current = folder_files(destination)
        if destination.exists() and not destination.is_dir():
            raise SkillsError("Destination must be a directory")
        items.append((entry, destination, current, wanted))
    return items, lock, installation


def preview(items):
    for entry, path, current, wanted in items:
        print(f"{entry['destination']}: {entry['provider']}@{entry['ref']} / {entry['skill']}")
        for name in sorted(current.keys() | wanted.keys()):
            before = current.get(name, (b"", ""))[0]
            after = wanted.get(name, (b"", ""))[0]
            if current.get(name) == wanted.get(name):
                continue
            try:
                print("".join(difflib.unified_diff(before.decode().splitlines(True), after.decode().splitlines(True),
                                                  fromfile="installed/" + name, tofile="selected/" + name)), end="")
            except UnicodeDecodeError:
                print(f"binary changed: {name}")
            if current.get(name, (b"", "absent"))[1] != wanted.get(name, (b"", "absent"))[1]:
                print(f"mode {name}: {current.get(name, (b'', 'absent'))[1]} -> {wanted.get(name, (b'', 'absent'))[1]}")


def install(project, items, lock, adoptable=None, client_link=None):
    # Validate the whole selection before changing any consumer folder.
    changed = []
    for entry, path, current, wanted in items:
        previous = lock["skills"].get(entry["destination"])
        if adoptable is not None and (not path.is_dir() or current not in (adoptable[entry["destination"]], wanted)):
            raise SkillsError(f"Adoption requires an exact complete pinned copy: {entry['destination']}")
        if path.exists() and previous is None and adoptable is None:
            raise SkillsError(f"Unmanaged destination already exists: {entry['destination']}")
        if previous is not None and digest(current) != previous.get("sha256"):
            raise SkillsError(f"Refusing locally edited copy: {entry['destination']}. Preserve adaptations in project policy or reconcile explicitly.")
        if current != wanted or previous != {**entry, "sha256": digest(wanted)}:
            changed.append((entry, path, current, wanted))

    backup_root = safe_path(project, ".agents/skills-backups")
    run_id = uuid.uuid4().hex
    backup = backup_root / run_id
    lock_path = safe_path(project, ".agents/skills-lock.json")
    old_lock = lock_path.read_bytes() if lock_path.exists() else None
    stage = Path(tempfile.mkdtemp(prefix=".skills-stage-", dir=project / ".agents"))
    applied = []
    created_link = None
    try:
        for index, (entry, path, current, wanted) in enumerate(changed):
            selected = stage / str(index)
            selected.mkdir()
            for name, (data, mode) in wanted.items():
                target = selected / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
                target.chmod(0o755 if mode == "100755" else 0o644)
        if changed:
            backup.mkdir(parents=True)
            if old_lock is not None:
                (backup / "skills-lock.json").write_bytes(old_lock)
        for index, (entry, path, current, wanted) in enumerate(changed):
            safe_path(project, entry["destination"])
            if folder_files(path) != current:
                raise SkillsError(f"Copy changed during installation: {path}")
            path.parent.mkdir(parents=True, exist_ok=True)
            previous = backup / path.name
            if path.exists():
                os.replace(path, previous)
            applied.append((path, previous))
            os.replace(stage / str(index), path)
        if client_link is not None:
            source, target = client_link
            if not target.is_symlink():
                target.parent.mkdir(parents=True, exist_ok=True)
                target.symlink_to(os.path.relpath(source, target.parent), target_is_directory=True)
                created_link = target
        for entry, path, current, wanted in items:
            lock["skills"][entry["destination"]] = {**entry, "sha256": digest(wanted)}
        staged_lock = stage / "lock.json"
        staged_lock.write_text(json.dumps(lock, indent=2) + "\n")
        os.replace(staged_lock, lock_path)
    except Exception:
        if created_link is not None and created_link.is_symlink() and created_link.resolve() == client_link[0].resolve():
            created_link.unlink()
        for path, previous in reversed(applied):
            if path.exists():
                shutil.rmtree(path)
            if previous.exists():
                os.replace(previous, path)
        raise
    finally:
        shutil.rmtree(stage)
    print(f"Installed {len(items)} pinned skills. Project policies remain project-owned.")
    if changed:
        print(f"Previous installed copies and lock (if present): {backup}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["list", "select", "preview", "install", "adopt", "check"])
    parser.add_argument("--project", type=Path, default=Path.cwd())
    parser.add_argument("--catalog", type=Path, default=ROOT / "skills/catalog.json")
    parser.add_argument("--provider", default="agent-kit", help="provider for select")
    parser.add_argument("--ref", help="full commit SHA for select")
    parser.add_argument("--skill", action="append", default=[], help="explicit skill for select; repeatable")
    parser.add_argument("--client", choices=["codex", "claude", "both"], help="discovery clients for select")
    parser.add_argument("--apply", action="store_true", help="write select's manifest; otherwise preview only")
    args = parser.parse_args(argv)
    try:
        catalog = read_json(args.catalog)
        if args.command == "list":
            list_skills(catalog)
            return 0
        project = args.project.resolve(strict=True)
        if args.command == "select":
            select(project, catalog, args.catalog.parent, args.provider, args.ref, args.skill, args.client, args.apply)
            return 0
        items, lock, installation = plan(project, catalog, args.catalog.parent)
        client_link = client_discovery(project, read_json(safe_path(project, ".agents/skills-manifest.json")))
        if args.command == "preview":
            preview(items)
            if client_link is not None and not client_link[1].is_symlink():
                print(f"WOULD LINK {client_link[1]} -> {client_link[0]}")
        elif args.command == "check":
            if client_link is not None and not client_link[1].is_symlink():
                raise SkillsError("Selected Claude discovery link is missing")
            for entry, path, current, wanted in items:
                expected = {**entry, "sha256": digest(wanted)}
                if digest(current) != expected["sha256"] or (installation == "copies" and lock["skills"].get(entry["destination"]) != expected):
                    raise SkillsError(f"Not installed at selected revision: {entry['destination']}")
            print("Selected skills match their pinned sources and lock.")
        else:
            if installation == "source-links":
                raise SkillsError("Source links are maintained by the source bootstrap; install never writes through runtime links")
            with installation_guard(project):
                catalog = read_json(args.catalog)
                items, lock, installation = plan(project, catalog, args.catalog.parent)
                client_link = client_discovery(project, read_json(safe_path(project, ".agents/skills-manifest.json")))
                adoptable = None
                if args.command == "adopt":
                    adoptable = {entry["destination"]: source_files(catalog["providers"][entry["provider"]], entry, args.catalog.parent)
                                 for entry, path, current, wanted in items}
                install(project, items, lock, adoptable=adoptable, client_link=client_link)
        return 0
    except (SkillsError, OSError, KeyError, TypeError, ValueError) as error:
        print(f"skills: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
