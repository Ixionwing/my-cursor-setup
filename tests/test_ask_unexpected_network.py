import subprocess
import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "cursor" / "hooks"))
from ask_unexpected_network import decide


class DecideTests(unittest.TestCase):
    def test_ask_curl_example(self):
        self.assertEqual(decide("curl https://example.com")[0], "ask")

    def test_allow_curl_loopback(self):
        self.assertEqual(decide("curl http://127.0.0.1:3000")[0], "allow")

    def test_allow_npm_install(self):
        self.assertEqual(decide("npm install")[0], "allow")


class FailClosedTests(unittest.TestCase):
    def test_invalid_json_fails_closed(self):
        script = (
            Path(__file__).resolve().parents[1]
            / "cursor/hooks/ask_unexpected_network.py"
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
