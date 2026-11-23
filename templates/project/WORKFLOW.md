# Workflow

Rules that connect the skills in this project. Each skill works without this file. Add a rule
here only when no skill can carry it.

- **Verify.** When the project requires it, run the project's `verify-<app>` skill once on the reviewed and corrected revision, before a PR is opened or a draft PR is marked ready. Check every acceptance criterion and record the action, the observation and the revision. A product failure or an unavailable environment keeps delivery open; record which one it was. Without a verify skill, ask the owner to run `create-verification-skill`.
