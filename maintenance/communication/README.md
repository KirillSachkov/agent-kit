# Communication skills

В Agent Kit остался [`recap`](../../skills/communication/recap/SKILL.md) для отчётов о законченной работе. В этой папке лежат проверки и [пример глобальных инструкций](docs/example-global-instructions.md).

## Установка

Из корня Agent Kit выбери полный SHA текущего коммита и подготовь manifest для целевого проекта:

```bash
python3 tools/skills.py select --project /path/to/project --ref FULL_SHA --skill recap --client both --apply
python3 tools/skills.py preview --project /path/to/project
python3 tools/skills.py install --project /path/to/project
python3 tools/skills.py check --project /path/to/project
```

`FULL_SHA` можно получить командой `git rev-parse HEAD`. Без `--apply` выбор только показывает план. Существующие точные копии сначала сверяют через команду `adopt`; изменённые копии установщик сохраняет для отдельного разбора.


Скиллы сохраняют формат Agent Skills. Generic `npx skills add` для нового layout пока не подтверждён; здесь документирован установщик Agent Kit.

## Проверки

Из корня Agent Kit:

```bash
python3 maintenance/communication/scripts/check.py
```

Проверка сверяет frontmatter скиллов и локальные ссылки. Готовый `recap` загружает Mermaid из CDN.

Сохранены MIT-лицензия, примеры, assets и история Git прежнего Agent Clarity. Его README до переноса доступен в [первоначальном публичном commit](https://github.com/KirillSachkov/agent-clarity/blob/a8b3f408ab5373667680b3622048eecfdf41c47f/README.md).
