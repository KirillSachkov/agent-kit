---
name: code-review
description: Review the candidate snapshot against project standards and the ticket.
---

Run `python3 service.py review` once. The adapter fans out Standards and Spec in parallel on one snapshot and returns both findings and their revision. Return both to the author.
