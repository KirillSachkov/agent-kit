# Updating Matt's upstream without losing our adaptations

The engineering library retains Matt Pocock's pristine source at
`a496f5513d4a4cf889bc48e189e579f4b0bdf6aa`. It is packed under
`provenance/upstream/mattpocock`, outside skill discovery. `ship` is locally authored;
the rename map retains `ask-matt` → `ask` and
`setup-matt-pocock-skills` → `setup-project`. AI-first is a local engineering reference,
not a replacement upstream identity; see [the adaptation contract](engineering-contract.md).

## Compare the accepted baseline

```bash
python3 tools/upstream.py diff --stat
python3 tools/upstream.py diff implement code-review
```

These compare our editable folders with the accepted pristine baseline, including
supporting files. Never edit the archive, SOURCE or its hashes by hand.

## Preview an incoming revision

Choose a full immutable Matt commit SHA after reading its changes. A branch or tag
is not accepted. The update command clones that explicit source into temporary storage
and computes `old upstream + our adaptation + incoming upstream` with the existing
three-way merge core:

```bash
python3 tools/upstream.py update FULL_40_CHARACTER_MATT_SHA --stat
python3 tools/upstream.py update FULL_40_CHARACTER_MATT_SHA
```

Without `--apply`, the real skill tree, accepted archive, SOURCE and NOTICE remain
unchanged. The output gives changed paths/full text and an `Input fingerprint`.
It preserves file modes, supporting files, renames, local deletions and shape changes.
New upstream skills are listed, not automatically installed. A removed borrowed
skill needs a separate decision and stops the update without modifying the library.

Conflicts stay in the disposable proposal and printed diff. The command returns a
failure and does not advance the accepted baseline. Reconcile the adaptation on an
owned branch, preserving project authority; commit it and preview again. Do not copy
conflict markers into the accepted archive or claim an unresolved proposal was adopted.

## Apply the reviewed proposal

Commit or preserve pending library changes first. Re-run preview from that clean
revision, then use its exact SHA and fingerprint:

```bash
python3 tools/upstream.py update FULL_40_CHARACTER_MATT_SHA \
  --apply --expected-input FINGERPRINT_FROM_PREVIEW
```

The fingerprint binds the library revision, skill/provenance bytes, paths and modes,
and the exact incoming repository and SHA.
Changed inputs refuse application. A cooperating-updater lock excludes another
apply; a stale lock requires checking its owner, not automatic removal. Do not run
with `GIT_DIR`, `GIT_COMMON_DIR` or `GIT_WORK_TREE` selecting another checkout.

The complete proposal is prepared before replacing accepted sections. A write failure
restores the preceding sections. If restoration itself fails, recovery is retained
at the reported `.upstream-apply-*` path; resolve it before another update. There is
no OS sandbox against an unrelated writer racing those operations: use an owned,
idle checkout. This is not a crash-consistent database transaction.

Successful application updates the pristine archive, proof, actual source identity
and current NOTICE link together with the adapted skills. A deliberate `--repository`
override records that actual source; it is not silently attributed to Matt's URL.
Retain inherited licenses and historical source records.

## Verify, publish, then update consumers

Run library checks, inspect the complete adaptation diff, update the adaptation
record when its meaning changes, commit and obtain independent Standards/Spec review.
Publish only within the current assignment's authority. Each consumer then explicitly
selects that checked library SHA through [distribution](distribution.md), with its
own harness and checks. Home snapshots and project installations do not change when
the library's upstream baseline changes.

Retain [Matt's notice](../provenance/engineering/LICENSE.mattpocock),
[HumanLayer's notice](../provenance/engineering/LICENSE.humanlayer),
[PR credits](../skills/engineering/pr/CREDITS.md), the root MIT license and NOTICE.

## The pstack baseline

`create-verification-skill` comes from [pstack](https://github.com/backnotprop/pstack)
(MIT, Lauren Tan). Its pristine folder and license at the pinned revision are packed
in `provenance/upstream/pstack/create-verification-skill.tar.gz`; `SOURCE` beside it
records the repository, revision and archive hash, which `scripts/check.py` verifies.
`tools/upstream.py` covers Matt's skills only. To compare, unpack the archive into a
temporary directory and `diff -r` its `skills/create-verification-skill` against ours.
Our copy drops the feature-map and maintenance steps, adds a Report section to the
generated skill, and adds `agents/openai.yaml` and `LICENSE.pstack`. To adopt a newer revision, read its changes, repack the
archive from that revision, update `SOURCE`, reapply these three edits and review.
