#!/usr/bin/env python3
"""Preview or apply a complete, pinned Agent Kit setup to a project directory."""
import argparse
from contextlib import contextmanager, redirect_stdout
from dataclasses import dataclass
import difflib
import hashlib
import io
import json
import os
from pathlib import Path
from urllib.parse import unquote
import re
import stat
import sys
import tempfile
import tomllib

import skills


KIT = Path(__file__).resolve().parents[1]
LOCK = ".agents/setup-lock.json"
MANIFEST = ".agents/skills-manifest.json"
TESTING = "docs/agents/testing.md"
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


TEST_GUIDE = re.compile(r"test|verification|quality|checks|тест|проверк|верификаци", re.I)
# A Markdown link or a named local document (including backtick paths) in agent instructions.
POINTER = re.compile(r"\[([^]\n]+)\]\((<[^>\n]+>|[^)\s]+)\)|`([^`\n]+)`|"
                     r"(?<![/:\w.-])(@?[\w./-]+\.(?:md|txt|rst|ya?ml))\b", re.I)


def local_pointers(project, source, content):
    for match in POINTER.finditer(content):
        label, href, quoted, plain = match.groups()
        target = unquote((href or quoted or plain).strip("<>").removeprefix("@").split("#")[0])
        if (not target or target.startswith(("/", "~")) or ":" in target or
                Path(target).suffix.lower() not in {".md", ".txt", ".rst", ".yaml", ".yml"}):
            continue
        for base in ((project / source).parent, project):
            path = Path(os.path.abspath(base / target))
            if not path.is_relative_to(project):
                continue
            name = path.relative_to(project)
            if ".git" in name.parts or name.parts[:2] in ((".agents", "skills"), (".claude", "skills")):
                continue
            if path.resolve() == path and path.is_file():
                yield str(name), bool(TEST_GUIDE.search(label or target))
                break


def find_sources(project, templates, lock, testing_file):
    docs = root_documents(project)
    policy = {}
    for name, data in docs.items():
        outside, _ = root_parts(data)
        if outside.strip():
            policy[name] = outside
    known = ("CONTRIBUTING.md", "docs/agents/delivery.md", "docs/agents/worktrees.md",
             "docs/agents/issue-tracker.md", "docs/agents/requirements.md",
             "docs/agents/verification.md", "docs/agents/verify.md", "docs/agents/owner-attention.md", ".cursorrules")
    fallback = ("TESTING.md", "testing.md", "docs/TESTING.md", "docs/testing.md", TESTING)
    managed = lock.get("files", {})
    if testing_file and ("\n" in testing_file or not read_optional(project, testing_file)):
        raise ERROR(f"Existing testing instruction unavailable: {testing_file}")
    sources = [*known, *fallback]
    if testing_file:
        sources.append(testing_file)
    for name in sources:
        if name not in managed:
            data = read_optional(project, name)
            if data:
                policy[name] = data.decode()
    pending = list(policy)
    candidates = []
    for source in pending:
        for name, testing in local_pointers(project, source, policy[source]):
            if name in managed or name in docs or name in ("AGENTS.md", "CLAUDE.md"):
                continue
            if testing and name.lower().endswith((".md", ".rst", ".txt")):
                candidates.append(name)
            if name not in policy:
                policy[name] = read_optional(project, name).decode()
                pending.append(name)
    testing = testing_file or next((name for name in (*candidates, *fallback) if name in policy), None)
    return docs, policy, testing or (TESTING if TESTING in templates else None)


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
                    "Choose their canonical instruction_owner in the decisions JSON.")
    else:
        owner = next(iter(docs), "AGENTS.md")
    return owner, delegates


