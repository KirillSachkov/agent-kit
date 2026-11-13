---
title: Interview Sensei как устроен скелет
task: ветка `spec/17-skeleton` · коммит `1f3140b`
---
Локальное приложение: кандидат открывает его в браузере, а сервер запускает его собственного агента и ведёт с ним разговор.

## Браузер говорит только с сервером, агент работает отдельным процессом на каждую сессию
```mermaid
flowchart LR
  B[Браузер · вкладка] <-->|HTTP, WebSocket| S
  subgraph S[Сервер · Node, Fastify]
    SE[Сессии агентов] -->|запусти агента| RT[Запуск агентов]
    SE -->|открой адрес| MCP[MCP-шлюз]
    T[Копия базы · таймер 5 мин]
  end
  RT -->|запускает, ACP| A[Агент кандидата]:::external
  A -->|вызывает инструменты| MCP
  SE -->|пишет журнал| DB[(PGlite · sessions, events)]
  T -->|пишет копию| F[(~/.interview-sensei)]
```
Фичи `agent-sessions`, `agent-runtime` и `mcp-gateway` живут внутри процесса сервера; агент отдельный процесс на каждую сессию.

## Фичи core импортирует только composition.ts
```mermaid
flowchart LR
  subgraph server[apps/server]
    R[run-server] --> SV[server]
    SV --> RT[session-routes] & MC[mcp.ts] & LC[lifecycle]
    RT & MC & LC --> C[composition.ts]
  end
  subgraph core[packages/core · фичи]
    AS[agent-sessions]
    AR[agent-runtime]
    MG[mcp-gateway]
    HE[health]
  end
  subgraph shared[core · shared]
    ST[storage]
    TM[time]
    SK[session-kinds]
  end
  C --> AS & AR & MG & HE
  C --> ST & TM & SK
  R --> ST & TM
  RT --> SK
  core -->|берут общее| shared
```
Построено из импортов ветки. Правило `server-composes-features-in-one-module` пускает к фичам core только `composition.ts`; общие модули `storage`, `time` и `session-kinds` открыты каждому файлу сервера. [[apps/server/.dependency-cruiser.cjs]] Фичи core друг друга не импортируют и берут только общие модули.

## Сообщение доходит до агента и возвращается потоком
```mermaid
sequenceDiagram
  participant B as Браузер
  participant S as Сессии
  participant DB as Журнал
  participant A as Агент
  B->>S: «Привет» по WebSocket
  S->>DB: prompt_sent, статус working
  S->>A: сообщение по ACP
  A-->>S: ответ по частям
  S-->>B: вид чата растёт по словам
  S->>DB: turn_ended, статус idle
```
1. Кандидат пишет в чат; браузер отправляет текст серверу по WebSocket.
2. Сессия записывает событие в журнал до отправки агенту.
3. Сессия передаёт текст процессу агента по ACP.
4. Агент отвечает частями; каждая часть ложится в журнал.
5. Сервер собирает вид чата из журнала, и ответ в браузере растёт по словам.
6. Ход закончен, статус снова idle.

## Статус сессии меняют шесть событий
```mermaid
stateDiagram-v2
  [*] --> starting
  starting --> idle: session_started, turn_ended, turn_failed
  working --> idle: session_started, turn_ended, turn_failed
  starting --> working: prompt_sent
  idle --> working: prompt_sent
  starting --> failed: session_failed
  idle --> failed: session_failed
  working --> failed: session_failed
  ended --> failed: session_failed
  starting --> ended: session_ended
  idle --> ended: session_ended
  working --> ended: session_ended
  failed --> [*]
  ended --> [*]
```
Переходы взяты из каждой ветки `statusAfter`: живой статус (`starting`, `idle`, `working`) принимает все события, `session_failed` ведёт в `failed` из любого статуса. [[packages/core/src/features/agent-sessions/domain/session-view.ts:13-38]]
