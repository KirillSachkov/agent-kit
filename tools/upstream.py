#!/usr/bin/env python3
"""Show local adaptations of Matt's skills and merge a new upstream revision into them.

The pristine upstream copy is packed under provenance/upstream/mattpocock and never edited by hand.
"""
from __future__ import annotations

import argparse
import filecmp
import contextlib
import difflib
import gzip
import hashlib
import io
import json
import os
import re
import tarfile
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = Path("provenance/upstream/mattpocock")
LOCAL = Path("skills/engineering")
REPOSITORY = "https://github.com/mattpocock/skills"


def identity(directory: Path) -> str:
    digest = hashlib.sha256()
    for file in sorted(directory.rglob("*"), key=lambda item: item.relative_to(directory).as_posix()):
        if file.is_file():
            digest.update(file.relative_to(directory).as_posix().encode() + b"\0" + file.read_bytes() + b"\0")
    return digest.hexdigest()


def read_source(root: Path) -> dict[str, str]:
    return dict(line.split(": ", 1) for line in (root / UPSTREAM / "SOURCE").read_text().splitlines() if ": " in line)


def local_names(root: Path) -> dict[str, str]:
    path = root / UPSTREAM / "RENAMES"
    if not path.is_file():
        return {}
    lines = [line.split("#", 1)[0].strip() for line in path.read_text().splitlines()]
    return dict(tuple(part.strip() for part in line.split(":", 1)) for line in lines if ":" in line)