def project_checks(project):
    checks = []
    package = read_optional(project, "package.json")
    if package:
        pkg = json.loads(package)
        manager = str(pkg.get("packageManager", "")).partition("@")[0]
        if manager not in ("npm", "yarn", "pnpm", "bun"):
            manager = next((m for lock, m in (("pnpm-lock.yaml", "pnpm"), ("yarn.lock", "yarn"),
                                             ("bun.lock", "bun")) if (project / lock).is_file()), "npm")
        for name, command in pkg.get("scripts", {}).items():
            if re.fullmatch(r"(test|check|lint|typecheck)(:[\w.-]+)?", name):
                checks.append(f"- `{manager} run {name}` from the project root ({name}, configured as `{command}` in package.json).")
    makefile = read_optional(project, "Makefile")
    if makefile:
        for target in re.findall(r"^(test|check|lint|verify|integration):", makefile.decode(), re.M):
            checks.append(f"- `make {target}` from the project root ({target} target in Makefile).")
    if read_optional(project, "scripts/check.py") is not None:
        checks.append("- `python3 scripts/check.py` from the project root (repository checks).")
    pyproject = read_optional(project, "pyproject.toml")
    if pyproject and "pytest" in tomllib.loads(pyproject.decode()).get("tool", {}):
        checks.append("- `python3 -m pytest` from the project root (configured pytest suite).")
    for name in ("tests", "test"):
        if (project / name).is_dir():
            checks.append(f"- Test sources in `{name}/`. Inspect the affected suite for its behavioral boundary.")
    for name in ("compose.yaml", "compose.yml", "docker-compose.yaml", "docker-compose.yml"):
        if read_optional(project, name) is not None:
            checks.append(f"- Service definitions in `{name}`. Confirm which services the affected checks use.")
    ci = {}
    for pattern in (".github/workflows/*.yml", ".github/workflows/*.yaml", ".gitlab-ci.yml",
                    ".circleci/config.yml", "Jenkinsfile"):
        for path in sorted(project.glob(pattern)):
            rel = path.relative_to(project).as_posix()
            data = read_optional(project, rel)
            if data is not None:
                ci[rel] = data.decode()
    return checks, ci


# These obligations conflict with the released workflow. Other project-specific instructions
# remain authoritative. Print actual source lines so the owner can resolve the divergence.
CONFLICTS = [
    (r"\b(verif(?:y|ication)|code.review)\b.{0,70}\b(after|again|repeat|rerun)\b.{0,50}\b(pr|ci|push|merge)\b",
     "The workflow completes local Verify before the PR and reuses it after CI fixes."),
    (r"\b(open|create|push|submit)\b.{0,40}\b(pull request|pr|draft)\b.{0,50}\b(before|immediately|first)\b",
     "The workflow opens a PR after the local evidence is ready."),
    (r"\b(repeat|rerun|new|fresh)\b.{0,50}\b(review|verif(?:y|ication))\b.{0,60}\b(every|after|each|ci|push|commit)\b",
     "The workflow runs one review and one required local Verify per delivery."),
    (r"\b(every|each|later|subsequent|ci)\b.{0,55}\b(commit|push|fix|edit|change)s?\b.{0,45}\b(fresh|repeat|rerun|new|renewed)\b.{0,22}\b(verify|verification|review)\b",
     "The workflow reuses the original local review and Verify after CI changes."),
    (r"(?:повтор\w*|заново|нов\w*)\s+(?:агентск\w*\s+)?(?:verify|верификаци\w*|ревью).{0,55}(?:после|при |кажд|CI)|"
     r"(?:после|кажд\w*)[^.!?]{0,70}(?:повтор\w*|заново|нов\w*)[^.!?]{0,25}(?:verify|верификаци\w*|ревью)",
     "The workflow reuses the completed local review and Verify after CI fixes."),
    (r"(?:откры\w*|созда\w*).{0,50}(?:PR|пулл.?реквест|черновик).{0,40}(?:\bдо\b|сразу|перед)|"
     r"(?:сразу|перед началом).{0,40}(?:откры\w*|созда\w*).{0,40}\bPR\b",
     "The workflow opens a PR after the local evidence is ready."),
    (r"\b(no|never|forbid|disable|do not use|must not use|don't use)\b.{0,30}\b(sub[ -]?agents?|reviewers?)\b",
     "The workflow uses parallel independent Standards and Spec reviewers."),
]


