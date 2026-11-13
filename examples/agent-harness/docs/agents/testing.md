# Verification

This repository currently contains Markdown, skill metadata, client pointers, a structural checker and an upstream merge script.
It has no product runtime, application tests or live-agent evaluation suite.

## Commands

Run from the repository root:

- `python3 scripts/check.py`: local Markdown links/anchors, canonical skill names and invocation metadata, the frozen upstream digest and client pointers.
- `python3 -m unittest discover -s ../../tests`: shared regression tests for upstream maintenance and the example client pointers, when run from this example directory.
- `git diff --check`: whitespace errors in the change.

Before a PR, run all three commands and report their actual results.
Root Agent Kit CI invokes the shared checks on the PR result. The original example used the job name `harness-check`; repository protection settings are separate from the written process.

## Appropriate evidence

For documentation or metadata changes, run structural checks and obtain independent review.
Check English/Russian meaning and owner actions during review; a link checker cannot do that.
For changed checker behavior, exercise a clean fixture and a fixture that should fail.
Record the observed failure and successful result rather than adding tests for prose wording.
For new executable behavior, add suitable regression tests as part of that issue.

Read proposed comparisons in `docs/experiments.en.md` or `docs/experiments.ru.md` when an experiment is assigned.
Record client/model, source revision, task, expected result, actual outcome and limits.
Keep private transcripts outside the public repository.
A static pass does not establish live-agent adherence, semantic translation parity or product correctness.
