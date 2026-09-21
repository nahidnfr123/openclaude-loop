# Structured result protocol

Approval is never inferred from prose. A verdict exists only inside a machine-readable block, and the word APPROVED anywhere else in the response means nothing.

Every review and inspection prompt requires the response to end with exactly one block:

```text
<OPENCLAUDE_RESULT>
{"verdict": "APPROVED", "summary": "...", "findings": [], "coverage": ["..."], "limitations": []}
</OPENCLAUDE_RESULT>
```

A revision round returns findings:

```text
<OPENCLAUDE_RESULT>
{"verdict": "REVISE",
 "summary": "The migration step loses rows when the backfill is interrupted.",
 "findings": [
   {"id": "F1", "severity": "high",
    "title": "Backfill deletes source rows before the copy is verified",
    "evidence": "PLAN.md step 4 drops legacy_orders immediately after the INSERT ... SELECT, and db/migrate.py:88 has no verification query.",
    "recommendation": "Verify the copied row count, then drop the source table in a later migration."}],
 "coverage": ["PLAN.md", "db/migrate.py", "app/orders/service.py"],
 "limitations": ["Could not inspect the production schema."]}
</OPENCLAUDE_RESULT>
```

When required evidence cannot be inspected at all, the verdict is `BLOCKED` with at least one entry in `limitations`.

## Parsing and validation

- Only text inside the sentinel block is parsed. No block means no verdict — that is a failed run, not a rejection.
- If several blocks appear, the **last** one wins, so a model that corrects itself is read correctly. A ```` ```json ```` fence inside the block is tolerated.
- `verdict`, `summary`, `findings` and `limitations` are required. `coverage` is optional but requested, and must be a list of non-empty strings when present. Any other top-level field is rejected.
- `verdict` must be exactly `APPROVED`, `REVISE` or `BLOCKED`. `summary` must be a non-empty string.
- Each finding needs `id`, `severity`, `title`, `evidence` and `recommendation`, all non-empty strings, plus an optional `path`. Severity is `high`, `medium` or `low`. Finding ids must be unique.
- `APPROVED` is rejected if any finding is `high` or `medium` — a verdict cannot contradict its own findings.
- `REVISE` needs at least one finding. `BLOCKED` needs at least one limitation.

Structural validation proves the result is well-formed and self-consistent. It cannot prove the review is correct, that the stated coverage really happened, or that the findings are true. Zero findings is a legitimate outcome and is not evidence of exhaustive correctness. Read the evidence; do not require a finding quota, which only rewards invented objections.

The delegated build mode does not use this protocol — the builder returns a prose report, which is explicitly advisory. Claude reads the actual diff and runs the proof itself.
