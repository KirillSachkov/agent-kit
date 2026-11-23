# Project instructions

Read [project settings](docs/agents/project-settings.md) for delivery, verification and the owner gate, and the [workflow](WORKFLOW.md) for the rules that connect skills here. When the settings file is missing, tell the user to run the `setup-matt-pocock-skills` skill.
A standalone question ends with its answer.
Before choosing tests, read the testing strategy the settings name and take the seam from it. When it has none for this kind of change, ask the owner once and record the answer there.
When a skill names another skill, load it with your client's skill mechanism, or read its `SKILL.md` when the client has none.
Human-invoked skills: @@human_invoked@@. They run only when the owner names them, so never read their files to follow them yourself. When one would be the next step, name its command and stop. The owner's approval answers the current step of the active skill and starts nothing else.
