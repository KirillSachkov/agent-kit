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
                            "[bracket start", '"unterminated', "'unterminated", "", "#only a comment",
                            "First line\n  second: line", "One\ndescription: Two"):
            with self.subTest(description=description):
                self.assertTrue(check.frontmatter_errors(skill(description)))
        self.assertEqual(check.frontmatter_errors("Body only\n"), ["no frontmatter block"])


class InvocationTest(unittest.TestCase):
    MANUAL = "---\nname: probe\ndescription: Probe.\ndisable-model-invocation: true\n---\n"
    OPEN = "---\nname: probe\ndescription: Probe.\n---\n"
    CLOSED_POLICY = "policy:\n  allow_implicit_invocation: false\n"

    def test_flags_must_agree_and_match_the_pristine_skill(self):
        self.assertEqual(check.invocation_errors("probe", self.MANUAL, self.CLOSED_POLICY, self.MANUAL), [])
        self.assertEqual(check.invocation_errors("probe", self.OPEN, "interface:\n  display_name: Probe\n", self.OPEN), [])
        self.assertEqual(check.invocation_errors("probe", self.OPEN, "", None), [])
        self.assertIn("disagree", check.invocation_errors("probe", self.MANUAL, "policy:\n  allow_implicit_invocation: true\n")[0])
        self.assertIn("disagree", check.invocation_errors("probe", self.OPEN, self.CLOSED_POLICY)[0])
        self.assertIn("pristine", check.invocation_errors("probe", self.OPEN, "", self.MANUAL)[0])

    def test_codex_flag_counts_only_under_policy(self):
        elsewhere = "interface:\n  allow_implicit_invocation: false\npolicy:\n  allow_implicit_invocation: true\n"
        self.assertIn("disagree", check.invocation_errors("probe", self.MANUAL, elsewhere)[0])
        nested = "interface:\n  display_name: Probe\npolicy:\n  other: 1\n  allow_implicit_invocation: false\n"
        self.assertEqual(check.invocation_errors("probe", self.MANUAL, nested), [])


if __name__ == "__main__":
    unittest.main()