def _atomic(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".pristine-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(name, 0o644)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def write_snapshot(root: Path, skills: Path, revision: str, date: str, repository: str = REPOSITORY) -> None:
    """Pack exact pristine bytes and modes; keep SKILL.md out of discovery trees."""
    output = io.BytesIO()
    files = []
    with gzip.GzipFile(fileobj=output, mode="wb", filename="", mtime=0) as zipped:
        with tarfile.open(fileobj=zipped, mode="w", format=tarfile.PAX_FORMAT) as archive:
            for path in sorted(skills.rglob("*"), key=lambda item: item.relative_to(skills).as_posix()):
                if path.is_symlink():
                    raise ValueError("pristine files cannot be symlinks")
                if not path.is_file():
                    continue
                name = path.relative_to(skills).as_posix()
                data = path.read_bytes()
                entry = tarfile.TarInfo(name)
                entry.size = len(data)
                entry.mode = 0o755 if path.stat().st_mode & 0o111 else 0o644
                archive.addfile(entry, io.BytesIO(data))
                files.append({"path": name, "mode": entry.mode, "sha256": hashlib.sha256(data).hexdigest()})
    payload = output.getvalue()
    proof = {"format": "tar+gzip", "sha256": hashlib.sha256(payload).hexdigest(), "directory_sha256": identity(skills), "files": files}
    _atomic(root / UPSTREAM / "skills.tar.gz", payload)
    _atomic(root / UPSTREAM / "ARCHIVE.json", (json.dumps(proof, indent=2) + "\n").encode())
    _atomic(root / UPSTREAM / "SOURCE", f"repository: {repository}\nrevision: {revision}\ndate: {date}\nsha256: {identity(skills)}\n".encode())


@contextlib.contextmanager
def pristine_skills(root: Path):
    """Read the lossless baseline in a private temporary extraction directory."""
    source = root / UPSTREAM / "skills.tar.gz"
    if source.is_symlink():
        raise ValueError("pristine archive cannot be a symlink")
    with tempfile.TemporaryDirectory(prefix="agent-kit-pristine-") as temporary:
        directory = Path(temporary)
        seen = set()
        with tarfile.open(source, "r:gz") as archive:
            for member in archive:
                relative = PurePosixPath(member.name)
                if relative.is_absolute() or ".." in relative.parts or "\\" in member.name or ":" in member.name or not relative.parts or not member.isfile():
                    raise ValueError(f"unsafe pristine archive member: {member.name}")
                if relative.as_posix() in seen:
                    raise ValueError(f"duplicate pristine archive member: {member.name}")
                seen.add(relative.as_posix())
                target = directory.joinpath(*relative.parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.extractfile(member) as stream:
                    target.write_bytes(stream.read())
                target.chmod(member.mode & 0o777)
        yield directory


def check_pristine(root: Path) -> list[str]:
    errors = []
    if not (root / UPSTREAM / "SOURCE").is_file():
        return [f"{UPSTREAM}/SOURCE: missing"]
    source = read_source(root)
    revision = source.get("revision", "")
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        errors.append(f"{UPSTREAM}/SOURCE: revision must be a full commit SHA")
    notice = root / "NOTICE"
    if notice.is_file() and revision:
        repository = source.get("repository", REPOSITORY)
        pinned = set(re.findall(re.escape(repository) + r"/tree/([0-9a-f]{40})", notice.read_text()))
        if pinned != {revision}:
            errors.append(f"NOTICE: Matt's snapshot link must name the SOURCE revision {revision}")
    try:
        proof = json.loads((root / UPSTREAM / "ARCHIVE.json").read_text())
        archive_bytes = (root / UPSTREAM / "skills.tar.gz").read_bytes()
        if hashlib.sha256(archive_bytes).hexdigest() != proof.get("sha256"):
            errors.append(f"{UPSTREAM}: archive differs from ARCHIVE.json")
        with pristine_skills(root) as directory:
            if identity(directory) != source.get("sha256") or identity(directory) != proof.get("directory_sha256"):
                errors.append(f"{UPSTREAM}: pristine copy differs from SOURCE; never edit it by hand")
            actual = [{"path": file.relative_to(directory).as_posix(), "mode": 0o755 if file.stat().st_mode & 0o111 else 0o644, "sha256": hashlib.sha256(file.read_bytes()).hexdigest()}
                      for file in sorted(directory.rglob("*"), key=lambda item: item.relative_to(directory).as_posix()) if file.is_file()]
            if actual != proof.get("files"):
                errors.append(f"{UPSTREAM}: pristine files differ from ARCHIVE.json")
            names = local_names(root)
            upstream = borrowed(directory)
            for name in sorted(set(names) - set(upstream)):
                errors.append(f"{UPSTREAM}/RENAMES: {name} is not a borrowed skill")
            for name, path in upstream.items():
                if not (root / LOCAL / names.get(name, name) / "SKILL.md").is_file():
                    errors.append(f"{UPSTREAM / 'skills' / path.relative_to(directory)}: no local skill with this name")
    except (OSError, ValueError, tarfile.TarError, json.JSONDecodeError) as error:
        errors.append(f"{UPSTREAM}: cannot read pristine archive: {error}")
    return errors


def borrowed(skills: Path) -> dict[str, Path]:
    """Map each skill name to its directory in an upstream `skills/<group>/<name>` layout."""
    found: dict[str, Path] = {}
    for directory in sorted(skills.glob("*/*")):
        if (directory / "SKILL.md").is_file():
            if directory.name in found:
                raise SystemExit(f"upstream has two skills named {directory.name}")
            found[directory.name] = directory
    return found


def files(directory: Path) -> set[str]:
    if not directory.is_dir():
        return set()
    return {file.relative_to(directory).as_posix() for file in directory.rglob("*") if file.is_file()}


def _validate_tree(directory: Path) -> None:
    if directory.is_symlink():
        raise ValueError(f"refusing symlink in skill tree: {directory}")
    if not directory.exists():
        return
    if not directory.is_dir():
        raise ValueError(f"skill tree must be a directory: {directory}")
    for path in directory.rglob("*"):
        mode = path.lstat().st_mode
        if stat.S_ISLNK(mode):
            raise ValueError(f"refusing symlink in skill tree: {path}")
        if not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
            raise ValueError(f"refusing special file in skill tree: {path}")


def _validate_owned_tree(root: Path, directory: Path) -> None:
    try:
        relative = directory.relative_to(root)
    except ValueError as error:
        raise ValueError(f"skill path escapes the repository: {directory}") from error
    if ".." in relative.parts:
        raise ValueError(f"skill path escapes the repository: {directory}")
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"refusing symlink in skill path: {current}")
    _validate_tree(directory)


def same(left: Path, right: Path) -> bool:
    return filecmp.cmp(left, right, shallow=False)


def _merged_mode(old: Path, new: Path, local: Path) -> int:
    mode = local.stat().st_mode & 0o777
    old_executable = bool(old.stat().st_mode & 0o111)
    new_executable = bool(new.stat().st_mode & 0o111)
    if old_executable != new_executable and bool(mode & 0o111) == old_executable:
        return (mode & ~0o111) | (new.stat().st_mode & 0o111)
    return mode


def _same_file(left: Path, right: Path) -> bool:
    return same(left, right) and bool(left.stat().st_mode & 0o111) == bool(right.stat().st_mode & 0o111)


def _same_tree(left: Path, right: Path) -> bool:
    entries = {path.relative_to(left) for path in left.rglob("*")}
    if entries != {path.relative_to(right) for path in right.rglob("*")}:
        return False
    for entry in entries:
        first, second = left / entry, right / entry
        if first.is_dir() != second.is_dir():
            return False
        if first.is_file() and not _same_file(first, second):
            return False
    return True


def pairs(root: Path, names: list[str]) -> list[tuple[Path, Path]]:
    """Pair each named skill (upstream or local name; all when empty) as (pristine copy, local copy)."""
    with pristine_skills(root) as directory:
        upstream = borrowed(directory)
        local = local_names(root)
        upstream_name = {name: original for original, name in local.items()}
        result = []
        for name in names or sorted(upstream):
            name = upstream_name.get(name, name)
            if name not in upstream:
                raise SystemExit(f"{name} is not a borrowed skill")
            result.append((UPSTREAM / "skills" / upstream[name].relative_to(directory), LOCAL / local.get(name, name)))
        return result


def diff(root: Path, names: list[str], stat: bool) -> int:
    command = ["git", "diff", "--no-index"] + (["--stat"] if stat else [])
    selected = pairs(root, names)
    with pristine_skills(root) as directory:
        for pristine, local in selected:
            original = directory / pristine.relative_to(UPSTREAM / "skills")
            result = subprocess.run(command + ["--", str(original), str(root / local)], cwd=root)
            if result.returncode > 1:
                return result.returncode
    return 0


def merge_skill(old: Path, new: Path, local: Path) -> list[str]:
    """Three-way merge one skill in place. Return the files that need a human."""
    for directory in (old, new, local):
        _validate_tree(directory)
    removed_directories = [
        path.relative_to(old) for path in old.rglob("*")
        if path.is_dir() and not (new / path.relative_to(old)).exists()
        and (local / path.relative_to(old)).is_dir() and _same_tree(path, local / path.relative_to(old))
    ]
    problems = []
    blocked = []
    for path in sorted(files(old) | files(new) | files(local)):
        if any(path.startswith(prefix + "/") for prefix in blocked):
            continue
        o, n, l = old / path, new / path, local / path
        name = f"{local.name}/{path}"
        changed_shape = (o.is_file() and n.is_dir()) or (o.is_dir() and n.is_file())
        if changed_shape and not l.exists():
            problems.append(f"{name}: changed upstream but removed locally; not restored")
            blocked.append(path)
            continue
        if n.is_file() and l.is_dir():
            if o.is_dir() and _same_tree(o, l):
                shutil.rmtree(l)
                shutil.copy(n, l)
            else:
                problems.append(f"{name}: replaced upstream but changed locally; local tree kept")
            blocked.append(path)
            continue
        if n.is_dir() and l.is_file():
            if o.is_file() and _same_file(o, l):
                l.unlink()
                shutil.copytree(n, l)
            else:
                problems.append(f"{name}: replaced upstream but changed locally; local tree kept")
            blocked.append(path)
            continue
        if o.is_file() and n.is_file() and l.is_file():
            mode = _merged_mode(o, n, l)
            if same(o, n):
                l.chmod(mode)
                continue
            if same(o, l):
                shutil.copyfile(n, l)
                l.chmod(mode)
                continue
            labels = ["-L", "local", "-L", "old upstream", "-L", "new upstream"]
            code = subprocess.run(["git", "merge-file", *labels, l, o, n]).returncode
            if code > 127:
                problems.append(f"{name}: git merge-file failed (binary or unreadable file); local file kept")
            elif code:
                problems.append(f"{name}: conflict markers left in the file")
            l.chmod(mode)
        elif n.is_file() and not o.is_file():
            if not l.is_file():
                l.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(n, l)
            elif not _same_file(n, l):
                problems.append(f"{name}: added both upstream and locally; local file kept")
        elif o.is_file() and not n.is_file() and l.is_file():
            if _same_file(o, l):
                l.unlink()
            else:
                problems.append(f"{name}: removed upstream but changed locally; local file kept")
        elif o.is_file() and n.is_file() and not _same_file(o, n):
            problems.append(f"{name}: changed upstream but removed locally; not restored")
    for relative in sorted(removed_directories, key=lambda path: len(path.parts), reverse=True):
        directory = local / relative
        if directory.is_dir() and not any(directory.iterdir()):
            directory.rmdir()
    return problems


def _merge_update(root: Path, checkout: Path, revision: str, date: str, repository: str) -> list[str]:
    """Merge only inside a disposable proposal tree, never the accepted checkout."""
    root = root.resolve()
    _validate_owned_tree(root, root / LOCAL)
    _validate_owned_tree(root, root / UPSTREAM)
    _validate_tree(checkout / "skills")
    new = borrowed(checkout / "skills")
    with pristine_skills(root) as directory:
        old = borrowed(directory)
        missing = sorted(set(old) - set(new))
        if missing:
            raise ValueError(f"skills missing upstream, nothing changed: {', '.join(missing)}")
        problems, local = [], local_names(root)
        for name in sorted(old):
            _validate_owned_tree(root, root / LOCAL / local.get(name, name))
        for name in sorted(old):
            problems += merge_skill(old[name], new[name], root / LOCAL / local.get(name, name))
        if problems:
            return problems
        with tempfile.TemporaryDirectory(prefix="agent-kit-new-pristine-") as temporary:
            selected = Path(temporary)
            for name in sorted(old):
                shutil.copytree(new[name], selected / new[name].relative_to(checkout / "skills"))
            previous = read_source(root)
            write_snapshot(root, selected, revision, date, repository)
            notice = root / "NOTICE"
            if notice.is_file():
                old_link = previous.get("repository", REPOSITORY) + "/tree/" + previous["revision"]
                notice.write_text(notice.read_text().replace(old_link, repository + "/tree/" + revision))
    adopted = sorted(set(new) - set(old))
    if adopted:
        print("New upstream skills, not adopted: " + ", ".join(adopted))
    return problems


SECTIONS = (LOCAL, UPSTREAM, Path("NOTICE"))


def input_fingerprint(root: Path) -> str:
    """Identity of all update inputs, including paths, file bytes and permissions."""
    for relative in (LOCAL, UPSTREAM):
        _validate_owned_tree(root, root / relative)
    notice = root / "NOTICE"
    if notice.is_symlink() or (notice.exists() and not notice.is_file()):
        raise ValueError("NOTICE must be a regular file")
    digest = hashlib.sha256()
    head = subprocess.run(["git", "-C", str(root), "rev-parse", "--verify", "HEAD"],
                          capture_output=True, check=False)
    digest.update(b"library-head\0" + (head.stdout.strip() if head.returncode == 0 else b"no-head") + b"\0")
    for relative in SECTIONS:
        folder = root / relative
        entries = [folder, *sorted(folder.rglob("*"))] if folder.is_dir() else [folder]
        for path in entries:
            kind = "directory" if path.is_dir() else "file" if path.is_file() else "absent"
            digest.update(str(path.relative_to(root)).encode() + b"\0" + kind.encode() + b"\0")
            if path.exists():
                digest.update(str(path.stat().st_mode & 0o777).encode() + b"\0")
            if path.is_file():
                digest.update(path.read_bytes())
            digest.update(b"\0")
    return digest.hexdigest()


def _copy_section(source: Path, destination: Path) -> None:
    if source.is_dir():
        shutil.copytree(source, destination)
    elif source.is_file():
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def review_fingerprint(local_input: str, repository: str, revision: str) -> str:
    """Bind the local state to the exact incoming immutable source."""
    payload = json.dumps([local_input, repository, revision], separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def _remove_owned(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def _apply_proposal(root: Path, proposal: Path, fingerprint: str) -> None:
    guard = root / ".upstream-update.lock"
    try:
        descriptor = os.open(guard, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise ValueError("another updater holds .upstream-update.lock; reconcile its owner before retrying") from None
    try:
        with os.fdopen(descriptor, "w") as stream:
            stream.write(str(os.getpid()) + "\n")
        # Materialize on the destination filesystem before the first replacement.
        transaction = Path(tempfile.mkdtemp(prefix=".upstream-apply-", dir=root))
        retain_recovery = False
        try:
            for relative in SECTIONS:
                _copy_section(proposal / relative, transaction / "new" / relative)
            if input_fingerprint(root) != fingerprint:
                raise ValueError("update inputs changed after preview; preview again")
            journal = []
            try:
                for relative in SECTIONS:
                    target, ready = root / relative, transaction / "new" / relative
                    backup = transaction / "old" / relative
                    row = {"target": target, "backup": backup, "old": False, "new": False}
                    journal.append(row)
                    if target.exists():
                        backup.parent.mkdir(parents=True, exist_ok=True)
                        os.replace(target, backup)
                        row["old"] = True
                    if ready.exists():
                        target.parent.mkdir(parents=True, exist_ok=True)
                        os.replace(ready, target)
                        row["new"] = True
            except BaseException as failure:
                rollback_errors = []
                for row in reversed(journal):
                    try:
                        if row["new"]:
                            _remove_owned(row["target"])
                        if row["old"]:
                            os.replace(row["backup"], row["target"])
                    except OSError as error:
                        rollback_errors.append(str(error))
                if rollback_errors:
                    retain_recovery = True
                    raise RuntimeError(f"rollback incomplete; recovery retained at {transaction}: " + "; ".join(rollback_errors)) from failure
                raise
        finally:
            if not retain_recovery:
                shutil.rmtree(transaction)
    finally:
        guard.unlink()


def _show_proposal(root: Path, proposal: Path, stat_only: bool) -> None:
    for relative in SECTIONS:
        old, new = root / relative, proposal / relative
        names = files(old) | files(new) if old.is_dir() or new.is_dir() else {""}
        for name in sorted(names):
            before, after = old / name if name else old, new / name if name else new
            a = before.read_bytes() if before.is_file() else b""
            b = after.read_bytes() if after.is_file() else b""
            a_mode = before.stat().st_mode & 0o777 if before.is_file() else None
            b_mode = after.stat().st_mode & 0o777 if after.is_file() else None
            if a == b and a_mode == b_mode:
                continue
            label = str(relative / name) if name else str(relative)
            print(f"CHANGE {label} ({a_mode!s} -> {b_mode!s})")
            if not stat_only:
                try:
                    print("".join(difflib.unified_diff(a.decode().splitlines(True), b.decode().splitlines(True),
                                                     fromfile="accepted/" + label, tofile="proposal/" + label)), end="")
                except UnicodeDecodeError:
                    print("Binary contents differ")


def update(root: Path, checkout: Path, revision: str, date: str, *, apply: bool = False,
           expected_input: str | None = None, repository: str = REPOSITORY, stat_only: bool = False) -> list[str]:
    root = root.resolve()
    fingerprint = input_fingerprint(root)
    reviewed = review_fingerprint(fingerprint, repository, revision)
    if apply and expected_input != reviewed:
        raise ValueError("update inputs changed after preview; use its --expected-input fingerprint")
    with tempfile.TemporaryDirectory(prefix="agent-kit-upstream-preview-") as temporary:
        proposal = Path(temporary)
        for relative in SECTIONS:
            _copy_section(root / relative, proposal / relative)
        problems = _merge_update(proposal, checkout, revision, date, repository)
        print("Input fingerprint: " + reviewed)
        print(f"Incoming: {repository} at {revision} ({date})")
        _show_proposal(root, proposal, stat_only)
        if problems:
            print("Conflicts in proposal only; accepted skills and baseline are unchanged.")
            return problems
        if apply:
            _apply_proposal(root, proposal, fingerprint)
            print("Applied the reviewed update. Run library checks and independent review before publication.")
        else:
            print("Preview only; skills and accepted baseline are unchanged.")
            print(f"Apply this SHA with --apply --expected-input {reviewed}")
    return []


def fetch(repository: str, revision: str, target: Path) -> tuple[str, str]:
    subprocess.run(["git", "clone", "--quiet", "--", repository, str(target)], check=True)
    subprocess.run(["git", "-C", str(target), "checkout", "--quiet", revision], check=True)
    output = subprocess.run(
        ["git", "-C", str(target), "log", "-1", "--format=%H %cs"], check=True, capture_output=True, text=True
    ).stdout.split()
    if output[0] != revision:
        raise ValueError("fetched revision does not match the requested immutable SHA")
    return output[0], output[1]


def main(argv: list[str], root: Path = ROOT) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    show = commands.add_parser("diff", help="show local adaptations against the pinned upstream copy")
    show.add_argument("skills", nargs="*")
    show.add_argument("--stat", action="store_true")
    merge = commands.add_parser("update", help="preview a three-way upstream update; apply only explicitly")
    merge.add_argument("revision")
    merge.add_argument("--repository", default=REPOSITORY)
    merge.add_argument("--apply", action="store_true")
    merge.add_argument("--expected-input", help="input fingerprint printed by the reviewed preview")
    merge.add_argument("--stat", action="store_true", help="show changed paths without full text diff")
    args = parser.parse_args(argv)

    if args.command == "diff":
        return diff(root, args.skills, args.stat)

    try:
        if any(os.environ.get(key) for key in ("GIT_DIR", "GIT_COMMON_DIR", "GIT_WORK_TREE")):
            raise ValueError("unset Git directory selectors before an upstream update")
        if not re.fullmatch(r"[0-9a-f]{40}", args.revision):
            raise ValueError("revision must be a full lowercase 40-character commit SHA")
        if args.apply and not args.expected_input:
            raise ValueError("--apply requires --expected-input from a reviewed preview")
        fingerprint = review_fingerprint(input_fingerprint(root.resolve()), args.repository, args.revision)
        if args.apply and args.expected_input != fingerprint:
            raise ValueError("update inputs changed after preview; preview again")
        if args.apply:
            dirty = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=root, check=True, capture_output=True, text=True,
            ).stdout
            if dirty:
                raise ValueError("commit or preserve pending library changes before applying an update")
        with tempfile.TemporaryDirectory() as temporary:
            revision, date = fetch(args.repository, args.revision, Path(temporary) / "upstream")
            problems = update(root, Path(temporary) / "upstream", revision, date, apply=args.apply,
                              expected_input=args.expected_input, repository=args.repository, stat_only=args.stat)
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"upstream: {error}", file=sys.stderr)
        return 1
    for problem in problems:
        print(problem, file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
