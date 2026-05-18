---
name: il-fix
description: Stage 3/4 of the il-loop workflow. Use only when the user explicitly asks to execute fixes for a triaged or brief-completed GitHub issue via phrases like "/il-fix", "il-loop:fix", "让 codex 修 issue NN", or "执行 issue NN". Dispatches the operations list to a per-issue codex session (created if missing for trivial path), monitors execution with intended/attempted/applied/failed tagging, and on partial failure invokes the D3 five-choice prompt (continue / stash / revert / abandon / escalate). Has the highest side-effect risk in il-loop — touches the git worktree. NEVER invoke automatically.
---

# /il-fix — Issue-Loop Execution (Stage 3/4)

Canonical design: `.claude/dev-loop/il-loop-design-v2.md` §5.3. The spec is authoritative; this skill executes it.

## Do NOT run this skill when

- The issue file does not exist.
- Trivial path: `status != triage`.
- Normal path: `status != brief`.
- The worktree lock is held by another issue.
- No TTY (D3 prompt requires interaction).

## Purpose

Stage 3 of 4. Send the operations list to codex, have codex actually edit project files, verify each change independently by Claude Read + git diff, log everything to `## Execute log` with tagged rows. On any failure, surface the D3 five-choice prompt; on success, advance status to `verify`.

Claude does NOT directly Edit / Write project files in this stage — that is codex's job per project memory and spec §11.

## Pre-checks

1. Issue file exists at `.claude/issues/<NN_PADDED>-*.md`.
2. Frontmatter status matches path:
   - trivial: status=triage
   - normal: status=brief
3. `git rev-parse HEAD` == frontmatter `start_commit`, OR is a fast-forward ahead with no unexpected files. If diverged, ask user (proceed / abort).
4. TTY present.
5. Operations list exists in `## Brief` section.

## Behavior

### Phase A — Acquire BOTH locks (issue-NN, then worktree)

```bash
NN_PADDED=$(printf "%04d" "$NN")
LOCK_ISSUE=".claude/issues/.locks/issue-${NN_PADDED}.lock"
LOCK_WT=".claude/issues/.locks/worktree.lock"
```

Acquire `LOCK_ISSUE` first (per §3.3 algorithm). Then attempt `LOCK_WT`. If worktree lock is held by a different issue:

> "Worktree is held by issue #XX (PID Y, command /il-fix). Wait, or release that lock if you're sure."

Release the issue lock and abort.

If worktree lock acquired: trap both for release on EXIT/INT/TERM.

### Phase B — Verify or create codex session

Read frontmatter `session_id`.

- If non-empty (normal path inherited from /il-brief):
  - Call continuo `terminal_list_sessions`; confirm session still exists.
  - If gone, treat as session-death (spec §6). Inform user; create a new session and record new session_id. Conversational context is lost; the markdown Brief is sufficient.
- If empty (trivial path):
  - Create new session: `terminal_create_session` with name `il-<NN>`, agentLabel `il-<NN>`, cwd project root, autorun `codex`.
  - Wait for codex startup (≤30s).
  - Record session_id in frontmatter.

### Phase C — Set status = fixing

Update frontmatter `status: fixing` and `updated_at`. Commit this to disk BEFORE sending any operation to codex.

### Phase D — Dispatch operations list

Send to codex (`terminal_send_text` + `terminal_press_key enter`):

```
You will execute an ordered operations list for GitHub issue #<NN>.

Rules:
1. Execute operations in order.
2. Before each operation, print: "INTENDED: <op N>: <description>"
3. After each file change, print: "APPLIED: <file path> | <one-line diff summary>"
4. On any failure, print: "FAILED: <file path> | <reason>" and STOP. Do not continue.
5. Do not run tests. Do not push. Do not interact with git beyond editing files.
6. Do not auto-create commits.

Operations:
<verbatim Operations list from Brief>
```

Append to `## Execute log` for each operation:
```
- 2026-05-12T10:20:00Z [intended]   <op N>: <description>
```
(Written when Claude sees the INTENDED line from codex.)

### Phase E — Monitor and verify

Poll `terminal_read_output` with cursor.

For each line:
- `INTENDED: <op N>: <desc>` → log `[intended]` row
- `APPLIED: <file> | <summary>` → log `[attempted]` row, then **Claude independently verifies** by Read on the file + `git diff <file>`. If diff matches the summary intent, log `[applied]`. If not, log `[failed]` with mismatch reason.
- `FAILED: <file> | <reason>` → log `[failed]` row, stop polling, jump to Phase G.

Timeout: 90s of no new output → check codex state (Working / idle / dead). If dead, treat as session-death.

### Phase F — Successful completion

If codex prints a done marker AND all attempted rows were verified `[applied]`:

1. Update frontmatter: `status: verify`, `updated_at`.
2. Release worktree lock (worktree work is over).
3. Release issue lock.
4. Report to user: count of files changed, suggest `/il-verify <NN>`.

Do NOT auto-invoke `/il-verify`.

### Phase G — D3 partial-failure prompt

Triggered when any `[failed]` row is logged, OR codex reports a blocker.

Steps:
1. Set frontmatter `status: blocked`, `updated_at`.
2. Run `git status --porcelain` and append snapshot to Execute log:
   ```
   - 2026-05-12T10:22:00Z [snapshot] git status:
     M src/auth.ts
     ?? src/auth.test.ts
   ```
3. Via `confirm()` (interactive prompt), ask user the **five-choice menu**:

   ```
   Issue #<NN> /il-fix failed at operation <N>. What now?
     (i)  continue: send codex a follow-up to fix the blocker; resume from operation <N>
     (ii) stash + retry: git stash with name "il-loop-<NN>-<timestamp>", then codex restarts from operation 1
     (iii) revert specific files: prompt for files; git checkout -- <files>; codex resumes
     (iv) abandon: leave dirty tree; status=abandoned; release locks
     (v)  escalate: status=escalated; release locks; advisory message (no auto dev-loop migration)
   Choice [i/ii/iii/iv/v]:
   ```

4. Execute the chosen branch. Per §12 default 4: stash uses `git stash push -u -m "il-loop-<NN>-<timestamp>"`.

5. For (i) / (ii) / (iii): set status back to `fixing`, re-send appropriate prompt to codex, return to Phase E.
   For (iv) / (v): set status, release locks, stop.

6. For (iv) abandon with dirty tree: explicit second `confirm()` — "Worktree will remain dirty. Proceed?".

### Phase H — Lock release safety

```bash
trap 'rm -f "$LOCK_WT" "$LOCK_ISSUE"' EXIT INT TERM
```

Set BEFORE any user-facing prompt or codex send. Per §12 default 5, no-TTY abort also releases both locks.

## Guardrails

- Claude MUST NOT Edit / Write project files. Use Read for verification only.
- Do not silently accept codex's `APPLIED` claim without Read+diff verification.
- Do not skip the `[snapshot]` git-status row on failure.
- Do not auto-pick a D3 choice; user must select.
- Do not release the worktree lock until either (a) status reached verify or (b) status reached abandoned/escalated. Mid-D3 the lock is held.
- Do not start codex without setting the trap first.

## Failure modes

- Worktree lock held by another issue → refuse, release issue lock, abort
- start_commit mismatch beyond fast-forward → ask user
- codex session creation fails → release both locks, abort
- codex session dies mid-flight → log [failed], trigger D3 (treat as failure at current operation)
- Claude's Read shows file does NOT match codex's APPLIED claim → log [failed] with "verification mismatch", trigger D3
- User declines all D3 choices (Ctrl-C) → release locks, status remains `blocked`, do not auto-resolve
