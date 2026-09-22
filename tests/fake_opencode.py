#!/usr/bin/env python3
"""A fake OpenCode CLI.

It reproduces the surface openclaude-loop depends on -- `--version`,
`debug paths`, `auth list`, `models`, `run --format json` and
`session export` -- without contacting a provider, so the suite consumes no
model quota. Behaviour is selected through FAKE_CASE.
"""
import json
import os
import pathlib
import stat
import sys
import time

SESSION = "ses_f3b7569e7ffeXRiX7DlsZNlq5x"
OTHER_SESSION = "ses_aaaa1111bbbb2222cccc3333dd"
STORE = pathlib.Path(os.environ.get("FAKE_STORE", "."))
RESULT_OPEN = "<OPENCLAUDE_RESULT>"
RESULT_CLOSE = "</OPENCLAUDE_RESULT>"


def review_payload(case):
    value = {"verdict": "APPROVED", "summary": "Inspected the supplied plan against the repository.",
             "findings": [], "coverage": ["custom plan.md"], "limitations": []}
    if case in ("revise", "revise_then_approve"):
        value.update(verdict="REVISE", findings=[{
            "id": "F1", "severity": "high", "title": "Deletion precedes verified copy",
            "evidence": "The plan removes the original before the new copy is verified.",
            "recommendation": "Verify the copy, then remove the original."}])
    if case == "blocked":
        value.update(verdict="BLOCKED", coverage=[], limitations=["The referenced schema is absent."])
    if case == "malformed_verdict":
        value.update(verdict="LGTM")
    if case == "bad_schema":
        value = {"verdict": "APPROVED"}
    if case == "approved_with_high":
        value.update(findings=[{"id": "F1", "severity": "high", "title": "Data loss",
                                "evidence": "x", "recommendation": "y"}])
    return value


def reply_text(case):
    if case == "build":
        return "Implemented the work order. Proof command exited 0."
    if case == "casual_approval":
        return "Looks good to me, APPROVED. VERDICT: APPROVED. No structured block follows."
    if case == "no_block":
        return "Everything is approved and fine."
    if case == "unfenced_prose":
        return ("Some prose first.\n" + RESULT_OPEN + "\n```json\n"
                + json.dumps(review_payload("ok")) + "\n```\n" + RESULT_CLOSE + "\n")
    if case == "double_block":
        return (RESULT_OPEN + "\n" + json.dumps(review_payload("revise")) + "\n" + RESULT_CLOSE
                + "\nOn reflection:\n" + RESULT_OPEN + "\n"
                + json.dumps(review_payload("ok")) + "\n" + RESULT_CLOSE + "\n")
    return ("Review notes.\n" + RESULT_OPEN + "\n"
            + json.dumps(review_payload(case)) + "\n" + RESULT_CLOSE + "\n")


def write_session(session, case, prompt, failed=False, error=None):
    messages = [{"id": "msg_user", "type": "user", "text": prompt, "files": []}]
    assistant = {"id": "msg_assistant", "type": "assistant", "agent": os.environ.get("FAKE_AGENT", "x"),
                 "model": {"id": "fake-model", "providerID": "fake"},
                 "content": [] if failed else [{"type": "text", "text": reply_text(case)}]}
    if failed:
        assistant["finish"] = "error"
        assistant["error"] = error or {"type": "provider.auth", "message": "Authentication failed",
                                       "status": 403}
    messages.append(assistant)
    messages.append({"id": "msg_idle", "type": "idle", "outcome": "failed" if failed else "success"})
    outcome = "failed" if failed else (os.environ.get("FAKE_OUTCOME") or "succeeded")
    directory = os.environ.get("PWD") or os.getcwd()
    if os.environ.get("FAKE_CASE") == "wrong_directory":
        directory = str(pathlib.Path(directory).parent)
    body = {"info": {"id": session, "agent": os.environ.get("FAKE_AGENT", "x"),
                     "outcome": outcome, "location": {"directory": directory}},
            "messages": messages}
    STORE.mkdir(parents=True, exist_ok=True)
    (STORE / f"{session}.json").write_text(json.dumps(body), encoding="utf-8")


