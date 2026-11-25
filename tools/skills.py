#!/usr/bin/env python3
"""Pinned, agent-independent skill distribution. No network or global updates."""
import argparse
from contextlib import contextmanager
import difflib
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


class SkillsError(Exception):
    pass


def safe_path(root, relative):
    parts = Path(relative).parts
    if Path(relative).is_absolute() or not parts or any(p in {".", ".."} for p in parts):
        raise SkillsError(f"Unsafe relative path: {relative}")
    target = root
    for part in parts:
        if target.exists() and not target.is_dir():
            raise SkillsError(f"Destination parent must be a directory: {target}")
        target = target / part
        if target.is_symlink():
            raise SkillsError(f"Symlink not allowed in managed path: {target}")
    if not target.resolve().is_relative_to(root.resolve()):
        raise SkillsError(f"Path escapes project: {relative}")
    return target


def read_json(path):
    try:
        if not path.is_file():
            raise ValueError("expected a regular JSON file")
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


def release(catalog, catalog_dir, name, ref):
    """Read release metadata at the same pin as the files, using the configured location."""
    if catalog.get("schema_version") != 1 or not isinstance(catalog.get("providers"), dict):
        raise SkillsError("Invalid catalog")
    provider = catalog["providers"].get(name)
    if provider is None:
        raise SkillsError(f"Unknown provider: {name}")
    if not isinstance(ref, str) or not re.fullmatch(r"[0-9a-f]{40}", ref):
        raise SkillsError("ref must be a full lowercase 40-character commit SHA")
    inventory = catalog
    if provider.get("catalog_path") and provider.get("snapshot_ref") != ref:
        path = Path(provider["catalog_path"])
        if path.is_absolute() or ".." in path.parts:
            raise SkillsError("Unsafe pinned catalog path")
        repo = provider_repository(provider, catalog_dir)
        inventory = json.loads(git(repo, "show", f"{ref}:{path}"))
        if inventory.get("schema_version") != 1 or name not in inventory["providers"]:
            raise SkillsError(f"Invalid pinned catalog for {name}@{ref}")
        # Only the local configuration determines where to read Git or snapshot data.
        pinned = inventory["providers"][name]
        provider = {"repository": provider["repository"], **{
            key: pinned[key] for key in ("skill_paths", "skills_prefix", "notices") if key in pinned}}
    rows = {row["skill"]: row for row in inventory.get("skills", []) if row["provider"] == name}
    return provider, rows


def skill_description(skill_md):
    lines = skill_md.decode("utf-8").splitlines()
    if not lines or lines[0] != "---" or "---" not in lines[1:]:
        return ""
    frontmatter = lines[1:lines.index("---", 1)]
    for index, line in enumerate(frontmatter):
        if line.startswith("description:"):
            value = line.partition(":")[2].strip()
            if value.rstrip("+-") in {"|", ">"} or not value:
                parts = []
                for continuation in frontmatter[index + 1:]:
                    if continuation and not continuation.startswith((" ", "\t")):
                        break
                    parts.append(continuation.strip())
                return " ".join(part for part in parts if part)
            if value.startswith('"'):
                return json.loads(value)
            if value.startswith("'") and value.endswith("'"):
                return value[1:-1].replace("''", "'")
            return value
    return ""


def list_skills(catalog, catalog_dir, provider_name, ref):
    if ref:
        provider, entries = release(catalog, catalog_dir, provider_name, ref)
        rows = entries.values()
    else:
        rows = catalog.get("skills", [])
    for entry in rows:
        state = " (internal)" if entry.get("internal") else ""
        print(f"{entry['group']}/{entry['skill']} [{entry['provider']}]{state}")
        if ref:
            source = source_files(provider, {**entry, "ref": ref}, catalog_dir)
            description = skill_description(source["SKILL.md"][0])
            if description:
                print("  " + description)
        for dep in entry.get("dependencies", []):
            kind = "reference" if dep.get("reference") else "required"
            if "feature" in dep:
                kind = f"feature {dep['feature']}"
            print(f"  {kind}: {dep['skill']} — {dep['reason']}")


def skill_entry(provider, ref, name):
    return {"provider": provider, "ref": ref, "skill": name, "destination": ".agents/skills/" + name}


def root_entries(manifest):
    if manifest.get("schema_version") != 1 or not isinstance(manifest.get("skills"), list):
        raise SkillsError("Invalid existing manifest")
    roots = {}
    destinations = set()
    for entry in manifest["skills"]:
        destination = entry["destination"]
        if destination in destinations:
            raise SkillsError(f"Duplicate destination: {destination}")
        destinations.add(destination)
        if destination not in manifest.get("dependency_reasons", {}):
            roots[destination] = entry
    return roots


