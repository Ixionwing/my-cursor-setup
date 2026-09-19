import json
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "cursor" / "hooks"))
from deny_destructive_db import decide


class DecideTests(unittest.TestCase):
    def test_deny_migrate_reset(self):
        self.assertEqual(decide("npx prisma migrate reset")[0], "deny")

    def test_deny_drop_database(self):
        self.assertEqual(decide('psql -c "DROP DATABASE foo"')[0], "deny")

    def test_deny_alembic_downgrade_rds(self):
        self.assertEqual(
            decide(
                "alembic -x url=postgresql://u:p@db.xyz.rds.amazonaws.com/app downgrade -1"
            )[0],
            "deny",
        )

    def test_ask_psql_rds(self):
        self.assertEqual(
            decide("psql -h db.xyz.rds.amazonaws.com -U u app")[0], "ask"
        )

    def test_allow_migrate_dev(self):
        self.assertEqual(decide("npx prisma migrate dev")[0], "allow")

    def test_allow_local_alembic_upgrade(self):
        self.assertEqual(decide("alembic upgrade head")[0], "allow")

    def test_allow_product_hostname(self):
        self.assertEqual(
            decide("psql -h product.example.com -U u app")[0], "ask"
        )


class FailClosedTests(unittest.TestCase):
    def test_invalid_json_fails_closed(self):
        script = (
            Path(__file__).resolve().parents[1]
            / "cursor/hooks/deny_destructive_db.py"
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
