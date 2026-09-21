---
name: opencode-build
description: "Hand a frozen work order to OpenCode to implement with controlled write access, while Claude Code stays the spec-writer, runs the proof itself and independently reviews the whole diff. Use for /opencode-build, have opencode build this, build this with opencode and have claude review it, delegate the build to opencode, or right after a plan is approved and OpenCode is chosen as the builder. Not for tiny edits, not for design work that still needs decisions, and not for anything needing this session's MCP servers, credentials or browser."
---

# OpenCode Build

Direct entry point: the builder is explicitly OpenCode, and Claude Code is the inspector. This is the role flip of `opencode-review` — the agent that writes the code is never the agent that grades it.

Load [the build reference](../openclaude-loop/references/build.md), [the runtime reference](../openclaude-loop/references/runtime.md) and [the security model](../openclaude-loop/references/security.md) from the sibling `openclaude-loop` skill; install it alongside this one.

Preserve `SPEC_FILE` (mapped to the runner's `--plan`), `LOG_FILE`, `PROOF_CMD`, `MAX_FIX_ROUNDS`, and any explicit `builder_model` and `builder_variant`. The spec may have any filename — never silently substitute `PLAN.md`.

Before delegating, settle any consequential decision the spec still leaves open. Do not build by inventing missing requirements; if writing the spec forces design choices, that is `openclaude-loop` first. Use the current valid plan approval when this follows a review. For an explicitly requested standalone work order, use `--unreviewed-spec` and record that no plan review happened.

Capture the pre-build commit and require a clean checkout — use a worktree rather than discarding anyone's work. Then delegate with `build --builder opencode`, supplying the approval and the agreed proof command.

OpenCode gets write access inside the repository and nothing more: committing, pushing, publishing, privilege escalation, network fetches and anything outside the repository are denied by the permission profile, not merely discouraged. If the user explicitly authorizes a commit or push, the human performs it; the profile is never widened for convenience. If the builder moves `HEAD` anyway, the run fails and you report it.

Use bounded fix rounds by resuming the **same** build session with concrete findings — never a new builder context and never `--continue`. Stop at `MAX_FIX_ROUNDS`.

Then do the inspection yourself: run the proof, read every change relative to the pre-build commit including staged, deleted, binary and untracked files, and bind your inspection to a fingerprint with `manifest` mode so later edits cannot be passed off as reviewed. The builder's own report and its claimed proof output are advisory, never verification.

If you take over coding, you have become a builder: your edits need a fresh OpenCode inspection. If both agents contributed code, log the authorship split and have each inspect the other's changes. Present the completed diff, proof results and residual findings for whatever sign-off the user's authorization still requires.
