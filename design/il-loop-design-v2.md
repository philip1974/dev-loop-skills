---
title: il-loop Design v2 (integrated red-team feedback)
type: design-draft
status: draft
created: 2026-05-12
updated: 2026-05-12
supersedes: il-loop-design-v1.md
---

# il-loop Design v2

A simplified workflow for processing GitHub issues with Claude + codex collaboration. Derived from dev-loop (6 stages, per-topic directories, multi-version files) but stripped down for issue-scale work.

## Changelog from v1

Red-team feedback integration. Each P0/P1/P2 item from `red-team-v1` is marked accepted (✅), partial-reject (⚠️), or deferred (⏭).

| # | Item | Decision |
|---|---|---|
| P0.1 | State file not crash/concurrency-safe | ✅ — added §3 lock model, §6 recovery |
| P0.2 | Issue source-of-truth contradictory | ✅ — D2 freeze-then-refresh-at-verify |
| P0.3 | `/il-fix` partial-success undefined | ✅ — D3 three-choice prompt |
| P0.4 | Session death is state-corrupting | ✅ — §6 session-death recovery |
| P1.1 | Trivial/normal/heavy boundary ambiguous | ✅ — §5.1 single decision tree |
| P1.2 | Per-issue session ≠ real independence | ⚠️ — only conversational isolation claimed; git isolation handled by worktree lock |
| P1.3 | push/PR/close one-gate too coarse | ✅ — three separate confirmation prompts |
| P1.4 | Missing gates on risky recovery | ✅ — confirm before stash/checkout/abandon-with-dirty/escalate |
| P1.5 | gh unavailability not handled | ⏭ — documented as prerequisite, no degraded path in v1 |
| P1.6 | base branch / start commit untracked | ✅ — triage records to frontmatter |
| P1.7 | dev-loop boundary vague | ⏭ — manual escalation, advisory only, v1 does not auto-migrate |
| P1.8 | Brief in-place edit not auditable | ✅ — pre-integration Brief preserved as collapsed `### Brief (pre-integration)` |
| P1.9 | Test command discovery too fragile | ✅ — user declares test command at triage; "no tests" explicit |
| P1.10 | Status transitions inconsistent | ✅ — §4 explicit state machine |
| P2.1 | Slug rule underspecified | ✅ — §2 lookup-by-issue-number; slug is cosmetic |
| P2.2 | Time format inconsistent / no TZ | ✅ — ISO 8601 with `Z` everywhere |
| P2.3 | Transcript ref vague | ✅ — `session_id + (start_seq, end_seq)` |
| P2.4 | Execute log conflates intended/attempted/actual | ✅ — log rows tagged `intended/attempted/applied/failed` |
| P2.5 | "No flag bypass" weak on non-interactive | ✅ — explicit `confirm()` helper, refuses if no TTY |
| P2.6 | Acceptance leaks skill-packaging detail | ✅ — split §10 acceptance from §11 packaging |
| Cross | State / git / GitHub / session can diverge | ✅ — §1 authoritative state table |
| Cross | Single-active-issue assumption | ✅ — §3 locks make concurrency explicit |
| Cross | Auditability uneven | ✅ — §7 audit trail (pre-integration Brief + tagged execute log + raw transcript ref) |
| Cross | Failure handling conversational | ✅ — §4 state machine + §6 recovery |
| Cross | Claude/codex boundary not protected | ⏭ — relies on convention + post-hoc Read/diff; no enforcement in v1 |

---

## 1. Authoritative state

When the same fact appears in multiple places, this table decides which one wins. All recovery and integrity checks defer to this:

| Resource | Authoritative source | Cached in markdown? |
|---|---|---|
| Working tree contents | `git` working tree on disk | no |
| Branch / base / start commit | `git` symbolic refs | yes, in frontmatter (cache only) |
| GitHub issue body + comments | `gh issue view <#>` live | yes, frozen at triage; refreshed at verify (see §5.4) |
| Workflow stage / decisions | issue's markdown file | n/a (it IS the source) |
| Codex conversation context | the codex session | n/a (transcript is volatile; markdown captures decisions) |

