# openclaude-loop

**Claude Code + OpenCode adversarial development loop.**

[![CI](https://github.com/nahidnfr123/openclaude-loop/actions/workflows/ci.yml/badge.svg)](https://github.com/nahidnfr123/openclaude-loop/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

A Claude Code plugin that puts a second, independent agent between you and the code. Claude Code does the recon, settles the requirements with you and writes the plan. The [OpenCode](https://opencode.ai) CLI then tears that plan apart in a genuinely read-only session, and the two argue — in one continuous OpenCode session — until the plan survives or the round budget runs out. Then somebody builds it, and **whoever built it never grades it**.

```text
Claude Code
    │
    │ coordinator: recon, requirements, PLAN.md, arbitration
    ▼
openclaude-loop
    │
    ▼
OpenCode CLI
    │
    ▼
configured OpenCode provider / model
```

Claude Code is the host and the only coordinator, because the plugin is installed into and invoked from Claude Code. OpenCode is always the external second agent.

> **OpenCode is not a model.** It is a CLI. The second opinion you get is whatever provider and model *you* configured OpenCode to use — see [Models](#models).

This is not an official Anthropic or OpenCode project.

## Features

- **Adversarial plan review before any code exists.** OpenCode reads your actual repository and the exact `PLAN.md`, and returns a structured `APPROVED` / `REVISE` / `BLOCKED`.
- **One continuous review session.** Revision rounds resume the *same* OpenCode session id, so the reviewer judges whether its own earlier findings were really fixed — not a fresh critic each round.
- **Review is read-only in fact, not by request.** Enforced through OpenCode's permission system with a generated deny-by-default profile, never by asking the model nicely.
- **Either agent can build.** `builder=claude` (default) or `builder=opencode`. The one that didn't build does the final inspection, always in a fresh session.
- **Verdicts are machine-readable.** Parsed only from an `<OPENCLAUDE_RESULT>` block and schema-validated. The word "approved" in prose is not approval.
- **Approvals and inspections are fingerprinted.** Approval binds to the plan's SHA256; inspection binds to a hash of every staged, unstaged, deleted and untracked change. Edit either and the binding breaks.
- **Failures stay failures.** A timeout, empty response, non-zero exit or malformed result can never become a verdict.
- **Proof, not promises.** Claude runs the verification command itself and records the exit code. An agent saying "tests should pass" is not evidence.
- **No quota in CI.** 73 contract tests drive a fake OpenCode CLI on Linux, macOS and Windows.

## Architecture

**The invariant: whoever creates something is never the agent that grades it.**

| | Claude Code | OpenCode |
|---|---|---|
| Recon, requirements, `PLAN.md` | owns | — |
| Plan review | arbitrates the findings | independent adversarial reviewer, read-only |
| `builder=claude` (default) | implements | fresh read-only session inspects the diff |
| `builder=opencode` | independently inspects the diff | implements with controlled write access |
| Proof commands | runs them itself | never trusted to verify its own work |

| Path | What it is |
|---|---|
| `skills/openclaude-loop/SKILL.md` | The workflow Claude follows |
| `skills/openclaude-loop/references/` | [`runtime.md`](skills/openclaude-loop/references/runtime.md), [`security.md`](skills/openclaude-loop/references/security.md), [`protocol.md`](skills/openclaude-loop/references/protocol.md), [`build.md`](skills/openclaude-loop/references/build.md) |
| `skills/openclaude-loop/scripts/runner.py` | The OpenCode adapter — one turn per invocation, no pip dependencies |
| `skills/opencode-review/`, `skills/opencode-build/` | Direct entry points |

## Requirements

| | Why |
|---|---|
| **Claude Code** | the host; this is a Claude Code plugin |
| **Python 3.10+** | the runner. No pip dependencies at runtime |
| **Git** | change fingerprinting and the clean-checkout build gate |
| **[OpenCode CLI](https://opencode.ai)** | the second agent |
| **An OpenCode provider** | the model behind that agent |

```bash
claude --version
opencode --version
git --version
```

**Installing this plugin does not give you model credentials.** It bundles none and never will. OpenCode needs its own configured provider:

```bash
opencode auth login
opencode auth list
```

Some OpenCode builds ship a usable default provider with no entry in `auth list`. Check everything at once after installing:

```bash
python ~/.claude/plugins/**/openclaude-loop/skills/openclaude-loop/scripts/runner.py doctor
```

`doctor` separates blocking `problems` (OpenCode missing, requested model unavailable) from advisory `warnings` (an empty `auth list`).

## Installation

From Claude Code:

```text
/plugin marketplace add nahidnfr123/openclaude-loop
/plugin install openclaude-loop@openclaude-loop
```

Or from your shell:

```bash
claude plugin marketplace add nahidnfr123/openclaude-loop
claude plugin install openclaude-loop@openclaude-loop
```

Confirm it loaded:

```bash
claude plugin details openclaude-loop
```

You should see three skills: `openclaude-loop`, `opencode-review`, `opencode-build`.

## Quick start

```text
/openclaude-loop:openclaude-loop
```

Then say what you want:

```text
Implement password reset for this project.
```

What happens:

```text
Claude recon            reads your code, tests and conventions first
   ↓
requirements            asks only what the repo cannot answer
   ↓
PLAN.md                 objective, scope, non-goals, acceptance criteria, proof
   ↓
OpenCode review         read-only, adversarial → REVISE + concrete findings
   ↓
Claude revision         accepts or rejects each finding, with reasons
   ↺ same session       the reviewer checks its own findings were fixed
   ↓
OpenCode APPROVED       bound to the plan's SHA256
   ↓
Claude build            implements the approved plan
   ↓
proof                   Claude runs the command; exit code recorded
   ↓
fresh OpenCode session  independent inspection of the actual diff
   ↓
you approve the diff
```

Asking for a plan does not authorize a build, and running the loop never implies permission to commit or push.

## Commands

```text
/openclaude-loop:openclaude-loop     the full loop
/openclaude-loop:opencode-review     you already have a plan; just stress-test it
/openclaude-loop:opencode-build      hand a frozen spec to OpenCode; Claude inspects
```

Plain language works too: *"openclaude this feature"*, *"openclaude this plan"*, *"review this plan with opencode"*, *"build this with opencode and have claude review it"*.

## Workflow

**Phase 0 — Recon.** Claude reads the repository before asking anything: relevant code, callers and writers of shared state, dependencies, docs, conventions, tests, CI. You get one assumptions ledger with a source per entry.

**Phase 1 — Requirements.** Only decisions that materially change the result, each with a recommendation, why it matters, and what breaks if the guess is wrong. Then `PLAN.md`: objective, scope, non-goals, architecture, affected files, sequence, edge cases, migrations, security considerations, acceptance criteria and exact proof commands.

**Phase 2 — Plan review.** OpenCode hunts incorrect assumptions, missing requirements, architecture problems, data-corruption and security risks, races, migration risks, incomplete error handling, missing authorization checks, compatibility breaks, wrong framework assumptions, tests that would not prove the requirement, unverifiable acceptance criteria, and steps that conflict with the codebase.

- `APPROVED` — no unresolved high or medium findings, bound to the plan hash.
- `REVISE` — Claude arbitrates each finding on evidence, logs accepted and rejected ones with reasons, updates the plan, and resumes the same session.
- `BLOCKED` — required evidence could not be inspected. Never approval.

**Phase 3 — Build, proof, cross-inspection.** The builder implements; Claude runs the proof itself; the *other* agent inspects. Fixes applied after an inspection are re-inspected in another fresh session before anything is called final.

## Configuration

| Argument | Default | Meaning |
|---|---|---|
| `mode` | `full` | `full` includes recon and requirements; `review` starts from an existing plan |
| `plan` / `PLAN_FILE` | `PLAN.md` | plan path, used for review, build and approval binding |
| `log` / `LOG_FILE` | `PLAN-REVIEW-LOG.md` | append-only audit trail |
| `builder` | `claude` | `claude` or `opencode` |
| `rounds` / `MAX_ROUNDS` | `5` | maximum completed plan-review rounds |
| `MAX_FIX_ROUNDS` | `2` | bounded build-fix rounds |
| `MAX_INSPECTION_ROUNDS` | `2` | initial inspection plus one after fixes |
| `inspect` | `on` | `off` is a logged explicit opt-out only |
| `research` | proportionate | `none`, `web`, or explicitly opted-in `deep` |
| `reviewer_model`, `builder_model`, `inspector_model` | `opencode/big-pickle` | `provider/model`, or `default` for OpenCode's configured default |
| `reviewer_variant`, `builder_variant`, `inspector_variant` | none | sent as `provider/model#variant` |
| `fallback_models` | `opencode/mimo-v2.6-flash-free,opencode/deepseek-v4-flash-free` with the default model, else none | tried in order when a fresh turn hits quota or rate limits; `none` disables |
| `PROOF_CMD` | derived from the repo | exact verification command |

Example:

```text
/openclaude-loop:openclaude-loop mode=review plan=docs/rfc.md builder=opencode rounds=3 reviewer_model=anthropic/claude-sonnet-5
```

## Models

This matters for reading any verdict honestly.

- **Claude Code** — the orchestration host, your current session.
- **OpenCode** — an external coding-agent CLI. A program, not a model.
- **The OpenCode model** — whatever provider and model you configured for OpenCode.

So the independence of a review depends entirely on how you configured OpenCode. Point it at the same provider as your session and you get a second *agent* with a fresh context and no authorship bias — genuinely useful, but not a second *provider*. The plugin calls OpenCode the *independent agent*, the *external reviewer* or the *second agent*, and claims a cross-provider review only when the configured model demonstrably comes from a different provider.

Unless you name another model, the plugin pins `opencode/big-pickle`; pass `default` to let OpenCode choose. Requested and observed models are recorded separately, and an unresolved default is reported as unresolved. If you name a model OpenCode does not have, the run stops.

When a fresh turn on the default model fails on quota or rate limits, the runner retries in a new session on `opencode/mimo-v2.6-flash-free`, then `opencode/deepseek-v4-flash-free`. It skips any fallback that `opencode models` does not list. It never falls back on other errors, inside a resumed session, or after a delegated build has touched the checkout. Every fallback is recorded: `requested_model` is what you asked for, `model` is what answered, and `fallback_attempts` lists what failed and why. **Nothing is ever silently substituted.**

## Permission model

Each run generates a complete ephemeral OpenCode configuration, passes it through `OPENCODE_CONFIG_CONTENT`, and runs under its own generated agent. Your `opencode.json` is never read for permissions, never edited and never left changed.

`--standalone` is mandatory and load-bearing: without it, `opencode run` attaches to the already-running background service that was started with *your* configuration, and the generated profile is silently ignored. The run also disables project-level config, so an `opencode.json` inside the repository being reviewed cannot re-enable plugins, MCP servers or permissions for its own review — and the profile declares no plugins, no MCP servers and no extra skills.

**Reviewer and inspector** deny everything by default, then allow exactly: reading files (except `*.env`), glob, grep, list, LSP, and a fixed read-only git allowlist (`git status*`, `git diff*`, `git log*`, `git show*`, …). Editing, writing, patching, committing, pushing, running builds or tests, web access, subagents, skills and anything outside the repository are denied.

**Builder** allows edits and normal shell work inside the repository, runs with `--auto` paired with explicit denials, and blocks every history- or publication-affecting git command, forge and publish tools, privilege escalation, destructive system commands, network access, and anything outside the repository. After a delegated build the runner re-reads `HEAD` and fails the run if the builder moved it.

Full detail, including what this does **not** cover: [`references/security.md`](skills/openclaude-loop/references/security.md).

## Security

- A permission profile is **not an operating-system sandbox**. Use a disposable worktree for delegated builds.
- The plan, and for inspection the diff, are sent to whichever provider OpenCode is configured with. That is the point of an external review — but it is a disclosure, so choose deliberately.
- `read` on `*.env` is denied to reduce incidental exposure. That is not a secret-scanning guarantee.
- Run artifacts hold prompts, plans and possibly private code. They are written **outside** the repository and the runner refuses an artifacts path inside it. Don't commit them and don't paste them into issues unsanitized.
- To report a vulnerability, see [SECURITY.md](SECURITY.md). Never open a public issue for one.

## Review sessions

OpenCode session ids look like `ses_…` — not UUIDs. The runner records the exact id and resumes with `--session`. It never uses `--continue`, which resumes whatever ran last and could attach a reviewer to a build session.

- **Plan review** creates one session and resumes that same id for every revision round, so the reviewer remembers its own findings.
- **Final inspection** always starts fresh; `--resume` is refused. The session that argued for the plan is not an independent reader of the code.
- Resuming requires a *successful* previous result with the same repo, plan, mode, model and variant. If OpenCode returns a different session id than requested, the result is refused.

`opencode run --format json` streams JSONL, but a truncated run leaves partial lines — and **an error event still carries a session id**, so a session id proves nothing. The runner captures stdout, stderr and the exit code, parses events best-effort, then reads the authoritative transcript with `opencode session export`.

## Build sessions

A delegated build creates its own session and resumes that same id for bounded fix rounds — never a new builder context. The clean-checkout gate applies to the first round only; a resumed round must run against the same recorded baseline, and the runner refuses if the checkout changed underneath it.

Artifacts per run: `result.json`, `prompt.txt`, `command.json`, `opencode-config.json`, `stdout.txt`, `stderr.txt`, `session-export.json`, `response.txt`.

## Testing

```bash
python scripts/validate.py                 # plugin metadata, skill structure, references
python -m unittest discover -s tests -v    # 73 contract tests
claude plugin validate .                   # Claude Code manifest validation
```

The suite drives a fake OpenCode CLI and disposable git repositories, so it consumes **no provider quota**. Fixtures deliberately use repository paths containing spaces and non-ASCII characters. See [VALIDATION.md](VALIDATION.md) for the full coverage map and the manual live checks.

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `OpenCode CLI is not installed` | `opencode` is not on `PATH`. Install it, or pass an absolute path via `--opencode-cli`. |
| `OpenCode has no authenticated provider` (warning) | Advisory only. Run `opencode auth login` if runs actually fail with a provider error. |
| `Requested OpenCode model is unavailable` | The model is not in `opencode models`. Fix the name — the plugin will not substitute one. |
| `OpenCode produced an empty response` | The turn returned no assistant text. Check `stderr.txt` in the artifact directory. |
| `OpenCode review timed out` | Raise `--timeout` (default 900s). The process tree is killed and nothing is approved. |
| `OpenCode session could not be resumed` | The session id is gone from OpenCode's store, or `session export` failed. Start a fresh review round. |
| `response contains no <OPENCLAUDE_RESULT> block` | The model answered in prose. Usually a weaker model; pin a more capable one. |
| `PLAN.md changed after approval` | Working as designed. Re-review the current plan. |
| `Build requires a clean checkout` | Delegated builds need a clean tree. Use `git worktree add`; do not discard work. |
| `OpenCode ran against '…', not the requested repository` | OpenCode resolved a different working directory. Report it with your OpenCode version. |
| Skills not showing after install | `claude plugin details openclaude-loop`, then restart Claude Code. |

Every run prints its artifact directory before launching. Read `result.json` there first — `status`, `error`, `exit_code` and `stdout_events` usually identify the problem immediately.

## Updating

```bash
claude plugin marketplace update openclaude-loop
claude plugin update openclaude-loop@openclaude-loop
```

Releases are tagged `vX.Y.Z`; see [CHANGELOG.md](CHANGELOG.md).

## Uninstalling

```bash
claude plugin uninstall openclaude-loop@openclaude-loop
claude plugin marketplace remove openclaude-loop
```

The plugin stores nothing outside its installation directory. Run artifacts live wherever you pointed `--artifacts` (the system temp directory by default) and can be deleted freely. Your OpenCode configuration was never modified, so there is nothing to restore.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup, the test contract, and the invariants a change must not break. Bug reports and feature requests use the [issue templates](.github/ISSUE_TEMPLATE).

## License

[MIT](LICENSE). Upstream copyright and permission notices that this project is obliged to preserve are in [NOTICE](NOTICE).

## Acknowledgements

openclaude-loop is **based on and inspired by [chaseai-yt/claudex-loop](https://github.com/chaseai-yt/claudex-loop)** by Chase AI, used under the MIT License, with the Codex integration replaced by OpenCode throughout. The upstream authors have not endorsed this project. See [ACKNOWLEDGMENTS.md](ACKNOWLEDGMENTS.md) for exactly what carries over and what is deliberately different, and [NOTICE](NOTICE) for the preserved upstream copyright and permission notices.

`CONTEXT-FORMAT.md` and `ADR-FORMAT.md` originate from skills by [Matt Pocock](https://github.com/mattpocock/skills), via claudex-loop, under the MIT License.

[OpenCode](https://opencode.ai) is an independent open-source project. This plugin drives its CLI and is not affiliated with, endorsed by, or an official project of either OpenCode or Anthropic.
