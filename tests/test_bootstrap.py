import json
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from bootstrap import HOOK_COMMAND, drift_warnings, install, main, merge_hooks_json, sha256_file
from yaml_subset import load_yaml_file, parse_yaml_subset


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def make_repo(root: Path) -> None:
    write(
        root / "catalog.yaml",
        """
profiles:
  core:
    skills: [demo-skill]
    agents: [demo-agent]
    rules: []
    hooks: [demo-hook]
  web-ts: { skills: [], agents: [], rules: [], hooks: [] }
  backend: { skills: [], agents: [], rules: [], hooks: [] }
  infra: { skills: [], agents: [], rules: [], hooks: [] }
skills:
  demo-skill:
    origin: local
    agents: [demo-agent]
agents:
  demo-agent:
    skills: [demo-skill]
rules: {}
hooks: {}
""",
    )
    write(
        root / "manifest.yaml",
        """
local_only:
  - .my-cursor-setup-state.json
files:
  demo-skill:
    src: cursor/skills/demo-skill
    dest: skills/demo-skill
  demo-agent:
    src: cursor/agents/demo-agent.md
    dest: agents/demo-agent.md
  catalog:
    src: catalog.yaml
    dest: my-cursor-setup-catalog.yaml
    always: true
""",
    )
    write(root / "cursor/skills/demo-skill/SKILL.md", "# demo\n")
    write(root / "cursor/agents/demo-agent.md", "# agent\n")


class InstallEngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.repo = self.tmp / "repo"
        self.dest = self.tmp / "dest"
        make_repo(self.repo)
        self.dest.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_copies_core_and_catalog(self):
        result = install(self.repo, self.dest, force=False, dry_run=False, extra_profile=None)
        self.assertTrue((self.dest / "skills/demo-skill/SKILL.md").is_file())
        self.assertTrue((self.dest / "agents/demo-agent.md").is_file())
        self.assertTrue((self.dest / "my-cursor-setup-catalog.yaml").is_file())
        self.assertIn("skills/demo-skill/SKILL.md", result["copied"])

    def test_leaves_unmanaged_file_alone(self):
        write(self.dest / "skills/my-local/SKILL.md", "local\n")
        install(self.repo, self.dest, force=False, dry_run=False, extra_profile=None)
        self.assertEqual((self.dest / "skills/my-local/SKILL.md").read_text(), "local\n")

    def test_does_not_overwrite_unstamped_destination_collision(self):
        target = self.dest / "agents/demo-agent.md"
        write(target, "pre-existing\n")

        result = install(self.repo, self.dest, force=False, dry_run=False, extra_profile=None)

        self.assertEqual(target.read_text(encoding="utf-8"), "pre-existing\n")
        self.assertIn("agents/demo-agent.md", result["skipped_dirty"])

    def test_force_does_not_overwrite_unstamped_destination_collision(self):
        target = self.dest / "agents/demo-agent.md"
        write(target, "pre-existing\n")

        result = install(self.repo, self.dest, force=True, dry_run=False, extra_profile=None)

        self.assertEqual(target.read_text(encoding="utf-8"), "pre-existing\n")
        self.assertIn("agents/demo-agent.md", result["skipped_dirty"])

    def test_skips_dirty_managed_file(self):
        install(self.repo, self.dest, force=False, dry_run=False, extra_profile=None)
        target = self.dest / "agents/demo-agent.md"
        target.write_text("edited locally\n", encoding="utf-8")
        result = install(self.repo, self.dest, force=False, dry_run=False, extra_profile=None)
        self.assertEqual(target.read_text(encoding="utf-8"), "edited locally\n")
        self.assertIn("agents/demo-agent.md", result["skipped_dirty"])

    def test_force_overwrites_dirty(self):
        install(self.repo, self.dest, force=False, dry_run=False, extra_profile=None)
        target = self.dest / "agents/demo-agent.md"
        target.write_text("edited locally\n", encoding="utf-8")
        install(self.repo, self.dest, force=True, dry_run=False, extra_profile=None)
        self.assertEqual(target.read_text(encoding="utf-8"), "# agent\n")

    def test_dry_run_does_not_write(self):
        install(self.repo, self.dest, force=False, dry_run=True, extra_profile=None)
        self.assertFalse((self.dest / "agents/demo-agent.md").exists())
        self.assertFalse((self.dest / ".my-cursor-setup-state.json").exists())

    def test_adopts_identical_unstamped_files_after_state_loss(self):
        install(self.repo, self.dest, force=False, dry_run=False, extra_profile=None)
        state_path = self.dest / ".my-cursor-setup-state.json"
        state_path.unlink()

        result = install(
            self.repo, self.dest, force=False, dry_run=False, extra_profile=None
        )

        self.assertNotIn("agents/demo-agent.md", result["skipped_dirty"])
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertIn("agents/demo-agent.md", state["stamps"])

    def test_prune_removes_stamp_not_in_plan(self):
        install(
            self.repo, self.dest, force=False, dry_run=False, extra_profile=None
        )
        extra = self.dest / "skills/gone/SKILL.md"
        write(extra, "# gone\n")
        state_path = self.dest / ".my-cursor-setup-state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["stamps"]["skills/gone/SKILL.md"] = sha256_file(extra)
        state_path.write_text(json.dumps(state), encoding="utf-8")
        result = install(
            self.repo, self.dest, force=False, dry_run=False, extra_profile=None
        )
        self.assertFalse(extra.exists())
        self.assertIn("skills/gone/SKILL.md", result["removed"])
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertNotIn("skills/gone/SKILL.md", state["stamps"])

    def test_prune_skips_dirty_stamp(self):
        install(
            self.repo, self.dest, force=False, dry_run=False, extra_profile=None
        )
        extra = self.dest / "skills/gone/SKILL.md"
        write(extra, "# gone\n")
        state_path = self.dest / ".my-cursor-setup-state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["stamps"]["skills/gone/SKILL.md"] = sha256_file(extra)
        state_path.write_text(json.dumps(state), encoding="utf-8")
        extra.write_text("# edited\n", encoding="utf-8")
        result = install(
            self.repo, self.dest, force=False, dry_run=False, extra_profile=None
        )
        self.assertTrue(extra.is_file())
        self.assertIn("skills/gone/SKILL.md", result["skipped_dirty"])
        self.assertEqual(extra.read_text(encoding="utf-8"), "# edited\n")

    def test_prune_does_not_delete_unstamped(self):
        install(
            self.repo, self.dest, force=False, dry_run=False, extra_profile=None
        )
        extra = self.dest / "skills/local/SKILL.md"
        write(extra, "local\n")
        install(
            self.repo, self.dest, force=False, dry_run=False, extra_profile=None
        )
        self.assertEqual(extra.read_text(encoding="utf-8"), "local\n")