def main():
    argv = sys.argv[1:]
    case = os.environ.get("FAKE_CASE", "ok")
    if "--version" in argv:
        print("opencode v2.0.11")
        return 0
    if argv[:2] == ["debug", "paths"]:
        print("home /home/fake")
        print(f"data {STORE}")
        print(f"tmp {STORE / 'tmp'}")
        return 0
    if argv[:2] == ["auth", "list"]:
        if case == "unauthenticated":
            print("No authenticated integrations")
            return 0
        print("fake")
        return 0
    if argv[:1] == ["models"]:
        print("fake/fake-model")
        print("fake/other-model")
        print("opencode/big-pickle")
        print("opencode/mimo-v2.6-flash-free")
        if case != "fallback_unlisted":
            print("opencode/deepseek-v4-flash-free")
        return 0
    if argv[:2] == ["session", "export"]:
        if case == "export_fails":
            print("session not found", file=sys.stderr)
            return 1
        path = STORE / f"{argv[2]}.json"
        if not path.is_file():
            print("session not found", file=sys.stderr)
            return 1
        body = path.read_text(encoding="utf-8")
        if case == "pipe_truncates" and stat.S_ISFIFO(os.fstat(sys.stdout.fileno()).st_mode):
            # The real CLI can exit before a large export drains into a pipe.
            body = body[:len(body) // 2]
        sys.stdout.write(body)
        return 0
    if argv[:1] != ["run"]:
        print(f"unknown command: {' '.join(argv)}", file=sys.stderr)
        return 2

    # --- run ---------------------------------------------------------------
    prompt = sys.stdin.read()
    (STORE / "last-prompt.txt").parent.mkdir(parents=True, exist_ok=True)
    (STORE / "last-prompt.txt").write_text(prompt, encoding="utf-8")
    (STORE / "last-argv.json").write_text(json.dumps(argv), encoding="utf-8")
    (STORE / "last-config.json").write_text(os.environ.get("OPENCODE_CONFIG_CONTENT", ""),
                                            encoding="utf-8")
    if "--standalone" not in argv:
        print("refusing: the background service would ignore the generated config", file=sys.stderr)
        return 3
    agent = argv[argv.index("--agent") + 1] if "--agent" in argv else ""
    os.environ["FAKE_AGENT"] = agent
    config = json.loads(os.environ.get("OPENCODE_CONFIG_CONTENT") or "{}")
    if agent not in (config.get("agent") or {}):
        print(json.dumps({"type": "error", "timestamp": int(time.time() * 1000),
                          "sessionID": SESSION, "error": {"type": "unknown",
                          "message": f'Agent not found: "{agent}"'}}))
        return 1

    session = argv[argv.index("--session") + 1] if "--session" in argv else SESSION
    if case == "wrong_session":
        session = OTHER_SESSION
    if case == "timeout":
        time.sleep(45)
    if case == "mutate_plan":
        pathlib.Path(os.environ["FAKE_PLAN"]).write_text("Changed after launch", encoding="utf-8")
    if case == "mutate_code":
        pathlib.Path("mutated.py").write_text("changed during inspection\n", encoding="utf-8")
    if case in ("build", "build_fix"):
        pathlib.Path("built.py").write_text("print(42)\n", encoding="utf-8")
    if case == "build_commits":
        pathlib.Path("built.py").write_text("print(42)\n", encoding="utf-8")
        # subprocess, not os.system: POSIX redirections are not valid in cmd.exe.
        import subprocess
        subprocess.run(["git", "add", "-A"], capture_output=True)
        subprocess.run(["git", "commit", "-qm", "sneaky"], capture_output=True)

    exhausted = [m for m in os.environ.get("FAKE_EXHAUSTED", "").split(",") if m]
    model = argv[argv.index("--model") + 1] if "--model" in argv else ""
    if model.split("#", 1)[0] in exhausted:
        error = {"type": "provider.rate_limit", "status": 429,
                 "message": f"Too Many Requests: free usage limit reached for {model}"}
        print(json.dumps({"type": "error", "timestamp": int(time.time() * 1000),
                          "sessionID": session, "error": error}))
        write_session(session, case, prompt, failed=True, error=error)
        return 1
    if case == "cli_error":
        print(json.dumps({"type": "error", "timestamp": int(time.time() * 1000),
                          "sessionID": session,
                          "error": {"type": "provider.auth", "message": "Authentication failed"}}))
        write_session(session, case, prompt, failed=True)
        return 1
    if case == "turn_failed":
        write_session(session, case, prompt, failed=True)
        print(json.dumps({"type": "session", "sessionID": session}))
        return 0
    if case == "no_session":
        print("something went very wrong", file=sys.stderr)
        return 1
    if case == "empty_response":
        write_session(session, "empty", prompt)
        (STORE / f"{session}.json").write_text(json.dumps({
            "info": {"id": session, "outcome": "success"},
            "messages": [{"id": "m", "type": "assistant", "content": [],
                          "model": {"id": "fake-model", "providerID": "fake"}}]}), encoding="utf-8")
        print(json.dumps({"type": "session", "sessionID": session}))
        return 0

    write_session(session, case, prompt)
    print(json.dumps({"type": "session", "sessionID": session}))
    if case == "empty_stdout":
        # Nothing further on stdout: the exported transcript must carry the result.
        return 0
    if case == "malformed_stdout":
        print("{not json at all")
        print(json.dumps({"type": "step_start", "sessionID": session}))
        print("<<<truncated")
        return 0
    print(json.dumps({"type": "step_start", "sessionID": session}))
    print(json.dumps({"type": "text", "sessionID": session, "text": reply_text(case)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
