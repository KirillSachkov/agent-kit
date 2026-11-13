#!/usr/bin/env python3
"""Turn an explanation written in Markdown into one offline page (in progress: see the explain skill).

    python3 build.py explain.md page.html           # build the page
    python3 build.py explain.md page.html --check   # final build: check the page in headless Chromium, network blocked

Mermaid diagrams become static SVG at build time. [[path:line]] marks show as references to the code.
"""

from __future__ import annotations

import argparse
import base64
import datetime
import glob
import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

KIT = Path(__file__).resolve().parent
CACHE = Path(os.environ.get("AGENT_CLARITY_CACHE", Path.home() / ".cache/agent-clarity"))
MERMAID_VERSION = "12.3.0"
MAX_BYTES = 512 * 1024
STATUS = {"✅": "done", "◐": "partial", "✗": "skipped", "❌": "fail", "…": "pending", "⚠️": "warn"}
LABEL = {"done": "сделано", "partial": "частично", "skipped": "не сделано", "fail": "упало", "pending": "ждёт", "warn": "внимание"}
EVIDENCE = re.compile(r"\[\[([^\]]+)\]\]")


# ---------- front matter ----------

def front_matter(text: str) -> Tuple[Dict, str]:
    meta: Dict = {}
    if not text.startswith("---\n"):
        return meta, text
    head, _, body = text[4:].partition("\n---\n")
    key = None
    for line in head.splitlines():
        if re.match(r"\s+- ", line) and key:
            meta.setdefault(key, []).append(line.strip()[2:].strip())
        elif ":" in line:
            key, _, value = line.partition(":")
            key = key.strip()
            if value.strip():
                meta[key] = value.strip()
    return meta, body


# ---------- inline Markdown ----------

def image(src: str, alt: str, base: Path) -> str:
    file = base / src
    if src.startswith(("http://", "https://")) or not file.exists():
        return f'<span class="missing">нет картинки {html.escape(src)}</span>'
    mime = {".png": "image/png", ".svg": "image/svg+xml", ".gif": "image/gif"}.get(file.suffix.lower(), "image/jpeg")
    return f'<img src="data:{mime};base64,{base64.b64encode(file.read_bytes()).decode()}" alt="{html.escape(alt)}">'


def inline(text: str, base: Path) -> str:
    keep: List[str] = []

    def hold(value: str) -> str:
        keep.append(value)
        return f"\x00{len(keep) - 1}\x00"

    text = re.sub(r"`([^`]+)`", lambda m: hold(f"<code>{html.escape(m.group(1))}</code>"), text)
    text = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", lambda m: hold(image(m.group(2), m.group(1), base)), text)
    text = EVIDENCE.sub(lambda m: "" if m.group(1).strip().startswith("covers:") else hold(f'<span class="ev">{html.escape(m.group(1).strip())}</span>'), text)
    text = html.escape(text, quote=False)
    text = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", r'<a href="\2" target="_blank" rel="noreferrer">\1</a>', text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<![\w*])_([^_]+)_(?!\w)", r"<i>\1</i>", text)
    return re.sub(r"\x00(\d+)\x00", lambda m: keep[int(m.group(1))], text)


# ---------- blocks ----------

class Page:
    def __init__(self, base: Path):
        self.base = base
        self.diagrams: List[Tuple[str, str]] = []
        self.items: List[Dict] = []
        self.nav: List[Tuple[str, str]] = []

    def diagram(self, code: str) -> str:
        did = f"mm{len(self.diagrams)}"
        self.diagrams.append((did, code))
        kind = "seq" if code.lstrip().startswith("sequenceDiagram") else "flow"
        return f'<figure class="mm {kind}" id="{did}"><pre class="mm-src">{html.escape(code)}</pre></figure>'


def slug(text: str, used: set) -> str:
    s = re.sub(r"[^\w]+", "-", text.lower()).strip("-") or "s"
    while s in used:
        s += "-"
    used.add(s)
    return s


LIST = re.compile(r"^(\s*)([-*]|\d+\.)\s+(.*)$")


