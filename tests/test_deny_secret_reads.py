import subprocess
import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "cursor" / "hooks"))
from deny_secret_reads import decide


class DecideTests(unittest.TestCase):
    def test_deny_id_rsa(self):
        perm, msg = decide("/home/u/.ssh/id_rsa")
        self.assertEqual(perm, "deny")
        self.assertTrue(msg)

    def test_deny_production_env_message(self):
        perm, msg = decide("/app/.env.production")
        self.assertEqual(perm, "deny")
        self.assertIn("production env file", msg.lower())
        self.assertIn("yourself", msg.lower())

    def test_allow_dotenv(self):
        self.assertEqual(decide("/app/.env")[0], "allow")

    def test_allow_pub(self):
        self.assertEqual(decide("/home/u/.ssh/id_rsa.pub")[0], "allow")

    def test_allow_pem(self):
        self.assertEqual(decide("/app/server.pem")[0], "allow")


class FailClosedTests(unittest.TestCase):
    def test_invalid_json_fails_closed(self):
        script = (
            Path(__file__).resolve().parents[1]
            / "cursor/hooks/deny_secret_reads.py"
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
