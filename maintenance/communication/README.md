# Communication skills

Сохранённая библиотека Agent Clarity стала разделом Agent Kit. Исходники находятся в `skills/communication/` корня; эта папка хранит проверки и пример глобальных инструкций.

| Скилл | Что делает |
| --- | --- |
| [plain-writing](../../skills/communication/plain-writing/SKILL.md) | Понятный текст для человека, общие правила и отдельный файл русского языка |
| [recap](../../skills/communication/recap/SKILL.md) | Отчёт о законченной работе со ссылками на результат и проверками |
| [setup-plain-writing](../../skills/communication/setup-plain-writing/SKILL.md) | Добавление согласованного блока в глобальные инструкции выбранных агентов |
| [explain](../../skills/communication/explain/SKILL.md) | Схемы по коду; скилл остаётся в работе и выбирается явно |

## Установка

Из корня Agent Kit выбери полный SHA текущего коммита и подготовь manifest для целевого проекта:

```bash
python3 tools/skills.py select --project /path/to/project --ref FULL_SHA --skill plain-writing --skill recap --skill setup-plain-writing --client both --apply
python3 tools/skills.py preview --project /path/to/project
python3 tools/skills.py install --project /path/to/project
python3 tools/skills.py check --project /path/to/project
```

`FULL_SHA` можно получить командой `git rev-parse HEAD`. Без `--apply` выбор только показывает план. Существующие точные копии сначала сверяют через команду `adopt`; изменённые копии установщик сохраняет для отдельного разбора.

После установки запусти `/setup-plain-writing`. Этот разговор выясняет язык и показывает блок глобальных инструкций, затем меняет только согласованные файлы. [Пример](docs/example-global-instructions.md) показывает блок рядом с личными настройками. Выбор и установка скилла не разрешает менять глобальные настройки автоматически.

Скиллы сохраняют формат Agent Skills. Generic `npx skills add` для нового layout пока не подтверждён; здесь документирован установщик Agent Kit.

## Проверки

Из корня Agent Kit:

```bash
python3 maintenance/communication/scripts/check.py
```

Проверка запускает прежние текстовые и rendering tests по новым путям. Рисование Mermaid требует Node, Chromium и playwright-core; эти зависимости не устанавливаются нашей миграцией. Готовый `recap` загружает Mermaid из CDN; `explain` встраивает схемы при сборке.

Сохранены MIT-лицензия, примеры, assets и история Git прежнего Agent Clarity. Его README до переноса доступен в [первоначальном публичном commit](https://github.com/KirillSachkov/agent-clarity/blob/a8b3f408ab5373667680b3622048eecfdf41c47f/README.md).