def render_body(body: str, page: Page) -> str:
    lines = body.splitlines()
    out: List[str] = []
    used: set = set()
    state = {"section": False, "verdict": True, "lead": False, "cards": "", "ask": False}

    def close_ask() -> None:
        if state["ask"]:
            out.append("</div>")
            state["ask"] = False
    buf: List[str] = []
    first = next((l for l in lines if l.strip()), "")
    if not first.startswith("#"):  # text before the first heading is the verdict section
        page.nav.append(("itog", "Итог"))
        used.add("itog")
        out.append('<section class="sec lead" id="itog">')
        state.update(section=True, lead=True)

    def para() -> None:
        text = " ".join(x.strip() for x in buf)
        buf.clear()
        if not text:
            return
        if re.fullmatch(r"\*\*(Нужно от тебя|Нужно от вас|Need from you):?\*\*", text):  # the closing block for the reader
            close_ask()
            out.append(f'<div class="ask"><p class="ask-h">{inline(text, page.base)}</p>')
            state["ask"] = True
            return
        shot = re.fullmatch(r"!\[([^\]]*)\]\(([^)]+)\)", text)
        if shot:
            out.append(f'<figure class="shot">{image(shot.group(2), shot.group(1), page.base)}<figcaption>{inline(shot.group(1), page.base)}</figcaption></figure>')
            return
        if state["verdict"] and state["lead"]:
            out.append(f'<p class="verdict">{inline(text, page.base)}</p><!--LEAD-->')
        else:
            out.append(f"<p>{inline(text, page.base)}</p>")
        state["verdict"] = False

    i = 0
    while i < len(lines):
        line = lines[i]
        fence = re.match(r"^(\s*)```(\w*)\s*$", line)
        if fence:
            para()
            indent, lang, code = len(fence.group(1)), fence.group(2), []
            i += 1
            while i < len(lines) and not re.match(r"^\s*```\s*$", lines[i]):
                code.append(lines[i][indent:] if not lines[i][:indent].strip() else lines[i])
                i += 1
            i += 1
            text = "\n".join(code)
            out.append(page.diagram(text) if lang == "mermaid" else f"<pre><code>{html.escape(text)}</code></pre>")
            continue
        heading = re.match(r"^(#{1,3})\s+(.*)$", line)
        if heading:
            para()
            level, title = len(heading.group(1)), heading.group(2).strip()
            if level <= 2:
                close_ask()
                if state["section"]:
                    out.append("</section>")
                state["lead"] = False
                sid = slug(title, used)
                page.nav.append((sid, title))
                out.append(f'<section class="sec" id="{sid}"><h2>{inline(title, page.base)}</h2>')
                state["section"] = True
                state["cards"] = "decision" if re.match(r"(Решени|Decision)", title, re.I) else "risk" if re.match(r"(Риск|Risk)", title, re.I) else ""
            else:
                out.append(f"<h3>{inline(title, page.base)}</h3>")
            i += 1
            continue
        if line.startswith(">"):
            para()
            quote = []
            while i < len(lines) and lines[i].startswith(">"):
                quote.append(lines[i][1:].strip())
                i += 1
            text = " ".join(quote)
            cls = "ask" if re.match(r"\**(Нужно от|Need from|Action)", text) else "note"
            out.append(f'<div class="{cls}">{inline(text, page.base)}</div>')
            continue
        if line.startswith("|"):
            para()
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            head = rows[0]
            body_rows = [r for r in rows[1:] if not all(re.fullmatch(r":?-+:?", c) for c in r)]
            out.append('<div class="tbl"><table><tr>' + "".join(f"<th>{inline(c, page.base)}</th>" for c in head) + "</tr>"
                       + "".join("<tr>" + "".join(f"<td>{inline(c, page.base)}</td>" for c in r) + "</tr>" for r in body_rows)
                       + "</table></div>")
            continue
        item = LIST.match(line)
        if item and not item.group(1):
            para()
            ordered = item.group(2)[0].isdigit()
            entries: List[Dict] = []
            while i < len(lines):
                m = LIST.match(lines[i])
                if m and not m.group(1):
                    entries.append({"text": m.group(3), "more": []})
                elif entries and lines[i].startswith("  "):
                    entries[-1]["more"].append(lines[i][2:])
                elif entries and not lines[i].strip() and i + 1 < len(lines) and (lines[i + 1].startswith("  ") or LIST.match(lines[i + 1] or "x")):
                    pass
                else:
                    break
                i += 1
            out.append(render_cards(entries, state["cards"], page) if state["cards"] else render_list(entries, ordered, page))
            continue
        if not line.strip():
            para()
        else:
            buf.append(line)
        i += 1
    para()
    close_ask()
    if state["section"]:
        out.append("</section>")
    return "\n".join(out)


