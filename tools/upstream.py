#!/usr/bin/env python3
"""Show local adaptations of Matt's skills and merge a new upstream revision into them.

The pristine upstream copy is packed under provenance/upstream/mattpocock and never edited by hand.
"""
from __future__ import annotations

import argparse
import filecmp
import contextlib
import gzip
import hashlib
import io
import json
import os
import re
import tarfile
import shutil
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


def write_snapshot(root: Path, skills: Path, revision: str, date: str) -> None:
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
    _atomic(root / UPSTREAM / "SOURCE", f"repository: {REPOSITORY}\nrevision: {revision}\ndate: {date}\nsha256: {identity(skills)}\n".encode())


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
        pinned = set(re.findall(r"mattpocock/skills/tree/([0-9a-f]{40})", notice.read_text()))
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


def same(left: Path, right: Path) -> bool:
    return filecmp.cmp(left, right, shallow=False)


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
    problems = []
    for path in sorted(files(old) | files(new) | files(local)):
        o, n, l = old / path, new / path, local / path
        name = f"{local.name}/{path}"
        if o.is_file() and n.is_file() and l.is_file():
            if same(o, n):
                continue
            if same(o, l):
                shutil.copy(n, l)
                continue
            labels = ["-L", "local", "-L", "old upstream", "-L", "new upstream"]
            code = subprocess.run(["git", "merge-file", *labels, l, o, n]).returncode
            if code > 127:
                problems.append(f"{name}: git merge-file failed (binary or unreadable file); local file kept")
            elif code:
                problems.append(f"{name}: conflict markers left in the file")
        elif n.is_file() and not o.is_file():
            if not l.is_file():
                l.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(n, l)
            elif not same(n, l):
                problems.append(f"{name}: added both upstream and locally; local file kept")
        elif o.is_file() and not n.is_file() and l.is_file():
            if same(o, l):
                l.unlink()
            else:
                problems.append(f"{name}: removed upstream but changed locally; local file kept")
        elif o.is_file() and n.is_file() and not same(o, n):
            problems.append(f"{name}: changed upstream but removed locally; not restored")
    return problems


def update(root: Path, checkout: Path, revision: str, date: str) -> list[str]:
    new = borrowed(checkout / "skills")
    with pristine_skills(root) as directory:
        old = borrowed(directory)
        missing = sorted(set(old) - set(new))
        if missing:
            raise SystemExit(f"skills missing upstream, nothing changed: {', '.join(missing)}")
        problems, local = [], local_names(root)
        for name in sorted(old):
            problems += merge_skill(old[name], new[name], root / LOCAL / local.get(name, name))
        with tempfile.TemporaryDirectory(prefix="agent-kit-new-pristine-") as temporary:
            selected = Path(temporary)
            for name in sorted(old):
                shutil.copytree(new[name], selected / new[name].relative_to(checkout / "skills"))
            write_snapshot(root, selected, revision, date)
    adopted = sorted(set(new) - set(old))
    if adopted:
        print("New upstream skills, not adopted: " + ", ".join(adopted))
    return problems


def fetch(repository: str, revision: str, target: Path) -> tuple[str, str]:
    subprocess.run(["git", "clone", "--quiet", repository, str(target)], check=True)
    subprocess.run(["git", "-C", str(target), "checkout", "--quiet", revision], check=True)
    output = subprocess.run(
        ["git", "-C", str(target), "log", "-1", "--format=%H %cs"], check=True, capture_output=True, text=True
    ).stdout.split()
    return output[0], output[1]


def main(argv: list[str], root: Path = ROOT) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    show = commands.add_parser("diff", help="show local adaptations against the pinned upstream copy")
    show.add_argument("skills", nargs="*")
    show.add_argument("--stat", action="store_true")
    merge = commands.add_parser("update", help="merge a new upstream revision into local skills")
    merge.add_argument("revision")
    merge.add_argument("--repository", default=REPOSITORY)
    args = parser.parse_args(argv)

    if args.command == "diff":
        return diff(root, args.skills, args.stat)

    dirty = subprocess.run(
        ["git", "status", "--porcelain", "--", str(LOCAL), str(UPSTREAM)], cwd=root, check=True, capture_output=True, text=True
    ).stdout
    if dirty:
        raise SystemExit("commit or preserve pending engineering/provenance changes before an update")
    with tempfile.TemporaryDirectory() as temporary:
        revision, date = fetch(args.repository, args.revision, Path(temporary) / "upstream")
        problems = update(root, Path(temporary) / "upstream", revision, date)
    print(f"Merged upstream {revision} ({date}). Review with: git diff -- skills/engineering provenance/upstream")
    print("Then update the current NOTICE snapshot link, catalogue hashes and adaptation notes; keep historical source records unchanged.")
    for problem in problems:
        print(problem, file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
