"""Contract tests for the OpenCode adapter.

Every test drives real subprocesses and disposable Git repositories through a
fake OpenCode CLI, so the suite never contacts a provider or spends quota.
"""
import contextlib
import copy
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "runner", ROOT / "skills/openclaude-loop/scripts/runner.py")
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)

FAKE = ROOT / "tests/fake_opencode.py"
SESSION = "ses_f3b7569e7ffeXRiX7DlsZNlq5x"
OTHER_SESSION = "ses_aaaa1111bbbb2222cccc3333dd"
GOOD = {"verdict": "APPROVED", "summary": "Inspected the plan.",
        "findings": [], "coverage": ["PLAN.md"], "limitations": []}


def block(payload):
    return f"{runner.RESULT_OPEN}\n{json.dumps(payload)}\n{runner.RESULT_CLOSE}"


class Base(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="openclaude-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        # Spaces and non-ASCII in every path the runner has to quote and hash.
        self.repo = self.root / "repo with spaces and ünïcode"
        self.repo.mkdir()
        self.plan = self.root / "custom plan ünïcode.md"
        self.plan.write_text("# Work order\nKeep the original until the copy is verified.\n",
                             encoding="utf-8")
        self.artifacts = self.root / "runs"
        self.store = self.root / "fake store"
        self.git("init", "-q")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "user.name", "Test")
        (self.repo / "existing.py").write_text("original\n")
        (self.repo / "delete.py").write_text("delete me\n")
        self.git("add", ".")
        self.git("commit", "-qm", "baseline")
        self.base = self.git("rev-parse", "HEAD").strip()

    def git(self, *args):
        return subprocess.check_output(["git", *args], cwd=self.repo,
                                       stderr=subprocess.PIPE).decode()

    def invoke(self, mode="review", case="ok", extra=(), env=None):
        args = [mode, "--repo", str(self.repo), "--plan", str(self.plan),
                "--artifacts", str(self.artifacts), *extra]
        before = set(self.artifacts.glob("*/result.json")) if self.artifacts.exists() else set()
        out, err = io.StringIO(), io.StringIO()
        overrides = {"FAKE_CASE": case, "FAKE_PLAN": str(self.plan), "FAKE_STORE": str(self.store)}
        overrides.update(env or {})
        with patch.object(runner, "opencode_prefix",
                          return_value=[sys.executable, str(FAKE)]), \
                patch.dict(os.environ, overrides), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = runner.main(args)
        after = set(self.artifacts.glob("*/result.json")) if self.artifacts.exists() else set()
        new = after - before
        path = next(iter(new)) if new else None
        record = json.loads(path.read_text(encoding="utf-8")) if path else None
        return code, record, (path.parent if path else None), err.getvalue(), out.getvalue()

    def last_argv(self):
        return json.loads((self.store / "last-argv.json").read_text(encoding="utf-8"))

    def last_config(self):
        return json.loads((self.store / "last-config.json").read_text(encoding="utf-8"))


# ------------------------------------------------------------------ prerequisites

class PrerequisiteTests(Base):
    def test_missing_opencode_executable_is_a_clear_error(self):
        with patch.object(runner.shutil, "which", return_value=None):
            with self.assertRaises(runner.RunError) as caught:
                runner.opencode_prefix()
        self.assertIn("OpenCode CLI is not installed", str(caught.exception))

    def test_doctor_reports_unauthenticated_provider(self):
        out, err = io.StringIO(), io.StringIO()
        with patch.object(runner, "opencode_prefix", return_value=[sys.executable, str(FAKE)]), \
                patch.dict(os.environ, {"FAKE_CASE": "unauthenticated", "FAKE_STORE": str(self.store)}), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = runner.main(["doctor"])
        report = json.loads(out.getvalue())
        # A missing auth entry is advisory: some builds have a working default,
        # verified live against OpenCode v2.0.11.
        self.assertEqual(code, 0)
        self.assertTrue(report["ok"])
        self.assertEqual(report["problems"], [])
        self.assertTrue(any("no authenticated provider" in w for w in report["warnings"]))

    def test_doctor_blocks_on_a_missing_executable(self):
        out = io.StringIO()
        with patch.object(runner.shutil, "which", return_value=None), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = runner.main(["doctor"])
        report = json.loads(out.getvalue())
        self.assertEqual(code, 1)
        self.assertFalse(report["ok"])
        self.assertTrue(any("not installed" in p for p in report["problems"]))

    def test_doctor_flags_an_unavailable_requested_model(self):
        out = io.StringIO()
        with patch.object(runner, "opencode_prefix", return_value=[sys.executable, str(FAKE)]), \
                patch.dict(os.environ, {"FAKE_CASE": "ok", "FAKE_STORE": str(self.store)}), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            runner.main(["doctor", "--model", "fake/not-installed"])
        report = json.loads(out.getvalue())
        self.assertTrue(any("model is unavailable" in p for p in report["problems"]))
        self.assertFalse(report["ok"])
        self.assertTrue(report["authenticated_providers"])

    def test_windows_shell_shim_is_refused(self):
        shim = self.root / "opencode.cmd"
        shim.write_text("@echo off\n")
        with patch.object(runner, "is_windows", return_value=True), \
                patch.object(runner.shutil, "which", return_value=str(shim)):
            with self.assertRaises(runner.RunError) as caught:
                runner.opencode_prefix()
        self.assertIn("shell shim", str(caught.exception))

    def test_windows_native_executable_is_preferred_over_shim(self):
        shim = self.root / "opencode.cmd"
        shim.write_text("@echo off\n")
        native = self.root / "opencode.exe"
        native.write_text("binary")
        with patch.object(runner, "is_windows", return_value=True), \
                patch.object(runner.shutil, "which", return_value=str(shim)):
            self.assertEqual(runner.opencode_prefix(), [str(native)])

    def test_explicit_cli_override_must_be_an_absolute_file(self):
        with self.assertRaises(runner.RunError):
            runner.opencode_prefix("opencode")


