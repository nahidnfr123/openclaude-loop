# Build, proof and final inspection

Resolve the runner from the installed `openclaude-loop` skill. Carry the exact acceptance criteria and proof commands from the approved plan into the build, and keep artifacts outside the repository.

## Before any code changes

Capture the pre-build commit. Every fingerprint, manifest and inspection is relative to it. For a repository with no history, establish an initial git baseline with the user's authorization rather than claiming a diff you cannot produce.

A delegated build requires a clean checkout, and the runner enforces it. The loop's own `PLAN.md` and `PLAN-REVIEW-LOG.md` can be what makes the tree dirty — keep them outside the build checkout or include them in an authorized baseline. Never discard someone else's work to satisfy the gate; use a worktree:

```text
git worktree add ../feature-build -b feature-build
```

Re-review the plan inside that worktree before relying on an approval there: approval binds to the repository path as well as the plan hash. A worktree isolates diffs; it is not an operating-system sandbox.

## builder=claude (default)

Implement the approved plan with this session's normal tools. Then, in order:

```text
python RUNNER proof   --repo REPO --proof "PROOF_CMD" --base BASE_COMMIT --artifacts RUNS
python RUNNER inspect --repo REPO --plan PLAN --base BASE_COMMIT --artifacts RUNS
```

`inspect` always opens a **fresh** OpenCode session — `--resume` is refused. The plan-review session already argued for this plan and is not an independent reader of the code. The runner supplies the tracked diff plus a manifest of every changed, deleted and untracked file, fingerprints that state, and fails the run if the code changes while the inspection is in flight.

## builder=opencode

```text
python RUNNER build --repo REPO --plan PLAN --builder opencode \
  --approval APPROVED_RESULT --proof "PROOF_CMD" --artifacts RUNS
```

The builder works only from the approved plan and under [the build permission profile](security.md). It cannot commit or push; if it moves `HEAD` anyway, the runner fails the run and says so rather than accepting the result. Use `--unreviewed-spec` in place of `--approval` only for an explicitly requested standalone work order, and record that no plan review happened — it does not waive inspection of the final code.

For bounded fix rounds, resume the **same** build session with concrete findings:

```text
python RUNNER build --repo REPO --plan PLAN --builder opencode --approval APPROVED_RESULT \
  --proof "PROOF_CMD" --artifacts RUNS --resume PREVIOUS_BUILD_RESULT --feedback FIX_LIST
```

The clean-checkout gate applies only to the first round; a resumed round must run against the same recorded baseline, and the runner refuses if the checkout changed underneath it. Stop at `MAX_FIX_ROUNDS` and report rather than looping.

Then inspect the result yourself, bound to a fingerprint:

```text
python RUNNER manifest --repo REPO --base BASE_COMMIT --out MANIFEST
python RUNNER proof    --repo REPO --proof "PROOF_CMD" --base BASE_COMMIT --artifacts RUNS
```

Read every changed file relative to the pre-build commit — staged changes, deletions, binary assets and untracked additions, not just the unstaged diff. Never treat the builder's own report or its claimed proof output as verification.

## Proof

The proof command comes from the plan or from repository convention. Run the agreed narrow check; do not invent a full-suite run that nobody agreed to. Record the command, exit code, relevant output and whether it passed — `proof` mode writes exactly that, with the snapshot it ran against when `--base` is supplied. An agent saying tests should pass is not proof.

If a proof command is denied by this session's permissions, that is a reported failure. It is never grounds to bypass permissions.

## Judging inspection findings

Separate blocking correctness defects and security or data-integrity problems from important maintainability problems and optional improvements. Cosmetic suggestions do not block completion unless they violate an explicit requirement in the plan. For changed tests, check that assertions express the acceptance criteria or a valid regression rather than simply confirming whatever the implementation happens to do; existing regression tests need not map to a new plan sentence.

Fix accepted findings, rerun the affected proof, then inspect again in another fresh session. An inspection applies only to the snapshot it recorded — later edits invalidate it, and `check_inspection` will say so. Never present an earlier inspection as covering later fixes.

If you take over coding after delegating, you have become a builder and your edits need a fresh OpenCode inspection. If both agents wrote code, log the authorship split and have each inspect the other's changes. Stop at `MAX_INSPECTION_ROUNDS` and report unresolved findings and any unreviewed edits explicitly instead of claiming approval.

Ignored files are not enumerated by git — inspect ignored build deliverables separately. A changed submodule needs an explicit inspection path; the runner refuses to pretend a directory entry is a reviewed file.

Finish with the final diff, proof results with exit codes, inspected snapshot, deviations, residual findings and rounds used. Commits, pushes and releases follow the user's existing authorization and are never implied by running the loop.