If markdown disagrees with git, **git wins** — markdown is corrected. If markdown disagrees with `gh`, **gh wins at verify time** — at other times markdown's frozen snapshot is used. If a codex session is missing or unreadable, it is treated as gone — markdown's decision log is sufficient to continue (a new session may be spawned).

## 2. File state

One markdown file per issue: `.claude/issues/<NN>-<slug>.md`.

- `NN` = GitHub issue number (zero-padded to 4 digits: `0042`).
- `slug` = kebab-case short title from issue, ≤6 words. **Cosmetic only** — lookup and uniqueness use `NN`. Renaming an issue does not rename the file; a `slug_history` frontmatter list records changes.
- Non-ASCII titles: transliterate to ASCII or use `issue-<NN>` slug.
- Abandoned files stay in place with `status: abandoned`. No archive directory in v1.

Frontmatter:

```yaml
---
issue: 42
slug: fix-login-redirect
slug_history: []                   # appended if issue is renamed
status: triage | brief | fixing | verify | done | abandoned | blocked
path: trivial | normal | escalated
session_id: term-xxxxxxxx          # empty until brief (normal) or fix (trivial)
base_branch: main                  # captured at triage
start_commit: abc1234              # captured at triage
work_branch: issue-42-fix-login    # current branch at fix start (may equal base)
test_command: "npm test"           # declared at triage; or null if "no tests"
created_at: 2026-05-12T10:00:00Z
updated_at: 2026-05-12T10:00:00Z
locks_held: []                     # transient; written by lock acquisition, removed on release
---
```

Body sections (appended over lifetime, never overwritten):

```
## Issue (frozen at triage)
<verbatim gh issue view output>

## Triage decision
- complexity: trivial | normal | heavy
- path: trivial | normal | escalated
- decision tree path: <branch IDs traversed, see §5.1>
- test command: <user-declared, or "none">
- base_branch / start_commit / work_branch
- reason: <one paragraph>

## Brief (pre-integration)              # collapsed copy, only for normal path
<original Brief written by Claude, before red-team>

## Brief                                # current Brief, edited in place after integration
- 背景 / Background
- 方案 / Approach
- 操作清单 / Operations (ordered, file-level)
- risks

## Red-team (codex)                     # normal path only
- P0 / P1 / P2 items
- raw transcript ref: session_id=term-xxx, seq=[start, end]

## Brief changelog
- v1 → v2 (2026-05-12T10:15:00Z): accepted [P0.1, P1.3], rejected [P1.2: reason], deferred [P2.1]
- v2 → v3 (...)

## Execute log
- 2026-05-12T10:20:00Z [intended]   plan: edit src/auth.ts add redirect handler
- 2026-05-12T10:21:30Z [attempted]  codex: editing src/auth.ts
- 2026-05-12T10:21:45Z [applied]    file: src/auth.ts (+12 -3) — verified by Claude Read
- 2026-05-12T10:22:00Z [failed]     file: src/auth.test.ts — codex reported test-not-found

## Verify
- gh issue refresh: clean | changed (diff: <list of changed fields>)
- diff vs start_commit: <file list>
- test_command result: pass | fail | skipped (reason)
- verify notes

## Outcome
- pushed: 2026-05-12T11:00:00Z (branch issue-42-fix-login → origin)
- PR: #43 (created | already existed | none)
- issue closed: 2026-05-12T11:05:00Z (reason: completed)
- session disposition: closed | kept
```

## 3. Concurrency model: two-layer locks

Lockfile location: `.claude/issues/.locks/` (add to `.gitignore`).

### 3.1 Lock files

```
.claude/issues/.locks/
├── issue-0042.lock              # per-issue state lock
└── worktree.lock                # project-wide git worktree lock
```

