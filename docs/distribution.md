# Pinned distribution

Use Git and Python 3.11 or later. The installer is independent of the agent client. It never fetches, updates global installations or changes project authority implicitly.

## Select a version

Run from this library's checkout with a known full commit SHA:

```bash
python3 tools/skills.py list
python3 tools/skills.py select --project /path/to/project --ref FULL_COMMIT_SHA --skill tdd --skill recap --client both
python3 tools/skills.py select --project /path/to/project --ref FULL_COMMIT_SHA --skill tdd --skill recap --client both --apply
```

Selection records `.agents/skills-manifest.json`. There is no implicit entire-library selection. The internal `explain` skill requires explicit selection. `--client both` uses the project's canonical `.agents/skills` index and a Claude alias; conflicting client folders are preserved and stop the change.

```json
{
  "schema_version": 1,
  "installation": "copies",
  "skills": [
    {
      "provider": "agent-kit",
      "ref": "FULL_40_CHARACTER_COMMIT_SHA",
      "skill": "tdd",
      "destination": ".agents/skills/tdd"
    }
  ]
}
```

## Preview, install, adopt, check

```bash
python3 tools/skills.py preview --project /path/to/project
python3 tools/skills.py install --project /path/to/project
python3 tools/skills.py check --project /path/to/project
```

Preview shows complete textual, binary and mode differences without creating files or locks. Installation copies entire folders, including references, scripts, assets, native metadata and license notices. A content lock records the chosen source and installed bytes in `.agents/skills-lock.json`.

An existing unmanaged directory is not silently replaced. For a verified exact source copy, use the separate explicit command:

```bash
python3 tools/skills.py adopt --project /path/to/project
```

Adoption compares the complete folder and executable modes with its pinned source before adding management metadata and notices. A changed, added or missing file stops the selected batch. A matching name or SKILL.md alone is insufficient. Keep intentional project adaptations owned by the project until their complete diff and policy implications are reconciled.

Updates require a new explicit SHA selection. Installed local edits stop installation; there is no force-overwrite option. The previous copy and lock are retained in `.agents/skills-backups/`. Restore them together in the authorized idle checkout after preserving later edits. Removing a manifest selection does not delete an installed folder.

## Sources and scope

The catalog maps skill names to source folders. Current-working-tree edits do not change the Git revision selected by an installation. A consumer can also use verified grouped snapshots through `snapshot_paths`, `snapshot_ref` and per-folder SHA-256 identities. Those snapshots work without a provider checkout.

The digest includes sorted relative paths, Git executable modes and bytes. Provider notices are part of the installed lock. Identity checks do not establish the correctness of a skill or an agent's output.

Installation preflights selected destinations and refuses unsafe paths, symlinks, submodules, special files, unmanaged copies and local edits. A cooperating-installer lock excludes parallel writers. This does not sandbox an adversarial process changing directories concurrently; use the project's assigned idle checkout.

Source-linked library discovery is checked separately from installed copies. The installer refuses to replace source-link destinations. Skills remain procedures; the target project's requirements, commands, permissions and delivery gates remain in its own instructions.
