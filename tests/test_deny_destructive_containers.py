import subprocess
import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "cursor" / "hooks"))
from deny_destructive_containers import decide


class DecideTests(unittest.TestCase):
    def test_deny_delete_namespace(self):
        self.assertEqual(decide("kubectl delete ns prod-apps")[0], "deny")

    def test_deny_prune_af(self):
        self.assertEqual(decide("docker system prune -af")[0], "deny")

    def test_deny_helm_uninstall_prod_context(self):
        self.assertEqual(
            decide("helm uninstall myrel --kube-context production")[0], "deny"
        )

    def test_ask_kubectl_apply_staging(self):
        self.assertEqual(
            decide("kubectl apply -f x.yaml --context staging")[0], "ask"
        )

    def test_allow_kubectl_get(self):
        self.assertEqual(decide("kubectl get pods")[0], "allow")

    def test_allow_compose_up(self):
        self.assertEqual(decide("docker compose up")[0], "allow")

    def test_allow_helm_uninstall_kind(self):
        self.assertEqual(
            decide("helm uninstall x --kube-context kind-kind")[0], "allow"
        )

    def test_allow_prune_without_all_force(self):
        self.assertEqual(decide("docker system prune")[0], "allow")


class FailClosedTests(unittest.TestCase):
    def test_invalid_json_fails_closed(self):
        script = (
            Path(__file__).resolve().parents[1]
            / "cursor/hooks/deny_destructive_containers.py"
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
