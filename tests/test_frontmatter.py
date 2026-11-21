"""Skill frontmatter must survive the strict YAML parsing that clients and installers apply."""
import importlib.util
from pathlib import Path
import unittest

KIT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("kit_check", KIT / "scripts/check.py")
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)


def skill(description, extra=""):
    return f"---\nname: probe\ndescription: {description}\n{extra}---\nBody\n"


class FrontmatterTest(unittest.TestCase):
    def test_accepts_plain_quoted_block_and_nested_values(self):
        for text in (skill("Observe a fixture."), skill('"Ask where you are: which flow fits."'),
                     skill("'It''s quoted: fine.'"), skill(">\n  Folded: text\n"),
                     skill("Plain.", "disable-model-invocation: true\nmetadata:\n  credits:\n    url: \"https://example.invalid\"\n")):
            with self.subTest(text=text):
                self.assertEqual(check.frontmatter_errors(text), [])

    def test_rejects_values_yaml_would_reject_or_misread(self):
        for description in ("Ask where you are: which flow fits.", "Trailing colon:", "Cut here #comment",
                            "[bracket start", '"unterminated', "'unterminated", ""):
            with self.subTest(description=description):
                self.assertTrue(check.frontmatter_errors(skill(description)))
        self.assertEqual(check.frontmatter_errors("Body only\n"), ["no frontmatter block"])

    def test_every_catalog_skill_parses(self):
        for path in sorted((KIT / "skills").glob("*/*/SKILL.md")):
            with self.subTest(skill=path.parent.name):
                self.assertEqual(check.frontmatter_errors(path.read_text()), [])


if __name__ == "__main__":
    unittest.main()