# --------------------------------------------------------------------- invocation

class InvocationTests(Base):
    def test_first_review_creates_a_session_and_binds_the_plan(self):
        code, record, path, err, _ = self.invoke()
        self.assertEqual(code, 0, record)
        self.assertEqual(record["session_id"], SESSION)
        self.assertEqual(record["plan"], str(self.plan))
        self.assertEqual(record["plan_sha256"], runner.digest(self.plan.read_bytes()))
        self.assertEqual(record["response"]["verdict"], "APPROVED")
        self.assertEqual(record["round"], 1)
        self.assertNotIn("--session", self.last_argv())
        self.assertIn(str(self.plan), (path / "prompt.txt").read_text(encoding="utf-8"))

    def test_run_always_uses_standalone_so_the_profile_is_not_ignored(self):
        self.invoke()
        argv = self.last_argv()
        self.assertIn("--standalone", argv)
        self.assertEqual(argv[argv.index("--format") + 1], "json")

    def test_working_directory_is_pinned_through_pwd_not_just_cwd(self):
        """OpenCode reads PWD, not the process cwd, and `run` has no directory flag.

        An inherited PWD silently scopes the session to the coordinator's
        directory, which makes the repository under review external and
        unreadable. Verified against the real CLI.
        """
        _, env = runner.run_environment("review", [], None, self.repo)
        self.assertEqual(env["PWD"], str(self.repo))
        self.assertNotIn("OLDPWD", env)
        code, record, _, _, _ = self.invoke()
        self.assertEqual(code, 0, record)
        self.assertEqual(Path(record["session_directory"]).resolve(), self.repo)

    def test_a_session_in_the_wrong_directory_is_refused(self):
        code, record, _, _, _ = self.invoke(case="wrong_directory")
        self.assertEqual(code, 1)
        self.assertIn("not the requested repository", record["error"])
        self.assertNotIn("response", record)

    def test_explicit_session_resume_across_revision_rounds(self):
        _, first, first_dir, _, _ = self.invoke(case="revise")
        self.assertEqual(first["response"]["verdict"], "REVISE")
        self.plan.write_text("# Work order\nVerify the copy before deleting.\n", encoding="utf-8")
        feedback = self.root / "dispositions.md"
        feedback.write_text("Accepted F1; reordered the steps.\n", encoding="utf-8")
        code, second, second_dir, _, _ = self.invoke(
            extra=("--resume", str(first_dir / "result.json"), "--feedback", str(feedback)))
        self.assertEqual(code, 0, second)
        self.assertEqual(second["session_id"], first["session_id"])
        self.assertEqual(second["round"], 2)
        argv = self.last_argv()
        self.assertEqual(argv[argv.index("--session") + 1], SESSION)
        self.assertNotIn("--continue", argv)
        self.assertNotIn("-c", argv)
        prompt = (second_dir / "prompt.txt").read_text(encoding="utf-8")
        self.assertIn("continues your earlier session", prompt)
        self.assertIn("Accepted F1", prompt)

    def test_resume_refuses_a_different_plan_or_model(self):
        _, _, first_dir, _, _ = self.invoke()
        code, record, _, err, _ = self.invoke(
            extra=("--resume", str(first_dir / "result.json"), "--model", "fake/other-model"))
        self.assertEqual(code, 1)
        self.assertIsNone(record)
        self.assertIn("requested_model", err)

    def test_resumed_session_mismatch_is_refused(self):
        _, _, first_dir, _, _ = self.invoke()
        code, record, _, _, _ = self.invoke(
            case="wrong_session", extra=("--resume", str(first_dir / "result.json")))
        self.assertEqual(code, 1)
        self.assertIn("different session", record["error"])

    def test_malformed_session_id_is_never_resumed(self):
        with self.assertRaises(runner.RunError):
            runner.run_argv(["opencode"], "review", None, None, "12345678-1234-4567-8123-123456789abc")
        with self.assertRaises(runner.RunError):
            runner.export_session(["opencode"], "not-a-session", {})

    def test_final_inspection_uses_a_fresh_session(self):
        _, _, review_dir, _, _ = self.invoke()
        code, _, _, err, _ = self.invoke(
            mode="inspect", extra=("--base", self.base, "--resume", str(review_dir / "result.json")))
        self.assertEqual(code, 1)
        self.assertIn("fresh OpenCode session", err)
        (self.repo / "feature.py").write_text("new feature\n")
        code, record, _, _, _ = self.invoke(mode="inspect", extra=("--base", self.base))
        self.assertEqual(code, 0, record)
        self.assertEqual(record["agent"], "openclaude-inspector")
        self.assertNotIn("--session", self.last_argv())

    def test_requested_model_and_variant_propagate(self):
        self.assertIsNone(runner.model_argument(None, None))
        self.assertEqual(runner.model_argument("fake/fake-model", None), "fake/fake-model")
        self.assertEqual(runner.model_argument("fake/fake-model", "thinking"),
                         "fake/fake-model#thinking")
        self.assertEqual(runner.model_argument("fake/fake-model#max", None), "fake/fake-model#max")
        with self.assertRaises(runner.RunError):
            runner.model_argument(None, "thinking")
        with self.assertRaises(runner.RunError):
            runner.model_argument("fake/fake-model#max", "thinking")
        code, record, _, _, _ = self.invoke(
            extra=("--model", "fake/fake-model", "--variant", "thinking"))
        self.assertEqual(code, 0, record)
        argv = self.last_argv()
        self.assertEqual(argv[argv.index("--model") + 1], "fake/fake-model#thinking")
        self.assertEqual(record["requested_model"], "fake/fake-model")
        self.assertEqual(record["requested_variant"], "thinking")
        self.assertEqual(record["observed_models"], ["fake/fake-model"])

    def test_unpinned_model_leaves_selection_to_opencode(self):
        code, record, _, _, _ = self.invoke()
        self.assertEqual(code, 0, record)
        self.assertNotIn("--model", self.last_argv())
        self.assertIsNone(record["requested_model"])


