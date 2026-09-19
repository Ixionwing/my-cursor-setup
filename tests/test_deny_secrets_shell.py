import subprocess
import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "cursor" / "hooks"))
from deny_secrets_shell import decide


class DecideTests(unittest.TestCase):
    def test_deny_git_add_env(self):
        self.assertEqual(decide("git add .env")[0], "deny")

    def test_deny_git_add_production_env(self):
        self.assertEqual(decide("git add .env.production")[0], "deny")

    def test_deny_cat_production_env(self):
        self.assertEqual(decide("cat .env.production")[0], "deny")

    def test_ask_cat_env(self):
        self.assertEqual(decide("cat .env")[0], "ask")

    def test_allow_git_add_example(self):
        self.assertEqual(decide("git add .env.example")[0], "allow")


class FailClosedTests(unittest.TestCase):
    def test_invalid_json_fails_closed(self):
        script = (
            Path(__file__).resolve().parents[1]
            / "cursor/hooks/deny_secrets_shell.py"
        )
        proc = subprocess.run(
            [sys.executable, str(script)],
            input="{",
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertNotIn('"permission": "allow"', proc.stdout)


if __name__ == "__main__":
    unittest.main()
