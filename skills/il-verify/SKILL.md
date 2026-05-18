---
name: il-verify
description: Stage 4/4 (final) of the il-loop workflow. Use only when the user explicitly asks to verify and ship a fixed GitHub issue via phrases like "/il-verify", "il-loop:verify", "验证 issue NN", or "推送 issue NN". Refreshes the GitHub issue from gh, diffs the worktree against start_commit, runs the user-declared test command, and walks three independent confirmation gates (push branch / create PR / close issue) before marking status=done. Highest commit-and-share side-effect risk in il-loop — NEVER invoke automatically.
---

# /il-verify — Issue-Loop Verification + Three-Gate Ship (Stage 4/4)

Canonical design: `.claude/dev-loop/il-loop-design-v2.md` §5.4. The spec is authoritative; this skill executes it.

## Do NOT run this skill when

- The issue file does not exist.
- `status != verify`.
- Another il-loop command is holding either lock.
- No TTY — all three gates require interactive confirmation.

## Purpose

Stage 4 of 4. Reconcile worktree, GitHub issue, and test results; then walk three independent user-confirmation gates: push branch, create PR, close issue. Each gate is INDEPENDENT — declining one does not block the others. Records the final Outcome and disposes of the codex session.

This is the highest-risk skill in il-loop. NEVER auto-invoke.

## Pre-checks

1. Issue file exists, `status == verify`.
2. TTY present.
3. `gh auth status` OK.
4. `git rev-parse HEAD` is a forward of frontmatter `start_commit` (else: ask user, since unexpected commits will be included in verification).

## Behavior

### Phase A — Acquire BOTH locks (issue-NN, then worktree)

Same as `/il-fix` Phase A. Refuse if worktree lock is held; report which issue is holding it.

### Phase B — D2 refresh: re-fetch GitHub issue

Per spec D2 / §5.4 step 2:

```bash
gh issue view "$NN" --comments --json title,body,labels,comments,state > /tmp/il-${NN}-issue-now.json
```

Diff against the frozen `## Issue` section in the issue file. Compare title, body, comments (presence + content of each comment), and labels.

- **Unchanged**: write to `## Verify` section: `gh issue refresh: clean`.
- **Changed**: write the diff (which fields changed, new comments added since triage) to `## Verify` section. Then `confirm()`:

  ```
  Issue #<NN> body / comments changed during the fix. Changes:
    - body: <diff summary>
    - new comments: <count> by <users>
    - labels: <added/removed>
  Proceed with verify, or pause to re-evaluate?
  [proceed/pause]:
  ```

  On `pause`: keep status=verify, release locks, exit. User can re-run after evaluating.

### Phase C — Diff worktree vs start_commit

```bash
git diff --name-status "${START_COMMIT}..HEAD" > /tmp/il-${NN}-files.txt
git diff --stat "${START_COMMIT}..HEAD" > /tmp/il-${NN}-stat.txt
```

Write summary to `## Verify`:

```markdown
### diff vs start_commit (${START_COMMIT})
- files: <count>
- +<lines> / -<lines>
- <file list>
```

If file list is EMPTY (no changes since triage): `confirm()` user — "No worktree changes detected. Verify anyway?". Default no.

### Phase D — Run test command

Read frontmatter `test_command`.

- If literal `"none"`: log `test_command result: skipped (declared none at triage)`.
- Else: run the command. Capture exit code, stdout/stderr (last 50 lines).
  - Exit 0 → `pass`
  - Non-zero → `fail`
  - Hang (>5 min, heuristic) → `timeout`; `confirm()` whether to continue gates despite test failure

Write result to `## Verify`:

```markdown
### test_command
- command: <verbatim>
- result: pass | fail | skipped | timeout
- exit_code: <N>
- tail:
  <last 20 lines>
```

If `fail` or `timeout`: `confirm()` — "Tests failed/timeout. Continue to confirmation gates anyway?" Default no.

### Phase E — Claude Reads touched files

For each file in the diff, Read it (or the relevant hunks for large files) and add a one-line note to `## Verify`:

