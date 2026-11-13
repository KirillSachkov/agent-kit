# Agent Kit

[English](README.en.md)

Общая библиотека скиллов для Claude Code, Codex и других агентов, которые читают `SKILL.md`.
Здесь находятся инженерные процедуры, скиллы для объяснений и отчётов, пример проектного harness и установщик выбранных версий.

## Что где лежит

| Раздел | Что содержит |
| --- | --- |
| [skills/engineering](skills/README.md#engineering) | 28 скиллов для обсуждения, проектирования, реализации, проверки и доставки |
| [skills/communication](skills/README.md#communication) | Стиль, отчёты, настройка стиля; `explain` остаётся внутренней работой в процессе |
| [examples/agent-harness](examples/agent-harness/AGENTS.md) | Пример самостоятельных правил проекта: запуск работ, worktrees, проверки и приёмка владельцем |
| [tools/skills.py](tools/skills.py) | Выбор версии, просмотр diff, установка, проверка и принятие точных существующих копий под управление |
| [provenance](provenance/sources.json) | История источников, лицензии и замороженный upstream для сравнения |

Скилл определяет процедуру. Проект сохраняет собственные команды, правила доступа, проверки и merge/deploy gates. Для рабочего проекта выбирай нужный набор, а не весь каталог.

## Установка в проект

Нужны Git и Python 3.11 или новее. Сначала клонируй библиотеку и выбери её проверенный commit:

```bash
git clone https://github.com/KirillSachkov/agent-kit.git
cd agent-kit
git rev-parse HEAD
```

Подставь полученный полный SHA и путь проекта:

```bash
python3 tools/skills.py select --project /path/to/project --ref FULL_COMMIT_SHA --skill tdd --skill recap --client both --apply
python3 tools/skills.py preview --project /path/to/project
python3 tools/skills.py install --project /path/to/project
python3 tools/skills.py check --project /path/to/project
```

`select` без `--apply` показывает план. Существующие неуправляемые папки установщик сохраняет. Для точных копий есть отдельный `adopt`; изменённые версии сначала нужно сравнить и согласовать у владельца проекта. [Формат manifest и обновление](docs/distribution.md).

## Происхождение и эксперименты

Agent Kit объединяет публичные Agent Harness и Agent Clarity с сохранением обеих историй Git. Старые source commits и отдельные draft/research-ветки доступны под `history/agent-harness/*` и `history/agent-clarity/*`. [Перенос и границы](docs/migration.md).

Инженерная библиотека содержит адаптации скиллов Matt Pocock. Атрибуция и полные MIT notices сохранены в [NOTICE](NOTICE) и `provenance/engineering/`. [Обновление upstream](docs/upstream.md).

## Проверки

```bash
python3 scripts/check.py
```

Проверки используют синтетические проекты. Они не авторизуют сервисы и не подтверждают правильность результата, который агент получит при исполнении скилла в другом проекте.