# --------------------------------------------------------------------- permissions

class PermissionTests(Base):
    def test_reviewer_profile_is_read_only(self):
        profile = runner.permission_profile("review", ["/tmp/opencode"])
        self.assertEqual(profile["*"], "deny")
        self.assertEqual(profile["edit"], "deny")
        self.assertEqual(profile["task"], "deny")
        self.assertEqual(profile["webfetch"], "deny")
        self.assertEqual(profile["question"], "deny")
        self.assertEqual(profile["bash"]["*"], "deny")
        self.assertEqual(profile["glob"], "allow")
        self.assertEqual(profile["grep"], "allow")
        self.assertEqual(profile["read"]["*"], "allow")
        self.assertEqual(profile["read"]["*.env"], "deny")
        self.assertEqual(profile["bash"]["git diff*"], "allow")
        self.assertEqual(profile["external_directory"]["*"], "deny")
        self.assertEqual(profile["external_directory"]["/tmp/opencode/*"], "allow")
        for command in ("git commit*", "git push*", "rm -rf /*"):
            self.assertNotIn(command, profile["bash"])

    def test_inspector_profile_matches_the_reviewer_profile(self):
        self.assertEqual(runner.permission_profile("inspect", []),
                         runner.permission_profile("review", []))

    def test_builder_profile_writes_but_cannot_publish(self):
        profile = runner.permission_profile("build", [])
        self.assertEqual(profile["*"], "allow")
        self.assertEqual(profile["edit"], "allow")
        self.assertEqual(profile["bash"]["*"], "allow")
        self.assertEqual(profile["question"], "deny")
        self.assertEqual(profile["external_directory"]["*"], "deny")
        for command in ("git commit*", "git push*", "git reset*", "git rebase*",
                        "gh *", "npm publish*", "sudo*", "curl*", "ssh*"):
            self.assertEqual(profile["bash"][command], "deny", command)
        # The catch-all must come first so later, more specific rules win.
        self.assertEqual(next(iter(profile["bash"])), "*")

    def test_generated_profile_is_isolated_from_user_configuration(self):
        code, record, _, _, _ = self.invoke()
        self.assertEqual(code, 0, record)
        config = self.last_config()
        self.assertEqual(config["plugin"], [])
        self.assertEqual(config["mcp"], {})
        self.assertEqual(config["instructions"], [])
        self.assertEqual(config["skills"], {"paths": [], "urls": []})
        self.assertEqual(config["share"], "disabled")
        self.assertEqual(config["default_agent"], "openclaude-reviewer")
        self.assertIn("openclaude-reviewer", config["agent"])
        self.assertEqual(record["agent"], "openclaude-reviewer")
        self.assertIn("permission_profile_sha256", record)

    def test_project_configuration_is_disabled_for_the_run(self):
        _, env = runner.run_environment("review", [], None)
        self.assertEqual(env["OPENCODE_DISABLE_PROJECT_CONFIG"], "1")
        self.assertEqual(env["OPENCODE_CONFIG_PROJECT_DISABLE"], "1")
        self.assertNotIn("OPENCODE_CONFIG", env)
        self.assertIn("openclaude-reviewer", json.loads(env["OPENCODE_CONFIG_CONTENT"])["agent"])

    def test_build_uses_auto_but_review_does_not(self):
        self.assertIn("--auto", runner.run_argv(["opencode"], "build", None, None, None))
        self.assertNotIn("--auto", runner.run_argv(["opencode"], "review", None, None, None))
        self.assertNotIn("--auto", runner.run_argv(["opencode"], "inspect", None, None, None))

    def test_user_permanent_configuration_is_never_written(self):
        """The profile travels in the environment; nothing on disk is edited."""
        config_dir = self.root / "user config"
        config_dir.mkdir()
        user_config = config_dir / "opencode.json"
        user_config.write_text('{"permission": {"edit": "allow"}}', encoding="utf-8")
        before = user_config.read_bytes()
        code, record, _, _, _ = self.invoke(env={"XDG_CONFIG_HOME": str(self.root / "user config")})
        self.assertEqual(code, 0, record)
        self.assertEqual(user_config.read_bytes(), before)
        self.assertEqual(sorted(p.name for p in config_dir.iterdir()), ["opencode.json"])
        self.assertIn("openclaude-reviewer", self.last_config()["agent"])


