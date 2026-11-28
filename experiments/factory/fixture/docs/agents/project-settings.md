# Project settings

## Read before implementing

- Workplace: worktree: implementation never starts on the base branch of the main checkout

## Read by `deliver`

- Delivery route: pr
- Delivery checks: `python3 -m unittest discover -s tests -q`
- Required CI: the `ci` check on the PR head must be green
- Owner gate: owner: every delivery waits for the owner and the agent never merges

## Read at the verify step

- Verification: verify when user-visible behaviour changes or the task has key scenarios
- Verifier: a fresh agent that did not write the change
- Verification report: `.evidence/`

## Read by `pr`

- Evidence: this host has no attachments; cite command output as text

## Read when choosing tests

- Testing strategy: docs/agents/testing.md