Lock content (YAML):

```yaml
acquired_at: 2026-05-12T10:23:45Z
pid: 41523
command_id: 7f3e2c1d              # UUID generated at command start
hostname: rigang-mbp
command: /il-fix
issue: 42
session_id: term-xxx              # if codex session is involved
```

### 3.2 Lock matrix

| Command | issue-NN lock | worktree lock |
|---|---|---|
| `/il-triage <NN>` | ✅ | ❌ |
| `/il-brief <NN>` | ✅ | ❌ |
| `/il-fix <NN>` | ✅ | ✅ |
| `/il-verify <NN>` | ✅ | ✅ |

Rationale: state-file-only commands take only the per-issue lock, allowing parallel triage/brief on different issues. Worktree-touching commands take the global worktree lock, serializing all git-affecting work.

### 3.3 Acquisition algorithm

```
acquire_lock(scope, NN?):
  path = ".claude/issues/.locks/{scope}.lock"  # "issue-NN" or "worktree"
  if not exists(path):
    write(path, current_lock_yaml)
    return OK

  existing = read_yaml(path)
  if existing.hostname != current_host:
    refuse: "lock held by other host {existing.hostname}; remove manually if stale"
    return FAIL

  if existing.command_id == current_command_id:
    # same invocation re-acquiring; allow (idempotent)
    return OK

  if not pid_alive(existing.pid):
    # auto-takeover
    log("stale lock from dead PID {existing.pid}, taking over")
    write(path, current_lock_yaml)
    return OK

  age = now - existing.acquired_at
  if age < 1 hour:
    refuse: "issue #{NN} is held by PID {existing.pid} running {existing.command} for {age}.
             Wait, or remove .claude/issues/.locks/{scope}.lock if you are sure that process is dead."
    return FAIL

  # age >= 1 hour, PID alive: probably hung
  ask user: "lock held for {age} by live PID {existing.pid}, suspected hang. Force-remove and continue?"
  if confirmed:
    write(path, current_lock_yaml)
    return OK
  else:
    return FAIL
```

### 3.4 Release

- Normal exit: every command MUST release its locks (in `finally` / `defer`).
- Crash: lock remains; recovered by next `pid_alive` check.
- User SIGINT: best-effort release on signal handler; if missed, recovered by PID check.

### 3.5 Confirmation helper

```
confirm(prompt):
  if not isatty(stdin):
    refuse: "{prompt} requires interactive confirmation; no TTY"
    abort()
  read y/n from user
```

All push / PR / close / stash / checkout / force-lock-remove / abandon-with-dirty-tree / escalate decisions route through `confirm()`. No environment variable or flag bypasses this in v1.

## 4. State machine

```
                          ┌────────────────────┐
                          │     (no file)      │
                          └─────────┬──────────┘
                                    │ /il-triage
                                    ▼
                          ┌────────────────────┐
                ┌─────────│      triage        │─────────┐
       trivial  │         └─────────┬──────────┘  heavy  │
                │                   │ normal             │
                ▼                   ▼                    ▼
        ┌──────────────┐   ┌────────────────┐    ┌──────────────┐
        │   triage     │   │     brief      │    │  escalated   │
        │  (path=triv) │   │ (path=normal)  │    │ (manual exit)│
        └──────┬───────┘   └────────┬───────┘    └──────────────┘
               │ /il-fix             │ /il-fix
               ▼                     ▼
        ┌────────────────────────────────────┐
        │              fixing                │
        └───┬──────────┬─────────────────────┘
            │ ok       │ partial-fail (D3 prompt)
            ▼          ▼
     ┌───────────┐  ┌──────────────────────────┐
     │  verify   │  │  blocked (D3 chosen)     │
     └─────┬─────┘  └──┬───────────────────────┘
           │           │ /il-fix retry
           │           ▼
           │     (back to fixing)
           │
           │ /il-verify, user confirms (3 gates)
           ▼
     ┌───────────┐
     │   done    │
     └───────────┘
```