# ------------------------------------------------------------------ output handling

class OutputTests(Base):
    def test_structured_verdicts_are_recognised(self):
        for case, verdict in (("ok", "APPROVED"), ("revise", "REVISE"), ("blocked", "BLOCKED")):
            with self.subTest(case=case):
                code, record, _, _, _ = self.invoke(case=case)
                self.assertEqual(code, 0, record)
                self.assertEqual(record["response"]["verdict"], verdict)

    def test_casual_approval_prose_is_not_approval(self):
        for case in ("casual_approval", "no_block"):
            with self.subTest(case=case):
                code, record, _, _, _ = self.invoke(case=case)
                self.assertEqual(code, 1)
                self.assertEqual(record["status"], "failed")
                self.assertIn("no <OPENCLAUDE_RESULT> block", record["error"])
                self.assertNotIn("response", record)

    def test_malformed_verdict_and_schema_are_rejected(self):
        for case, fragment in (("malformed_verdict", "Invalid verdict"),
                               ("bad_schema", "missing"),
                               ("approved_with_high", "unresolved high")):
            with self.subTest(case=case):
                code, record, _, _, _ = self.invoke(case=case)
                self.assertEqual(code, 1)
                self.assertIn(fragment, record["error"])

    def test_last_block_wins_and_fenced_json_is_accepted(self):
        code, record, _, _, _ = self.invoke(case="double_block")
        self.assertEqual(code, 0, record)
        self.assertEqual(record["response"]["verdict"], "APPROVED")
        code, record, _, _, _ = self.invoke(case="unfenced_prose")
        self.assertEqual(code, 0, record)
        self.assertEqual(record["response"]["verdict"], "APPROVED")

    def test_empty_stdout_recovers_through_session_export(self):
        code, record, path, _, _ = self.invoke(case="empty_stdout")
        self.assertEqual(code, 0, record)
        self.assertEqual(record["text_source"], "session-export")
        self.assertEqual(record["response"]["verdict"], "APPROVED")
        self.assertTrue((path / "session-export.json").is_file())

    def test_resumed_run_with_missing_stdout_recovers_through_export(self):
        _, _, first_dir, _, _ = self.invoke(case="revise")
        code, record, _, _, _ = self.invoke(
            case="empty_stdout", extra=("--resume", str(first_dir / "result.json")))
        self.assertEqual(code, 0, record)
        self.assertEqual(record["session_id"], SESSION)
        self.assertEqual(record["text_source"], "session-export")

    def test_malformed_json_lines_are_counted_not_fatal(self):
        code, record, _, _, _ = self.invoke(case="malformed_stdout")
        self.assertEqual(code, 0, record)
        self.assertGreaterEqual(record["stdout_events"]["malformed_lines"], 2)
        self.assertIn("step_start", record["stdout_events"]["event_types"])
        self.assertEqual(record["response"]["verdict"], "APPROVED")

    def test_a_step_start_event_alone_is_not_success(self):
        events = runner.parse_events(json.dumps({"type": "step_start", "sessionID": SESSION}))
        self.assertEqual(events["session_ids"], [SESSION])
        self.assertEqual(events["text"], "")
        with self.assertRaises(runner.RunError):
            runner.extract_result_block(events["text"])

    def test_real_world_success_outcome_is_accepted(self):
        """The live CLI reports `succeeded`; an allowlist of guessed values
        would reject every good run."""
        for outcome in ("succeeded", "success", "completed", None):
            with self.subTest(outcome=outcome):
                code, record, _, _, _ = self.invoke(
                    case="ok", env={"FAKE_OUTCOME": "" if outcome is None else outcome})
                self.assertEqual(code, 0, record)
                self.assertEqual(record["response"]["verdict"], "APPROVED")

    def test_failed_outcomes_are_rejected(self):
        for outcome in ("failed", "aborted", "cancelled", "interrupted"):
            with self.subTest(outcome=outcome):
                code, record, _, _, _ = self.invoke(case="ok", env={"FAKE_OUTCOME": outcome})
                self.assertEqual(code, 1)
                self.assertIn("not a completed turn", record["error"])
                self.assertNotIn("response", record)

    def test_empty_assistant_response_is_a_failure(self):
        code, record, _, _, _ = self.invoke(case="empty_response")
        self.assertEqual(code, 1)
        self.assertIn("empty response", record["error"])

    def test_nonzero_exit_and_failed_turn_never_approve(self):
        for case, fragment in (("cli_error", "Authentication failed"),
                               ("turn_failed", "failed turn"),
                               ("no_session", "no session id")):
            with self.subTest(case=case):
                code, record, path, _, _ = self.invoke(case=case)
                self.assertEqual(code, 1)
                self.assertEqual(record["status"], "failed")
                self.assertIn(fragment, record["error"])
                self.assertNotIn("response", record)
                self.assertTrue((path / "stderr.txt").is_file())

    def test_export_failure_is_an_infrastructure_error_not_a_verdict(self):
        code, record, _, _, _ = self.invoke(case="export_fails")
        self.assertEqual(code, 1)
        self.assertIn("export failed", record["error"])
        self.assertNotIn("response", record)

    def test_timeout_records_failure(self):
        code, record, _, _, _ = self.invoke(case="timeout", extra=("--timeout", "2"))
        self.assertEqual(code, 1)
        self.assertIn("timed out", record["error"])
        self.assertNotIn("response", record)

    def test_each_round_gets_its_own_artifact_directory(self):
        _, _, first, _, _ = self.invoke()
        _, _, second, _, _ = self.invoke(case="cli_error")
        self.assertNotEqual(first, second)
        self.assertFalse((second / "response.txt").exists())