class MergeHooksTests(unittest.TestCase):
    def test_creates_when_missing(self):
        payload = {
            "version": 1,
            "hooks": {
                "beforeShellExecution": [
                    {"command": HOOK_COMMAND, "failClosed": False}
                ]
            },
        }
        out = merge_hooks_json(payload, None)
        self.assertEqual(out["version"], 1)
        self.assertEqual(
            out["hooks"]["beforeShellExecution"][0]["command"], HOOK_COMMAND
        )

    def test_preserves_foreign_hooks(self):
        existing = {
            "version": 1,
            "hooks": {
                "beforeShellExecution": [
                    {"command": "./hooks/other.sh"},
                    {"command": HOOK_COMMAND, "failClosed": True},
                ]
            },
        }
        payload = {
            "version": 1,
            "hooks": {
                "beforeShellExecution": [
                    {"command": HOOK_COMMAND, "failClosed": False}
                ]
            },
        }
        out = merge_hooks_json(payload, existing)
        commands = [h["command"] for h in out["hooks"]["beforeShellExecution"]]
        self.assertEqual(commands.count("./hooks/other.sh"), 1)
        self.assertEqual(commands.count(HOOK_COMMAND), 1)
        ours = next(
            h
            for h in out["hooks"]["beforeShellExecution"]
            if h["command"] == HOOK_COMMAND
        )
        self.assertFalse(ours["failClosed"])

    def test_merges_before_read_file_without_dropping_shell(self):
        existing = {
            "version": 1,
            "hooks": {
                "beforeShellExecution": [
                    {"command": "./hooks/other.sh"},
                    {"command": HOOK_COMMAND, "failClosed": True},
                ]
            },
        }
        payload = {
            "version": 1,
            "hooks": {
                "beforeShellExecution": [
                    {"command": HOOK_COMMAND, "failClosed": False}
                ],
                "beforeReadFile": [
                    {
                        "command": "./hooks/deny_secret_reads.py",
                        "failClosed": False,
                    }
                ],
            },
        }
        out = merge_hooks_json(payload, existing)
        shell = [h["command"] for h in out["hooks"]["beforeShellExecution"]]
        self.assertEqual(shell.count("./hooks/other.sh"), 1)
        self.assertEqual(shell.count(HOOK_COMMAND), 1)
        self.assertFalse(
            next(
                h
                for h in out["hooks"]["beforeShellExecution"]
                if h["command"] == HOOK_COMMAND
            )["failClosed"]
        )
        self.assertEqual(
            out["hooks"]["beforeReadFile"][0]["command"],
            "./hooks/deny_secret_reads.py",
        )


class DriftTests(unittest.TestCase):
    def test_reports_missing_inverse_edge(self):
        catalog = parse_yaml_subset(
            """
skills:
  a:
    agents: [x]
agents:
  x:
    skills: []
"""
        )
        warnings = drift_warnings(catalog)
        self.assertTrue(any("x" in w and "a" in w for w in warnings))

    def test_clean_when_symmetric(self):
        catalog = parse_yaml_subset(
            """
skills:
  a:
    agents: [x]
agents:
  x:
    skills: [a]
"""
        )
        self.assertEqual(drift_warnings(catalog), [])

    def test_persona_missing_inverse_edge(self):
        catalog = parse_yaml_subset(
            """
skills:
  s:
    agents: []
    personas: [p]
personas:
  p:
    skills: []
"""
        )
        warnings = drift_warnings(catalog)
        self.assertTrue(any("p" in w and "s" in w for w in warnings))

    def test_persona_symmetric_is_clean(self):
        catalog = parse_yaml_subset(
            """
skills:
  s:
    agents: []
    personas: [p]
personas:
  p:
    skills: [s]
"""
        )
        self.assertEqual(drift_warnings(catalog), [])


class CliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.repo = self.tmp / "repo"
        self.dest = self.tmp / "dest"
        make_repo(self.repo)
        write(
            self.repo / "cursor/hooks.json",
            json.dumps(
                {
                    "version": 1,
                    "hooks": {
                        "beforeShellExecution": [
                            {"command": HOOK_COMMAND, "failClosed": False}
                        ]
                    },
                }
            ),
        )
        write(
            self.repo / "manifest.yaml",
            (self.repo / "manifest.yaml").read_text(encoding="utf-8")
            + """
  hooks-json:
    src: cursor/config/custom-hooks.json
    dest: config/hooks.json
    merge: hooks
    hook: demo-hook
""",
        )
        (self.repo / "cursor/config").mkdir(parents=True)
        (self.repo / "cursor/hooks.json").replace(
            self.repo / "cursor/config/custom-hooks.json"
        )
        self.dest.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_dest_and_status(self):
        code = main(
            [
                "--dest",
                str(self.dest),
                "--repo",
                str(self.repo),
            ]
        )
        self.assertEqual(code, 0)
        self.assertTrue((self.dest / "config/hooks.json").is_file())
        data = json.loads(
            (self.dest / "config/hooks.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            data["hooks"]["beforeShellExecution"][0]["command"], HOOK_COMMAND
        )
        code = main(
            ["--status", "--dest", str(self.dest), "--repo", str(self.repo)]
        )
        self.assertEqual(code, 0)

    def test_merges_into_unstamped_foreign_hooks_json(self):
        foreign = {"command": "./hooks/foreign.py", "failClosed": True}
        target = self.dest / "config/hooks.json"
        write(
            target,
            json.dumps(
                {
                    "version": 1,
                    "hooks": {"beforeShellExecution": [foreign]},
                }
            ),
        )

        code = main(["--dest", str(self.dest), "--repo", str(self.repo)])

        self.assertEqual(code, 0)
        hooks = json.loads(target.read_text(encoding="utf-8"))
        entries = hooks["hooks"]["beforeShellExecution"]
        self.assertIn(foreign, entries)
        self.assertTrue(any(item.get("command") == HOOK_COMMAND for item in entries))

    def test_does_not_merge_when_hook_is_not_enabled(self):
        catalog_path = self.repo / "catalog.yaml"
        catalog_path.write_text(
            catalog_path.read_text(encoding="utf-8").replace(
                "hooks: [demo-hook]", "hooks: []"
            ),
            encoding="utf-8",
        )
        shutil.copy2(
            self.repo / "cursor/config/custom-hooks.json",
            self.repo / "cursor/hooks.json",
        )

        code = main(["--dest", str(self.dest), "--repo", str(self.repo)])

        self.assertEqual(code, 0)
        self.assertFalse((self.dest / "config/hooks.json").exists())
        self.assertFalse((self.dest / "hooks.json").exists())

    def test_cli_dry_run_does_not_write(self):
        stdout = StringIO()
        with redirect_stdout(stdout):
            code = main(
                [
                    "--dry-run",
                    "--dest",
                    str(self.dest),
                    "--repo",
                    str(self.repo),
                ]
            )

        self.assertEqual(code, 0)
        self.assertIn("copied:", stdout.getvalue())
        self.assertFalse((self.dest / "config/hooks.json").exists())
        self.assertFalse((self.dest / ".my-cursor-setup-state.json").exists())

    def test_profile_persists(self):
        main(
            [
                "--dest",
                str(self.dest),
                "--repo",
                str(self.repo),
                "--profile",
                "web-ts",
            ]
        )
        state = json.loads(
            (self.dest / ".my-cursor-setup-state.json").read_text()
        )
        self.assertEqual(state["profiles"], ["core", "web-ts"])

    def test_status_prints_managed_paths(self):
        main(["--dest", str(self.dest), "--repo", str(self.repo)])
        stdout = StringIO()
        with redirect_stdout(stdout):
            code = main(
                ["--status", "--dest", str(self.dest), "--repo", str(self.repo)]
            )
        self.assertEqual(code, 0)
        self.assertIn("in-sync: config/hooks.json", stdout.getvalue())
        self.assertIn("in-sync: agents/demo-agent.md", stdout.getvalue())


class DomainProfileTests(unittest.TestCase):
    def setUp(self):
        self.repo = Path(__file__).resolve().parents[1]
        self.dest = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.dest, ignore_errors=True)

    def test_core_omits_backend_skills(self):
        self.assertEqual(main(["--dest", str(self.dest), "--repo", str(self.repo)]), 0)
        self.assertFalse((self.dest / "skills/node-api-conventions/SKILL.md").exists())
        self.assertFalse((self.dest / "skills/python-api-conventions/SKILL.md").exists())
        self.assertFalse((self.dest / "skills/domain-reviewer/SKILL.md").exists())

    def test_core_omits_docker_and_kubernetes_skills(self):
        main(["--dest", str(self.dest), "--repo", str(self.repo)])
        self.assertFalse(
            (self.dest / "skills/docker-conventions/SKILL.md").exists()
        )
        self.assertFalse((self.dest / "skills/kubernetes-skill/SKILL.md").exists())

    def test_core_omits_github_actions_skill(self):
        main(["--dest", str(self.dest), "--repo", str(self.repo)])
        self.assertFalse(
            (self.dest / "skills/github-actions/SKILL.md").exists()
        )
        self.assertFalse(
            (self.dest / "rules/github-actions-files.mdc").exists()
        )

    def test_core_omits_rag_and_mcp_skills(self):
        main(["--dest", str(self.dest), "--repo", str(self.repo)])
        self.assertFalse((self.dest / "skills/llamaindex-ingest/SKILL.md").exists())
        self.assertFalse((self.dest / "skills/pydantic-ai-rag/SKILL.md").exists())
        self.assertFalse((self.dest / "skills/fastmcp/SKILL.md").exists())

    def test_rag_profile_installs_ingest_rag_and_db(self):
        code = main(
            ["--dest", str(self.dest), "--repo", str(self.repo), "--profile", "rag"]
        )
        self.assertEqual(code, 0)
        self.assertTrue((self.dest / "skills/llamaindex-ingest/SKILL.md").is_file())
        self.assertTrue((self.dest / "skills/pydantic-ai-rag/SKILL.md").is_file())
        self.assertTrue(
            (self.dest / "skills/python-db-conventions/SKILL.md").is_file()
        )
        self.assertTrue((self.dest / "skills/domain-reviewer/SKILL.md").is_file())
        self.assertFalse((self.dest / "skills/fastmcp/SKILL.md").exists())
        self.assertFalse(
            (self.dest / "skills/vercel-react-best-practices/SKILL.md").exists()
        )
        installed = load_yaml_file(self.dest / "my-cursor-setup-catalog.yaml")
        self.assertIn("tdd", installed["personas"]["rag"]["skills"])
        self.assertIn(
            "verification-before-completion",
            installed["personas"]["rag"]["skills"],
        )
        self.assertIn("llamaindex-ingest", installed["personas"]["rag"]["skills"])
        self.assertIn("pydantic-ai-rag", installed["personas"]["rag"]["skills"])
        self.assertIn(
            "python-db-conventions", installed["personas"]["rag"]["skills"]
        )
        self.assertIn("rag", installed["skills"]["llamaindex-ingest"]["personas"])
        self.assertIn("rag", installed["skills"]["pydantic-ai-rag"]["personas"])
        self.assertIn(
            "rag", installed["skills"]["python-db-conventions"]["personas"]
        )
        self.assertIn("rag", installed["skills"]["tdd"]["personas"])
        self.assertNotIn("fastmcp", installed["personas"]["rag"]["skills"])

    def test_mcp_profile_installs_fastmcp_not_rag(self):
        code = main(
            ["--dest", str(self.dest), "--repo", str(self.repo), "--profile", "mcp"]
        )
        self.assertEqual(code, 0)
        self.assertTrue((self.dest / "skills/fastmcp/SKILL.md").is_file())
        self.assertTrue((self.dest / "skills/domain-reviewer/SKILL.md").is_file())
        self.assertFalse((self.dest / "skills/llamaindex-ingest/SKILL.md").exists())
        self.assertFalse((self.dest / "skills/pydantic-ai-rag/SKILL.md").exists())
        installed = load_yaml_file(self.dest / "my-cursor-setup-catalog.yaml")
        self.assertEqual(
            installed["personas"]["mcp"]["skills"],
            ["fastmcp", "tdd", "verification-before-completion"],
        )
        self.assertIn("mcp", installed["skills"]["fastmcp"]["personas"])
        self.assertIn("mcp", installed["skills"]["tdd"]["personas"])
        self.assertNotIn("mcp", installed["skills"]["llamaindex-ingest"]["personas"])

    def test_rag_then_mcp_accumulates(self):
        main(
            ["--dest", str(self.dest), "--repo", str(self.repo), "--profile", "rag"]
        )
        main(
            ["--dest", str(self.dest), "--repo", str(self.repo), "--profile", "mcp"]
        )
        self.assertTrue((self.dest / "skills/llamaindex-ingest/SKILL.md").is_file())
        self.assertTrue((self.dest / "skills/pydantic-ai-rag/SKILL.md").is_file())
        self.assertTrue((self.dest / "skills/fastmcp/SKILL.md").is_file())

    def test_state_drop_prunes_web_ts_on_next_bootstrap(self):
        main(
            [
                "--dest",
                str(self.dest),
                "--repo",
                str(self.repo),
                "--profile",
                "web-ts",
            ]
        )
        skill = self.dest / "skills/vercel-react-best-practices/SKILL.md"
        self.assertTrue(skill.is_file())
        state_path = self.dest / ".my-cursor-setup-state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["profiles"] = ["core"]
        state_path.write_text(json.dumps(state), encoding="utf-8")
        stdout = StringIO()
        with redirect_stdout(stdout):
            code = main(["--dest", str(self.dest), "--repo", str(self.repo)])
        self.assertEqual(code, 0)
        self.assertFalse(skill.exists())
        self.assertIn("removed:", stdout.getvalue())

    def test_disable_web_ts_removes_vercel_keeps_core(self):
        main(
            [
                "--dest",
                str(self.dest),
                "--repo",
                str(self.repo),
                "--profile",
                "web-ts",
            ]
        )
        code = main(
            [
                "--dest",
                str(self.dest),
                "--repo",
                str(self.repo),
                "--disable-profile",
                "web-ts",
            ]
        )
        self.assertEqual(code, 0)
        self.assertFalse(
            (self.dest / "skills/vercel-react-best-practices/SKILL.md").exists()
        )
        self.assertFalse((self.dest / "rules/web-ts-ui.mdc").exists())
        self.assertTrue((self.dest / "rules/commit-style.mdc").is_file())
        state = json.loads(
            (self.dest / ".my-cursor-setup-state.json").read_text()
        )
        self.assertEqual(state["profiles"], ["core"])

    def test_disable_web_ts_keeps_shared_reviewer_when_backend_on(self):
        main(
            [
                "--dest",
                str(self.dest),
                "--repo",
                str(self.repo),
                "--profile",
                "web-ts",
            ]
        )
        main(
            [
                "--dest",
                str(self.dest),
                "--repo",
                str(self.repo),
                "--profile",
                "backend",
            ]
        )
        main(
            [
                "--dest",
                str(self.dest),
                "--repo",
                str(self.repo),
                "--disable-profile",
                "web-ts",
            ]
        )
        self.assertFalse(
            (self.dest / "skills/vercel-react-best-practices/SKILL.md").exists()
        )
        self.assertTrue(
            (self.dest / "skills/node-api-conventions/SKILL.md").is_file()
        )
        self.assertTrue(
            (self.dest / "skills/domain-reviewer/SKILL.md").is_file()
        )

    def test_disable_core_rejected(self):
        main(["--dest", str(self.dest), "--repo", str(self.repo)])
        code = main(
            [
                "--dest",
                str(self.dest),
                "--repo",
                str(self.repo),
                "--disable-profile",
                "core",
            ]
        )
        self.assertNotEqual(code, 0)
        self.assertTrue((self.dest / "rules/commit-style.mdc").is_file())

    def test_disable_unknown_rejected(self):
        code = main(
            [
                "--dest",
                str(self.dest),
                "--repo",
                str(self.repo),
                "--disable-profile",
                "nosuch",
            ]
        )
        self.assertNotEqual(code, 0)

    def test_disable_absent_profile_idempotent(self):
        main(["--dest", str(self.dest), "--repo", str(self.repo)])
        code = main(
            [
                "--dest",
                str(self.dest),
                "--repo",
                str(self.repo),
                "--disable-profile",
                "web-ts",
            ]
        )
        self.assertEqual(code, 0)

    def test_disable_dirty_skipped_without_force(self):
        main(
            [
                "--dest",
                str(self.dest),
                "--repo",
                str(self.repo),
                "--profile",
                "web-ts",
            ]
        )
        skill = self.dest / "skills/vercel-react-best-practices/SKILL.md"
        skill.write_text("edited\n", encoding="utf-8")
        stdout = StringIO()
        with redirect_stdout(stdout):
            code = main(
                [
                    "--dest",
                    str(self.dest),
                    "--repo",
                    str(self.repo),
                    "--disable-profile",
                    "web-ts",
                ]
            )
        self.assertEqual(code, 0)
        self.assertTrue(skill.is_file())
        self.assertIn("skipped_dirty:", stdout.getvalue())

    def test_disable_dry_run_does_not_persist(self):
        main(
            [
                "--dest",
                str(self.dest),
                "--repo",
                str(self.repo),
                "--profile",
                "web-ts",
            ]
        )
        main(
            [
                "--disable-profile",
                "web-ts",
                "--dry-run",
                "--dest",
                str(self.dest),
                "--repo",
                str(self.repo),
            ]
        )
        self.assertTrue(
            (self.dest / "skills/vercel-react-best-practices/SKILL.md").is_file()
        )
        state = json.loads(
            (self.dest / ".my-cursor-setup-state.json").read_text()
        )
        self.assertIn("web-ts", state["profiles"])

    def test_uninstall_removes_core_payload(self):
        main(["--dest", str(self.dest), "--repo", str(self.repo)])
        code = main(
            ["--uninstall", "--dest", str(self.dest), "--repo", str(self.repo)]
        )
        self.assertEqual(code, 0)
        self.assertFalse((self.dest / "rules/commit-style.mdc").exists())
        self.assertFalse((self.dest / "hooks/safety_match.py").exists())
        self.assertFalse(
            (self.dest / ".my-cursor-setup-state.json").exists()
        )
        hooks_path = self.dest / "hooks.json"
        if hooks_path.is_file():
            data = json.loads(hooks_path.read_text(encoding="utf-8"))
            commands = [
                item.get("command")
                for event in (data.get("hooks") or {}).values()
                for item in event
            ]
            self.assertNotIn("./hooks/deny_destructive_shell.py", commands)

    def test_uninstall_empty_dest_ok(self):
        code = main(
            ["--uninstall", "--dest", str(self.dest), "--repo", str(self.repo)]
        )
        self.assertEqual(code, 0)

    def test_uninstall_keeps_foreign_hook(self):
        main(["--dest", str(self.dest), "--repo", str(self.repo)])
        hooks_path = self.dest / "hooks.json"
        data = json.loads(hooks_path.read_text(encoding="utf-8"))
        data["hooks"]["beforeShellExecution"].append(
            {"command": "./hooks/foreign.py", "failClosed": True}
        )
        hooks_path.write_text(json.dumps(data), encoding="utf-8")
        state_path = self.dest / ".my-cursor-setup-state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["stamps"]["hooks.json"] = sha256_file(hooks_path)
        state_path.write_text(json.dumps(state), encoding="utf-8")
        main(
            ["--uninstall", "--dest", str(self.dest), "--repo", str(self.repo)]
        )
        data = json.loads(hooks_path.read_text(encoding="utf-8"))
        commands = [
            item.get("command")
            for event in (data.get("hooks") or {}).values()
            for item in event
        ]
        self.assertIn("./hooks/foreign.py", commands)
        self.assertNotIn("./hooks/deny_destructive_shell.py", commands)

    def test_uninstall_dirty_without_force_keeps_file(self):
        main(["--dest", str(self.dest), "--repo", str(self.repo)])
        target = self.dest / "rules/commit-style.mdc"
        target.write_text("edited\n", encoding="utf-8")
        code = main(
            ["--uninstall", "--dest", str(self.dest), "--repo", str(self.repo)]
        )
        self.assertEqual(code, 0)
        self.assertTrue(target.is_file())
        self.assertTrue(
            (self.dest / ".my-cursor-setup-state.json").is_file()
        )
        main(
            [
                "--uninstall",
                "--force",
                "--dest",
                str(self.dest),
                "--repo",
                str(self.repo),
            ]
        )
        self.assertFalse(target.exists())

    def test_uninstall_rejects_profile_flags(self):
        code = main(
            [
                "--uninstall",
                "--profile",
                "web-ts",
                "--dest",
                str(self.dest),
                "--repo",
                str(self.repo),
            ]
        )
        self.assertNotEqual(code, 0)
        code = main(
            [
                "--uninstall",
                "--disable-profile",
                "web-ts",
                "--dest",
                str(self.dest),
                "--repo",
                str(self.repo),
            ]
        )
        self.assertNotEqual(code, 0)

    def test_status_reports_dirty(self):
        main(["--dest", str(self.dest), "--repo", str(self.repo)])
        (self.dest / "rules/commit-style.mdc").write_text(
            "edited\n", encoding="utf-8"
        )
        stdout = StringIO()
        with redirect_stdout(stdout):
            code = main(
                ["--status", "--dest", str(self.dest), "--repo", str(self.repo)]
            )
        self.assertEqual(code, 0)
        self.assertIn("dirty: rules/commit-style.mdc", stdout.getvalue())

    def test_status_reports_orphan(self):
        main(
            [
                "--dest",
                str(self.dest),
                "--repo",
                str(self.repo),
                "--profile",
                "web-ts",
            ]
        )
        state_path = self.dest / ".my-cursor-setup-state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["profiles"] = ["core"]
        state_path.write_text(json.dumps(state), encoding="utf-8")
        stdout = StringIO()
        with redirect_stdout(stdout):
            code = main(
                ["--status", "--dest", str(self.dest), "--repo", str(self.repo)]
            )
        self.assertEqual(code, 0)
        self.assertIn(
            "orphan: skills/vercel-react-best-practices/SKILL.md",
            stdout.getvalue(),
        )

    def test_status_rejects_mutate_flags(self):
        dest = str(self.dest)
        repo = str(self.repo)
        for extra in (
            ["--status", "--uninstall"],
            ["--status", "--disable-profile", "web-ts"],
            ["--status", "--profile", "web-ts"],
            ["--status", "--dry-run"],
            ["--status", "--force"],
        ):
            code = main([*extra, "--dest", dest, "--repo", repo])
            self.assertNotEqual(code, 0, extra)

    def test_backend_profile_installs_node_python_and_reviewer(self):
        code = main(
            ["--dest", str(self.dest), "--repo", str(self.repo), "--profile", "backend"]
        )
        self.assertEqual(code, 0)
        self.assertTrue((self.dest / "skills/node-api-conventions/SKILL.md").is_file())
        self.assertTrue((self.dest / "skills/python-api-conventions/SKILL.md").is_file())
        self.assertTrue((self.dest / "skills/domain-reviewer/SKILL.md").is_file())
        self.assertTrue((self.dest / "rules/backend-node.mdc").is_file())
        self.assertTrue((self.dest / "rules/backend-python.mdc").is_file())
        self.assertFalse((self.dest / "skills/terraform-skill/SKILL.md").exists())
        self.assertFalse(
            (self.dest / "skills/vercel-react-best-practices/SKILL.md").exists()
        )

    def test_web_ts_profile_installs_vercel_not_terraform(self):
        code = main(
            ["--dest", str(self.dest), "--repo", str(self.repo), "--profile", "web-ts"]
        )
        self.assertEqual(code, 0)
        self.assertTrue(
            (self.dest / "skills/vercel-react-best-practices/SKILL.md").is_file()
        )
        self.assertTrue((self.dest / "skills/domain-reviewer/SKILL.md").is_file())
        self.assertTrue((self.dest / "rules/web-ts-ui.mdc").is_file())
        self.assertFalse((self.dest / "skills/terraform-skill/SKILL.md").exists())
        self.assertFalse((self.dest / "skills/node-api-conventions/SKILL.md").exists())

    def test_infra_profile_installs_terraform_not_vercel(self):
        code = main(
            ["--dest", str(self.dest), "--repo", str(self.repo), "--profile", "infra"]
        )
        self.assertEqual(code, 0)
        self.assertTrue((self.dest / "skills/terraform-skill/SKILL.md").is_file())
        self.assertTrue((self.dest / "rules/terraform-files.mdc").is_file())
        self.assertTrue((self.dest / "skills/docker-conventions/SKILL.md").is_file())
        self.assertTrue((self.dest / "rules/docker-files.mdc").is_file())
        self.assertTrue((self.dest / "skills/kubernetes-skill/SKILL.md").is_file())
        self.assertTrue((self.dest / "rules/k8s-files.mdc").is_file())
        self.assertTrue(
            (self.dest / "skills/kubernetes-skill/references/conditional/eks-patterns.md").is_file()
        )
        self.assertFalse(
            (self.dest / "skills/kubernetes-skill/references/conditional/gke-patterns.md").exists()
        )
        self.assertFalse(
            (self.dest / "skills/vercel-react-best-practices/SKILL.md").exists()
        )
        self.assertFalse(
            (self.dest / "skills/github-actions/SKILL.md").exists()
        )

    def test_profiles_accumulate(self):
        main(["--dest", str(self.dest), "--repo", str(self.repo), "--profile", "web-ts"])
        main(["--dest", str(self.dest), "--repo", str(self.repo), "--profile", "backend"])
        self.assertTrue(
            (self.dest / "skills/vercel-react-best-practices/SKILL.md").is_file()
        )
        self.assertTrue((self.dest / "skills/node-api-conventions/SKILL.md").is_file())

    def test_core_omits_python_db_skill(self):
        main(["--dest", str(self.dest), "--repo", str(self.repo)])
        self.assertFalse(
            (self.dest / "skills/python-db-conventions/SKILL.md").exists()
        )
        self.assertFalse((self.dest / "skills/prisma-cli/SKILL.md").exists())
        self.assertFalse((self.dest / "skills/prisma-client-api/SKILL.md").exists())
        self.assertFalse(
            (self.dest / "skills/prisma-database-setup/SKILL.md").exists()
        )

    def test_db_profile_installs_python_db(self):
        code = main(
            ["--dest", str(self.dest), "--repo", str(self.repo), "--profile", "db"]
        )
        self.assertEqual(code, 0)
        self.assertTrue(
            (self.dest / "skills/python-db-conventions/SKILL.md").is_file()
        )
        self.assertTrue((self.dest / "skills/domain-reviewer/SKILL.md").is_file())
        self.assertTrue((self.dest / "rules/db-python.mdc").is_file())
        self.assertTrue((self.dest / "rules/db-prisma.mdc").is_file())
        self.assertFalse(
            (self.dest / "skills/vercel-react-best-practices/SKILL.md").exists()
        )
        self.assertTrue((self.dest / "skills/prisma-cli/SKILL.md").is_file())
        self.assertTrue((self.dest / "skills/prisma-client-api/SKILL.md").is_file())
        self.assertTrue(
            (self.dest / "skills/prisma-database-setup/SKILL.md").is_file()
        )
        self.assertFalse((self.dest / "skills/terraform-skill/SKILL.md").exists())

    def test_db_then_web_ts_accumulates(self):
        main(["--dest", str(self.dest), "--repo", str(self.repo), "--profile", "db"])
        main(["--dest", str(self.dest), "--repo", str(self.repo), "--profile", "web-ts"])
        self.assertTrue((self.dest / "skills/python-db-conventions/SKILL.md").is_file())
        self.assertTrue((self.dest / "skills/prisma-cli/SKILL.md").is_file())
        self.assertTrue(
            (self.dest / "skills/vercel-react-best-practices/SKILL.md").is_file()
        )

    def test_infra_then_web_ts_accumulates(self):
        main(["--dest", str(self.dest), "--repo", str(self.repo), "--profile", "infra"])
        main(["--dest", str(self.dest), "--repo", str(self.repo), "--profile", "web-ts"])
        self.assertTrue((self.dest / "skills/terraform-skill/SKILL.md").is_file())
        self.assertTrue((self.dest / "skills/docker-conventions/SKILL.md").is_file())
        self.assertTrue((self.dest / "skills/kubernetes-skill/SKILL.md").is_file())
        self.assertTrue(
            (self.dest / "skills/vercel-react-best-practices/SKILL.md").is_file()
        )

    def test_ci_profile_installs_github_actions(self):
        code = main(
            ["--dest", str(self.dest), "--repo", str(self.repo), "--profile", "ci"]
        )
        self.assertEqual(code, 0)
        self.assertTrue(
            (self.dest / "skills/github-actions/SKILL.md").is_file()
        )
        self.assertTrue(
            (self.dest / "rules/github-actions-files.mdc").is_file()
        )
        self.assertTrue((self.dest / "skills/domain-reviewer/SKILL.md").is_file())
        self.assertFalse(
            (self.dest / "skills/vercel-react-best-practices/SKILL.md").exists()
        )
        self.assertFalse((self.dest / "skills/terraform-skill/SKILL.md").exists())
        self.assertFalse(
            (self.dest / "skills/docker-conventions/SKILL.md").exists()
        )
        self.assertFalse((self.dest / "skills/kubernetes-skill/SKILL.md").exists())
        self.assertFalse((self.dest / "skills/prisma-cli/SKILL.md").exists())

    def test_ci_then_web_ts_accumulates(self):
        main(
            ["--dest", str(self.dest), "--repo", str(self.repo), "--profile", "ci"]
        )
        main(
            [
                "--dest",
                str(self.dest),
                "--repo",
                str(self.repo),
                "--profile",
                "web-ts",
            ]
        )
        self.assertTrue(
            (self.dest / "skills/github-actions/SKILL.md").is_file()
        )
        self.assertTrue(
            (self.dest / "skills/vercel-react-best-practices/SKILL.md").is_file()
        )


