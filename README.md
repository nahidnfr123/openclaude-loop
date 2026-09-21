# openclaude-loop

A Claude Code plugin that puts a second, independent agent between you and the code.

Claude Code does the recon, settles the requirements with you and writes the plan. The [OpenCode](https://opencode.ai) CLI then reviews that plan adversarially in a genuinely read-only session, and the two argue — in one continuous OpenCode session — until the plan survives or the round budget runs out. Then somebody builds it, and **whoever built it never grades it**.

```text
Claude Code
    ↕
openclaude-loop
    ↕
OpenCode CLI
```

## The invariant

**Whoever creates something is never the agent that grades it.**

| | Claude Code | OpenCode |
|---|---|---|
| Recon, requirements, `PLAN.md` | owns | — |
| Plan review | arbitrates the findings | independent adversarial reviewer, read-only |
| `builder=claude` (default) | implements | fresh read-only session inspects the diff |
| `builder=opencode` | independently inspects the diff | implements with controlled write access |
| Proof commands | runs them itself | never trusted to verify its own work |

Claude Code is always the coordinator, because the plugin is installed into and invoked from Claude Code. OpenCode is always the external agent.

## OpenCode is not a model

This matters for reading any verdict honestly.

- **Claude Code** — the orchestration host, this session.
- **OpenCode** — an external coding-agent CLI. It is a program, not a model.
- **The OpenCode model** — whatever provider and model the user configured for OpenCode.

So the independence of a review depends entirely on what you configured OpenCode to use. If OpenCode is pointed at the same provider as this session, you get a second *agent* with a fresh context and no authorship bias — which is genuinely useful — but not a second *provider*. The plugin calls OpenCode the *independent agent*, the *external reviewer* or the *second agent*, and only claims a cross-provider review when the configured model demonstrably comes from a different provider. Requested and observed models are recorded separately, and an unresolved default is reported as unresolved.

## Flow

```text
                 Recon  (Claude reads the repo before asking you anything)
                   ↓
            Requirements  (only decisions that change the outcome)
                   ↓
                PLAN.md
                   ↓
    OpenCode adversarial review  (read-only, structured verdict)
                   ↓ REVISE
      Claude arbitrates each finding, revises the plan
                   ↺ same OpenCode session, every round
                   ↓ APPROVED   (bound to the plan's SHA256)
                  Build  (builder=claude | builder=opencode)
                   ↓
                 Proof  (Claude runs it; exit code recorded)
                   ↓
   Independent final inspection  (fresh session; whoever built does not inspect)
                   ↓
       You receive the final diff, proof results and residual findings
```

## Install

```text
/plugin marketplace add <owner>/openclaude-loop
/plugin install openclaude-loop@openclaude-loop
```

### Prerequisites

- Claude Code.
- Python 3.10+ — the runner has no pip dependencies.
- Git, for the fingerprinting and build gates.
- The [OpenCode CLI](https://opencode.ai), with an authenticated provider:

```bash
opencode auth login
opencode auth list
```

Check everything at once:

```bash
python <plugin>/skills/openclaude-loop/scripts/runner.py doctor
```

`doctor` reports the Claude and OpenCode versions, the resolved executable, authenticated providers and, with `--model`, whether the model you asked for actually exists. It separates blocking `problems` (OpenCode missing, requested model unavailable) from advisory `warnings` — an empty `opencode auth list` is a warning, not a failure, because some builds still have a working default. Prerequisite failures are reported as failures; they are never turned into a review verdict.

## Commands

```text
/openclaude-loop:openclaude-loop     the full loop
/openclaude-loop:opencode-review     you already have a plan; just stress-test it
/openclaude-loop:opencode-build      hand a frozen spec to OpenCode; Claude inspects
```

Plain language works too: *"openclaude this feature"*, *"openclaude this plan"*, *"review this plan with opencode"*, *"build this with opencode and have claude review it"*.

## Phases

**0 — Recon.** Claude reads the repository first: relevant code, callers and writers of shared state, dependencies, docs, architecture, conventions, tests, CI. It does not ask you anything the repository already answers. You get one assumptions ledger with a source per entry.

**1 — Requirements.** Only decisions that materially change the result, each with a recommendation, why it matters and what breaks if the guess is wrong. Then `PLAN.md`: objective, scope, non-goals, architecture, affected files, implementation sequence, edge cases, migrations, security considerations, acceptance criteria and exact proof commands. Asking for a plan is not authorizing a build.

**2 — Plan review.** OpenCode reads the actual repository and the exact `PLAN.md`, hunting incorrect assumptions, missing requirements, architecture problems, data-corruption and security risks, races, migration risks, incomplete error handling, missing authorization checks, compatibility breaks, wrong framework assumptions, tests that would not prove the requirement, unverifiable acceptance criteria, and steps that conflict with the codebase. It returns `APPROVED`, `REVISE` or `BLOCKED`. On `REVISE`, Claude accepts or rejects each finding on evidence, logs both, updates the plan, and **resumes the same OpenCode session** so the reviewer can judge whether its own findings were actually fixed. Default `MAX_ROUNDS=5`.

**3 — Build, proof, cross-inspection.** The builder implements the approved plan; Claude runs the proof itself; the other agent inspects. Fixes after an inspection are re-inspected in another fresh session before anything is called final.

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
| `reviewer_model`, `builder_model`, `inspector_model` | OpenCode default | `provider/model` |
| `reviewer_variant`, `builder_variant`, `inspector_variant` | none | sent as `provider/model#variant` |
| `PROOF_CMD` | derived from the repo | exact verification command |

If you name no model, OpenCode uses its configured default and the record says the model is unresolved. If you name a model that OpenCode does not have, the run stops. Nothing is ever silently substituted.

## Security model

The review is read-only because OpenCode's permission system enforces it, not because the prompt asked. Each run generates a complete ephemeral OpenCode configuration, passes it in `OPENCODE_CONFIG_CONTENT`, and runs under its own generated agent. Your `opencode.json` is never read for permissions, never edited and never left changed.

`--standalone` is mandatory and load-bearing: without it, `opencode run` attaches to the already-running background service that was started with your configuration, and the generated profile would be silently ignored. The run also disables project-level config, so an `opencode.json` inside the repository being reviewed cannot re-enable plugins, MCP servers or permissions for its own review — and it declares no plugins, no MCP servers and no extra skills, so unrelated extensions never load into the review environment.

**Reviewer and inspector** deny everything by default, then allow exactly: reading files (except `*.env`), glob, grep, list, LSP, and a fixed read-only git allowlist (`git status*`, `git diff*`, `git log*`, `git show*`, …). Editing, writing, patching, committing, pushing, running builds or tests, web access, subagents, skills and anything outside the repository are denied.

**Builder** allows edits and normal shell work inside the repository, runs with `--auto` paired with explicit denials, and blocks every history- or publication-affecting git command, forge and publish tools, privilege escalation, destructive system commands, network and remote access, and anything outside the repository. After a delegated build the runner re-reads `HEAD` and fails the run if the builder moved it.

Full detail, including what this does **not** cover: [`skills/openclaude-loop/references/security.md`](skills/openclaude-loop/references/security.md).

## Session handling

OpenCode session ids look like `ses_…` — not UUIDs. The runner records the exact id and resumes with `--session`. It never uses `--continue`, which resumes whatever ran last and could attach a reviewer to a build session.

- **Plan review** creates one session and resumes that same id for every revision round, so the reviewer remembers its own findings.
- **Final inspection** always starts fresh; `--resume` is refused. The session that argued for the plan is not an independent reader of the code.
- **Delegated build** creates its own session and resumes that same id for bounded fix rounds.
- Resuming requires a *successful* previous result with the same repo, plan, mode, model and variant. If OpenCode returns a different session id than requested, the result is refused.

## Output handling

`opencode run --format json` streams JSONL, but a truncated or killed run leaves partial lines — and **an error event still carries a session id**. So the runner captures stdout, stderr and the exit code, parses the events best-effort, then reads the authoritative transcript with `opencode session export`, which also yields the observed model. Malformed lines are counted in the record, never fatal.

None of these is success: a started process, an existing session id, a `step_start` event, an empty assistant response, a malformed result, a non-zero exit, a timeout, a permission failure or a provider failure. A completed review needs a successful run, a non-empty final response, a valid structured result and a recognized verdict.

Verdicts are read only from a machine-readable block:

```text
<OPENCLAUDE_RESULT>
{"verdict": "REVISE", "summary": "...",
 "findings": [{"id": "F1", "severity": "high", "title": "...",
               "evidence": "...", "recommendation": "..."}],
 "coverage": ["..."], "limitations": []}
</OPENCLAUDE_RESULT>
```

The word "approved" in prose is not approval. `APPROVED` carrying a high or medium finding is rejected as self-contradictory; `REVISE` needs a concrete finding; `BLOCKED` needs a stated limitation. Details: [`references/protocol.md`](skills/openclaude-loop/references/protocol.md).

## Artifacts

`PLAN.md` and `PLAN-REVIEW-LOG.md` live in your repository. The log is a structured audit trail — plan hash per round, session id, each finding with Claude's disposition, accepted and rejected findings with reasons, verdicts, requested and observed model, CLI errors, proof commands with exit codes, build info, inspection results and remaining uncertainty.

Raw diagnostics stay **outside** the repository, in a unique per-run artifact directory holding `result.json`, `prompt.txt`, `command.json`, `opencode-config.json`, `stdout.txt`, `stderr.txt`, `session-export.json` and `response.txt`. The runner refuses an artifact path inside the checkout. Don't commit them — they contain your plan, prompts and possibly private code.

Approval binds to the canonical plan path, its SHA256, the session id, the requested and observed model, the CLI version, a timestamp, the verdict and the round. Edit the plan and the approval is invalid — a build cannot claim a modified plan was approved. Inspection binds the same way to a fingerprint of the pre-build commit plus every staged, unstaged, deleted and untracked change; edit the code afterwards and the inspection is stale.

## Failure handling

Infrastructure failures are reported as failures, never as verdicts: *OpenCode CLI is not installed*, *OpenCode has no authenticated provider*, *Requested OpenCode model is unavailable*, *OpenCode review timed out*, *OpenCode produced an empty response*, *OpenCode session could not be resumed*. A timeout kills the process tree. A verdict parsed before a failure is moved to `unverified_response`, where no approval check can read it. `BLOCKED`, a failed process and a malformed result are all non-approval, and none of them is a reason to silently retry with a different model or provider.

## Testing

```bash
python scripts/validate.py                    # plugin metadata, skill structure, references
python -m unittest discover -s tests -v       # contract tests
```

The suite drives a fake OpenCode CLI and disposable git repositories, so it consumes **no provider quota**. It covers a missing executable, session creation and id extraction, explicit resume, the same session across revision rounds, a fresh session for inspection, JSON text extraction, malformed lines, empty stdout, non-zero exits, timeouts, structured `APPROVED`/`REVISE`/`BLOCKED`, malformed verdicts, casual "approved" prose, recovery through `session export` including on a resumed run, plan-hash validation, changed plans invalidating approval, the clean-git gate, build session resumption, inspection fingerprints, untracked files in the manifest, post-inspection staleness, permission-profile generation, model and variant propagation, spaces and non-ASCII in repository paths, and Windows shim handling.

CI runs both on Linux, macOS and Windows. See [VALIDATION.md](VALIDATION.md) for live smoke tests and the OpenCode version actually exercised.

## Limitations

- Structural validation proves a result is well-formed and self-consistent. It cannot prove the review is correct, that the claimed coverage happened, or that the findings are true. Zero findings is legitimate and is not proof of correctness — read the evidence.
- A permission profile is not an operating-system sandbox. Use a disposable worktree for delegated builds.
- The plan, and for inspection the diff, are sent to whichever provider OpenCode is configured with. That is the point, but it is a disclosure.
- Ignored files are invisible to git, so ignored build deliverables need separate inspection. Changed submodules need an explicit inspection path.
- Developed against OpenCode v2.0.11. v2 replaced v1's `OPENCODE_PERMISSION` and `tools` booleans with the `permission` config block, and `run` has no `--dir` or `--pure` flag. A `--version` probe does not establish model compatibility.
- Not for trivial edits. The loop costs more than the change is worth below roughly twenty lines.

## Attribution

openclaude-loop is a derivative of [chaseai-yt/claudex-loop](https://github.com/chaseai-yt/claudex-loop) by Chase AI, used under the MIT License, with Codex replaced by OpenCode throughout. See [ACKNOWLEDGMENTS.md](ACKNOWLEDGMENTS.md) for what carries over and what is deliberately different, and [LICENSE](LICENSE).

Not affiliated with or endorsed by the OpenCode project.
