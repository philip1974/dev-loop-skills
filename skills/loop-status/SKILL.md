---
name: loop-status
description: Read-only viewer for the dev-loop loop-scout digest. Use only when the user explicitly asks to inspect automation status via phrases like "/loop-status" or "show loop-scout digest". Defaults to a fresh scan; "--cached" reads the advisory cache.
---

# /loop-status — Loop Scout Digest Viewer

## Do NOT run this skill when

- The user did not explicitly ask to view the loop-scout digest or automation status.
- The user wants to advance a dev-loop stage such as req, plan, red-team, integrate, execute, or verify.
- The user asks to run any suggested next command from the digest.
- The user asks to install or load launchd automation.

## Purpose

Show the advisory digest produced by `loop-scout.py`. This skill is read-only:
it may refresh the digest cache and display it, but it never runs any suggested
dev-loop command.

## Behavior

### Default: fresh scan

Run:

```bash
python3 ~/.claude/dev-loop-shared/loop-scout.py --projects ~/.claude/dev-loop-shared/loop-projects.yaml
```

Then display the digest from:

```bash
cat ~/.claude/loop-scout-cache/loop-inbox.md
```

Present the sections as written:
- `Actionable`
- `Needs human`
- `Stale`
- `Checks`

### Cached mode

If the user includes `--cached`, do not refresh. Run:

```bash
python3 ~/.claude/dev-loop-shared/loop-scout.py --projects ~/.claude/dev-loop-shared/loop-projects.yaml --cached
```

This prints the cache `generated_at` line and emits a stale warning if the cache
is older than 1 hour.

## Hard Rules

- Do not run `/dl-*` or any command shown in the digest.
- Do not edit topic files, project files, git state, launchd jobs, or GitHub.
- Do not call `launchctl`.
- Treat loop-scout output as advisory; canonical workflow state remains in each
  project's `.claude/dev-loop/` topic files.
