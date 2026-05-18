---
title: il-loop Design v1 (Issue-Loop, simplified dev-loop for GitHub issues)
type: design-draft
status: draft
created: 2026-05-12
updated: 2026-05-12
---

# il-loop Design v1

## Purpose

A lightweight workflow for processing GitHub issues, derived from dev-loop but simplified. Target use case: a project with ~tens of mixed-complexity issues to work through. Preserves Claude + codex two-agent collaboration; drops dev-loop's directory-per-topic, multi-version file state, and mandatory full 6-stage flow.

## Constraints

- GitHub-native: issue body is the source of requirement; clarifications via gh issue comment.
- Mixed complexity: trivial (≤10 LoC, no business logic) coexists with normal (half-day to one-day) issues.
- Heavy issues (>100 LoC, multi-module, architectural) are out of scope; il-loop suggests escalation to full dev-loop.
- File state per issue must be a single markdown file (not a directory).
- All project-file changes are executed by codex (Claude does not Edit/Write project files).
- Push and issue-close require explicit user confirmation per issue.

## Commands

Four slash commands. Each maps to a single skill.

| Command | Driver | Phase | Trigger condition |
|---|---|---|---|
| `/il-triage <issue#>` | Claude | entry | every issue starts here |
| `/il-brief <issue#>` | Claude + codex (red-team inline) | design | only on `path: normal` |
| `/il-fix <issue#>` | codex executes; Claude monitors | execute | both `trivial` and `normal` |
| `/il-verify <issue#>` | Claude | verify | both paths; user confirmation required |

## File state

One markdown file per issue: `.claude/issues/<NN>-<slug>.md` where `NN` = GitHub issue number, `slug` = kebab-case short title (≤6 words).

Sections are appended over the issue's lifetime in the same file. Frontmatter is updated in place.

```
---
issue: 42
slug: fix-login-redirect
status: triage | brief | fixing | verify | done | abandoned
path: trivial | normal | escalated
session_id: term-xxxx              # codex session bound to this issue
created: YYYY-MM-DD
updated: YYYY-MM-DD
---

## Issue
<frozen copy of `gh issue view <#> --comments` output>

## Triage decision
- complexity: trivial | normal | heavy
- path: trivial | normal | escalated
- reason: <one-line justification>
- LoC estimate: <number or range>
- touches business logic: yes | no

## Brief                                  # skipped if path=trivial
- 背景 / Background
- 方案 / Approach
- 操作清单 / Operations (ordered, file-level)
- risk / Known risks
- changelog:
  - vN: integrated codex red-team feedback YYYY-MM-DD (P0 items applied, P1 noted)

## Red-team (codex, inline)               # skipped if path=trivial
- P0: <blockers>
- P1: <should-fix>
- P2: <nits>
- raw transcript ref: session_id + read range

## Execute log
- YYYY-MM-DD HH:MM  codex touched <file>: <one-line summary>
- ...

## Verify
- diff verified by Claude Read: yes/no
- tests run: <command> → pass/fail
- verify notes: ...

## Outcome
- PR: #NN (link)
- pushed: YYYY-MM-DD HH:MM
- issue closed: YYYY-MM-DD HH:MM (reason: completed | abandoned)
- session disposition: kept | closed
```

## Stage specifications

### `/il-triage <issue#>` — Claude only

Inputs: GitHub issue number, current git repo as project root.

Steps:
1. Run `gh issue view <#> --comments` and capture full text.
2. Choose slug: kebab-case, ≤6 words, derived from issue title. If conflict in `.claude/issues/`, append a short hash.
3. Create `.claude/issues/<NN>-<slug>.md` with frontmatter (status=`triage`, session_id empty) and the Issue section frozen from gh output.
4. Classify complexity:
   - **trivial**: estimated change ≤10 LoC AND does not touch business logic (typo, docs, config flag, single-point obvious bug).
   - **normal**: estimated half-day to one-day change; touches business logic OR spans 1–3 files; requires non-trivial design choices.
   - **heavy**: spans >3 files OR >100 LoC OR architectural decision required.
5. Write Triage decision section.
6. If trivial → status=`brief` skipped, next step is `/il-fix`.
   If normal → next step is `/il-brief`.
   If heavy → report to user and suggest manual escalation to full dev-loop; do not auto-create a dev-loop topic in v1.

Outputs: file created/updated, classification reported to user, next command suggested.

### `/il-brief <issue#>` — Claude writes Brief; codex red-teams inline

Pre-conditions: file exists with `path: normal`, status ∈ {`triage`, `brief`}.

