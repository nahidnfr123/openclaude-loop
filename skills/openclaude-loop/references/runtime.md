# OpenCode runtime

Python 3.10+ and the runner installed at `../scripts/runner.py` relative to this file. Resolve it from the **skill's installation path**, not from a similarly named file in the repository under review. Below, `RUNNER` stands for that absolute path; quote paths containing spaces.

The runner has no pip dependencies. It orchestrates **one OpenCode turn per invocation** — it never owns the interview, the arbitration, the round budget or the human conversation, and it never calls a model API directly. OpenCode is authenticated with its own supported flow (`opencode auth login`); this session's login, model choice, MCP servers and credentials do not transfer to it.

## Prerequisites

```text
python RUNNER doctor [--model provider/model]
```

Reports the Claude and OpenCode CLI versions, the resolved executable, authenticated providers and OpenCode's managed directories, and splits findings into blocking `problems` and advisory `warnings`.

Exit code 1 and a non-empty `problems` list mean a real prerequisite failure: OpenCode is not installed, or an explicitly requested model is not one OpenCode lists. `warnings` do not block — notably, `opencode auth list` reporting no authenticated provider, because some builds still have a working default. Fix the prerequisite; never turn it into a verdict.

## Commands

```text
python RUNNER review   --repo REPO --plan PLAN --artifacts RUNS
python RUNNER review   --repo REPO --plan PLAN --artifacts RUNS --resume PREVIOUS_RESULT --feedback DISPOSITIONS
python RUNNER check    --repo REPO --plan PLAN --approval APPROVED_RESULT
python RUNNER build    --repo REPO --plan PLAN --builder opencode --approval APPROVED_RESULT --proof "npm test" --artifacts RUNS
python RUNNER inspect  --repo REPO --plan PLAN --base BASE_COMMIT --artifacts RUNS
python RUNNER manifest --repo REPO --base BASE_COMMIT --out MANIFEST
python RUNNER proof    --repo REPO --proof "npm test" --base BASE_COMMIT --artifacts RUNS
```

`--repo` is the working directory for the OpenCode process. OpenCode v2's `run` has no working-directory flag; the runner sets the process working directory instead, which is what scopes `external_directory` to that repository.

| Mode | Agent | Session | Who it is for |
|---|---|---|---|
| `review` | `openclaude-reviewer`, read-only | new, then resumed by explicit id | plan review rounds |
| `inspect` | `openclaude-inspector`, read-only | always fresh; `--resume` is refused | final inspection of what Claude built |
| `build` | `openclaude-builder`, controlled write | new, then resumed by explicit id | delegated implementation |
| `manifest` | none — no CLI launched | — | fingerprints changes so Claude's own inspection is bound to them |
| `proof` | none — no CLI launched | — | records the verification command, exit code and output |
| `check` | none — no CLI launched | — | re-verifies an approval against the current plan |

## Models and variants

Omit `--model` to let OpenCode use its configured default; the record then says the model is unresolved. Pass `--model provider/model` for an explicit choice and `--variant NAME` for a variant — OpenCode expresses this as `provider/model#variant`, and the runner assembles it. Repeat the same model and variant when resuming; a mismatch is refused before launch rather than silently changing agents mid-conversation.

There is no automatic fallback. A model that is unavailable is an error, not an invitation to use a different one.

## Sessions

OpenCode session ids look like `ses_` followed by base62 characters — they are not UUIDs. The runner validates that shape, stores the id in `result.json`, and resumes with `--session`. It never uses `--continue` or `-c`, which resume "whatever ran last" and can silently attach a reviewer to a build session.

`--resume` accepts only a **successful** previous `result.json` with the same repository, plan path, mode, model and variant. The plan may have changed — that is the point of a revision round — but the resulting approval binds only to the new hash. If OpenCode returns a different session id than the one requested, the result is refused.

## Output handling

Every run captures `stdout.txt`, `stderr.txt` and the process exit code, then reads the authoritative transcript with `opencode session export`. `opencode run --format json` streams JSONL, but a truncated, interleaved or killed run can leave partial lines, and **an error event still carries a session id** — so a session id proves nothing about success. The export is the source of truth; stdout text is used only when the export has no assistant text. Malformed JSONL lines are counted in the record, not treated as fatal.

None of the following is ever success: a started process, an existing session id, a `step_start` event, an empty assistant response, a malformed structured result, a non-zero exit, a failed turn, a timeout, a permission failure or a provider failure. A completed review requires a successful run, a non-empty final assistant response, a valid structured result and a recognized verdict.

The default timeout is 900 seconds; raise it with `--timeout` for a justified build. A timeout kills the process tree and records a failure. Use this session's background execution for long calls and keep reporting progress.

## Artifacts

Each run prints its unique artifact directory before launch and writes `result.json`, `prompt.txt`, `command.json`, `opencode-config.json`, `stdout.txt`, `stderr.txt`, `session-export.json` and `response.txt` into it. Pass `--artifacts PATH` to keep them; the path must be **outside** the repository, and the runner refuses otherwise so diagnostics never pollute the reviewed diff. Do not commit them: they contain the plan, prompts and possibly private code. Reference them from the log by path.

Exit code zero means a completed turn, **not APPROVED** — the verdict may be REVISE or BLOCKED. On a failure, any verdict parsed before the failure is moved to `unverified_response` so no approval check can read it. Do not fall back to an older successful result after a newer round fails.

See [the structured result protocol](protocol.md), [the security model](security.md) and [build and inspection](build.md).

## Compatibility

Developed against **OpenCode v2.0.11** and Claude Code 2.1.278. v2 replaced the v1 `OPENCODE_PERMISSION` environment variable and the `tools` booleans with the `permission` config block, and it has no `--dir` or `--pure` flag on `run`. A `--version` probe does not establish model compatibility; see [VALIDATION.md](../../../VALIDATION.md) for what was actually exercised live. The automated suite drives a fake CLI and consumes no provider quota.

Primary references: [OpenCode CLI](https://opencode.ai/docs/cli/), [permissions](https://opencode.ai/docs/permissions/), [agents](https://opencode.ai/docs/agents/), [config](https://opencode.ai/docs/config/).