# ------------------------------------------------------------------------ protocol

class ProtocolTests(unittest.TestCase):
    def test_valid_payloads_pass(self):
        runner.validate_review(copy.deepcopy(GOOD))
        runner.validate_review({"verdict": "APPROVED", "summary": "ok",
                                "findings": [], "limitations": []})

    def test_coverage_is_optional_but_typed(self):
        value = copy.deepcopy(GOOD)
        value["coverage"] = [""]
        with self.assertRaises(runner.RunError):
            runner.validate_review(value)

    def test_unknown_fields_are_rejected(self):
        value = copy.deepcopy(GOOD)
        value["approved"] = True
        with self.assertRaises(runner.RunError):
            runner.validate_review(value)

    def test_finding_fields_and_severities_are_enforced(self):
        value = copy.deepcopy(GOOD)
        value.update(verdict="REVISE", findings=[
            {"id": "F1", "severity": "critical", "title": "t", "evidence": "e",
             "recommendation": "r"}])
        with self.assertRaises(runner.RunError):
            runner.validate_review(value)
        value["findings"][0]["severity"] = "low"
        runner.validate_review(value)
        value["findings"].append(dict(value["findings"][0]))
        with self.assertRaises(runner.RunError):
            runner.validate_review(value)

    def test_verdict_consistency_rules(self):
        revise = copy.deepcopy(GOOD)
        revise.update(verdict="REVISE", findings=[])
        with self.assertRaises(runner.RunError):
            runner.validate_review(revise)
        blocked = copy.deepcopy(GOOD)
        blocked.update(verdict="BLOCKED", limitations=[])
        with self.assertRaises(runner.RunError):
            runner.validate_review(blocked)

    def test_extraction_ignores_prose_and_requires_the_block(self):
        with self.assertRaises(runner.RunError):
            runner.extract_result_block("VERDICT: APPROVED")
        with self.assertRaises(runner.RunError):
            runner.extract_result_block("")
        with self.assertRaises(runner.RunError):
            runner.extract_result_block(f"{runner.RESULT_OPEN}not json{runner.RESULT_CLOSE}")
        self.assertEqual(runner.extract_result_block("chatter " + block(GOOD))["verdict"], "APPROVED")


