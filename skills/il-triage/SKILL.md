---
name: il-triage
description: Stage 1/4 of the il-loop workflow (issue-loop, simplified dev-loop for GitHub issues). Use only when the user explicitly asks to triage a GitHub issue via phrases like "/il-triage", "il-loop:triage", "处理 issue NN", or "为 issue NN 做 triage". Reads a GitHub issue, classifies it (trivial / normal / heavy) via a T1-T5 decision tree, captures git base state, asks user for the test command, and writes `.claude/issues/<NN>-<slug>.md`. Do NOT invoke for ordinary "I want to fix..." requests, code edits without a referenced issue number, or full dev-loop work.
---

# /il-triage — Issue-Loop Triage (Stage 1/4)

Canonical design: `.claude/dev-loop/il-loop-design-v2.md` (in the project being worked on, or this file's repo). The spec is authoritative; this skill executes §5.1.

## Do NOT run this skill when

- No GitHub issue number was given.
- The user is asking a general question about issues.
- The user wants to start full dev-loop (not il-loop).
- Another il-loop stage on the same issue is already running (check `.claude/issues/.locks/issue-<NN>.lock`).

If any of the above match, decline politely and suggest the correct action.

## Purpose

Stage 1 of 4. Produce `.claude/issues/<NN>-<slug>.md` containing frozen issue body, triage decision, and the operations plan for trivial-path issues. Stops at file written — does not auto-invoke `/il-brief` or `/il-fix`.

## Pre-checks (abort on any failure)

1. `gh --version` succeeds; `gh auth status` shows authenticated.
2. Current directory is inside a git repo (`git rev-parse --git-dir`).
3. `git status --porcelain` is empty. If dirty, ask the user: stash / abort / proceed-at-own-risk. Record the choice in the file.
4. Working stdin is a TTY (`test -t 0`); if not, abort — il-loop requires interactive confirmation per §3.5 of spec.
5. `.claude/issues/` directory exists or can be created.

## Behavior

### Phase A — Acquire issue-NN lock

```bash
NN_PADDED=$(printf "%04d" "$NN")
LOCK=".claude/issues/.locks/issue-${NN_PADDED}.lock"
mkdir -p ".claude/issues/.locks"

if [ -f "$LOCK" ]; then
  EXISTING_PID=$(awk '/^pid:/{print $2}' "$LOCK")
  EXISTING_AGE_SEC=$(( $(date +%s) - $(date -j -f "%Y-%m-%dT%H:%M:%SZ" "$(awk '/acquired_at/{print $2}' "$LOCK")" +%s) ))
  if ! kill -0 "$EXISTING_PID" 2>/dev/null; then
    echo "Taking over stale lock from dead PID $EXISTING_PID"
    rm "$LOCK"
  elif [ "$EXISTING_AGE_SEC" -lt 3600 ]; then
    echo "Issue #$NN is held by PID $EXISTING_PID; refuse."
    exit 1
  else
    # ask user; on confirm rm the lock
    ...
  fi
fi

COMMAND_ID=$(uuidgen | tr 'A-Z' 'a-z')
cat > "$LOCK" <<EOF
acquired_at: $(date -u +%Y-%m-%dT%H:%M:%SZ)
pid: $$
command_id: $COMMAND_ID
hostname: $(hostname)
command: /il-triage
issue: $NN
session_id: ""
EOF
trap 'rm -f "$LOCK"' EXIT INT TERM
```

### Phase B — Fetch and freeze issue

```bash
gh issue view "$NN" --comments --json title,body,labels,comments,state,url > /tmp/il-${NN}-issue.json
TITLE=$(jq -r '.title' /tmp/il-${NN}-issue.json)
```

If `gh issue view` fails (auth, network, not found), abort with explicit "gh prerequisite not met"; release lock.

### Phase C — Slug + filename

1. Build slug: lowercase, replace non-alphanumeric with `-`, collapse repeats, truncate to ≤6 words.
2. Non-ASCII title → use `issue-${NN_PADDED}` slug.
3. Lookup-by-NN: scan `.claude/issues/${NN_PADDED}-*.md`. If a file already exists for this issue:
   - If slug matches: ask user — re-triage (overwrite Triage section, preserve audit history) or abort.
   - If slug differs: keep original filename, append new title to `slug_history` in frontmatter.

Filename: `.claude/issues/${NN_PADDED}-${SLUG}.md`.

### Phase D — Capture git base state

```bash
BASE_BRANCH=$(git symbolic-ref --short HEAD 2>/dev/null || echo "DETACHED")
START_COMMIT=$(git rev-parse HEAD)
WORK_BRANCH="$BASE_BRANCH"  # may change at /il-fix
```

### Phase E — Ask user for test command

Ask exactly one question, single line:

> Test command for issue #$NN (or 'none' if no tests apply)?
> Example: `npm test`, `pytest tests/`, `cargo test`, or `none`.

Store verbatim. If `none`, the `test_command` field will be the literal string `none` and `/il-verify` will mark tests skipped.

### Phase F — Classify (decision tree T1-T5 from spec §5.1)

Estimate `loc` and `files_touched` from issue title + body + linked PRs (best effort). Then traverse:

```
T1: typo / doc / single-flag / single-constant / pure-comment / pure-rename-no-callers
    AND loc <= 10                                                    → trivial
T2: schema migration / >3 modules / API contract / epic / discussion → heavy
T3: loc > 100 OR files_touched > 3                                   → heavy
T4: loc <= 10 AND touches business logic                             → normal
T5: default                                                          → normal
```

Record the FIRST branch that matches as `decision tree path: TN`.

### Phase G — For trivial path, write operations list now

If `path == trivial`, Claude writes the operations list inside the Triage section (per §12 default 3 in spec): an ordered list of file-level changes. `/il-fix` will send this verbatim to codex.

For normal path: operations list is left to `/il-brief`.

For heavy path: skip operations; advise user to escalate manually.

### Phase H — Write the issue file

Path: `.claude/issues/${NN_PADDED}-${SLUG}.md`

Frontmatter (see spec §2):
```yaml
---
issue: <NN>
slug: <slug>
slug_history: []
status: triage
path: trivial | normal | escalated
session_id: ""
base_branch: <BASE_BRANCH>
start_commit: <START_COMMIT>
work_branch: <WORK_BRANCH>
test_command: <user input verbatim>
created_at: <now ISO>
updated_at: <now ISO>
locks_held: []
---
```

Body sections to write:
- `## Issue (frozen at triage)` — verbatim `gh issue view` output
- `## Triage decision` — complexity / path / decision tree branch / test_command / base info / reason
- For trivial path only: append `## Brief` containing only the operations list (no 背景/方案 needed for trivial)
- For normal/heavy: do NOT yet write `## Brief`

### Phase I — Release lock and report

```bash
rm "$LOCK"
```

Report to user:
1. File written: `.claude/issues/${NN_PADDED}-${SLUG}.md`
2. Classification + decision tree branch
3. Captured `base_branch` / `start_commit`
4. Next step:
   - trivial → suggest `/il-fix <NN>`
   - normal → suggest `/il-brief <NN>`
   - heavy → no next il-loop step; suggest manual dev-loop escalation

Then stop. Do NOT auto-invoke next stage.

## Guardrails

- Do not run if no TTY — abort and release lock.
- Do not classify based on author tone or labels alone; use the T1-T5 tree.
- Do not skip Phase D dirty-tree check.
- Do not invent issue content; if `gh issue view` returns partial data, log and ask.
- Do not auto-invoke `/il-brief` or `/il-fix` even if path is trivial.
- Lock release on EXIT / INT / TERM must be set BEFORE any user-facing prompt — otherwise Ctrl-C leaves a stale lock.

## Failure modes

- gh auth/network failure → abort, release lock, message "gh prerequisite not met"
- Slug collision after lookup → keep original filename, update slug_history
- User aborts mid-Q&A → release lock; file is not written (atomic at Phase H)
- Lock contention → message per §3.3, abort
- Working tree dirty + user declines all 3 options → release lock, abort
