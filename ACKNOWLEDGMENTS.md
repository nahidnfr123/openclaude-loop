# Acknowledgments

## claudex-loop

**openclaude-loop is based on and inspired by [chaseai-yt/claudex-loop](https://github.com/chaseai-yt/claudex-loop)** by Chase AI, used under the MIT License. If you want the original Claude ↔ Codex workflow, use that project.

The core ideas are theirs. This project reimplements them against a different second agent, and the following carry over as substantial reuse rather than mere inspiration:

- The four-phase shape: recon → requirements interview → adversarial plan review → build with cross-inspection.
- The central invariant that whoever creates something is never the agent that grades it.
- Binding an approval to the plan's SHA256, so any edit after approval invalidates it.
- The change snapshot: hashing tracked, staged, deleted and untracked files plus the diff into one fingerprint, and refusing a result if the code moved during inspection.
- Resuming an explicit recorded session id instead of "whatever ran last", and a fresh session for final inspection.
- Refusing to treat a started process, an output file or a session event as success.
- Keeping run artifacts outside the reviewed checkout, and requiring a clean checkout for a delegated build.
- The single-file, dependency-free runner and the fake-CLI contract-test approach, including several test cases ported directly.
- [`skills/openclaude-loop/CONTEXT-FORMAT.md`](skills/openclaude-loop/CONTEXT-FORMAT.md) and [`skills/openclaude-loop/ADR-FORMAT.md`](skills/openclaude-loop/ADR-FORMAT.md), reused essentially verbatim.

## Matt Pocock

`CONTEXT-FORMAT.md` and `ADR-FORMAT.md` were adapted by claudex-loop from skills by [Matt Pocock](https://github.com/mattpocock/skills), used under the MIT License. See [`NOTICE`](NOTICE) and [`skills/openclaude-loop/THIRD-PARTY-NOTICES.md`](skills/openclaude-loop/THIRD-PARTY-NOTICES.md).

## OpenCode

[OpenCode](https://opencode.ai) is an independent open-source coding agent. This plugin drives its CLI; it is not affiliated with or endorsed by the OpenCode project.

## What is different here

This is not a rename. Codex and OpenCode solve the same problem with incompatible mechanisms, and the differences are deliberate:

| Upstream (Codex) | openclaude-loop (OpenCode) |
|---|---|
| Either Claude Code or Codex could host | Claude Code always hosts; the host abstraction and the whole Claude-CLI adapter are removed |
| `codex exec -s read-only` sandbox flag | a generated permission profile injected as an ephemeral config — OpenCode has no sandbox flag |
| (config always applied) | `--standalone` is **required**, or the run silently inherits the user's background-service config |
| `--output-schema` for native structured output | an `<OPENCLAUDE_RESULT>` sentinel block with its own strict schema validation — OpenCode has no structured-output flag |
| `-o reply.txt` for the reply | `opencode session export` as the authoritative transcript |
| session ids are UUIDs | session ids are `ses_…`, and an error event carries one too |
| `model_reasoning_effort` config | `provider/model#variant` |
| `.codex-plugin/` packaging | Claude Code plugin only; there is no `.codex-plugin` |

Codex is not required, referenced or supported anywhere in this project.
