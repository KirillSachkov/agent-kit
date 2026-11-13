# Bootstrap verification

The initial independent Standards and Spec reviews covered `0e499bdcb5d31f91405c014ee624537773b1032b..febb56e613025a2310dc67da17c3557e6a864747`. Corrections were reviewed at `59dfed423e26aad86b0c0156cd2f93ebd7ddb133` and `b0570c6006289437cd587a362d26b4594c987e26`. Both axes closed with no open findings at the last code head.

## Corrections

Upstream maintenance now preserves executable changes and local adaptations during file/directory transitions. Local deletions survive shape changes with a conflict diagnostic. Symlinks and special files are refused before a selected batch writes anything. Cleanup removes only confirmed unchanged empty baseline directories that disappeared upstream.

Ten regression cases were added across these corrections. The 27 combinations of absent/file/directory baseline, local and incoming paths were checked independently. Arbitrary operating-system I/O interruption and adversarial concurrent modification are outside that matrix; this tool is not a filesystem sandbox.

## Evidence

- `python3 scripts/check.py` passes: 50 unit cases, the 28-skill harness example's structural checks and the communication checker/build tests.
- Upstream's 27 tests also pass with the system Python on the maintainer's Mac.
- A real temporary consumer selected, previewed, installed and checked all 32 skills at the first canonical commit. It received 245 files, including 128 provider notice files. Its pre-existing AGENTS.md was unchanged.
- The internal `explain` skill was explicitly selected for that smoke test; it remains internal in the catalog.
- All 17 original source commit objects and four history refs are present. Canonical skill changes are limited to the documented path/attribution fixes; source licenses and the historical README are preserved byte-for-byte.
- The public tree contains the two public source histories and generic distribution tooling. Private project inventories, account configuration and personal wiki data are not part of this repository.

The [public bootstrap CI](https://github.com/KirillSachkov/agent-kit/actions/runs/43432432388) passed on published commit `5ee5fbb61fb10876f916afce786abfdd52987664`. Both original source repositories were verified archived on 2026-11-13. Client discovery and consumer adoption have their own operational receipts; these tests do not claim every external installation has upgraded. See [migration](migration.md) for the publication and archival outcome.
