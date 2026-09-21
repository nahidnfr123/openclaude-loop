---
name: openclaude-loop
description: "Harden a plan with an independent OpenCode review, then build it and cross-inspect the result. Claude Code coordinates recon, requirements and PLAN.md; OpenCode reviews the plan in a read-only session; whoever builds never inspects. Use for openclaude this feature, openclaude this plan, review this plan with opencode, build this with opencode and have claude review it, or /openclaude-loop. Not for trivial edits."
---

# openclaude-loop

Claude Code is the host and the only coordinator. OpenCode is an external coding-agent CLI that acts as the second, independent agent. The invariant is absolute:

**Whoever creates something is never the agent that grades it.**

| Phase | Claude Code | OpenCode |
|---|---|---|
| Recon, requirements, `PLAN.md` | owns | — |
| Plan review | arbitrates findings | independent adversarial reviewer (read-only) |
| Build, `builder=claude` (default) | implements | fresh read-only session inspects the diff |
| Build, `builder=opencode` | independently inspects the diff | implements with controlled write access |
| Proof commands | runs them itself | never trusted to verify its own work |

OpenCode is not a model. It is a CLI that runs whatever provider and model the user has configured. Call it the *independent agent*, the *external reviewer* or the *second agent*. Only claim a cross-provider review when the configured OpenCode model demonstrably comes from a different provider than this session; report the requested and observed model separately and say so honestly when the model is unresolved.

Read [the runtime reference](references/runtime.md) before launching anything, and [the security model](references/security.md) before claiming any run was read-only. Resolve the runner relative to **this installed SKILL.md**, never relative to the repository under review, and launch it by absolute path.

## Tunables

Echo the resolved values before starting.

| Argument | Default | Meaning |
|---|---|---|
| `mode` | `full` | `full` runs recon and requirements; `review` starts from an existing plan |
| `plan` / `PLAN_FILE` | `PLAN.md` | Plan path used for review, build handoff and approval binding |
| `log` / `LOG_FILE` | `PLAN-REVIEW-LOG.md` | Append-only audit trail |
| `builder` | `claude` | `claude` or `opencode` |
| `rounds` / `MAX_ROUNDS` | `5` | Maximum completed plan-review rounds |
| `MAX_FIX_ROUNDS` | `2` | Bounded build-fix rounds before reporting or taking over |
| `MAX_INSPECTION_ROUNDS` | `2` | Initial inspection plus one after accepted fixes |
| `inspect` | `on` | `off` is a logged explicit opt-out only |
| `research` | proportionate | `none`, `web`, or explicitly opted-in `deep` |
| `reviewer_model` / `builder_model` / `inspector_model` | OpenCode default | `provider/model`, mapped to `--model` |
| `reviewer_variant` / `builder_variant` / `inspector_variant` | none | mapped to `--variant` (sent as `provider/model#variant`) |
| `PROOF_CMD` | derived from the repo | Exact verification command |

If no OpenCode model is given, let OpenCode use its configured default and record it as unresolved. If an explicit model is requested and unavailable, stop and say so. Never substitute another model or provider silently.

Preserve existing authorization. A request to plan does not authorize building; a request to plan and implement does. Committing, pushing and publishing follow the user's separate authorization and are never implied by running this loop.

Run `doctor` before the first OpenCode call. Infrastructure failures — missing CLI, no authenticated provider, unavailable model, timeout, empty response, unresumable session — are reported as failures. They are never converted into a review verdict.

## Phase 0 — Recon

Inspect the repository before asking anything: relevant code, callers and writers of shared state, dependencies, existing documentation, architecture, conventions, tests, and CI. Read `CONTEXT.md` / `CONTEXT-MAP.md` and relevant ADRs when present. For greenfield work, research prior art, a plausible stack and concrete failure modes at the requested depth; `deep` research requires explicit opt-in and an available tool, otherwise use targeted research and report the limitation.

Do not ask the user anything the repository already answers. Produce one assumptions and decisions ledger with a source path or link per entry, and ask for corrections as a single batch.

Do not assume this session's MCP servers, credentials, browser or skills are available to OpenCode. They are not; the review environment is deliberately isolated.

## Phase 1 — Requirements

Keep a short visible decision map. Ask only about decisions that materially change the result. For each consequential question give a recommendation, why it matters, and what breaks if the guess is wrong. Batch independent questions, ask dependent ones in sequence, and offer "accept all remaining recommendations" when the list is long. Resolve ambiguous domain language; maintain glossary-only context lazily with [CONTEXT-FORMAT.md](CONTEXT-FORMAT.md) and record an ADR only for expensive-to-reverse trade-offs using [ADR-FORMAT.md](ADR-FORMAT.md).

