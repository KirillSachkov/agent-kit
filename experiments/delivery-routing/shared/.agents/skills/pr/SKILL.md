---
name: pr
description: Create the local PR and present actual delivery evidence.
---

Use `python3 service.py open` to open the local PR. To update the same PR after classification, use `python3 service.py report --status STATUS --reviewed REVIEW_REV --verified VERIFY_REV --candidate FINAL_CI_REV --note TEXT`. Explain any changes since Verify, the CI outcome and the concrete owner action if needed.