Allowed transitions only. Any other transition is a bug. `abandoned` is reachable from any state with explicit user confirmation.

## 5. Commands

### 5.1 `/il-triage <issue#>` — Claude

**Locks**: issue-NN.

Steps:
1. Acquire `issue-NN` lock.
2. Run `gh issue view <#> --comments`. If `gh` fails: abort with "gh prerequisite not met"; do not create file.
3. Generate slug from title; if file already exists with different slug, append new slug to `slug_history` and keep original filename.
4. Capture `base_branch = git symbolic-ref --short HEAD`, `start_commit = git rev-parse HEAD`. Refuse if working tree is not clean (asks user: stash, abort, or proceed with dirty tree at own risk).
5. Ask user for test command (single prompt): "test command for this issue (or 'none')". Store in frontmatter.
6. Classify via decision tree:

```
classify(issue):
  estimate_loc = best-effort heuristic from issue text + linked PRs
  files_touched = guess from issue text (file paths, module names)

  # T1: forced trivial
  if matches any of: typo-only, doc-only, single-config-flag, single-constant,
                     pure-comment, pure-rename-no-callers
      AND estimate_loc <= 10:
    return trivial, reason="T1: limited surface, no logic"

  # T2: forced heavy
  if any of: requires schema migration, touches >3 modules,
             requires API contract change, listed as "epic" or "discussion":
    return heavy, reason="T2: scope exceeds il-loop"

  # T3: forced heavy by size
  if estimate_loc > 100 OR files_touched > 3:
    return heavy, reason="T3: size exceeds il-loop"

  # T4: trivial business-logic edge
  if estimate_loc <= 10 AND touches business logic:
    return normal, reason="T4: small but logic-bearing → red-team worth it"

  # T5: default
  return normal, reason="T5: default for in-scope issues"
```

7. Write `## Triage decision` section with classified path AND decision tree path traversed (e.g., "T4").
8. Set `status = triage`, `path = trivial|normal|escalated`.
9. Release lock.
10. Report to user; suggest next command (`/il-fix` for trivial, `/il-brief` for normal, manual escalation message for heavy).

### 5.2 `/il-brief <issue#>` — Claude + codex red-team

**Locks**: issue-NN.

Pre-conditions: `status ∈ {triage, brief}`, `path == normal`.

Steps:
1. Acquire `issue-NN` lock.
2. Claude writes the **Brief** section (背景/方案/操作清单/risks).
3. Save a verbatim copy as `## Brief (pre-integration)` (collapsed details block in markdown).
4. Create new codex session via continuo (`agentLabel: il-<NN>`, `cwd: project root`). Record `session_id` in frontmatter.
5. Build a **neutral red-team prompt** (no Claude rationale, no preferences). Send: Issue text + current Brief + request for P0/P1/P2 findings.
6. Wait for codex output. Record `(start_seq, end_seq)` of the response in the Red-team section as the transcript reference.
7. Per item, Claude decides accept/reject/defer.
8. Edit the **current Brief in place** to apply accepted items. Append a row to `## Brief changelog` with timestamp, vN→v(N+1), and per-item disposition with reasons.
9. Set `status = brief`. Release lock.

Session disposition: kept alive for `/il-fix`.

### 5.3 `/il-fix <issue#>` — codex executes, Claude monitors

**Locks**: issue-NN AND worktree.

Pre-conditions:
- trivial path: `status == triage`.
- normal path: `status == brief`.