```markdown
### file review notes
- src/auth.ts: redirect handler added, no obvious regressions
- src/auth.test.ts: new test covers redirect path
```

This is Claude's independent post-hoc check, NOT trusted from codex's APPLIED log.

### Phase F — Gate 1: push

```
confirm():
  Push current branch (${WORK_BRANCH}) to origin?
  - Will run: git push -u origin ${WORK_BRANCH}
  [y/n]:
```

- y → `git push -u origin "$WORK_BRANCH"`. On success, write to `## Outcome`:
  ```
  - pushed: <ISO> (branch <WORK_BRANCH> → origin)
  ```
  On push failure (rejected, auth, network): show error, log to Outcome as `push failed: <reason>`, continue to next gate (do NOT auto-retry).
- n → record `push: skipped` in Outcome; proceed to next gate.

### Phase G — Gate 2: PR

Only offered if:
- `WORK_BRANCH != BASE_BRANCH`
- Push succeeded in Phase F (or branch is already pushed)
- No open PR for this branch (`gh pr list --head "$WORK_BRANCH" --state open` returns empty)

```
confirm():
  Create PR from ${WORK_BRANCH} → ${BASE_BRANCH}?
  - Will run: gh pr create --base ${BASE_BRANCH} --head ${WORK_BRANCH} --title "<title>" --body "Closes #${NN}"
  [y/n]:
```

- y → `gh pr create ...`. Capture PR number. Write to Outcome:
  ```
  - PR: #<N> (created at <ISO>, base <BASE_BRANCH>)
  ```
- n → `PR: skipped` in Outcome.

If a PR already existed: write `PR: #<N> (pre-existing)` to Outcome; do not prompt.

### Phase H — Gate 3: close issue

```
confirm():
  Close GitHub issue #<NN> as completed?
  - Will run: gh issue close <NN> --reason completed
  [y/n]:
```

- y → `gh issue close "$NN" --reason completed`. Write to Outcome:
  ```
  - issue closed: <ISO> (reason: completed)
  ```
- n → `issue close: skipped`.

### Phase I — Final state + session disposition

If ANY gate succeeded: set frontmatter `status: done`, `updated_at`. If ALL THREE gates were declined: status remains `verify` (user can re-run later).

Session disposition (per spec §5.4 step 9):
- trivial path: close session via continuo `terminal_kill`. Record in Outcome: `session disposition: closed`.
- normal path: keep session alive. Record: `session disposition: kept (session_id ${SESSION_ID})`.

### Phase J — Release locks, report

```bash
rm -f "$LOCK_WT" "$LOCK_ISSUE"
```

Report to user:
1. Final status
2. Each gate outcome (pushed? PR? closed?)
3. Session disposition
4. File path of the issue's markdown for future reference

Stop. il-loop ends here.

## Guardrails

- Three gates are INDEPENDENT. Do not bundle them. Do not auto-derive one from another.
- Do not auto-retry failed push / PR create / close. Surface the error and let user decide.
- Do not skip Phase B (GitHub refresh) — silently shipping when the issue body changed is exactly the failure mode P0.2 targeted.
- Do not skip Phase D (test command), even if user implies "I already tested". `none` is a valid declaration but must be explicit at triage.
- Do not edit project files in this stage. Only `git push` and `gh` calls touch externally-visible state.
- Do not release locks until Phase J. The whole verify+ship sequence is one critical section.

## Failure modes

- Phase B detects changes + user pauses → status remains verify, locks released, exit
- Phase D test fails + user declines to continue → status remains verify, locks released, exit
- Phase F push rejected (e.g., needs --force-with-lease) → log failure to Outcome, continue to next gate; do NOT auto-force-push
- Phase G PR creation fails (auth, repo config) → log failure, continue to Phase H
- Phase H close fails (no permission, locked issue) → log failure
- Any `confirm()` no-TTY abort → release locks, status preserved
- User Ctrl-C mid-gate → trap releases locks; status preserved at last completed gate