def render_cards(entries: List[Dict], kind: str, page: Page) -> str:
    """Decisions and risks: one card each, with what the owner must do about it."""
    cards = []
    for e in entries:
        text = " ".join([e["text"]] + [l.strip() for l in e["more"]])
        body, _, action = text.rpartition(" → ") if " → " in text else (text, "", "")
        title = re.match(r"\*\*(.+?)\*\*\s*(.*)", body)
        head, rest = (title.group(1).rstrip("."), title.group(2)) if title else (body, "")
        if action:
            calm = re.match(r"(ничего|nothing|no action)", action, re.I)
            act = f'<div class="act {"calm" if calm else "need"}"><b>От тебя:</b> {inline(action, page.base)}</div>'
        else:
            act = ""
        cards.append(f'<div class="card {kind}"><div class="kind">{"решение агента" if kind == "decision" else "риск"}</div>'
                     f'<h4>{inline(head, page.base)}</h4>{f"<p>{inline(rest, page.base)}</p>" if rest else ""}{act}</div>')
    return '<div class="cards">' + "".join(cards) + "</div>"


def render_list(entries: List[Dict], ordered: bool, page: Page) -> str:
    rows, status_list = [], False
    for e in entries:
        text, status = e["text"], None
        for mark, name in STATUS.items():
            if text.startswith(mark):
                status, text, status_list = name, text[len(mark):].strip(), True
                break
        refs = [r.strip() for r in EVIDENCE.findall(re.sub(r"`[^`]+`", "", text))]  # marks inside code are examples
        covers = [g for r in refs if r.startswith("covers:") for g in r[7:].split()]
        files = [r for r in refs if not r.startswith("covers:")]
        link = bool(re.search(r"\]\(https?://", text))
        command = bool(re.search(r"`[^`]+`\s*[—–-]\s*\S", text))  # `command` — its result
        unproven = status in ("done", "partial") and not files and not link and not command
        page.items.append({"status": status, "files": files, "covers": covers, "unproven": unproven})
        extra = ""
        if e["more"]:
            joined = "\n".join(e["more"])
            code = re.search(r"```\w*\n(.*?)\n\s*```", joined, re.S)
            rest = re.sub(r"```\w*\n.*?\n\s*```", "", joined, flags=re.S).strip()
            if rest:
                extra += f'<div class="more">{inline(" ".join(rest.split()), page.base)}</div>'
            if code:
                extra += f"<details><summary>вывод</summary><pre><code>{html.escape(code.group(1))}</code></pre></details>"
        pill = f'<span class="pill {status}">{LABEL[status]}</span>' if status else ""
        flag = '<span class="unp">без доказательства</span>' if unproven else ""
        rows.append(f"<li>{pill}<div>{inline(text, page.base)}{flag}{extra}</div></li>")
    tag = "ol" if ordered else "ul"
    cls = ' class="status"' if status_list else ""
    return f"<{tag}{cls}>" + "".join(rows) + f"</{tag}>"


# ---------- facts ----------

FENCE = re.compile(r"^[ \t]*```[^\n]*\n.*?^[ \t]*```[ \t]*$", re.S | re.M)


def check_links(links: List[str], base: Path) -> List[str]:
    errors = []
    for line in links:
        label, _, url = line.strip().rpartition(" ")
        if not label.strip() or not (re.match(r"[a-z][a-z0-9+.-]*://\S", url) or (base / url.split("#")[0]).is_file()):
            errors.append(f'links: "{line}" has no URL: write "<label> https://…", or a page path next to the source')
    return errors


def find_chromium() -> Optional[str]:
    if os.environ.get("VX_CHROME"):
        return os.environ["VX_CHROME"]
    for root in (Path.home() / "Library/Caches/ms-playwright", Path.home() / ".cache/ms-playwright"):
        for pattern in ("chromium_headless_shell-*/chrome-headless-shell-*/chrome-headless-shell",
                        "chromium-*/chrome-mac*/Chromium.app/Contents/MacOS/Chromium",
                        "chromium_headless_shell-*/chrome-linux*/headless_shell", "chromium-*/chrome-linux*/chrome"):
            found = sorted(glob.glob(str(root / pattern)))
            if found:
                return found[-1]
    for system in ("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", shutil.which("chromium") or "", shutil.which("google-chrome") or ""):
        if system and Path(system).exists():
            return system
    return None


def find_playwright() -> Optional[str]:
    if os.environ.get("VX_PLAYWRIGHT"):
        return os.environ["VX_PLAYWRIGHT"]
    roots = [CACHE / "node_modules", Path.home() / ".local/lib/node_modules"]
    npm = shutil.which("npm")
    if npm:
        out = subprocess.run([npm, "root", "-g"], capture_output=True, text=True, check=False)
        roots.insert(1, Path(out.stdout.strip()))
    for root in roots:
        for rel in ("playwright-core", "@playwright/cli/node_modules/playwright-core", "playwright/node_modules/playwright-core"):
            if (root / rel / "package.json").exists():
                return str(root / rel)
    return None


