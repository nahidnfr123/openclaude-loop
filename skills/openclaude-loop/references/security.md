# Security boundary

The review must be read-only in fact, not because the prompt asked politely. OpenCode's permission system enforces it; the prompt only explains it.

## How the profile is applied

For every run the runner generates a complete, ephemeral OpenCode configuration and passes it in `OPENCODE_CONFIG_CONTENT`. The user's `opencode.json` / `opencode.jsonc` is never read for permissions, never edited, and never left changed. The generated configuration is written to `opencode-config.json` in the artifact directory for audit, and its permission block is hashed into `permission_profile_sha256` in the record.

**`--standalone` is mandatory and load-bearing.** Without it, `opencode run` attaches to the already-running background service, which was started with the user's own configuration and environment — the generated profile would be silently ignored and the run would inherit the user's permissions. The runner always passes `--standalone` so a private server starts inside the process with this environment. Treat any change that drops that flag as a security regression, not a refactor.

The run also sets `OPENCODE_DISABLE_PROJECT_CONFIG` and `OPENCODE_CONFIG_PROJECT_DISABLE`, so an `opencode.json` committed inside the repository under review cannot re-enable plugins, MCP servers or permissions for its own review. The generated configuration declares `plugin: []`, `mcp: {}`, `instructions: []` and empty skill paths, so unrelated user extensions are not loaded into the review environment. Authentication is untouched — the reviewer still uses the user's configured provider.

Each mode runs as its own generated primary agent (`openclaude-reviewer`, `openclaude-inspector`, `openclaude-builder`). Agent-level permissions take precedence over global configuration, so the profile holds even if some global setting survives.

OpenCode evaluates permission rules per action, and within an action **the last matching pattern wins** — so every profile writes its catch-all first and its specific rules after.

## Reviewer and inspector profile (read-only)

| Action | Effect |
|---|---|
| `*` | **deny** — anything not listed below is denied, including actions added by future OpenCode versions |
| `read` | allow, except `*.env` and `*.env.*` |
| `glob`, `grep`, `list`, `lsp`, `todowrite` | allow |
| `bash` | deny, except a fixed read-only git allowlist: `git status*`, `git diff*`, `git log*`, `git show*`, `git blame*`, `git ls-files*`, `git ls-tree*`, `git rev-parse*`, `git cat-file*`, `git describe*`, `git shortlog*`, `git config --get*` |
| `edit` | **deny** — covers edit, write and patch |
| `task`, `skill` | deny — no subagent or skill can be used to escape the profile |
| `webfetch`, `websearch` | deny |
| `question` | deny — a non-interactive run cannot answer one, so it fails fast instead of stalling |
| `doom_loop` | deny |
| `external_directory` | deny, except OpenCode's own managed directories, discovered per machine from `opencode debug paths` |

The reviewer can therefore read the repository, list and search it, and inspect git state — and cannot edit, write, patch, commit, push, run builds or tests, reach the network, delegate, or touch anything outside the repository. It is told never to claim it ran tests, because it cannot.

## Builder profile (controlled write)

Build is a different job and needs a different boundary. It runs with `--auto`, which auto-approves requests that are *not explicitly denied*; explicit denials are still enforced, so `--auto` is paired with a deny list rather than used as a blanket bypass.

| Action | Effect |
|---|---|
| `*` | allow |
| `read` | allow, except `*.env` and `*.env.*` |
| `edit`, `glob`, `grep`, `list`, `lsp`, `todowrite` | allow |
| `bash` | allow, **except** the deny list below |
| `task`, `skill`, `webfetch`, `websearch`, `question` | deny |
| `external_directory` | deny, except OpenCode's own managed directories |

Denied commands: every history- or publication-affecting git operation (`git commit*`, `git push*`, `git reset*`, `git checkout*`, `git switch*`, `git restore*`, `git rebase*`, `git merge*`, `git cherry-pick*`, `git revert*`, `git clean*`, `git stash*`, `git tag*`, `git remote*`, `git branch*`, `git filter-branch*`, `git filter-repo*`, `git submodule*`, `git worktree*`, `git am*`, `git format-patch*`, `git gc*`, `git reflog*`, `git update-ref*`); forge and publish tools (`gh *`, `glab *`, `hub *`, `npm publish*`, `yarn publish*`, `pnpm publish*`, `cargo publish*`, `twine*`, `gem push*`, `docker push*`, `flutter pub publish*`); privilege and destructive system commands (`sudo*`, `doas*`, `su *`, `chown*`, `chmod 777*`, `shutdown*`, `reboot*`, `halt*`, `mkfs*`, `diskutil*`, `dd *`, `rm -rf /*`, `rm -rf ~*`, fork bombs); network and remote access (`ssh*`, `scp*`, `rsync*`, `curl*`, `wget*`, `nc *`, `ftp*`); and scheduling or system configuration (`crontab*`, `launchctl*`, `systemctl*`, `reg *`, `regedit*`).

The builder can install dependencies, run builds, run tests and edit files inside the repository. It cannot commit, push, publish, escalate privileges or reach outside the repository. After a delegated build the runner re-reads `HEAD` and fails the run if the builder moved it, so a bypass would still be caught and reported rather than accepted. If the user explicitly authorizes a commit or push, the human performs it — the plugin never widens the profile to do it.

## What this does not cover

- "Read-only" describes the reviewer's project tools. The OpenCode process itself still writes its own session database, logs and caches outside the repository; that is how a session can be resumed and exported at all.
- This is a permission boundary, not an operating-system sandbox. A deliberately hostile model with an allowed command could still do something unintended inside the repository during a build. Use a disposable worktree for delegated builds.
- A model can misreport its own coverage. The structure of a result is validated; its truthfulness cannot be. Read the evidence rather than trusting the verdict.
- Denied `read` on `*.env` reduces incidental secret exposure; it is not a secret-scanning guarantee. Do not point the loop at a repository whose working tree holds credentials you would not share with the configured provider.
- The plan body and, for inspection, the change manifest and diff are sent to whatever provider OpenCode is configured with. That is the whole point of an external review — but it is a disclosure, so choose the provider deliberately.
