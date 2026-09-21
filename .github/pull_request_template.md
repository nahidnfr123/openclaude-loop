## What this changes

<!-- One or two sentences. Link the issue if there is one. -->

## Why

<!-- The problem this solves. -->

## Checks

- [ ] `python -m unittest discover -s tests -v` passes
- [ ] `python scripts/validate.py` passes
- [ ] `claude plugin validate .` passes
- [ ] `CHANGELOG.md` updated under `## [Unreleased]`
- [ ] Relevant reference doc updated (`references/security.md` still describes the actual permission profile)

## Invariants

- [ ] `--standalone` is still always passed to `opencode run`
- [ ] `PWD` is still pinned to the repository under review
- [ ] Sessions are still resumed by explicit id (no `--continue`)
- [ ] Final inspection still uses a fresh session
- [ ] Review and inspection profiles still deny by default
- [ ] No failure path can produce an `APPROVED` verdict
- [ ] No automated test calls a real provider

## Live testing

- [ ] I ran the live checks in `VALIDATION.md`
- [ ] I did not run them

OpenCode version tested against: <!-- e.g. v2.0.11, or "not run" -->

<!-- Do not paste raw run artifacts: they contain plans, prompts and possibly private code. -->
