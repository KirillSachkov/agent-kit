# Agent Kit workflow

## Choose the requested work

- **Discuss or investigate.** Return the decision, diagnosis or observations. An issue reference identifies the subject.
- **Prepare a spec.** The owner invokes `to-spec`. Read back the saved spec before linking it. When the owner accepts it, hand back the next command: `$to-tickets <spec>`. If the owner invokes it in the acceptance message, begin the breakdown immediately.
- **Prepare tickets.** In `to-tickets`, propose the slices and dependencies. On approval, save the agreed tickets in the configured tracker, verify their references and show the ready tickets. This completes planning.
- **Implement.** Take one assigned issue directly with `implement`. For an entire spec, a separate assignment starts `implement-spec` against its published ticket graph. Apply the project's start rule. A ready ticket, an accepted spec and approval to publish tickets each describe planning state.
- **Stop or resume.** Use the assigned endpoint, bounded by project authority. “Stop before review” returns the tested change and its review base. A standalone `code-review` returns the findings. A request to deliver resumes from the recorded handoff through the configured local or PR route.

Read the project settings for the tracker, start rule and delivery authority.

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
    G --> Q["Вызвать to-tickets"]
    Q --> N["Согласовать тикеты"]
    N --> P["Записать тикеты"]
    P --> H{"Есть поручение?"}
    H -->|Нет| W["Ждать поручения"]
    F -->|Нет| H
    H -->|Разрешён| I["Реализовать"]
    I --> J["Запустить тесты"]
    J -->|Ошибка| I
    J -->|Прошли| K{"До ревью?"}
    K -->|Стоп| X["Передать diff"]
    K -->|Продолжить| R["Подготовить ревью"]
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
