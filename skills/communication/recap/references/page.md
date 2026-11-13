# The recap page

One HTML file, one scrolling page with a table of contents. You write only the body; the styles and the script come from this skill's `assets/`.
[The example page](../examples/interview-sensei/page.html) shows every element in use; match its look, and lay out your own content.

1. Write `body.html`, next to the recap, with the classes below:

   ```html
   <div class="pg">
   <header><div class="top"><span class="pill ok">готово</span><span class="task">spec #17 · PR #28</span></div><h1>Result title</h1></header>
   <div class="wrap"><nav class="toc"><a href="#itog">Итог</a><a href="#sdelano">Что сделано</a></nav><main>
     <section class="sec lead" id="itog"><p class="verdict">What now works.</p><div class="links">…</div><div class="stats">…</div></section>
     <section class="sec" id="sdelano"><h2>Что сделано</h2>…</section>
     <footer>Собрано 2026-11-09</footer>
   </main></div></div>
   ```

2. Assemble the page; `SKILL_DIR` is this skill's folder, `LANG` and `TITLE` are the reader's language and the result title:

   ```bash
   { printf '<!doctype html><html lang="%s"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>%s</title><style>\n' "$LANG" "$TITLE"
     cat "$SKILL_DIR/assets/page.css"; printf '</style></head><body>\n'; cat body.html
     printf '<script type="module">\n'; cat "$SKILL_DIR/assets/page.js"; printf '</script></body></html>\n'; } > page.html
   ```

## Elements

| Markdown | HTML |
|---|---|
| status line | `<span class="pill ok">готово</span>`; tones `ok`, `wait`, `warn`, `bad` |
| links | `<div class="links"><a class="lnk" href="…" target="_blank" rel="noreferrer">PR #28<span>↗</span></a></div>` |
| numbers | `<div class="stats"><div class="stat"><b>188</b><span>тестов прошло</span></div></div>` |
| `## heading` | a `<section class="sec" id="…">` with an `<h2>`, and a link to it in `.toc` |
| a list with ✅ ◐ ✗ ⚠️ | `<ul class="status"><li><span class="pill done">сделано</span><div>…</div></li></ul>`; `partial`, `skipped`, `warn` |
| `` `path:line` `` | `<span class="ev">path:line</span>` |
| other `` `code` `` | `<code>code</code>`; no Markdown stays in the HTML |
| a table | `<div class="tbl"><table>…</table></div>` |
| a Mermaid block | `<figure class="mm flow"><pre class="mermaid">…</pre></figure>`; `class="mm seq"` for a `sequenceDiagram`, followed by its `<ol>` of notes |
| a screenshot | `<figure class="shot"><img src="data:image/…" alt="…"><figcaption>…</figcaption></figure>`, the image embedded so the single file carries it |
| Решения, Риски | `<div class="cards"><div class="card decision">` or `card risk`, with `.kind`, `h4`, `p` and `<div class="act calm|need"><b>От тебя:</b> …</div>` |
| **Нужно от тебя** | `<div class="ask"><p class="ask-h"><b>Нужно от тебя</b></p>…</div>`, the last block |

- Shrink screenshots before embedding them: the page must stay light enough to open in a chat preview.
- Colours come from the host theme; leave `page.css` as it is.
- Diagrams load Mermaid from cdn.jsdelivr.net; without the network they stay as text, and the page still reads.
