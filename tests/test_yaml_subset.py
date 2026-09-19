import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from yaml_subset import parse_yaml_subset


CATALOG = """
profiles:
  core:
    skills: [verification-before-completion]
    agents: [implementer, reviewer]
    rules: [route-context, commit-style]
    hooks: [deny-destructive-shell]
  web-ts: { skills: [], agents: [], rules: [], hooks: [] }
  backend: { skills: [], agents: [], rules: [], hooks: [] }
  infra: { skills: [], agents: [], rules: [], hooks: [] }

skills:
  verification-before-completion:
    origin: third_party/superpowers/verification-before-completion
    agents: [implementer, reviewer]

agents:
  implementer:
    skills: [verification-before-completion]
  reviewer:
    skills: [verification-before-completion]

rules:
  route-context:
    alwaysApply: true
  commit-style:
    alwaysApply: true

hooks:
  deny-destructive-shell:
    event: beforeShellExecution
"""

MANIFEST = """
local_only:
  - .my-cursor-setup-state.json

files:
  verification-before-completion:
    src: cursor/skills/verification-before-completion
    dest: skills/verification-before-completion
  implementer:
    src: cursor/agents/implementer.md
    dest: agents/implementer.md
  catalog:
    src: catalog.yaml
    dest: my-cursor-setup-catalog.yaml
    always: true
  hooks-json:
    src: cursor/hooks.json
    dest: hooks.json
    merge: hooks
"""


class ParseYamlSubsetTests(unittest.TestCase):
    def test_catalog_profiles_and_inline_empty_maps(self):
        data = parse_yaml_subset(CATALOG)
        self.assertEqual(
            data["profiles"]["core"]["skills"],
            ["verification-before-completion"],
        )
        self.assertEqual(data["profiles"]["web-ts"]["skills"], [])
        self.assertEqual(data["profiles"]["infra"]["hooks"], [])
        self.assertEqual(
            data["skills"]["verification-before-completion"]["agents"],
            ["implementer", "reviewer"],
        )
        self.assertTrue(data["rules"]["route-context"]["alwaysApply"])
        self.assertEqual(
            data["hooks"]["deny-destructive-shell"]["event"],
            "beforeShellExecution",
        )

    def test_manifest_lists_and_flags(self):
        data = parse_yaml_subset(MANIFEST)
        self.assertEqual(data["local_only"], [".my-cursor-setup-state.json"])
        entry = data["files"]["hooks-json"]
        self.assertEqual(entry["dest"], "hooks.json")
        self.assertEqual(entry["merge"], "hooks")
        self.assertTrue(data["files"]["catalog"]["always"])

    def test_comments_ignored(self):
        data = parse_yaml_subset("a: 1\n# nope\nb: two\n")
        self.assertEqual(data, {"a": 1, "b": "two"})

    def test_unsupported_multiline_raises(self):
        with self.assertRaises(ValueError):
            parse_yaml_subset("a: |\n  hello\n")


if __name__ == "__main__":
    unittest.main()