def resolve_manifest(manifest, catalog, catalog_dir):
    """Resolve each explicit root in its release with that root's chosen features."""
    selections = root_entries(manifest)
    roots = selections.copy()
    reasons = {}
    releases = {}
    visited = set()

    def visit(entry, features, path):
        provider, ref, name = entry["provider"], entry["ref"], entry["skill"]
        if name in path:
            raise SkillsError("Dependency cycle: " + " -> ".join((*path, name)))
        key = (entry["destination"], features)
        if key in visited:
            return
        if (provider, ref) not in releases:
            releases[provider, ref] = release(catalog, catalog_dir, provider, ref)[1]
        rows = releases[provider, ref]
        for dep in rows.get(name, {}).get("dependencies", []):
            if dep.get("reference") or ("feature" in dep and dep["feature"] not in features):
                continue
            target = dep["skill"]
            if target not in rows:
                raise SkillsError(f"Missing dependency {target} required by {name} at {ref}")
            if dep.get("provider", provider) != provider or dep.get("ref", ref) != ref:
                raise SkillsError(f"Version conflict: {name} requires {target} outside {provider}@{ref}")
            dependency = skill_entry(provider, ref, target)
            destination = dependency["destination"]
            existing = selections.setdefault(destination, dependency)
            if any(existing[k] != dependency[k] for k in ("provider", "ref", "skill")):
                raise SkillsError(f"Version conflict: {name} requires {provider}/{target}@{ref}, "
                                  f"but {destination} selects {existing['provider']}/{existing['skill']}@{existing['ref']}")
            if destination not in roots:
                kind = f"feature {dep['feature']}" if "feature" in dep else "required"
                reason = f"{name} ({kind}): {dep['reason']}"
                values = reasons.setdefault(destination, [])
                if reason not in values:
                    values.append(reason)
            visit(existing, features, (*path, name))
        visited.add(key)

    for destination, entry in roots.items():
        features = manifest.get("selection_features", {}).get(destination, [])
        visit(entry, frozenset(features), ())
    for entry in manifest["skills"]:
        expected = selections.get(entry["destination"])
        if expected is not None and expected != entry:
            raise SkillsError(f"Version conflict in recorded dependency: {entry['destination']}")
    resolved = {**manifest, "skills": list(selections.values())}
    resolved.pop("dependency_reasons", None)
    if reasons:
        resolved["dependency_reasons"] = reasons
    return resolved


def select_manifest(project, catalog, catalog_dir, provider_name, ref, names, client, features=()):
    _, rows = release(catalog, catalog_dir, provider_name, ref)
    select_all = names is None
    if select_all:
        names = [name for name, row in rows.items() if not row.get("internal")]
    if not names:
        raise SkillsError("Select at least one released skill (or --all)")
    available_features = {dep["feature"] for row in rows.values() for dep in row.get("dependencies", [])
                          if "feature" in dep}
    unknown = set(features) - available_features
    if unknown:
        raise SkillsError("Unknown feature at selected revision: " + ", ".join(sorted(unknown)))
    path = safe_path(project, ".agents/skills-manifest.json")
    manifest = read_json(path) if path.exists() else {"schema_version": 1, "installation": "copies", "skills": []}
    if manifest.get("installation", "copies") != "copies":
        raise SkillsError("Source-link selections belong to their source bootstrap")
    roots = root_entries(manifest)
    selected_features = dict(manifest.get("selection_features", {}))
    for name in names:
        if name not in rows:
            raise SkillsError(f"Skill is not in this catalog: {name}")
        entry = skill_entry(provider_name, ref, name)
        destination = entry["destination"]
        if destination in roots and any(roots[destination][key] != entry[key] for key in ("provider", "skill")):
            raise SkillsError(f"Provider conflict at {destination}")
        roots[destination] = entry
        enabled = set(features)
        if select_all:
            enabled.update(selected_features.get(destination, []))
        if enabled:
            selected_features[destination] = sorted(enabled)
        else:
            selected_features.pop(destination, None)
    # A skill that left this provider's catalog stays recorded at its old revision without pulling its
    # old dependencies in; the setup tool removes it, or refuses when the project edited it.
    left = [roots.pop(destination) for destination, entry in list(roots.items())
            if select_all and entry["provider"] == provider_name and entry["skill"] not in rows]
    manifest["skills"] = list(roots.values())
    manifest.pop("dependency_reasons", None)
    if selected_features:
        manifest["selection_features"] = selected_features
    else:
        manifest.pop("selection_features", None)
    if client is not None:
        manifest["clients"] = ["codex", "claude"] if client == "both" else [client]
    client_discovery(project, manifest)
    resolved = resolve_manifest(manifest, catalog, catalog_dir)
    resolved["skills"] += left
    return resolved


