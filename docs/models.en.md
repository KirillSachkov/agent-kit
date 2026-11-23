# Models for sessions and subagents

[Русский](models.ru.md)

The Kit does not choose models. This page shows where each client takes the model from, so a project can give, say, review to one model and implementation to another. Checked on 2026-11-23 against the clients' documentation and Codex CLI 0.171 and OpenCode 2.4 on one machine; the Codex rows come from its documentation only.

## Two levels

| Level | Who starts it | Where the model is set |
| --- | --- | --- |
| A session | you, or a program that runs the client without a window | the client's model flag |
| A subagent inside a session | the session, when a skill tells it to | the client's subagent definition |

A skill such as `code-review` starts its subagents inside the session that runs it. Nothing outside the client can choose their model. When the model of a piece of work must be guaranteed, run that work as a session of its own.

## Sessions

| | Claude Code | Codex | OpenCode |
| --- | --- | --- | --- |
| Run without a window | `claude -p "<prompt>" --model <model>` | `codex exec -m <model> "<prompt>"` | `opencode run -m <provider/model> "<prompt>"` |
| Invoke a skill in the prompt | `/name` | `$name` | `@name` |
| Reopen the session later | `claude --resume <id>` | `codex exec resume <id>` | `opencode run -s <id>` |

## Subagents

| | Claude Code | Codex | OpenCode |
| --- | --- | --- | --- |
| Definition | `.claude/agents/<name>.md` | `.codex/agents/<name>.toml` | `.opencode/agents/<name>.md` |
| Model field | `model` | `model` | `model` |
| One model for every subagent | `CLAUDE_CODE_SUBAGENT_MODEL` in the `env` of `settings.json` | `agents.default_subagent_model` in `config.toml` | none found |
| With nothing set | the parent's model | the parent's model | the parent's model |

In Claude Code a model named when the subagent is started wins over its definition, and the definition wins over the variable.

## Example: a reviewer on a chosen model

Claude Code, `.claude/agents/reviewer.md`:

```markdown
---
name: reviewer
description: Reviews a finished diff against the project's standards.
model: opus
---
Review the diff you are given. Report findings; change nothing.
```

Codex, `.codex/agents/reviewer.toml`:

```toml
name = "reviewer"
description = "Reviews a finished diff against the project's standards."
model = "<model>"
developer_instructions = "Review the diff you are given. Report findings; change nothing."
```

OpenCode, `.opencode/agents/reviewer.md`:

```markdown
---
description: Reviews a finished diff against the project's standards.
mode: subagent
model: <provider/model>
---
Review the diff you are given. Report findings; change nothing.
```

The Kit's skills start general subagents and do not name these definitions. To put all of a skill's subagents on one model, use the client's setting for every subagent.