Steps:
1. Acquire `issue-NN` lock, then `worktree` lock. If worktree lock is held by another issue, refuse with that issue's number.
2. Verify worktree is at `start_commit` or a known forward of it. If diverged unexpectedly, ask user (proceed / abort).
3. If trivial path AND `session_id` empty, create new codex session (agentLabel `il-<NN>`); record session_id.
4. Set `status = fixing`.
5. Send to codex the operations list (from Brief for normal path, or generated from Issue + Triage for trivial path), with instruction: "execute in order; after each file change report path and one-line summary".
6. For each codex report, log `[attempted]` then run independent verification (Read file, `git diff`), log `[applied]` or `[failed]`.
7. On codex completion AND all attempts applied: set `status = verify`. Release worktree lock. Release issue lock.
8. On any failure (codex reports blocker, Claude's diff doesn't match, or codex session dies mid-flight):
   - log `[failed]` row with reason
   - set `status = blocked`
   - run `git status --porcelain` and snapshot output to Execute log
   - via `confirm()` ask user **three choices** (D3):
     - (i) continue: send codex a follow-up to fix the blocker; status returns to `fixing`
     - (ii) stash + retry: `git stash push -u -m "il-loop NN partial"`; codex restarts from operation 1; record stash ref in Execute log
     - (iii) revert specific files: prompt for files; `git checkout -- <files>`; codex resumes
   - User can also choose: (iv) abandon → status = `abandoned`, release locks, leave dirty tree (with explicit confirm)
   - (v) escalate → status = `escalated`, release locks, advisory message (no auto-migration in v1)

### 5.4 `/il-verify <issue#>` — Claude, with three confirmation gates

**Locks**: issue-NN AND worktree.

Pre-conditions: `status == verify`.

Steps:
1. Acquire both locks.
2. **Refresh issue from GitHub** (D2): run `gh issue view <#>` again. Diff against frozen Issue section:
   - If unchanged: note "gh issue refresh: clean" in Verify section.
   - If changed: append diff to Verify section. `confirm()`: "issue body / comments changed during fix. Proceed with verify, or pause to re-evaluate?"
3. Run `git diff <start_commit>..HEAD` and list all touched files.
4. Run `test_command` from frontmatter; if `"none"` declared at triage, note skipped + reason.
5. Claude Reads each touched file and writes verify notes.
6. **Gate 1 (push)**: `confirm()`: "push current branch ({work_branch}) to origin?"
   - yes → `git push -u origin <work_branch>`; log to Outcome
   - no → status remains `verify`; release locks; user can re-invoke
7. **Gate 2 (PR)**: only if push succeeded AND branch != base_branch AND no PR open for this branch:
   - `confirm()`: "create PR against {base_branch}?"
   - yes → `gh pr create`; record PR # in Outcome
   - no → skip; user may create later
8. **Gate 3 (close issue)**:
   - `confirm()`: "close GitHub issue #<NN> as completed?"
   - yes → `gh issue close <#> --reason completed`; log to Outcome
   - no → skip
9. If all three gates result in some progress: set `status = done`. Session disposition:
   - trivial path: close session (`continuo terminal_kill`)
   - normal path: keep session (user may manually close)
10. Release locks.

## 6. Recovery rules

| Failure | Detection | Recovery |
|---|---|---|
| Stale lock from dead PID | `pid_alive` returns false | Auto-takeover, log to Execute log |
| Stale lock from hung PID (age > 1h) | acquisition algorithm | Ask user to force-remove |
| Crash mid-`/il-fix` | next command sees `status=fixing` but no held lock | Markdown says fixing, git may be partial. Replay D3 three-choice prompt before resuming. |
| Codex session dies | session_id no longer in `terminal_list_sessions` | Mark in Execute log; new session may be created at next stage; conversational context is lost but markdown state is sufficient |
| Codex session hangs | no output for 5 min during `/il-fix` (heuristic) | `confirm()` user: continue waiting, kill session and create new, or abandon |
| GitHub issue edited mid-flow | detected at `/il-verify` D2 refresh | User confirms whether changes affect verification; not auto-handled mid-fix |
| `gh` returns auth/network error | any stage | Abort with explicit "gh prerequisite not met"; no degraded path in v1 |
| `git` worktree diverges from `start_commit` unexpectedly | `/il-fix` pre-check | Ask user (proceed / abort) |
| Markdown disagrees with git | any time | git wins; correct frontmatter and log correction |

