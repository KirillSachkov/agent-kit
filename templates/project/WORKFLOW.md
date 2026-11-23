# Workflow

Rules that connect the skills in this project. Each skill works without this file. Add a rule
here only when no skill can carry it.

- **Verify.** When the [project settings](docs/agents/project-settings.md) call for verification, the verifier they name runs the project's `verify-<app>` skill once on the reviewed revision and checks every acceptance criterion. This comes before delivery: before `ship`, or before a draft PR is marked ready. A `FAIL` or `BLOCKED` verdict keeps delivery open. Without a verify skill, ask the owner to run `create-verification-skill`.