Write `PLAN_FILE` containing: objective; scope; non-goals; architecture; affected files and modules; implementation sequence; edge cases; migrations where applicable; security considerations; observable acceptance criteria; and the exact proof commands with expected results. Derive proof commands from the repository; ask only when what counts as success is genuinely unclear.

Start `LOG_FILE` with roles, requested models, scope, authorization and round limits. A request for a plan is not a request to implement it — stop here unless building was authorized.

With `mode=review`, load the supplied plan, fill only material gaps, and go straight to Phase 2.

## Phase 2 — Independent plan review

First round creates a session; every later round resumes that exact session id so OpenCode can judge whether its own earlier findings were actually fixed.

```text
python RUNNER review --repo REPO --plan PLAN_PATH [--model provider/model] [--variant V] --artifacts RUNS
python RUNNER review --repo REPO --plan PLAN_PATH --resume PREVIOUS_RESULT --feedback DISPOSITIONS
```

Never create a new session for a revision round, never guess a session id, and never use `--continue`. Exit code zero means a completed turn, **not** APPROVED.

- **APPROVED** — no unresolved high or medium findings. The approval binds to the exact plan path and SHA256. Present remaining low findings and stated limitations; zero findings is valid and is not proof of correctness.
- **REVISE** — arbitrate every finding yourself. Accept what the evidence supports and update the plan; reject the rest with a stated reason. Record both in `LOG_FILE`, then resume the same session with a `--feedback` file containing your dispositions.
- **BLOCKED**, a failed process, or a malformed result — never approval. Explain the missing evidence or the operational failure. Do not burn rounds on blind retries and do not silently switch model or provider.

Stop at `MAX_ROUNDS` and present unresolved findings with your position rather than manufacturing agreement. Any later edit to the plan invalidates the approval: run `check` against the final plan before building.

```text
python RUNNER check --repo REPO --plan PLAN_PATH --approval APPROVED_RESULT
```

If the user explicitly chooses to build without approval, record that override and use the unreviewed-spec path. Never label it approved.

## Phase 3 — Build, proof and cross-inspection

Read [the build reference](references/build.md). Present the reviewed plan and remaining limits, and get the implementation decision if it is not already authorized.

**`builder=claude` (default).** Implement the approved plan with your normal tools. Capture the pre-build commit first. Then run the proof, and have a **fresh** OpenCode session inspect the result. The plan-review session is never reused for code inspection.

**`builder=opencode`.** Delegate through the runner's `build` mode against a clean checkout, then inspect the complete resulting diff yourself and run the proof yourself. Bind your inspection to a fingerprint with `manifest` mode. OpenCode may not commit or push; that is denied by policy, not by instruction.

Run the proof yourself either way. An agent reporting that tests pass is not proof.

```text
python RUNNER proof    --repo REPO --proof "PROOF_CMD" --base BASE_COMMIT --artifacts RUNS
python RUNNER inspect  --repo REPO --plan PLAN_PATH --base BASE_COMMIT --artifacts RUNS
python RUNNER manifest --repo REPO --base BASE_COMMIT --out MANIFEST_PATH
```

Classify inspection findings as blocking correctness, security or data integrity, important maintainability, or optional. Cosmetic suggestions do not block completion unless they violate an explicit requirement in the plan. Fix accepted findings, rerun the affected proof, then inspect again in another fresh session — code that changed after an inspection is not covered by it, and saying otherwise is a false claim.

If you take over coding after delegating, you have become a builder: your edits need a fresh OpenCode inspection. If both agents wrote code, log the authorship split and have each inspect the other's changes. When the round budget runs out, report the unresolved findings and any unreviewed edits explicitly.

Finish with the final diff, proof results with exit codes, inspection coverage, unresolved findings, deviations, rounds used, and the artifact paths. Leave commits and pushes to the user's existing authorization.

## Audit trail

Keep `LOG_FILE` structured and readable — initial plan hash, session id, each round with OpenCode's findings and your disposition of each, accepted and rejected findings with reasons, the plan hash per round, the final verdict, requested and observed model, CLI errors, proof commands with exit codes, build information, inspection results, and remaining uncertainty. Reference artifact directories by path; keep raw stdout, prompts and transcripts in the artifact directory outside the repository, never pasted into the log or committed.
