import json
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "cursor" / "hooks"))
from deny_destructive_shell import decide


class DecideTests(unittest.TestCase):
    def test_allow_normal_push(self):
        self.assertEqual(decide("git push origin main", None)[0], "allow")

    def test_deny_commit_no_verify(self):
        self.assertEqual(decide("git commit --no-verify", None)[0], "deny")

    def test_deny_commit_dash_n(self):
        self.assertEqual(decide("git commit -n -m x", None)[0], "deny")

    def test_deny_commit_clustered_an(self):
        self.assertEqual(decide("git commit -an -m x", None)[0], "deny")

    def test_deny_push_no_verify(self):
        self.assertEqual(
            decide("git push --no-verify origin main", None)[0], "deny"
        )

    def test_allow_push_dash_n_dry_run(self):
        self.assertEqual(decide("git push -n origin main", None)[0], "allow")

    def test_allow_push_dry_run_long(self):
        self.assertEqual(
            decide("git push --dry-run origin main", None)[0], "allow"
        )

    def test_allow_normal_commit(self):
        self.assertEqual(decide("git commit -m x", None)[0], "allow")

    def test_allow_bash_c_commit_no_verify(self):
        self.assertEqual(
            decide("bash -c 'git commit --no-verify'", None)[0], "allow"
        )

    def test_deny_force_to_main(self):
        self.assertEqual(decide("git push --force origin main", None)[0], "deny")

    def test_deny_force_with_lease_master(self):
        self.assertEqual(
            decide("git push --force-with-lease origin master", None)[0], "deny"
        )
    
    def test_deny_force_with_lease_equal_main(self):
        self.assertEqual(
            decide("git push --force-with-lease=main origin main", None)[0], "deny"
        )

    def test_allow_force_with_lease_equal_feature(self):
        self.assertEqual(
            decide("git push --force-with-lease=feature origin feature", None)[0], "allow"
        )

    def test_deny_dash_f_to_main(self):
        self.assertEqual(decide("git push -f origin main", None)[0], "deny")

    def test_deny_clustered_force_flag_to_main(self):
        self.assertEqual(decide("git push -uf origin main", None)[0], "deny")

    def test_allow_clustered_force_flag_to_feature(self):
        self.assertEqual(decide("git push -uf origin feature", None)[0], "allow")

    def test_deny_clustered_force_with_push_option_attached(self):
        # -fofoo should be treated as a cluster containing 'f' and 'o' with an attached value,
        # and therefore considered a force when 'f' is present.
        self.assertEqual(decide("git push -fofoo origin main", None)[0], "deny")

    def test_deny_force_to_plus_main(self):
        self.assertEqual(decide("git push --force origin +main", None)[0], "deny")

    def test_allow_force_to_plus_feature(self):
        self.assertEqual(
            decide("git push --force origin +feature", None)[0], "allow"
        )

    def test_deny_clustered_force_with_separate_push_option_value(self):
        self.assertEqual(decide("git push -fo foo origin", None)[0], "deny")

    def test_allow_short_push_option_with_attached_value(self):
        self.assertEqual(decide("git push -ofoo origin main", None)[0], "allow")

    def test_allow_short_push_option_with_separate_value(self):
        # -o foo (separate value) is a push-option and not a force flag.
        self.assertEqual(decide("git push -o foo origin main", None)[0], "allow")

    def test_allow_force_to_feature(self):
        self.assertEqual(decide("git push --force origin feature-x", None)[0], "allow")

    def test_allow_force_with_upstream_to_feature(self):
        self.assertEqual(
            decide("git push --force -u origin feature", None)[0], "allow"
        )

    def test_deny_force_with_upstream_to_main(self):
        self.assertEqual(decide("git push --force -u origin main", None)[0], "deny")

    def test_deny_bare_force_push(self):
        self.assertEqual(decide("git push --force", None)[0], "deny")

    def test_deny_force_push_with_remote_but_no_ref(self):
        self.assertEqual(decide("git push --force origin", None)[0], "deny")

    def test_deny_force_push_to_head(self):
        self.assertEqual(decide("git push -f origin HEAD", None)[0], "deny")

    def test_deny_force_push_to_at(self):
        self.assertEqual(decide("git push -f origin @", None)[0], "deny")

    def test_allow_force_with_repo_option_and_ref(self):
        # --repo <name> provided; first positional is a refspec
        self.assertEqual(
            decide("git push --force --repo origin feature", None)[0], "allow"
        )

    def test_allow_force_with_repo_option_equal_and_ref(self):
        # --repo=<name> provided; first positional is a refspec
        self.assertEqual(
            decide("git push --force --repo=origin feature", None)[0], "allow"
        )

    def test_deny_force_with_repo_option_to_main(self):
        # --repo provided but refspec points to main -> deny
        self.assertEqual(
            decide("git push --force --repo origin main", None)[0], "deny"
        )

    def test_filename_starting_with_dash_is_not_force_flag(self):
        self.assertEqual(decide("git push -file origin main", None)[0], "allow")

    def test_deny_rm_rf_home(self):
        self.assertEqual(decide("rm -rf /home/x/git/repo", None)[0], "deny")

    def test_deny_rm_uppercase_recursive_force_home(self):
        self.assertEqual(decide("rm -Rf /home/x", None)[0], "deny")

    def test_deny_rm_force_uppercase_recursive_home(self):
        self.assertEqual(decide("rm -fR /home/x", None)[0], "deny")

    def test_deny_rm_long_recursive_force_home(self):
        self.assertEqual(
            decide("rm --recursive --force /home/x", None)[0], "deny"
        )

    def test_deny_rm_recursive_without_force_home(self):
        self.assertEqual(decide("rm -r /home/x", None)[0], "deny")

    def test_allow_rm_rf_tmp(self):
        self.assertEqual(decide("rm -rf /tmp/build-abc", "/tmp")[0], "allow")

    def test_allow_rm_recursive_without_force_tmp(self):
        self.assertEqual(decide("rm -r /tmp/build-abc", "/tmp")[0], "allow")

    def test_deny_rm_long_recursive_without_force_home(self):
        self.assertEqual(decide("rm --recursive /home/x", None)[0], "deny")

    def test_allow_rm_non_recursive_file(self):
        self.assertEqual(decide("rm /home/x/file.txt", None)[0], "allow")

    def test_deny_rm_fr_mixed_paths(self):
        self.assertEqual(decide("rm -fr /tmp/a /etc/passwd", "/tmp")[0], "deny")

    def test_deny_rm_hyphen_path_after_double_dash(self):
        self.assertEqual(
            decide("rm -rf -- /tmp/safe -outside", "/tmp")[0], "deny"
        )

    def test_allow_dashdash_then_hyphen_filename(self):
        # "rm -- -rf" should treat "-rf" as a filename, not flags.
        self.assertEqual(decide("rm -- -rf", None)[0], "allow")

    def test_allow_rf_flags_before_double_dash_with_tmp(self):
        # flags before "--" should be respected; path under tmp allowed
        self.assertEqual(decide("rm -rf -- /tmp/x", "/tmp")[0], "allow")

    def test_deny_rf_flags_before_double_dash_outside_tmp(self):
        # flags before "--" should be respected; path outside tmp denied
        self.assertEqual(decide("rm -rf -- /etc/passwd", "/tmp")[0], "deny")

    def test_deny_rm_in_andand_segment(self):
        self.assertEqual(decide("cd /x && rm -rf /x", None)[0], "deny")

    def test_deny_sudo_rm(self):
        self.assertEqual(decide("sudo rm -rf /x", None)[0], "deny")

    def test_deny_env_time_nohup_wrapped_rm(self):
        self.assertEqual(
            decide("env FOO=bar time nohup rm -rf /x", None)[0], "deny"
        )

    def test_deny_force_push_in_pipe_segment(self):
        self.assertEqual(
            decide("printf x | git push -f origin main", None)[0], "deny"
        )


class ScriptStdinTests(unittest.TestCase):
    def test_stdin_deny_json(self):
        script = (
            Path(__file__).resolve().parents[1]
            / "cursor/hooks/deny_destructive_shell.py"
        )
        proc = subprocess.run(
            [sys.executable, str(script)],
            input=json.dumps({"command": "git push --force origin main"}),
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0)
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["permission"], "deny")
        self.assertEqual(payload["user_message"], payload["agent_message"])

    def test_accepts_shell_command_key(self):
        script = (
            Path(__file__).resolve().parents[1]
            / "cursor/hooks/deny_destructive_shell.py"
        )
        proc = subprocess.run(
            [sys.executable, str(script)],
            input=json.dumps({"shell_command": "git push --force origin main"}),
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(json.loads(proc.stdout)["permission"], "deny")

    def test_invalid_json_fails_closed(self):
        script = (
            Path(__file__).resolve().parents[1]
            / "cursor/hooks/deny_destructive_shell.py"
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
