# Security policy

## Reporting a vulnerability

**Please do not report security vulnerabilities in public GitHub issues, discussions, or pull requests.**

Report privately through GitHub's private vulnerability reporting:

1. Go to <https://github.com/nahidnfr123/openclaude-loop/security/advisories/new>
2. Describe the issue, the impact, and how to reproduce it.

If that form is unavailable, open a public issue containing **only** the sentence "I would like to report a security issue privately" with no technical detail, and a maintainer will arrange a private channel.

Please include, where relevant:

- openclaude-loop version
- Claude Code version and OpenCode version
- Operating system
- Reproduction steps
- What the issue allows an attacker to do

Expect an initial response within 7 days. There is no bug bounty.

## Supported versions

Only the latest released version receives fixes.

| Version | Supported |
|---|---|
| 0.1.x | yes |

## What counts as a vulnerability here

This plugin's security claims are specific and narrow. The following are in scope:

- The reviewer or inspector permission profile failing to be read-only — any way for a review or inspection run to write, patch, commit, push, execute arbitrary shell commands, reach the network, or touch paths outside the repository under review.
- The generated permission profile not being applied — for example a code path that drops `--standalone`, which causes OpenCode to attach to the background service running under the user's own configuration and silently ignore the profile.
- The build profile failing to deny commits, pushes, publishing, privilege escalation, or out-of-repository writes.
- Approval or inspection binding being bypassable — a modified plan accepted as approved, or an inspection presented as covering code it never saw.
- A failed, empty, timed-out or malformed run being convertible into an `APPROVED` verdict.
- Prompt injection in a plan or repository file that causes the reviewer to perform an action its profile should have denied. (Injection that merely produces a wrong *opinion* is a correctness bug, not a vulnerability — see below.)
- Credentials, tokens or private repository content being written into a committed file or leaked into an unexpected location.

## What is explicitly out of scope

These are documented limitations, not vulnerabilities:

- **A permission profile is not an operating-system sandbox.** A delegated build can run allowed commands inside the repository. Use a disposable worktree.
- **The plan, and for inspection the diff, are sent to whichever provider OpenCode is configured with.** That is the purpose of an external review, and it is a deliberate disclosure. Choose the provider accordingly.
- **A model can misreport its own coverage or findings.** Structural validation proves a result is well-formed and self-consistent; it cannot prove it is truthful.
- **`read` on `*.env` is denied to reduce incidental exposure.** This is not a secret-scanning guarantee. Do not point the loop at a working tree holding credentials you would not share with the configured provider.
- Vulnerabilities in Claude Code, the OpenCode CLI, or a model provider. Report those to the respective projects.

## Scope note

This project is not an official Anthropic or OpenCode project.
