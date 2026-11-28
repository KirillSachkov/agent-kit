# Agent Kit

[English](README.en.md)

Agent Kit переносит рабочий процесс разработки в новый или существующий проект. Можно настроить весь набор практик или взять один скилл с его зависимостями. Когда агент вправе начать, какие проверки нужны и кто принимает результат, решает проект.

## Первая установка

Из рабочей копии Kit подставь путь к проекту и выбери полный SHA. Первая команда показывает состав и diff. Вторая применяет выбранный вариант.

```bash
kit_ref=$(git rev-parse HEAD)
python3 tools/setup.py --project /path/to/project --ref "$kit_ref"
python3 tools/setup.py --project /path/to/project --ref "$kit_ref" --apply
```

После установки новая сессия может прочитать инструкции проекта и объяснить, как взять первую задачу и где нужно решение владельца. Требуются Git и Python 3.11+. [Первый проект](docs/first-project.ru.md) · [Карта частей](docs/parts.ru.md)

Готовую ветку сдаёшь через `$deliver`: агент выполняет проверки и передаёт результат тебе на приёмку или завершает слияние по правилам проекта. Для готового тикета или спеки есть экспериментальный `$run-pipeline`: он ведёт работу от реализации до приёмки. [Два способа работы](experiments/factory/README.md)

## Выбрать отдельный скилл

```bash
python3 tools/skills.py select --project /path/to/project --ref "$kit_ref" --skill implement --apply
python3 tools/skills.py preview --project /path/to/project
python3 tools/skills.py install --project /path/to/project
python3 tools/skills.py check --project /path/to/project
```

Выбор показывает причину каждой зависимости. Например, `implement` включает `code-review`, а `grilling` можно поставить самостоятельно. [Каталог](skills/README.md) · [Версии, обновления и существующие копии](docs/distribution.md)

## Как устроен Kit

- [Эксперимент с фабрикой](experiments/factory/README.md): цепочка от готового тикета до PR без человека и её прогоны на трёх клиентах.
- [Модели для сессий и субагентов](docs/models.ru.md): откуда каждый клиент берёт модель.
- [Карта частей](docs/parts.ru.md) показывает восемь частей Kit, скиллы каждой и файлы проекта, которые они читают и пишут.
- [Инженерные скиллы](skills/README.md) задают процедуры.
- [Происхождение](docs/migration.md) описывает сохранённые истории Agent Harness и Agent Clarity. Для скиллов Matt Pocock сохранены лицензии, исходная ревизия и механизм сравнения адаптаций. [Обновление upstream](docs/upstream.ru.md)
- Команда `python3 scripts/check.py` проверяет каталог, целостность источников и поведение инструментов на временных проектах.