class V1RepoTests(unittest.TestCase):
    def test_real_catalog_installs_core(self):
        repo = Path(__file__).resolve().parents[1]
        dest = Path(tempfile.mkdtemp())
        try:
            code = main(["--dest", str(dest), "--repo", str(repo)])
            self.assertEqual(code, 0)
            self.assertTrue(
                (dest / "skills/verification-before-completion/SKILL.md").is_file()
            )
            self.assertTrue((dest / "skills/tdd/SKILL.md").is_file())
            self.assertFalse((dest / "agents/implementer.md").exists())
            self.assertFalse((dest / "agents/reviewer.md").exists())
            self.assertTrue((dest / "rules/route-context.mdc").is_file())
            self.assertTrue((dest / "rules/commit-style.mdc").is_file())
            self.assertTrue((dest / "rules/quality-style.mdc").is_file())
            installed = load_yaml_file(dest / "my-cursor-setup-catalog.yaml")
            self.assertEqual(installed["profiles"]["core"]["agents"], [])
            self.assertNotIn("implementer", installed.get("agents") or {})
            self.assertNotIn("reviewer", installed.get("agents") or {})
            impl_personas = [
                "web-ts",
                "backend-node",
                "backend-python",
                "infra",
                "db-python",
                "db-prisma",
                "ci",
            ]
            for pid in impl_personas:
                skills = installed["personas"][pid]["skills"]
                self.assertIn("tdd", skills, pid)
                self.assertIn("verification-before-completion", skills, pid)
            self.assertIn(
                "verification-before-completion",
                installed["personas"]["domain-reviewer"]["skills"],
            )
            self.assertNotIn("tdd", installed["personas"]["domain-reviewer"]["skills"])
            self.assertEqual(installed["skills"]["tdd"]["agents"], [])
            self.assertEqual(
                installed["skills"]["verification-before-completion"]["agents"], []
            )
            for pid in impl_personas:
                self.assertIn(pid, installed["skills"]["tdd"]["personas"])
                self.assertIn(
                    pid,
                    installed["skills"]["verification-before-completion"]["personas"],
                )
            self.assertIn(
                "domain-reviewer",
                installed["skills"]["verification-before-completion"]["personas"],
            )
            self.assertIn("quality-style", installed["profiles"]["core"]["rules"])
            self.assertTrue(installed["rules"]["quality-style"]["alwaysApply"])
            self.assertTrue((dest / "hooks/deny_destructive_shell.py").is_file())
            self.assertTrue(
                (dest / "hooks/deny_destructive_shell.py").stat().st_mode & 0o111
            )
            self.assertTrue((dest / "my-cursor-setup-catalog.yaml").is_file())
            hooks = json.loads((dest / "hooks.json").read_text(encoding="utf-8"))
            self.assertEqual(
                hooks["hooks"]["beforeShellExecution"][0]["command"],
                HOOK_COMMAND,
            )
            self.assertTrue(
                hooks["hooks"]["beforeShellExecution"][0]["failClosed"]
            )
            for name in (
                "deny_destructive_db.py",
                "deny_secrets_shell.py",
                "ask_unexpected_network.py",
                "deny_secret_reads.py",
                "deny_destructive_containers.py",
                "deny_destructive_github.py",
            ):
                path = dest / "hooks" / name
                self.assertTrue(path.is_file(), name)
            commands = [
                h["command"]
                for h in hooks["hooks"]["beforeShellExecution"]
            ]
            self.assertIn(HOOK_COMMAND, commands)
            self.assertIn("./hooks/deny_destructive_db.py", commands)
            self.assertIn("./hooks/deny_secrets_shell.py", commands)
            self.assertIn("./hooks/ask_unexpected_network.py", commands)
            self.assertIn("./hooks/deny_destructive_containers.py", commands)
            self.assertIn("./hooks/deny_destructive_github.py", commands)
            self.assertEqual(
                hooks["hooks"]["beforeReadFile"][0]["command"],
                "./hooks/deny_secret_reads.py",
            )
            self.assertTrue(hooks["hooks"]["beforeReadFile"][0]["failClosed"])
            self.assertFalse(
                (dest / "skills/python-db-conventions/SKILL.md").exists()
            )
            catalog = load_yaml_file(repo / "catalog.yaml")
            self.assertEqual(drift_warnings(catalog), [])
        finally:
            shutil.rmtree(dest, ignore_errors=True)


class DefaultDestConfirmTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.repo = Path(__file__).resolve().parents[1]

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_nontty_omitted_dest_fails_closed(self):
        with (
            patch("bootstrap.Path.home", return_value=self.home),
            patch("sys.stdin.isatty", return_value=False),
        ):
            code = main(["--repo", str(self.repo)])
        self.assertNotEqual(code, 0)
        self.assertFalse((self.home / ".cursor").exists())

    def test_tty_wrong_line_fails_closed(self):
        stdin = StringIO("nope\n")
        stdin.isatty = lambda: True  # type: ignore[method-assign]
        with (
            patch("bootstrap.Path.home", return_value=self.home),
            patch("sys.stdin", stdin),
        ):
            code = main(["--repo", str(self.repo)])
        self.assertNotEqual(code, 0)
        self.assertFalse((self.home / ".cursor").exists())

    def test_tty_matching_path_installs(self):
        dest = self.home / ".cursor"
        stdin = StringIO(str(dest) + "\n")
        stdin.isatty = lambda: True  # type: ignore[method-assign]
        with (
            patch("bootstrap.Path.home", return_value=self.home),
            patch("sys.stdin", stdin),
        ):
            code = main(["--repo", str(self.repo)])
        self.assertEqual(code, 0)
        self.assertTrue((dest / "rules/commit-style.mdc").is_file())

    def test_explicit_dest_skips_prompt(self):
        dest = self.tmp / "explicit"
        stdin = StringIO("should-not-be-read\n")
        stdin.isatty = lambda: True  # type: ignore[method-assign]
        with patch("sys.stdin", stdin):
            code = main(
                ["--dest", str(dest), "--repo", str(self.repo)]
            )
        self.assertEqual(code, 0)
        self.assertTrue((dest / "rules/commit-style.mdc").is_file())

    def test_dry_run_omitted_dest_does_not_prompt_or_write(self):
        stdin = StringIO("should-not-be-read\n")
        stdin.isatty = lambda: True  # type: ignore[method-assign]
        with (
            patch("bootstrap.Path.home", return_value=self.home),
            patch("sys.stdin", stdin),
        ):
            code = main(["--dry-run", "--repo", str(self.repo)])
        self.assertEqual(code, 0)
        self.assertFalse((self.home / ".cursor").exists())


if __name__ == "__main__":
    unittest.main()
