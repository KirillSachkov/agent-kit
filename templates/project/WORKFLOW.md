# Agent Kit workflow

These maps show the available routes. The project's root instructions select the start rule, tests, Verify scenarios, delivery mode and owner decisions.

On a narrow display, pan or expand each diagram to read it at its natural size.

## От запроса до ревью

```mermaid
---
config:
  flowchart:
    useMaxWidth: false
    nodeSpacing: 16
    rankSpacing: 28
---
flowchart TD
    A["Запрос"] --> B{"Цель ясна?"}
    B -->|Нет| C["Уточнить цель"]
    C --> B
    B -->|Да| D{"Что нужно?"}
    D -->|Ответ| E["Дать ответ"]
    D -->|Изменение| F{"Нужна спека?"}
    F -->|Да| G["Согласовать спеку"]
    G --> H["Проверить старт"]
    F -->|Нет| H
    H -->|Разрешён| I["Реализовать"]
    I --> J["Запустить тесты"]
    J -->|Ошибка| I
    J -->|Прошли| K["Подготовить diff"]
```

## От ревью до сдачи

```mermaid
---
config:
  flowchart:
    useMaxWidth: false
    nodeSpacing: 16
    rankSpacing: 28
---
flowchart TD
    R["code-review"] --> A["Standards"]
    R --> B["Spec"]
    A --> C{"Есть замечания?"}
    B --> C
    C -->|Да| F["Внести правки"]
    F --> T["Запустить тесты"]
    T -->|Прошли| V
    C -->|Нет| V{"Нужен Verify?"}
    V -->|Да| L["Локальный Verify"]
    L -->|Дефект или блокер| X["Критерий открыт"]
    L -->|Прошёл| S["ship"]
    V -->|Нет| S
    S --> P{"Как сдаём?"}
    P -->|main| J["Проверки проекта"]
    P -->|PR| O["Открыть PR"]
    O -->|Нужен CI| W["Дождаться CI"]
    O -->|Без CI| M
    W -->|Прошёл| M
    W -->|Ошибка| D{"Причина?"}
    D -->|Дефект| U["Правка и тесты"]
    U --> PUSH["Отправить в PR"]
    PUSH --> W
    D -->|Сбой среды| H["Один повтор CI"]
    H -->|Прошёл| M
    H -->|Снова сбой| DI["Разобрать лог"]
    DI -->|Есть решение| U
    DI -->|Нужна помощь| Z["Сообщить блокер"]
    D -->|Нужна помощь| Z
    J -->|Прошли| M{"Классификатор?"}
    M -->|Включён| N["Оценить поставку"]
    N --> G["Пройти приёмку"]
    M -->|Выключен| G
    G -->|Разрешено| I["Сдать работу"]
    I --> K["Сверить версию"]
```

A delivery is one PR or one main-checkout handoff. Grouped tickets share a review. Verify records the local revision. CI records the final revision and the changes between them. Keep a failed required check open.