## 7. Audit trail

For any decision to be reconstructable post-hoc, the file preserves:

- `## Issue` — frozen at triage (Q: what was asked)
- `## Triage decision` — including decision tree branch ID (Q: why this path)
- `## Brief (pre-integration)` — original draft before red-team (Q: what Claude proposed)
- `## Red-team (codex)` — items + transcript ref (Q: what codex objected to)
- `## Brief changelog` — per-item accept/reject/defer with reasons (Q: how Claude resolved feedback)
- `## Execute log` — tagged rows: `[intended]`, `[attempted]`, `[applied]`, `[failed]` (Q: what actually happened)
- `## Verify` — diff list + test result + gh refresh status (Q: what was checked before push)
- `## Outcome` — push/PR/close timestamps + actor (user-confirmed) (Q: what shipped)

Markdown is append-only after each stage's first write. Updates to frontmatter and the **current Brief** are the only allowed in-place edits; **Brief (pre-integration)** and prior `## Brief changelog` rows are immutable.

## 8. Out of scope for v1

- Batch / parallel issue processing.
- Auto-migration from `escalated` into a dev-loop topic.
- Auto-merge of PRs.
- Cross-issue dependency tracking.
- Reuse of codex sessions across issues.
- Auto-comment on the GitHub issue describing progress.
- Degraded paths for `gh` / `continuo` / `git` unavailability — all are prerequisites.
- Multi-machine / NFS-based concurrency.
- Auto-rerun on flaky tests.

## 9. Prerequisites

- `git` available, current directory inside a repo, clean (or user accepts dirty-tree warning at triage).
- `gh` installed and authenticated to the repo's GitHub remote.
- `continuo` MCP server reachable from Claude Code.
- `codex` CLI installed; user's `~/.codex/config.toml` has appropriate sandbox settings for the project.
- Interactive TTY for all confirmation prompts.

## 10. Acceptance criteria (behavioral)

- All four commands can complete a happy-path trivial issue (triage → fix → verify → done) without invoking `/il-brief`.
- A normal issue's audit trail can fully reconstruct red-team item disposition.
- Two concurrent `/il-fix` calls on different issues are rejected by worktree lock with a clear message.
- A killed Claude session, restarted later, recovers cleanly: stale locks released, status correctly reflected.
- D3 partial-fail prompt is reachable and all five choices (continue / stash / revert / abandon / escalate) are exercisable.
- Push, PR-create, and issue-close are three independent confirmations; declining any one does not block the others.
- Live GitHub issue edits during fix are surfaced at verify and require explicit user reconciliation.
- Non-interactive shells (no TTY) abort at the first `confirm()` call.

## 11. Skill packaging (separate concern)

The four commands are implemented as Claude Code skills under `~/.claude/skills/` or project-local `.claude/skills/`. Frontmatter limited to `name` + `description` only (other fields break registration per local environment).

Skill names: `il-triage`, `il-brief`, `il-fix`, `il-verify`. Lock helpers, confirm helper, and gh/git wrappers live in a shared `tools/il-loop/` directory of pure-Python or shell scripts, invoked from skills.

## 12. Open questions remaining for v2 ratification

1. Should `[applied]` execute-log rows include a diff hash so a later audit can detect file tampering?
2. Should the `## Brief (pre-integration)` be re-snapshotted on every Brief changelog bump, or only the first?
3. For the trivial path, is the operations list generated by Claude (Triage section) or by codex on first prompt?
4. Stash naming convention for D3 (ii): `il-loop-<NN>-<timestamp>` proposed, but stash references can be lost — should we use a per-issue branch instead?
5. When `confirm()` aborts on no-TTY, should the lock be released or preserved for a later interactive run?
