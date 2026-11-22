# Project instructions

Read [project settings](docs/agents/project-settings.md) for the authorized start, working
context, practice choices and delivery authority. Before choosing tests for a spec or a
change, read the [testing strategy](@@testing_file@@).
When a skill names another skill, load it with your client's skill mechanism, or read its `SKILL.md` when the client has none.
Use the [workflow](WORKFLOW.md) to route a request, an accepted spec or a delivery handoff. A standalone question ends with its answer.
When the workflow hands a command to the owner, wait for the owner to invoke it before loading that skill, including by reading its file. An approval answers the current step of the already active skill.
