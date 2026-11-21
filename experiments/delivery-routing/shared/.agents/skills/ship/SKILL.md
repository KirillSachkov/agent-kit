---
name: ship
description: Run the required delivery checks and carry out the authorized handoff.
---

Run `python3 service.py ci` for the PR. Diagnose and correct a reported packaging failure. Test the affected change using testing.md and run CI on the new candidate. Retain each disposition and revision. The merge action is `python3 service.py merge`.