def conflicts(policy):
    found = []
    for name, content in policy.items():
        for line in re.split(r"[\n.!?]", content):
            if re.search(r"\b(do not|must not|never|avoid|without|no need to|don't)\s+(open|create|submit|repeat|rerun|run|reverify)\b", line, re.I):
                continue
            if re.search(r"(?:\bне\s+(?:нуж\w*|требу\w*|выполня\w*|повтор\w*|запуска\w*|откры\w*|созда\w*)|"
                         r"без повтор\w*|повтор\w*.{0,28}\bнет\b|"
                         r"(?:repeat|fresh|second|new).{0,40}(?:unnecessary|not required)|no (?:repeat|second|new))", line, re.I):
                continue
            for pattern, reason in CONFLICTS:
                if re.search(pattern, line, re.I):
                    found.append(f"{name}: {line.strip()}\n  {reason}")
                    break
    return found


@dataclass
class Edit:
    name: str
    before: bytes | None
    after: bytes


@dataclass
class SetupPlan:
    edits: list
    items: list
    changed: list
    skill_lock: dict
    link: tuple | None
    policy: dict
    checks: list
    ci: dict
    differences: list
    blocker: str | None

    def needs_link(self):
        return self.link and not self.link[1].is_symlink()


def project_choices(defaults, previous, overrides):
    options = previous | overrides
    unknown = set(options) - defaults.keys() - {"testing_file", "resolution", "instruction_owner"}
    if unknown:
        raise ERROR("Unknown decisions for this release: " + ", ".join(sorted(unknown)))
    for key, value in options.items():
        if key == "owner_attention":
            if type(value) is not bool:
                raise ERROR("owner_attention must be true or false")
        elif not isinstance(value, str) or not value.strip():
            raise ERROR(f"{key} must be nonempty text")
    choices = defaults | options
    if choices.get("delivery", "local") not in ("pr", "main", "local"):
        raise ERROR("delivery must be local, main or pr")
    if "instruction_owner" in options and options["instruction_owner"] not in ("AGENTS.md", "CLAUDE.md"):
        raise ERROR("instruction_owner must be AGENTS.md or CLAUDE.md")
    return options, choices


PR = r"(?:pull requests?|PRs?)\b"
NEGATION = r"(?:never|do not|must not|don't|cannot|no|without)\s+"
PR_ACTION = r"(?:(?:open|create|submit|use|require)\s+)?(?:an? |the |draft )*"
CLASSIFIER = r"\b(?:owner[- ]attention(?: classification| classifier)?|owner classifier)\b"
DISABLED = r"(?:disabled?|off|optional and disabled|not (?:enabled|required)|never run|do not (?:use|run))"
ENABLED = r"(?:enable[ds]?|on|require[ds]?|mandatory|must run|must use|always run|run|use)"


def policy_constraints(line):
    """Recognize explicit, unconditional choices, keeping each source sentence as evidence."""
    prohibited = re.search(r"\b" + NEGATION + PR_ACTION + PR, line, re.I)
    if prohibited:
        if not re.search(r"\b(before|until|without|unless)\b", line[prohibited.end():], re.I):
            yield "delivery", {"local", "main"}
    elif re.search(r"\b(via|through|requires?|open|submit|create|use)\s+(?:an? |the |draft )*" + PR
                   + r"|\b(?:delivery route|delivery)\s*:\s*pr\b", line, re.I):
        yield "delivery", {"pr"}
    if re.search(r"\b(?:deliver(?:y)?|land|commit)\s+(?:directly\s+)?(?:on|to|in|via)\s+"
                 r"(?:the\s+)?main\b|\b(?:delivery route|delivery)\s*:\s*main\b", line, re.I):
        yield "delivery", {"main"}
    if re.search(r"\b(?:keep|deliver|delivery)\b.{0,38}\blocal(?:ly)?\b(?:\s+only)?\s*$|"
                 r"\b(?:delivery route|delivery)\s*:\s*local\b", line, re.I):
        yield "delivery", {"local"}
    if re.search(r"\bno owner[- ]attention (?:classifier|classification)\b", line, re.I):
        yield "owner_attention", {False}
        return
    for indicator, enabled in ((DISABLED, False), (ENABLED, True)):
        if re.search(CLASSIFIER + r"\s*(?::|is|must be|=)?\s*" + indicator + r"\b|"
                     r"\b" + indicator + r"\s+(?:the |an? )?" + CLASSIFIER, line, re.I):
            yield "owner_attention", {enabled}
            break


