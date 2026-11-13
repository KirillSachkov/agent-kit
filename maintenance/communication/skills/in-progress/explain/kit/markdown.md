# Marks and diagrams

Used by `explain`: its build reads these marks and draws these diagrams.

## Marks

| Mark | Meaning |
|---|---|
| `✅` `◐` `✗` `❌` `…` `⚠️` at the start of a list item | done, partial, not done, failed, pending, attention |
| `[[path]]`, `[[path:42]]`, `[[path:40-48]]` | evidence in the repository; the build checks the file and line exist |
| `[[covers: glob glob]]` | changed files this item covers; with `--base` every changed file must be covered |
| a link `[text](https://…)` | evidence outside the repository: PR, CI run, issue |

The build checks every `[[…]]` in the text: items, paragraphs, tables and cards. A mark inside `` `code` `` is an example.
Every `links` line ends with a URL or a page path; the build rejects a line without one.

A `✅` or `◐` item needs `[[…]]`, a link, or a command with its result (`` `pnpm test` — 182 passed ``); otherwise it shows «без доказательства» and is counted in the footer.
An indented code block under an item becomes a collapsible «вывод».

## Diagrams

Use Mermaid; the build draws it as a static picture in the page theme. GitHub draws the same block in the PR.

| Question | Diagram |
|---|---|
| How the parts connect | `flowchart LR` with 4–10 nodes; `subgraph` for a process or package |
| What happens in order | `sequenceDiagram`; the page adds ← → to step through messages |
| Which states an entity has | `stateDiagram-v2`, only when the work is about states |

- Every edge label is a verb: `-->|пишет журнал|`.
- Mark the work's change: `:::added`, `:::changed`, `:::removed`; `:::external` for parts outside the system.
- Keep labels short: up to 4 words in a node.
- After a `sequenceDiagram`, an ordered list with one item per message explains each step. The page shows the item for the current step; the PR shows the list.
- The owner can click any diagram or screenshot to open it full screen and zoom.