# -------------------------------------------------------------- fingerprinting

class FingerprintTests(Base):
    def test_manifest_covers_staged_unstaged_deleted_and_untracked_files(self):
        (self.repo / "existing.py").write_text("staged version\n")
        self.git("add", "existing.py")
        (self.repo / "existing.py").write_text("unstaged final version\n")
        (self.repo / "delete.py").unlink()
        (self.repo / "untracked new.py").write_text("brand new\n")
        snap = runner.snapshot(self.repo, self.base)
        self.assertEqual({f["path"] for f in snap["files"]},
                         {"existing.py", "delete.py", "untracked new.py"})
        by_path = {f["path"]: f for f in snap["files"]}
        self.assertEqual(by_path["delete.py"]["kind"], "deleted")
        self.assertEqual(by_path["existing.py"]["sha256"],
                         runner.digest((self.repo / "existing.py").read_bytes()))

    def test_manifest_mode_binds_a_claude_side_inspection(self):
        (self.repo / "untracked new.py").write_text("brand new\n")
        out = self.root / "manifest.json"
        code, _, _, _, stdout = self.invoke(
            mode="manifest", extra=("--base", self.base, "--builder", "opencode",
                                    "--out", str(out)))
        self.assertEqual(code, 0)
        record = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(record["inspector"], "claude")
        self.assertIn("untracked new.py", [f["path"] for f in record["snapshot"]["files"]])
        self.assertEqual(record["snapshot"]["sha256"], runner.snapshot(self.repo, self.base)["sha256"])

    def test_inspection_prompt_carries_the_manifest_and_diff(self):
        (self.repo / "existing.py").write_text("changed\n")
        (self.repo / "added.py").write_text("added\n")
        code, record, path, _, _ = self.invoke(mode="inspect", extra=("--base", self.base))
        self.assertEqual(code, 0, record)
        prompt = (path / "prompt.txt").read_text(encoding="utf-8")
        self.assertIn("CHANGE MANIFEST", prompt)
        self.assertIn("added.py", prompt)
        self.assertIn("TRACKED DIFF", prompt)
        self.assertEqual(record["snapshot"]["sha256"], runner.snapshot(self.repo, self.base)["sha256"])

    def test_code_changed_during_inspection_fails(self):
        (self.repo / "existing.py").write_text("changed\n")
        code, record, _, _, _ = self.invoke(mode="inspect", case="mutate_code",
                                            extra=("--base", self.base))
        self.assertEqual(code, 1)
        self.assertIn("Code changed during inspection", record["error"])

    def test_post_inspection_changes_make_the_inspection_stale(self):
        (self.repo / "existing.py").write_text("changed\n")
        _, record, _, _, _ = self.invoke(mode="inspect", extra=("--base", self.base))
        runner.check_inspection(record, self.repo, self.base)
        (self.repo / "existing.py").write_text("changed again after inspection\n")
        with self.assertRaises(runner.RunError) as caught:
            runner.check_inspection(record, self.repo, self.base)
        self.assertIn("stale", str(caught.exception))

    def test_opencode_cannot_inspect_its_own_build(self):
        code, _, _, err, _ = self.invoke(mode="inspect",
                                         extra=("--base", self.base, "--builder", "opencode"))
        self.assertEqual(code, 1)
        self.assertIn("OpenCode inspects only what Claude built", err)


# ------------------------------------------------------------------------ approval

class ApprovalTests(Base):
    def test_approval_binds_to_the_exact_plan_hash(self):
        _, record, dir_, _, _ = self.invoke()
        runner.check_approval(record, self.plan, self.repo)
        for field in ("session_id", "requested_model", "cli_version", "round",
                      "observed_models", "plan_sha256"):
            self.assertIn(field, record)
        self.plan.write_text("Different requirements\n", encoding="utf-8")
        with self.assertRaises(runner.RunError) as caught:
            runner.check_approval(record, self.plan, self.repo)
        self.assertIn("approval is invalid", str(caught.exception))
        code, _, _, err, _ = self.invoke(
            mode="check", extra=("--approval", str(dir_ / "result.json")))
        self.assertEqual(code, 1)
        self.assertIn("approval is invalid", err)

    def test_revise_and_blocked_are_completed_runs_but_not_approval(self):
        for case in ("revise", "blocked"):
            with self.subTest(case=case):
                code, record, _, _, _ = self.invoke(case=case)
                self.assertEqual(code, 0)
                with self.assertRaises(runner.RunError):
                    runner.check_approval(record, self.plan, self.repo)

    def test_approval_from_another_repository_is_refused(self):
        _, record, _, _, _ = self.invoke()
        record["repo"] = str(self.root / "elsewhere")
        with self.assertRaises(runner.RunError) as caught:
            runner.check_approval(record, self.plan, self.repo)
        self.assertIn("different repository", str(caught.exception))

    def test_plan_changed_during_the_review_fails(self):
        code, record, _, _, _ = self.invoke(case="mutate_plan")
        self.assertEqual(code, 1)
        self.assertIn("changed during the run", record["error"])
        self.assertNotIn("response", record)
        self.assertEqual(record["unverified_response"]["verdict"], "APPROVED")
        with self.assertRaises(runner.RunError):
            runner.check_approval(record, self.plan, self.repo)


