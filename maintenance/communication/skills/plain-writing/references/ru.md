# Plain writing in Russian

What Russian adds to the rules in [SKILL.md](../SKILL.md). Accuracy and natural Russian outrank every rule here.

## Words

Write words the way a Russian-speaking developer says them to a colleague.

| Case | Write | Example |
|---|---|---|
| A loan word that lives in speech | Cyrillic | скилл, коммит, ветка, пушить, мержить, деплой, баг |
| A name: product, company, model, branch, command, file | the original | Codex, Claude Code, Orca, `main`, `pnpm test`, `build.py` |
| A term with no settled Russian form | Latin, explained in a few words the first time | software factory, то есть подход, где агенты пишут код по конвейеру |
| A common Russian word exists | the Russian word | проверить, а не провалидировать; запустить, а не заранить |

- Keep code, commands, paths, identifiers and error text verbatim, in backticks.
- Address the reader as «ты», unless their instructions say otherwise.

## Sentences

- A verb, not a verbal noun: «удалил», not «осуществил удаление»; «помогает», not «оказывает помощь».
- Plain words, not bureaucratic ones: «это», not «является»; «этот», not «данный»; «сейчас», not «в данный момент»; «в задаче», not «в рамках задачи»; «позволяет», not «обеспечивает возможность».
- Untangle chains of nouns in the genitive into a verb: «проверка соответствия требованиям безопасности» becomes «проверили, что код безопасен».
- At most one participial or adverbial participial phrase in a sentence; turn the rest into verbs or separate sentences.
- Keep the small words that carry meaning: «уже», «ещё», «может», «поэтому», «но».
- A full phrase with its link verb: «в процессе есть три результата», not «в процессе три результата».
- Calques from English become Russian: «это логично», not «это делает смысл»; «в итоге», not «в конце дня»; «решить проблему», not «адресовать проблему».

## Punctuation

- **No long dash (—) anywhere in prose.** Write the link word, a comma, or a new sentence: «Сборка проверяет ссылки. Если файла нет, страница не собирается».
  Instead of «`recap` — это скилл, который пишет отчёт», say what it does: «`recap` пишет отчёт». In a list of names, a colon follows the name: «`recap`: отчёт о работе».
  The short dash stays in number ranges: 2–3.
- A colon only before a list, code or an example, or after a name in a list. Join an explanation with a word, or give it its own sentence.

## Reread

After the questions in [SKILL.md](../SKILL.md#before-sending):

1. Would the reader say this word out loud, in this form?
2. Is there a verb where a verbal noun or a bureaucratic word stood?
3. Is a long dash (—) left anywhere outside code? Replace it.
