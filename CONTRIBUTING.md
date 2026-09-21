# Contributing

Thanks for your interest. This document covers setup, the test contract, and what a reviewable change looks like.

## Development setup

You need Python 3.10+ and Git. The **runtime has no pip dependencies** — that is deliberate, and a change that adds one to `skills/openclaude-loop/scripts/runner.py` will not be accepted. Only the validator needs a package.

```bash
git clone https://github.com/nahidnfr123/openclaude-loop.git
cd openclaude-loop

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
```

For live testing you also need the [OpenCode CLI](https://opencode.ai) with a working provider. It is **not** required for the automated suite.

## Commands

```bash
python -m unittest discover -s tests -v    # contract tests (no network, no quota)
python scripts/validate.py                 # plugin metadata, skill structure, links
claude plugin validate .                   # Claude Code's own manifest validation
```

All three must pass before a pull request is ready. CI runs them on Linux, macOS and Windows across Python 3.10 and 3.13.

## Architecture in five minutes

Claude Code is the host and the only coordinator. OpenCode is the external second agent. The invariant is that **whoever creates something is never the agent that grades it**.

| Path | What it is |
|---|---|
| `skills/openclaude-loop/SKILL.md` | The main workflow Claude follows. Instructions, not code. |
| `skills/openclaude-loop/references/` | `runtime.md` (CLI contract), `security.md` (permission boundary), `protocol.md` (verdict schema), `build.md` (build and inspection) |
| `skills/openclaude-loop/scripts/runner.py` | The whole adapter. Drives exactly one OpenCode turn per invocation and writes an auditable `result.json`. It owns no loop, no arbitration and no human interaction. |
| `skills/opencode-review/`, `skills/opencode-build/` | Thin entry points that delegate to the shared skill |
| `tests/fake_opencode.py` | A fake OpenCode CLI |
| `scripts/validate.py` | Metadata and link validation |

Runner modes: `doctor`, `review`, `build`, `inspect`, `manifest`, `proof`, `check`.

## Invariants that must not regress

Changing any of these without a very good reason will be rejected. Several exist because a live run found the bug the hard way.

1. **`--standalone` is always passed.** Without it OpenCode attaches to the background service started with the user's own configuration and the generated permission profile is silently ignored. This is a security boundary, not a flag.
2. **`PWD` is pinned to the repository.** OpenCode resolves its working directory from `$PWD`, not the process working directory, and `opencode run` has no directory flag.
3. **Sessions are resumed by explicit id.** Never `--continue`, never a guessed id.
4. **Final inspection always uses a fresh session.** The session that argued for the plan is not an independent reader of the code.
5. **Review and inspection profiles deny by default.** New capabilities must be added explicitly, never by widening the catch-all.
6. **No failure path can produce an approval.** A non-zero exit, empty response, timeout, malformed result or failed turn is an operational failure, never a verdict.
7. **Verdicts come only from the `<OPENCLAUDE_RESULT>` block.** Prose is never parsed for approval.
8. **Automated tests never call a real provider.**

## The test contract

`tests/fake_opencode.py` stands in for the real CLI, reproducing `--version`, `debug paths`, `auth list`, `models`, `run --format json` and `session export`. Tests select behaviour with the `FAKE_CASE` environment variable and patch `runner.opencode_prefix` to launch it.

Adding a scenario usually means adding a `FAKE_CASE` branch to the fake and a test that asserts on the resulting `result.json`. Test fixtures deliberately use a repository path containing a space and non-ASCII characters — keep it that way.

**Automated tests must never consume paid model quota.** No test may call a real provider, and CI has no credentials. If a change cannot be tested without a live model, it belongs in the manual section of [VALIDATION.md](VALIDATION.md) instead.

## Optional live integration testing

Live checks are manual, cost quota, and are never run in CI. [VALIDATION.md](VALIDATION.md) documents the full procedure: a flawed plan producing `REVISE`, the same session resuming to `APPROVED`, approval binding breaking when the plan changes, and a read-only proof where the plan itself tries to make the reviewer write a file.

Always use a disposable repository and an explicit model. Never run them against work you care about. If you run them, record the OpenCode version and your results in `VALIDATION.md`.

## Pull requests

- Branch from `main`, one logical change per PR.
- Update `CHANGELOG.md` under `## [Unreleased]`.
- Update the relevant reference doc when you change behaviour. `references/security.md` must keep describing the actual profile.
- Say in the PR whether you ran the live checks, and against which OpenCode version. Do not claim a live result you did not observe.
- Do not paste raw run artifacts into issues or PRs — they contain prompts, plans and possibly private code. Sanitize first.

## Security issues

Do not open a public issue. See [SECURITY.md](SECURITY.md).

## License

Contributions are accepted under the [MIT License](LICENSE). This project is a derivative of [claudex-loop](https://github.com/chaseai-yt/claudex-loop); do not remove upstream attribution from `NOTICE`, `ACKNOWLEDGMENTS.md` or `skills/openclaude-loop/THIRD-PARTY-NOTICES.md`.