# --------------------------------------------------------------------------- build

class BuildTests(Base):
    def approval(self):
        _, _, dir_, _, _ = self.invoke()
        return str(dir_ / "result.json")

    def test_delegated_build_requires_a_clean_checkout(self):
        approval = self.approval()
        (self.repo / "user work.py").write_text("preserve me\n")
        code, _, _, err, _ = self.invoke(
            mode="build", case="build",
            extra=("--builder", "opencode", "--approval", approval, "--proof", "true"))
        self.assertEqual(code, 1)
        self.assertIn("clean checkout", err)
        self.assertEqual((self.repo / "user work.py").read_text(), "preserve me\n")

    def test_build_requires_approval_or_an_explicit_override(self):
        code, _, _, err, _ = self.invoke(
            mode="build", case="build", extra=("--builder", "opencode", "--proof", "true"))
        self.assertEqual(code, 1)
        self.assertIn("--approval", err)

    def test_build_requires_a_proof_command(self):
        code, _, _, err, _ = self.invoke(
            mode="build", case="build",
            extra=("--builder", "opencode", "--unreviewed-spec"))
        self.assertEqual(code, 1)
        self.assertIn("--proof", err)

    def test_build_refuses_a_stale_approval(self):
        approval = self.approval()
        self.plan.write_text("Different requirements\n", encoding="utf-8")
        code, record, _, err, _ = self.invoke(
            mode="build", case="build",
            extra=("--builder", "opencode", "--approval", approval, "--proof", "true"))
        self.assertEqual(code, 1)
        self.assertIn("approval is invalid", err + (record or {}).get("error", ""))

    def test_build_session_resumes_against_the_same_baseline(self):
        extra = ("--builder", "opencode", "--unreviewed-spec", "--proof", "python -c pass")
        code, first, first_dir, _, _ = self.invoke(mode="build", case="build", extra=extra)
        self.assertEqual(code, 0, first)
        self.assertEqual(first["base"], self.base)
        self.assertEqual(first["session_id"], SESSION)
        self.assertEqual(first["agent"], "openclaude-builder")
        self.assertIn("built.py", [f["path"] for f in first["snapshot"]["files"]])
        fixes = self.root / "fixes.md"
        fixes.write_text("Fix the failing assertion in built.py.\n", encoding="utf-8")
        code, second, second_dir, _, _ = self.invoke(
            mode="build", case="build_fix",
            extra=extra + ("--resume", str(first_dir / "result.json"), "--feedback", str(fixes)))
        self.assertEqual(code, 0, second)
        self.assertEqual(second["base"], self.base)
        self.assertEqual(second["session_id"], first["session_id"])
        self.assertEqual(second["round"], 2)
        argv = self.last_argv()
        self.assertEqual(argv[argv.index("--session") + 1], SESSION)
        self.assertIn("Fix the failing assertion", (second_dir / "prompt.txt").read_text(encoding="utf-8"))

    def test_intervening_edits_block_a_build_resume(self):
        extra = ("--builder", "opencode", "--unreviewed-spec", "--proof", "true")
        _, _, first_dir, _, _ = self.invoke(mode="build", case="build", extra=extra)
        (self.repo / "intervening.py").write_text("someone else edited this\n")
        code, _, _, err, _ = self.invoke(
            mode="build", case="build",
            extra=extra + ("--resume", str(first_dir / "result.json")))
        self.assertEqual(code, 1)
        self.assertIn("checkout changed", err.lower())

    def test_a_builder_that_commits_is_reported(self):
        code, record, _, _, _ = self.invoke(
            mode="build", case="build_commits",
            extra=("--builder", "opencode", "--unreviewed-spec", "--proof", "true"))
        self.assertEqual(code, 1)
        self.assertIn("moved HEAD", record["error"])

    def test_claude_builder_cannot_delegate_the_build(self):
        code, _, _, err, _ = self.invoke(
            mode="build", case="build", extra=("--unreviewed-spec", "--proof", "true"))
        self.assertEqual(code, 1)
        self.assertIn("--builder opencode", err)

    def test_build_prompt_carries_the_proof_command_and_no_commit_contract(self):
        code, record, path, _, _ = self.invoke(
            mode="build", case="build",
            extra=("--builder", "opencode", "--unreviewed-spec", "--proof", "pytest tests/unit"))
        self.assertEqual(code, 0, record)
        prompt = (path / "prompt.txt").read_text(encoding="utf-8")
        self.assertIn("pytest tests/unit", prompt)
        self.assertIn("Do not commit, push", prompt)
        self.assertNotIn(runner.RESULT_OPEN, prompt)
        self.assertEqual(record["proof_command"], "pytest tests/unit")
        self.assertIsInstance(record["response"], str)