def explain_selection(manifest):
    for entry in manifest["skills"]:
        reasons = manifest.get("dependency_reasons", {}).get(entry["destination"], ["selected"])
        print(f"{entry['skill']} @ {entry['ref']}: " + " / ".join(reasons))


def preflight_selection(project, catalog, catalog_dir, manifest):
    items, lock, _ = plan(project, catalog, catalog_dir, manifest)
    for entry, path, current, wanted in items:
        previous = lock["skills"].get(entry["destination"])
        if previous is not None and digest(current) != previous.get("sha256"):
            raise SkillsError(f"Refusing locally edited copy: {entry['destination']}")
        if previous is None and path.exists() and current != wanted:
            # Permit explicit adoption of an exact source copy that lacks provider notices.
            provider, _ = release(catalog, catalog_dir, entry["provider"], entry["ref"])
            if current != source_files(provider, entry, catalog_dir):
                raise SkillsError(f"Unmanaged destination differs from its pinned copy: {entry['destination']}")


def select(project, catalog, catalog_dir, provider_name, ref, names, client, apply, features=()):
    path = safe_path(project, ".agents/skills-manifest.json")
    before = path.read_text() if path.exists() else ""
    manifest = select_manifest(project, catalog, catalog_dir, provider_name, ref, names, client, features)
    preflight_selection(project, catalog, catalog_dir, manifest)
    explain_selection(manifest)
    after = json.dumps(manifest, indent=2) + "\n"
    print("".join(difflib.unified_diff(before.splitlines(True), after.splitlines(True),
                                      fromfile="current-manifest", tofile="selected-manifest")), end="")
    if apply and before != after:
        path.parent.mkdir(parents=True, exist_ok=True)
        with installation_guard(project):
            if (path.read_text() if path.exists() else "") != before:
                raise SkillsError("Manifest changed while selecting; retry from its new version")
            client_discovery(project, manifest)
            preflight_selection(project, catalog, catalog_dir, manifest)
            descriptor, temporary = tempfile.mkstemp(prefix=".skills-manifest-", dir=path.parent)
            try:
                with os.fdopen(descriptor, "w") as stream:
                    stream.write(after)
                os.replace(temporary, path)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
        print("Selected pinned skills; run preview, then install or explicit adopt.")
    return manifest


@lru_cache(maxsize=1024)
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


def provider_repository(provider, catalog_dir):
    repository = Path(provider["repository"]).expanduser()
    return repository if repository.is_absolute() else catalog_dir.resolve() / repository


def source_files(provider, entry, catalog_dir):
    ref = entry["ref"]
    if not re.fullmatch(r"[0-9a-f]{40}", ref):
        raise SkillsError("ref must be a full lowercase 40-character commit SHA")
    repo = provider_repository(provider, catalog_dir)
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
    source_prefix = provider.get("skills_prefix")
    if not source_path and source_prefix is None:
        raise SkillsError(f"Skill is not in the provider catalog: {entry['skill']}")
    prefix_path = Path(source_path) if source_path else Path(source_prefix) / entry["skill"]
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
            repository = provider_repository(provider, catalog_dir)
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


def plan(project, catalog, catalog_dir, manifest=None):
    if manifest is None:
        manifest = read_json(safe_path(project, ".agents/skills-manifest.json"))
    manifest = resolve_manifest(manifest, catalog, catalog_dir)
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
    for entry in manifest["skills"]:
        if not isinstance(entry, dict):
            raise SkillsError("Skill entries must be objects")
        if not re.fullmatch(r"\.agents/skills/[a-z0-9][a-z0-9-]*", entry["destination"]):
            raise SkillsError(f"Unsafe destination: {entry['destination']}")
        previous = lock["skills"].get(entry["destination"])
        if previous is not None and any(previous.get(key) != entry[key] for key in ("provider", "skill")):
            raise SkillsError(f"Installed skill identity conflict at {entry['destination']}: "
                              f"{previous.get('provider')}/{previous.get('skill')} is already managed there")
        provider, _ = release(catalog, catalog_dir, entry["provider"], entry["ref"])
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


def preflight_changed(project, items, lock, adoptable=None):
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

    if changed:
        backup_root = safe_path(project, ".agents/skills-backups")
        if backup_root.exists() and not backup_root.is_dir():
            raise SkillsError(f"Backup destination must be a directory: {backup_root}")
    return changed


