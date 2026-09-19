import json
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "cursor" / "hooks"))
from deny_destructive_github import decide


class DecideTests(unittest.TestCase):
    def test_deny_repo_delete(self):
        self.assertEqual(decide("gh repo delete")[0], "deny")

    def test_deny_repo_delete_name(self):
        self.assertEqual(decide("gh repo delete org/repo")[0], "deny")

    def test_deny_repo_delete_yes(self):
        self.assertEqual(decide("gh repo delete --yes")[0], "deny")

    def test_deny_sudo_repo_delete(self):
        self.assertEqual(decide("sudo gh repo delete x")[0], "deny")

    def test_ask_secret_set(self):
        self.assertEqual(decide("gh secret set NAME")[0], "ask")

    def test_ask_variable_set(self):
        self.assertEqual(decide("gh variable set NAME")[0], "ask")

    def test_allow_secret_list(self):
        self.assertEqual(decide("gh secret list")[0], "allow")

    def test_allow_api(self):
        self.assertEqual(decide("gh api user")[0], "allow")

    def test_allow_workflow_run(self):
        self.assertEqual(decide("gh workflow run ci.yml")[0], "allow")

    def test_allow_pr_merge(self):
        self.assertEqual(decide("gh pr merge 1")[0], "allow")

    def test_allow_bash_c_unparsed(self):
        self.assertEqual(decide("bash -c 'gh repo delete x'")[0], "allow")


class FailClosedTests(unittest.TestCase):
    def test_invalid_json_fails_closed(self):
        script = (
            Path(__file__).resolve().parents[1]
            / "cursor/hooks/deny_destructive_github.py"
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
