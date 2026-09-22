# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- `LICENSE` now contains only the standard MIT text so automated license
  detection recognises it. The derivative-work statement and the upstream
  copyright and permission notices this project must preserve moved to a
  dedicated [`NOTICE`](NOTICE) file, which also reproduces the Matt Pocock
  notice in full.
- OpenCode runs now default to `opencode/big-pickle` when no model is given.
  Pass `--model default` (or `reviewer_model=default` etc.) to let OpenCode
  use its own configured default, recorded as unresolved.
- Quota and rate-limit fallback: when a fresh turn on the default model fails
  on quota or rate limits, the runner retries in a new session on
  `opencode/mimo-v2.6-flash-free`, then `opencode/deepseek-v4-flash-free`
  (`--fallback-model` to choose, `--no-fallback` to disable). Resumed sessions
  and builds that changed the checkout never fall back. Every attempt is
  recorded in `fallback_attempts`.

## [0.1.0] - 2026-09-21

Initial public release.

### Added

- **Four-phase loop** coordinated from Claude Code: recon → requirements → `PLAN.md` → independent OpenCode plan review → build → proof → independent cross-inspection.
- **Three skills**: `openclaude-loop` (full loop), `opencode-review` (review an existing plan), `opencode-build` (delegate implementation to OpenCode).
- **OpenCode CLI adapter** (`skills/openclaude-loop/scripts/runner.py`): a single-file, standard-library-only runner with no pip dependencies, driving one OpenCode turn per invocation.
- **Read-only reviewer permissions** enforced by OpenCode's permission system rather than by prompt instruction, through an ephemeral generated agent and config. The user's own OpenCode configuration is never read for permissions, edited, or left changed.
- **Controlled build permissions**: writes inside the repository, with commits, pushes, publishing, privilege escalation, network access and out-of-repository paths denied. A builder that moves `HEAD` fails the run.
- **Explicit session management**: plan review creates one session and resumes that exact id across revision rounds; final inspection always uses a fresh session; delegated builds resume their own build session for bounded fix rounds. `--continue` is never used.
- **Structured verdict protocol**: `APPROVED` / `REVISE` / `BLOCKED` parsed only from an `<OPENCLAUDE_RESULT>` block and validated against a strict schema. Prose containing the word "approved" is not approval, and `APPROVED` carrying a high or medium finding is rejected as self-contradictory.
- **Robust output handling**: stdout, stderr and exit code captured; JSONL parsed best-effort; the authoritative transcript recovered through `opencode session export`, which also yields the observed model.
- **Plan approval fingerprinting**: approval binds to the plan path and SHA256, plus session id, requested and observed model, CLI version, verdict and round. Editing the plan invalidates the approval.
- **Change fingerprinting**: the pre-build commit plus every staged, unstaged, deleted and untracked change is hashed into one snapshot. Code changing during an inspection fails the run; changing after it marks the inspection stale.
- **`doctor`, `manifest`, `proof` and `check` modes** for prerequisites, Claude-side inspection binding, recorded verification evidence, and approval re-validation.
- **Cross-platform test suite**: 73 contract tests driving a fake OpenCode CLI and disposable git repositories, consuming no provider quota, running on Linux, macOS and Windows across Python 3.10 and 3.13.

### Notes

- Built against OpenCode **v2.0.11** and Claude Code **2.1.278**.
- Two defects found by live testing during development are fixed and regression-tested: OpenCode reports a `succeeded` session outcome, and OpenCode resolves its working directory from `$PWD` rather than the process working directory.
- Derived from [claudex-loop](https://github.com/chaseai-yt/claudex-loop) with the Codex integration replaced by OpenCode. See [ACKNOWLEDGMENTS.md](ACKNOWLEDGMENTS.md).

[Unreleased]: https://github.com/nahidnfr123/openclaude-loop/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/nahidnfr123/openclaude-loop/releases/tag/v0.1.0