def install(project, items, lock, adoptable=None, client_link=None):
    changed = preflight_changed(project, items, lock, adoptable)
    backup = None
    lock_path = safe_path(project, ".agents/skills-lock.json")
    old_lock = lock_path.read_bytes() if lock_path.exists() else None
    stage = Path(tempfile.mkdtemp(prefix=".skills-stage-", dir=project / ".agents"))
    new_directories = []
    applied = []
    created_link = None
    staged_lock = stage / "lock.json"
    swapping_lock = False
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
            backup_root = safe_path(project, ".agents/skills-backups")
            if not backup_root.exists():
                new_directories.append(backup_root)
                backup_root.mkdir()
            backup = Path(tempfile.mkdtemp(dir=backup_root))
            if old_lock is not None:
                (backup / "skills-lock.json").write_bytes(old_lock)
        for index, (entry, path, current, wanted) in enumerate(changed):
            safe_path(project, entry["destination"])
            if folder_files(path) != current:
                raise SkillsError(f"Copy changed during installation: {path}")
            if not path.parent.exists():
                new_directories.append(path.parent)
            path.parent.mkdir(parents=True, exist_ok=True)
            previous = backup / path.name
            applied.append((path, previous, stage / str(index)))
            if path.exists():
                os.replace(path, previous)
            os.replace(stage / str(index), path)
        if client_link is not None:
            source, target = client_link
            if not target.is_symlink():
                if not target.parent.exists():
                    new_directories.append(target.parent)
                target.parent.mkdir(parents=True, exist_ok=True)
                created_link = target
                target.symlink_to(os.path.relpath(source, target.parent), target_is_directory=True)
        updated = {**lock, "skills": dict(lock["skills"])}
        for entry, path, current, wanted in items:
            updated["skills"][entry["destination"]] = {**entry, "sha256": digest(wanted)}
        staged_lock.write_text(json.dumps(updated, indent=2) + "\n")
        if old_lock is not None:
            os.link(lock_path, stage / "old-lock")
        swapping_lock = True
        os.replace(staged_lock, lock_path)
        print(f"Installed {len(items)} pinned skills. Project policies remain project-owned.")
        if changed:
            print(f"Previous installed copies and lock (if present): {backup}")
    except BaseException:
        if swapping_lock and not staged_lock.exists():
            if old_lock is None:
                lock_path.unlink()
            else:
                os.replace(stage / "old-lock", lock_path)
        if created_link is not None and created_link.is_symlink() and created_link.resolve() == client_link[0].resolve():
            created_link.unlink()
        for path, previous, staged in reversed(applied):
            if not staged.exists() and path.exists():
                shutil.rmtree(path)
            if previous.exists():
                os.replace(previous, path)
        if backup is not None:
            shutil.rmtree(backup)
        for directory in reversed(new_directories):
            if directory.is_dir() and not any(directory.iterdir()):
                directory.rmdir()
        raise
    finally:
        shutil.rmtree(stage)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["list", "select", "preview", "install", "adopt", "check"])
    parser.add_argument("--project", type=Path, default=Path.cwd())
    parser.add_argument("--catalog", type=Path, default=ROOT / "skills/catalog.json")
    parser.add_argument("--provider", default="agent-kit", help="provider for select")
    parser.add_argument("--ref", help="full commit SHA for select")
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--all", action="store_true", help="select every released skill at --ref")
    parser.add_argument("--feature", action="append", default=[], help="enable a conditional dependency; repeatable")
    selection.add_argument("--skill", action="append", default=[], help="explicit skill for select; repeatable")
    parser.add_argument("--client", choices=["codex", "claude", "both"], help="discovery clients for select")
    parser.add_argument("--apply", action="store_true", help="write select's manifest; otherwise preview only")
    args = parser.parse_args(argv)
    try:
        catalog = read_json(args.catalog)
        if args.command == "list":
            list_skills(catalog, args.catalog.parent, args.provider, args.ref)
            return 0
        project = args.project.resolve(strict=True)
        if args.command == "select":
            select(project, catalog, args.catalog.parent, args.provider, args.ref, None if args.all else args.skill,
                   args.client, args.apply, args.feature)
            return 0
        manifest = resolve_manifest(read_json(safe_path(project, ".agents/skills-manifest.json")), catalog, args.catalog.parent)
        items, lock, installation = plan(project, catalog, args.catalog.parent, manifest)
        client_link = client_discovery(project, manifest)
        explain_selection(manifest)
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
                manifest = read_json(safe_path(project, ".agents/skills-manifest.json"))
                items, lock, installation = plan(project, catalog, args.catalog.parent, manifest)
                if installation != "copies":
                    raise SkillsError("Source-link manifest changed while acquiring installation lock")
                client_link = client_discovery(project, manifest)
                adoptable = None
                if args.command == "adopt":
                    adoptable = {entry["destination"]: source_files(
                        release(catalog, args.catalog.parent, entry["provider"], entry["ref"])[0], entry, args.catalog.parent)
                                 for entry, path, current, wanted in items}
                install(project, items, lock, adoptable=adoptable, client_link=client_link)
        return 0
    except (SkillsError, OSError, KeyError, TypeError, ValueError) as error:
        print(f"skills: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