# --------------------------------------------------------------------------- proof

class ProofTests(Base):
    def test_proof_records_command_exit_code_and_output(self):
        code, record, _, _, _ = self.invoke(
            mode="proof", extra=("--proof", "echo proof-marker && exit 0"))
        self.assertEqual(code, 0)
        self.assertTrue(record["passed"])
        self.assertEqual(record["exit_code"], 0)
        self.assertIn("proof-marker", record["stdout_tail"])

    def test_a_failing_proof_is_recorded_as_failing(self):
        code, record, _, _, _ = self.invoke(
            mode="proof", extra=("--proof", "echo boom >&2 && exit 3"))
        self.assertEqual(code, 1)
        self.assertFalse(record["passed"])
        self.assertEqual(record["exit_code"], 3)
        self.assertIn("boom", record["stderr_tail"])

    def test_proof_can_bind_to_the_inspected_snapshot(self):
        (self.repo / "existing.py").write_text("changed\n")
        _, record, _, _, _ = self.invoke(
            mode="proof", extra=("--proof", "echo ok", "--base", self.base))
        self.assertEqual(record["snapshot"]["sha256"], runner.snapshot(self.repo, self.base)["sha256"])


# ------------------------------------------------------------------------ hygiene

class HygieneTests(Base):
    def test_artifacts_cannot_contaminate_the_target_checkout(self):
        code, _, _, err, _ = self.invoke(extra=("--artifacts", str(self.repo / "runs")))
        self.assertEqual(code, 1)
        self.assertIn("outside the target checkout", err)

    def test_shipped_plugin_has_no_upstream_agent_references(self):
        """Nothing a user runs or reads as instructions may mention the old agent.

        The attribution documents below deliberately name it -- that is the
        licence obligation, and `test_upstream_attribution_is_present` requires it.
        """
        attribution = {"ACKNOWLEDGMENTS.md", "LICENSE",
                       "skills/openclaude-loop/THIRD-PARTY-NOTICES.md"}
        meta = {"VALIDATION.md", "scripts/validate.py",
                "tests/test_runner.py", "tests/fake_opencode.py"}
        offenders = []
        for path in ROOT.rglob("*"):
            relative = path.relative_to(ROOT).as_posix()
            if not path.is_file() or set(path.relative_to(ROOT).parts) & {".git", "__pycache__", ".venv"}:
                continue
            if relative in attribution | meta:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for number, line in enumerate(text.splitlines(), 1):
                lowered = line.lower()
                if "codex" not in lowered and "claudex" not in lowered:
                    continue
                # Naming the upstream project is attribution, not a leftover.
                if "claudex-loop" in lowered:
                    continue
                # An explicit statement that the old agent is NOT needed is the
                # opposite of a leftover dependency.
                if any(phrase in lowered for phrase in (
                        "does not require", "is not required", "not required",
                        "must not exist", "no codex", "never required",
                        "replaced by opencode", "instead of codex")):
                    continue
                offenders.append(f"{relative}:{number}: {line.strip()[:110]}")
        self.assertEqual(offenders, [],
                         "Unattributed upstream-agent references:\n" + "\n".join(offenders))

    def test_no_upstream_runtime_dependency(self):
        """The plugin must not require, launch or import the upstream agent."""
        for relative in ("skills/openclaude-loop/scripts/runner.py",
                         "skills/openclaude-loop/SKILL.md",
                         "skills/opencode-review/SKILL.md",
                         "skills/opencode-build/SKILL.md",
                         ".claude-plugin/plugin.json",
                         ".claude-plugin/marketplace.json"):
            text = (ROOT / relative).read_text(encoding="utf-8").lower()
            for token in ("codex", "openai", "claudex"):
                self.assertNotIn(token, text, f"{relative} references {token}")

    def test_upstream_attribution_is_present(self):
        acknowledgments = (ROOT / "ACKNOWLEDGMENTS.md").read_text(encoding="utf-8")
        licence = (ROOT / "LICENSE").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for text in (acknowledgments, licence, readme):
            self.assertIn("chaseai-yt/claudex-loop", text)
        self.assertIn("MIT", licence)
        self.assertIn("based on", acknowledgments.lower())

    def test_no_codex_plugin_directory(self):
        self.assertFalse((ROOT / ".codex-plugin").exists())


if __name__ == "__main__":
    unittest.main()