Steps:
1. Claude writes the Brief section: 背景 / 方案 / 操作清单 / risk. Operations are file-scoped and ordered. Risk lists known unknowns and rollback notes.
2. Create a new codex terminal session via continuo MCP: agentLabel `il-<NN>`, cwd = project root. Record the new session_id in frontmatter.
3. Send to codex a **neutral red-team prompt** containing only: Issue text, Brief text, and instructions to return P0 / P1 / P2 findings. No Claude reasoning, no preferences, no rationale for design choices is included.
4. Wait for codex output. Read transcript and extract P0 / P1 / P2 items.
5. Claude decides per item: accept (modify Brief operations), reject (note reason), defer (move to P2 with rationale). All edits applied **in place** in the Brief section; a single changelog line is added at the bottom of Brief: `v<N>: integrated red-team feedback YYYY-MM-DD — accepted X / rejected Y / deferred Z`.
6. Red-team section is written with the raw item list (post-integration). status → `brief`.

Session disposition: session is kept alive for the same issue's `/il-fix`.

### `/il-fix <issue#>` — codex executes; Claude monitors

Pre-conditions:
- For trivial path: status=`triage`, codex session does not yet exist (created at fix start).
- For normal path: status=`brief`, session_id present in frontmatter.

Steps:
1. If session_id is empty (trivial path), create a new codex session (agentLabel `il-<NN>`, cwd = project root) and record session_id.
2. Send the operations list to codex with instruction: "Execute in order. After each file change, report the file path and a one-line diff summary."
3. Claude reads codex output incrementally (continuo `terminal_read_output` with cursor).
4. After codex reports completion, Claude independently verifies actual file changes by Read + `git diff` — does NOT trust codex's self-report.
5. Append each executed step to Execute log: timestamp, file, summary.
6. status → `fixing` during execution, then `verify` when codex reports done and Claude's diff check passes.

Failure handling: if codex reports a blocker, Claude appends to Execute log and asks user whether to (a) update Brief operations and retry, (b) abandon, (c) escalate to dev-loop.

### `/il-verify <issue#>` — Claude only; user confirmation gate

Pre-conditions: status=`verify`.

Steps:
1. Claude re-reads all touched files and runs `git diff` against the issue's branch base.
2. Runs project test command if one is discoverable (e.g., `npm test`, `pytest`, `cargo test`); records result.
3. Writes Verify section with diff check result, test result, and any notes.
4. Asks user: "Issue #<NN> ready to push and close. Confirm?"
5. On user confirmation:
   - `git push` (current branch).
   - Either `gh pr create` (if branch is not main and PR not yet open) OR `gh issue close <#> --reason completed` (if direct push is appropriate).
   - Writes Outcome section with PR number / close timestamp.
   - status → `done`.
   - Session disposition: trivial → close session; normal → keep session for a configurable window (default: until next `/il-triage` on a different issue).
6. On user rejection or "needs more work": status returns to `brief` (normal) or `triage` (trivial) for re-iteration. Verify section is preserved as an append, not overwritten.

## Codex session policy

- One codex session per issue. session_id is persisted in the issue file's frontmatter.
- Sessions are created at `/il-brief` (normal path) or `/il-fix` (trivial path).
- Sessions are NOT reused across issues. This is a deliberate override of any general "prefer reuse" rule in this workflow.
- Session disposition at `done`:
  - trivial: closed by default.
  - normal: kept until next triage or explicit cleanup; allows re-entry if verify fails.

## Out of scope for v1

- Batch mode (processing multiple issues in parallel).
- Automatic escalation from triage `heavy` into a dev-loop topic.
- Auto-merge of PRs.
- Cross-issue dependency tracking.
- Reuse of codex sessions across issues.
- Auto-comment on the GitHub issue describing progress.

## Open questions

1. When `/il-fix` for a trivial issue fails its diff check, should it auto-promote to normal path and require `/il-brief`, or just halt?
2. Should the Issue section be refreshed from `gh issue view` at the start of `/il-verify`, in case the issue body was edited mid-flow?
3. Where do failed / abandoned issue files live? Same directory with `status: abandoned`, or moved to `.claude/issues/archive/`?
4. Should `/il-triage` ever auto-skip itself for an already-tracked issue, or always re-run and bump `updated`?
5. What happens if the user runs `/il-fix` on `path: normal` without going through `/il-brief` first — hard error, or silently fall back to trivial flow?

## Acceptance criteria for v1 ship

- All four commands implemented as Claude Code skills with frontmatter `name` + `description` only (per project memory: other frontmatter fields break skill registration).
- Single-file state model holds across all four stages; no directory per issue.
- Codex session lifecycle observable via continuo `terminal_list_sessions` (session_id stored in frontmatter).
- Push and close-issue require explicit interactive user confirmation; no flag bypasses this in v1.
- Trivial path can complete `triage → fix → verify` without ever invoking `/il-brief`.
