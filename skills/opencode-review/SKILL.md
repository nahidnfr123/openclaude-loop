---
name: opencode-review
description: "Have OpenCode independently review an implementation plan you already have, while Claude Code arbitrates a bounded revision loop against the same OpenCode session. Use for /opencode-review, review this plan with opencode, have opencode review my plan, adversarial plan review, or a second-agent sanity check before high-stakes work. For the full recon and requirements interview first, use openclaude-loop instead. Not for reviewing already-written code — that is the inspection phase of openclaude-loop."
---

# OpenCode Review

Direct entry point: you already have a plan, or a clear enough idea to write one, and you want the independent stress-test without a requirements interview first.

Load [openclaude-loop](../openclaude-loop/SKILL.md) and start at `mode=review`. The shared workflow, the security boundary and the runner all live in that sibling skill; install it alongside this one. Read [the runtime reference](../openclaude-loop/references/runtime.md) and resolve the runner from the installed skill, never from the repository under review.

Preserve `PLAN_FILE`, `LOG_FILE`, `MAX_ROUNDS` / `rounds`, and any explicit `reviewer_model` and `reviewer_variant`. Use the actual resolved plan path on every round and on any build handoff.

Draft `PLAN.md` first if the user has only described the work — objective, scope, non-goals, architecture, affected files, sequence, edge cases, security considerations, acceptance criteria and proof commands. Fill material gaps with the user, but do not restart a full interview when the supplied plan is already adequate.

Then run the bounded loop: first round creates an OpenCode session; every revision round resumes **that exact session id** with a `--feedback` file holding your disposition of each finding, so OpenCode judges whether its own findings were actually fixed. Arbitrate every finding on evidence, accept or reject each one with a reason, and log both.

A completed run and an `APPROVED` verdict are both required. Failed, empty, blocked or malformed results are never approval, and a stated infrastructure failure is never converted into a verdict. Approval binds to the plan's SHA256 — any later edit invalidates it, so run `check` before building.

This command authorizes reviewing, not implementing. If implementation follows, use the shared build and inspection phase: an independent plan review does not replace an independent review of the final code.