def reconcile(project, policy, ci, options, choices):
    if ci and "ci" not in options:
        choices["ci"] = "Found " + ", ".join(f"`{path}`" for path in ci) + ". Confirm required jobs and delivered revision with the project before delivery."
    if (project / ".github/ISSUE_TEMPLATE").is_dir() and "tracker" not in options:
        choices["tracker"] = "Use the assigned issue and the project's .github/ISSUE_TEMPLATE conventions."
    material = conflicts(policy | ci)
    constraints = {}
    for name, body in policy.items():
        for line in re.split(r"[\n.!?;]", body):
            for key, allowed in policy_constraints(line):
                constraints.setdefault(key, []).append((f"{name}: {line.strip()}", allowed))
    missing = []
    for key, rules in constraints.items():
        if key not in choices:
            continue
        permitted = set.intersection(*(values for _, values in rules))
        if key not in options and len(permitted) == 1:
            choices[key] = next(iter(permitted))
        if choices[key] not in permitted:
            if key not in options:
                missing.append(key)
            for source, allowed in rules:
                if key in missing or choices[key] not in allowed:
                    material.append(f"{source}\n  Selected {key}: {json.dumps(choices[key])}.")
    for key, words in (("start", "authorization to start|implementation starts|start rule"),
                       ("language", "language"), ("access", "credentials|service access"),
                       ("publication", "merge authority|deploy permission|publication authority|authorization"),
                       ("acceptance", "acceptance|owner approval"), ("ci", r"required checks|required CI|CI policy"),
                       ("evidence", "evidence requirements"), ("cleanup", "cleanup|retire worktrees"),
                       ("worktree", "worktree"), ("verifier", "independent verif|fresh verifier"),
                       ("tdd", "TDD|test.driven"), ("tracker", "issue tracker|tracker operations")):
        existing = [name for name, body in policy.items() if re.search(words, name + "\n" + body, re.I)]
        if existing and key not in options:
            choices[key] = "Follow " + ", ".join(f"`{name}`" for name in existing) + "."
    return material, missing


