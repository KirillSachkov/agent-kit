"""explain's build (in progress): Markdown to an offline page."""

from __future__ import annotations

import io
import re
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KIT = ROOT / "skills/in-progress/explain/kit"
sys.path.insert(0, str(KIT))

import build  # noqa: E402

EXAMPLES = sorted((ROOT / "skills/in-progress/explain/examples").glob("*/*.md"))


def page(text: str):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "explain.md"
        path.write_text(text, encoding="utf-8")
        return build.build_page(path)


class PageTest(unittest.TestCase):
    @unittest.skipUnless(build.shutil.which("node") and build.find_chromium() and build.find_playwright(),
                         "drawing diagrams needs node, Chromium and playwright-core")
    def test_examples_build(self) -> None:
        for path in EXAMPLES:
            with self.subTest(path=path.name), tempfile.TemporaryDirectory() as tmp:
                out = Path(tmp) / "p.html"
                with redirect_stderr(io.StringIO()) as err, redirect_stdout(io.StringIO()):
                    code = build.main([str(path), str(out)])
                self.assertEqual(code, 0, err.getvalue())
                html = out.read_text(encoding="utf-8")
                self.assertLess(len(html.encode()), build.MAX_BYTES)
                self.assertNotIn("<script src", html)

    def test_sections_and_marks(self) -> None:
        html, errors, _, _ = page("---\ntitle: T\n---\nVerdict.\n\n## Что сделано\n- ✅ A [[kit/build.py:3]]\n")
        self.assertEqual(errors, [])
        self.assertIn('<p class="verdict">Verdict.</p>', html)
        self.assertIn("Что сделано</a>", html)
        self.assertIn('<span class="ev">kit/build.py:3</span>', html)

    def test_text_is_escaped(self) -> None:
        html, _, _, _ = page("---\ntitle: T\n---\n<script>alert(1)</script> and `<b>`\n")
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)
        self.assertIn("<code>&lt;b&gt;</code>", html)

    def test_title_is_required(self) -> None:
        _, errors, _, _ = page("Text without front matter.\n")
        self.assertTrue(any("title is required" in e for e in errors), errors)


if __name__ == "__main__":
    unittest.main()