def mermaid_js() -> Optional[Path]:
    js = CACHE / "node_modules/mermaid/dist/mermaid.min.js"
    if js.exists():
        return js
    npm = shutil.which("npm")
    if not npm:
        return None
    print(f"installing mermaid@{MERMAID_VERSION} into {CACHE} (once)", file=sys.stderr)
    CACHE.mkdir(parents=True, exist_ok=True)
    subprocess.run([npm, "install", "--no-audit", "--no-fund", "--prefix", str(CACHE), f"mermaid@{MERMAID_VERSION}"], capture_output=True, check=False)
    return js if js.exists() else None


class Unavailable(Exception):
    pass


class Chrome:
    """One headless Chromium per build, started on first use: Mermaid and the check share it."""

    def __init__(self) -> None:
        self.proc: Optional[subprocess.Popen] = None
        self.log = None

    def ask(self, request: Dict):
        if self.proc is None:
            node, chromium, playwright = shutil.which("node"), find_chromium(), find_playwright()
            missing = [n for n, v in (("node", node), ("Chromium", chromium), ("playwright-core", playwright)) if not v]
            if missing:
                raise Unavailable("missing " + ", ".join(missing))
            self.log = tempfile.TemporaryFile(mode="w+")
            env = dict(os.environ, VX_CHROME=chromium, VX_PLAYWRIGHT=playwright)
            self.proc = subprocess.Popen([node, str(KIT / "chrome.mjs")], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                         stderr=self.log, text=True, encoding="utf-8", env=env)
        assert self.proc.stdin and self.proc.stdout
        try:
            self.proc.stdin.write(json.dumps(request) + "\n")
            self.proc.stdin.flush()
            line = self.proc.stdout.readline()
        except OSError:
            line = ""
        if not line:
            self.log.seek(0)
            raise Unavailable(self.log.read().strip()[-400:] or "Chromium exited")
        answer = json.loads(line)
        if isinstance(answer, dict) and answer.get("fatal"):
            raise Unavailable(answer["fatal"])
        return answer

    def close(self) -> None:
        if self.proc:
            try:
                self.proc.stdin.close()
                self.proc.wait(timeout=30)
            except (OSError, subprocess.TimeoutExpired):
                self.proc.kill()
            self.proc = None


def svg_cache(code: str) -> Path:
    key = hashlib.sha256((MERMAID_VERSION + (KIT / "chrome.mjs").read_text(encoding="utf-8") + code).encode()).hexdigest()[:32]
    return CACHE / "svg" / f"{key}.svg"


def render_diagrams(diagrams: List[Tuple[str, str]], chrome: Chrome) -> Tuple[Dict[str, str], List[str], List[str]]:
    """Return SVG by diagram id, errors in diagram code, and notes when rendering is unavailable.
    A diagram drawn before comes from the cache, so a rebuild that changes only text starts no browser."""
    svgs = {d: svg_cache(c).read_text(encoding="utf-8") for d, c in diagrams if svg_cache(c).is_file()}
    todo = [(d, c) for d, c in diagrams if d not in svgs]
    if not todo:
        return svgs, [], []
    js = mermaid_js()
    if not js:
        return svgs, [], ["diagrams stay as text: missing mermaid (npm)"]
    try:
        result = chrome.ask({"op": "render", "mermaid": str(js), "diagrams": [{"id": d, "code": c} for d, c in todo]})
    except Unavailable as error:
        return svgs, [], [f"diagrams stay as text: {error}"]
    code = dict(todo)
    for r in result:
        if r.get("svg"):
            svgs[r["id"]] = r["svg"]
            cache = svg_cache(code[r["id"]])
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(r["svg"], encoding="utf-8")
    number = {d: i + 1 for i, (d, _) in enumerate(diagrams)}
    return svgs, [f"diagram {number[r['id']]}: {r['error']}" for r in result if r.get("error")], []


# ---------- page ----------

