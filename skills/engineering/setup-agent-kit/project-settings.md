# Project settings

## Read by `ship`

- Delivery route: <local, main, pr, or the project's own rule>
- Delivery checks: <commands that must pass before delivery>
- Required CI: <checks that must be green on the PR head, or none>
- Owner gate: <owner: every delivery waits for the owner and the agent never merges | conditions: run `owner-gate` once before delivery against docs/agents/owner-gate.md; a status that needs no owner permits the merge | none: the agent may merge>

## Read at the verify step

- Verification: <when behaviour is verified>
- Verifier: <who verifies>

## Read by `pr`

- Evidence: <where evidence files go>

## Read when choosing tests

- Testing strategy: <docs/agents/testing.md, or the project's own document>

## Read by every skill: rules kept from the project

<each existing rule the owner kept where these skills do otherwise, with its file. Omit when there are none.>
