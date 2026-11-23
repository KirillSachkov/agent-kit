# Модели для сессий и субагентов

[English](models.en.md)

Kit не выбирает модели и не ставит в проект описаний субагентов. Эта страница показывает, откуда каждый клиент берёт модель, чтобы проект мог, например, отдать ревью одной модели, а реализацию другой. Проверено 23 ноября 2026 года по документации клиентов. Строки о сессиях проверены ещё и на Codex CLI 0.171 и OpenCode 2.4; строки о субагентах взяты только из документации.

## Два уровня

| Уровень | Кто запускает | Где задаётся модель |
| --- | --- | --- |
| Сессия | ты или программа, которая запускает клиент без окна | флаг модели у клиента |
| Субагент внутри сессии | сама сессия, когда так велит скилл | описание субагента в клиенте |

Скилл вроде `code-review` запускает субагентов внутри сессии, которая его выполняет. Снаружи клиента выбрать их модель нельзя. Если модель для какой-то работы должна быть гарантирована, эту работу запускают отдельной сессией.

## Сессии

| | Claude Code | Codex | OpenCode |
| --- | --- | --- | --- |
| Запуск без окна | `claude -p "<запрос>" --model <модель>` | `codex exec -m <модель> "<запрос>"` | `opencode run -m <провайдер/модель> "<запрос>"` |
| Вызов скилла в запросе | `/имя` | `$имя` | `@имя` |
| Открыть сессию позже | `claude --resume <номер>` | `codex exec resume <номер>` | `opencode run -s <номер>` |

## Субагенты

| | Claude Code | Codex | OpenCode |
| --- | --- | --- | --- |
| Описание | `.claude/agents/<имя>.md` | `.codex/agents/<имя>.toml` | `.opencode/agents/<имя>.md` |
| Поле модели | `model` | `model` | `model` |
| Одна модель для всех субагентов | `CLAUDE_CODE_SUBAGENT_MODEL` в `env` файла `settings.json` | `agents.default_subagent_model` в `config.toml` | не нашлось |
| Если ничего не задано | модель родителя | модель родителя | модель родителя |

В Claude Code модель, названная при запуске субагента, сильнее его описания, а описание сильнее переменной.

## Пример: ревьюер на выбранной модели

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

Скиллы Kit запускают обычных субагентов и не называют эти описания. Чтобы перевести всех субагентов скилла на одну модель, используй настройку клиента для всех субагентов.