def head_and_lead(meta: Dict) -> Tuple[str, str]:
    label, _, tone = meta.get("status", "").partition("|")
    links = "".join(f'<a class="lnk" href="{html.escape(u.strip())}" target="_blank" rel="noreferrer">{html.escape(t.strip())}<span>↗</span></a>'
                    for t, _, u in (l.rpartition(" ") for l in meta.get("links", [])))
    stats = "".join(f'<div class="stat"><b>{html.escape(n.strip())}</b><span>{html.escape(t.strip())}</span></div>'
                    for n, _, t in (s.partition("|") for s in meta.get("stats", [])))
    pill = f'<span class="pill {html.escape(tone.strip() or "wait")}">{html.escape(label.strip())}</span>' if label.strip() else ""
    task = f'<span class="task">{inline(meta["task"], Path("."))}</span>' if meta.get("task") else ""
    head = f'<header>{"<div class=top>" + pill + task + "</div>" if pill or task else ""}<h1>{inline(meta.get("title", ""), Path("."))}</h1></header>'
    lead = (f'<div class="links">{links}</div>' if links else "") + (f'<div class="stats">{stats}</div>' if stats else "")
    return head, lead


def build_page(md_path: Path, chrome: Optional[Chrome] = None) -> Tuple[str, List[str], List[str], Dict]:
    meta, body = front_matter(md_path.read_text(encoding="utf-8"))
    for key in ("links", "stats"):
        if isinstance(meta.get(key), str):
            meta[key] = [meta[key]]
    page = Page(md_path.parent)
    content = render_body(body, page)
    errors: List[str] = [] if meta.get("title") else ["front matter: title is required"]
    errors += check_links(meta.get("links", []), md_path.parent)
    own = chrome is None
    chrome = chrome or Chrome()
    try:
        svgs, diagram_errors, notes = render_diagrams(page.diagrams, chrome)
    finally:
        if own:
            chrome.close()
    errors += diagram_errors
    for did, svg in svgs.items():
        content = re.sub(rf'(<figure class="mm \w+" id="{did}">)<pre class="mm-src">.*?</pre>', lambda m: m.group(1) + svg, content, flags=re.S)
    foot = f"Собрано {datetime.date.today().isoformat()}"
    head, lead = head_and_lead(meta)
    content = content.replace("<!--LEAD-->", lead, 1) if "<!--LEAD-->" in content else lead + content
    nav = "".join(f'<a href="#{sid}">{inline(t, Path("."))}</a>' for sid, t in page.nav)
    shell = (KIT / "page.html").read_text(encoding="utf-8")
    for marker, value in (("/*TITLE*/", html.escape(meta.get("title", ""))), ("/*CSS*/", (KIT / "page.css").read_text(encoding="utf-8")),
                          ("/*JS*/", (KIT / "page.js").read_text(encoding="utf-8")), ("<!--HEAD-->", head), ("<!--NAV-->", nav),
                          ("<!--BODY-->", content), ("<!--FOOT-->", html.escape(foot))):
        shell = shell.replace(marker, value, 1)
    return shell, errors, notes, {"meta": meta, "body": body}


def check(page: Path, chrome: Chrome) -> int:
    """Open the page offline in light, dark and phone width: JS errors, requests, sideways scroll, every step played."""
    shots = Path(tempfile.mkdtemp(prefix=page.stem + "-check-"))
    try:
        result = chrome.ask({"op": "check", "page": str(page.resolve()), "shots": str(shots)})
    except Unavailable as error:
        print(f"check skipped: {error}", file=sys.stderr)
        return 2
    for p in result["problems"]:
        print("✗ " + p)
    for n in result["notes"]:
        print("! " + n)
    if not result["problems"]:
        print("✓ offline, no errors, light and dark themes, phone width, every step played")
    print("screenshots:\n" + "\n".join(result["pictures"]))
    return 1 if result["problems"] else 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("source", type=Path, help="explain.md")
    parser.add_argument("out", type=Path, help="page to write")
    parser.add_argument("--check", action="store_true", help="final build: check the page in headless Chromium, network blocked")
    args = parser.parse_args(argv)
    chrome = Chrome()
    try:
        return run(args, chrome)
    finally:
        chrome.close()


def run(args: argparse.Namespace, chrome: Chrome) -> int:
    page, errors, notes, info = build_page(args.source, chrome)
    for note in notes:
        print("! " + note, file=sys.stderr)
    for error in errors:
        print(error, file=sys.stderr)
    if errors:
        return 1
    size = len(page.encode("utf-8"))
    if size > MAX_BYTES:
        print(f"page is {size} bytes, limit {MAX_BYTES}: shrink images or split the page", file=sys.stderr)
        return 1
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(page, encoding="utf-8")
    print(f"{args.out} · {size // 1024} KB", flush=True)
    if args.check:
        return check(args.out, chrome)
    print("! not checked in a browser: run the final build once with --check", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
