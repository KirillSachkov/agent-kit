# Testing

Use this file when specifying expected behavior, choosing TDD, implementing or delivering.
The task specifies the desired result. Use the applicable project checks to observe it.

## Boundaries, commands and working directories

@@checks@@

Setup inspects files without executing project commands. Record the exact command, directory,
revision and result after running a check. Record an unavailable service or missing tool as a
blocked check with the reason. A discovered command has no recorded result until it runs.

- Data and services: @@access@@
- During development: @@development_checks@@
- Before delivery: @@delivery_checks@@
- Required CI: @@ci@@
- Behavior: @@behavior@@