def build_plan(project, ref, client, options):
    templates = pinned_templates(ref)
    old_state = read_optional(project, LOCK)
    state = json.loads(old_state) if old_state else {}
    if old_state is not None and (state.get("schema_version") != 1 or not isinstance(state.get("files"), dict)):
        raise ERROR(f"Invalid setup lock: {LOCK}")
    previous = state.get("decisions", {})
    defaults = json.loads(templates.pop("defaults.json", b"{}"))
    options = dict(options)
    agreement = options.pop("conflict_id", None)
    options, choices = project_choices(defaults, previous, options)
    docs, policy, testing = find_sources(project, templates, state, choices.get("testing_file"))
    checks, ci = project_checks(project)
    material, missing = reconcile(project, policy, ci, options, choices)
    if defaults and "WORKFLOW.md" not in templates:
        raise ERROR(f"Missing pinned workflow template at {ref}")
    signature = sha(encoded(material))
    recorded = signature == state.get("conflicts") and options.get("resolution") == previous.get("resolution")
    current_resolution = agreement == signature if agreement is not None else recorded
    blocker = None
    if material and not (options.get("resolution") and current_resolution):
        blocker = ("Resolve the displayed process conflict before --apply. Record the agreed 'resolution' "
                   f"and this conflict_id in the decisions JSON: {signature}")
    if missing:
        blocker = "Choose " + ", ".join(missing) + " in the decisions JSON and preview the differences again."
    details = dict(choices)
    details["sources"] = ("Existing instructions: " + ", ".join(f"`{f}`" for f in policy) + "."
                          if policy else "No prior project policy was discovered.")
    details["testing_file"] = "<" + testing + ">" if testing and " " in testing else testing or ""
    details["checks"] = "\n".join(checks) or "No local test command or test directory was discovered."
    details["resolution"] = "Project resolution: " + options["resolution"] if "resolution" in options else ""
    conditions = [name for name, body in policy.items()
                  if re.search(CLASSIFIER, name + "\n" + body, re.I)
                  and re.search(r"\b(status(?:es)?|conditions|decision rules)\b", body, re.I)]
    condition_refs = ", ".join(f"`{name}`" for name in conditions) or "[owner attention conditions](owner-attention.md)"
    details["owner_attention"] = (f"Enabled. Apply {condition_refs} once after technical checks."
                                  if choices.get("owner_attention") else "Disabled.")
    edits = []
    managed = dict(state.get("files", {}))
    def add(name, before, after):
        skills.safe_path(project, name)
        if before != after:
            edits.append(Edit(name, before, after))
    roots = dict(state.get("roots", {}))
    canonical, delegates = instruction_owner(project, docs, state.get("instruction_owner"), choices.get("instruction_owner"))
    catalog_dir = KIT / "skills"
    catalog = skills.read_json(catalog_dir / "catalog.json")
    manifest = skills.select_manifest(project, catalog, catalog_dir, "agent-kit", ref, None, client)
    items, skill_lock, _ = skills.plan(project, catalog, catalog_dir, manifest=manifest)
    changed = skills.preflight_changed(project, items, skill_lock)
    link = skills.client_discovery(project, manifest)
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
        if name == TESTING and name != testing:
            continue
        if defaults and ((name.startswith(".github/") and choices["delivery"] != "pr") or
                         (name.endswith("/owner-attention.md") and (not choices["owner_attention"] or conditions))):
            continue
        before = read_optional(project, name)
        after = render(raw, details)
        if name not in managed and before is not None:
            if name in (TESTING, "evidence-manifest.json", ".github/pull_request_template.md",
                        "docs/agents/owner-attention.md"):
                continue
            raise ERROR(f"Unmanaged project document already exists: {name}")
        if name in managed and (before is None or sha(before) != managed[name]):
            raise ERROR(f"Reconcile locally changed starter document: {name}")
        add(name, before, after)
        managed[name] = sha(after)
    add(MANIFEST, read_optional(project, MANIFEST), encoded(manifest))
    state = dict(schema_version=1, ref=ref, decisions=options, roots=roots,
                 instruction_owner=canonical, files=managed, conflicts=signature)
    add(LOCK, old_state, encoded(state))
    return SetupPlan(edits, items, changed, skill_lock, link, policy, checks, ci, material, blocker)


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
                staged.write_bytes(edit.after)
                if edit.before is not None:
                    mode = stat.S_IMODE(target.stat().st_mode)
                    staged.chmod(mode)
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


def describe(result, project):
    for name, content in result.policy.items():
        print(f"Existing project instructions ({name}):\n{content.strip()}")
    for fact in result.checks:
        print(fact)
    if result.ci:
        print("CI configurations found: " + ", ".join(result.ci))
    for message in result.differences:
        print("Project workflow difference: " + message)
    print("Selected skills and activation conditions:")
    for entry, _, _, files in result.items:
        print(f"  {entry['skill']}: " + skills.skill_description(files["SKILL.md"][0]))
    for edit in result.edits:
        print("".join(difflib.unified_diff((edit.before or b"").decode().splitlines(True),
                                          edit.after.decode().splitlines(True),
                                          fromfile="current/" + edit.name, tofile="selected/" + edit.name)), end="")
    skills.preview(result.changed)
    if result.changed:
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
    if result.blocker:
        print(result.blocker)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, type=Path, help="existing project directory (may be empty)")
    parser.add_argument("--ref", required=True, help="full locally available Agent Kit commit SHA")
    parser.add_argument("--client", choices=("codex", "claude", "both"), help="project skill discovery clients")
    parser.add_argument("--decisions", type=Path, help="JSON object of project choices overriding release defaults")
    parser.add_argument("--apply", action="store_true", help="write the complete setup after preflight")
    args = parser.parse_args(argv)
    try:
        project = args.project.resolve(strict=True)
        if not project.is_dir():
            raise ERROR("--project must be an existing directory")
        guard = skills.safe_path(project, ".agents/skills-sync.lock")
        if guard.exists():
            raise ERROR("Another installation holds skills-sync.lock; reconcile its owner before retrying")
        options = skills.read_json(args.decisions) if args.decisions else {}
        result = build_plan(project, args.ref, args.client, options)
        describe(result, project)
        if result.blocker:
            return 1
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
                latest = build_plan(project, args.ref, args.client, options)
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
