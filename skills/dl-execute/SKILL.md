---
name: dl-execute
description: Stage 5/6 of the dev-loop workflow. Use only when the user explicitly asks to execute a tracked plan via phrases like "/dl-execute", "dev-loop:execute", "执行 plan", or "进入 execute 阶段". Runs the Operations from plan.md in order, appends to execute-log.md, records actually-touched files. Has the highest side-effect risk in the dev-loop (writes project files, may run commands, may affect git working tree). NEVER invoke automatically — must be explicit user request.
---

# /dl-execute — Dev-Loop Execute (Stage 5/6)

## Do NOT run this skill when

- Topic status is not `ready-for-execute` (must come through /dl-integrate first).
- No `plan.md` exists in the topic directory.
- The user is asking for a generic "run my code" or "do this task" request unrelated to a tracked dev-loop topic.
- The user says "execute" or "run" in ordinary language without a topic id.
- Another dev-loop stage is already active and this stage was not requested.

If matched, decline.

## Purpose

Stage 5 of 6. Run the Operations from `plan.md` (which points to the latest plan-vN.md after integrate). Log every step to `execute-log.md` (append-only). Record actual touched files. Stop on deep failure; recover from shallow failure (within retry limits).

This is the **highest side-effect** stage: writes project files, runs commands, may affect git working tree. Operate carefully.

## Shared assets

- `~/.claude/skills/dev-loop-shared/project-detect.sh`
- `~/.claude/skills/dev-loop-shared/topic-metadata-template.yaml`

## Behavior

### Phase A — Locate topic and validate

1. Resolve topic; verify `(project_root, topic_id)` against cwd (议题 F.4).
2. Verify topic `status: ready-for-execute`.
3. Verify `<topic_dir>/plan.md` exists (议题 D.5: if `plan.md` does not match the latest `plan-vN.md`, abort — fix state pointer first).
4. Verify `execute_retry < 2` (议题 D.3). If at limit, abort: "execute has failed 2x; go back to /dl-plan, don't continue patching."
5. Read plan.md Operations + affects_files.declared + Safeguards (from req.md).

### Phase B — Re-detect project + workspace sanity (议题 D.5)

1. Run `bash ~/.claude/skills/dev-loop-shared/project-detect.sh`. Compare with topic.project_root → mismatch aborts.
2. `git status --porcelain` (议题 D.5 "用户手动改了工作区文件"):
   - If unrelated to topic's `affects_files.declared`: warn user, ask whether to stash / commit / proceed with overlap.
   - If overlaps with `affects_files.declared`: abort — user must commit/stash first, OR rerun /dl-plan if the existing changes change scope.
3. Re-read Safeguards from req.md. Re-extract from CLAUDE.md/AGENTS.md. Build a runtime safety check list.

### Phase C — Cross-topic conflict check (议题 F.2 mandatory scan #4)

#### C.0 Net-cutover preflight for deprecated topic.status values

Scan all topics under `<plans_dir>/`, excluding `topic_id == <current topic_id>`. If any non-terminal topic (`status ∉ {done, aborted}`) still uses a deprecated topic.status value (`red-teamed`, `integrated`, `executing`, `verifying`, `pending-plan-revision`), **abort** and require migration or manual adjudication before execute.

# See `deprecated_values` in `~/.claude/dev-loop-shared/canonical-state-machine-v1.yaml`.

#### C.1 Active conflict scan

Scan all topics under `<plans_dir>/` where `status ∈ active_conflict_states {planning, pending-red-team, ready-for-integrate, ready-for-execute, executed}`, excluding `topic_id == <current topic_id>`. Compare each topic's `affects_files.declared ∪ inferred` with this topic's `affects_files.declared ∪ inferred`.

# See `active_conflict_states` in `~/.claude/dev-loop-shared/canonical-state-machine-v1.yaml`.

If another topic overlaps, **abort**: race condition; rerun /dl-integrate or resolve the conflicting topic first. Set `status: blocked`, `conflicts_with: [...]`.

Micro topics skip /dl-red-team and /dl-integrate, so this Phase C scan is their mandatory F.2 timing #4 backstop for the skipped integrate-time scan.

### Phase D — Session strategy for execute (议题 C.3)

**Lookup order (prefer reuse, never blindly create new)** — same pattern as /dl-red-team Phase B:

1. Check topic metadata `codex_sessions[]` for stage `execute`. Alive → reuse.
2. Check topic metadata for stage `red-team` session. Alive → **reuse if** `code` project + `standard`/`micro` complexity. For `major` or `wiki`/`mixed`, prefer step 3.
3. Call `terminal_list_sessions`. **Reuse only if ALL 4 hard rules pass** (2026-05-27 patch — Claude+codex design discussion, same as dl-red-team Phase B):
   - `session.origin === 'agent'` (security boundary; never touch origin='user')
   - `String(session.agent_label).toLowerCase() === 'codex'` (snake_case returned field, exact match — note API asymmetry vs `agentLabel` camelCase input parameter)
   - `session.exit_code === null` (liveness)
   - `session.cwd === <topic.project_root>` (cross-project isolation)

   Multiple matches → pick latest `created_at`. **Output banner grep FORBIDDEN** — Claude's own conversation contains "codex" / "gpt-5-codex" and would self-pollute the T1 (Claude-owned) terminal output, causing Claude to send_text to its own PTY.
   Legacy Continuo without these fields → create new (step 4), no fallback grep.
4. None reusable → only now `terminal_create_session(agentLabel="codex", autorun="codex")`.

Always send the **mode-switch preamble** on reuse (议题 C.3 contract):

> "你现在是 executor 不是 reviewer。topic={{TOPIC_ID}}, 按 integrated plan-v{{N}}.md 执行，**不要回头修 plan**。红队原文仅供参考，最终以 integrate plan 为准。"

Record session into topic.codex_sessions with `stage: execute`. For reused sessions, set `reused_from_existing: true` (议题 F.5 revision)

### Phase E — Initialize execute-log.md (append-only)

Path: `<topic_dir>/execute-log.md`. If not exists, create with header:

```markdown
---
type: execute-log
topic_id: <id>
plan_pointer: plan.md (currently plan-v<N>.md)
session_id: <codex session id>
started_at: <now>
executor: codex
---

# Execute Log

```

All subsequent writes are **append-only** (议题 D.2 — failed runs are audit trail; never overwrite).

### Phase F — Drive codex through Operations (codex is executor, Claude is orchestrator)

**Critical division of labor**:
- **codex executes** project file changes / shell commands (using its own tools inside the terminal)
- **Claude orchestrates**: sends Op-by-Op instructions, polls sentinels, verifies side effects, writes execute-log.md
- **Claude never** directly uses Write/Edit/Bash on project files in this phase
- **Claude only uses** Write/Edit on dev-loop state files (execute-log.md, topic metadata) and Read/Bash for verification (`git status`, `git diff`, reading files codex modified)

For each `Op1, Op2, ...` from plan.md:

#### F.1 Pre-op check (Claude)

- Op references specific files / commands. Verify they ⊆ `affects_files.declared ∪ inferred`. If Op touches a file NOT in either list → **stop and ask user**. Don't expand scope silently.
- For wiki project: re-confirm `raw/` is not in Op's scope (Safeguard).

#### F.2 Send Op instruction to codex (Claude → codex)

Use `terminal_send_text` + `terminal_press_key("enter")` to send a precise instruction:

```
Op<N>: <exact action from plan.md>

约束:
- 只动这些文件: <affects_files for this Op>
- 不得动: raw/ <plus any other Safeguard files>
- 完成后用工具验证（cat 文件 / git diff / ls）
- 成功后另起一行打印: ###OP<N>-DONE###
- 失败立即停止并打印: ###OP<N>-FAIL: <one-line reason>###
```

If this is the first Op of the run, **prepend the mode-switch preamble** (议题 C.3):

> "你现在是 executor 不是 reviewer。topic={{TOPIC_ID}}, 按 integrated plan-v{{N}}.md 执行，不要回头修 plan。红队原文仅供参考，最终以 integrate plan 为准。"

#### F.3 Wait for sentinel (Claude polls)

`ScheduleWakeup` with delay tuned to Op type:

| Op type | Wakeup delay | Max retries |
|---|---|---|
| File create / edit (small) | 60s | 3 (~3min cap) |
| Multi-file refactor | 180s | 3 (~9min cap) |
| Test/lint/typecheck run | 120s | 3 (~6min cap) |
| Build / install | 270s | 3 (~13.5min cap) |

On each wake: `terminal_read_output` with `since_seq` from last read. Search for `###OP<N>-DONE###` or `###OP<N>-FAIL:<reason>###` on a line by itself.

If max retries exceeded without sentinel: treat as timeout failure (议题 D.5). Mark `op<N> status: incomplete`. Ask user whether to inspect terminal or abort.

#### F.4 Parse codex output and verify (Claude)

On `###OP<N>-DONE###`:

1. Extract codex's chat output from prompt-send to sentinel
2. **Verify side effects directly**:
   - For file create/edit: `Read` the file, confirm it matches expectation
   - For file delete: `Bash ls` confirm file is gone
   - For commands: `Bash git status --porcelain` confirm expected changes
3. **Safeguard re-check**: `Bash git diff --stat raw/` must show nothing (wiki). Read req.md Safeguards list — re-check each. If any violated, **treat as F.7 Safeguard violation** even though codex claimed success.

#### F.5 Append to execute-log.md (Claude is the only writer)

```markdown
## Op<N>: <one-line description>
- **time**: <ISO timestamp>
- **sent_to_codex**: <truncated instruction>
- **codex_output**: <truncated codex chat output>
- **sentinel**: ###OP<N>-DONE### | ###OP<N>-FAIL: ...### | timeout
- **claude_verification**: <what Claude checked + result>
- **safeguard_recheck**: pass | fail-<safeguard-id>
- **result**: success | failure
- **next**: continue | retry | escalate
```

#### F.6 Record actually-touched files (议题 F.2 scan #5 prep)

After verification, add actually-modified files (from `git diff --name-only` since Op start) to `affects_files.executed`.

If overshoot (touched file ∉ declared ∪ inferred) → stop, ask user to update plan or roll back. **Do not silently expand scope.**

#### F.7 On failure (议题 D.1 classification)

| Failure type | Behavior |
|---|---|
| **codex reported ###OP<N>-FAIL:...###** + shallow (lint, formatting, simple wiki check) | Resend Op with the failure reason appended: "上次 Op<N> 失败原因 X，请重试解决"; max 2 attempts (议题 D.3); log each |
| **codex reported FAIL** + deep (plan-level wrong, scope expansion needed) | **Stop**. `status: blocked`, `execute_retry += 1`. Suggest /dl-plan. |
| **Claude verification failed** (codex said done but verification disagrees) | Treat as deep failure. **Stop**. Likely codex hallucinated. Log discrepancy carefully. |
| **Safeguard violation** (议题 D.1 触碰 Safeguards) detected in F.4 re-check | **Stop immediately**. `status: blocked`. Show user what file was touched. Ask whether to roll back via `git checkout` or `git restore`. Suggest /dl-req to re-confirm boundaries. |
| **Sentinel timeout** (no ###OP<N>-DONE/FAIL### within retry cap) | Mark `op<N> status: incomplete`. Read terminal output for partial progress. Ask user. |

Do NOT auto-retry deep failures or safeguard violations; the议题 D.3 retry limit applies.

### Phase G — Record actually-touched files (议题 F.2 scan #5 prep)

After each Op, add the actually-modified file to `affects_files.executed` in topic metadata. By end of execute, this should be the ground truth.

If `executed ⊃ declared ∪ inferred` (touched files not declared) → **stop** at the moment of overshoot, ask user to either:

- Update plan retroactively (back to /dl-plan), or
- Roll back the unexpected change

Do not silently include extra files.

### Phase H — Wiki project special handling (议题 B.5 writeback_policy)

If `project_type ∈ {wiki, mixed}`:

- **execute may write** to `.claude/dev-loop/<topic_dir>/` freely (internal state).
- **execute may write** to project files declared in `affects_files.declared`.
- **execute should NOT** silently write to `wiki/synthesis/` or other "promotion" locations unless an Op explicitly does so AND the user confirms. Those are typically /dl-integrate or /dl-verify "promotion" writes (议题 B.1).
- For `mixed`, read `topic.writeback_policy` from metadata and respect it.

### Phase I — Final state and handoff

After last Op:

1. Topic status:
   - All Ops succeeded → `executed` (议题 D.2 next state machine value)
   - Any deep failure (and retry exhausted) → `blocked`
   - User aborted → `aborted` + `last_stage: execute`
2. `affects_files.executed`: final list
3. `executed_at`: now

Report:

- Ops succeeded / failed counts
- `affects_files.executed` summary (count + paths)
- Any out-of-scope touches (should be zero — if non-zero, user already saw the warning)
- Next step: `/dl-verify` — **do not auto-invoke**

Stop.

## Guardrails

- **Codex executes, Claude orchestrates.** Claude does NOT use Write / Edit / Bash on project files during Phase F — only via codex. Claude's Write/Edit are reserved for dev-loop state files (execute-log.md, topic metadata). Claude's Bash is reserved for verification reads (`git status`, `git diff`, `ls`).
- **Do not auto-invoke** /dl-verify.
- **Do not expand scope** — every touched file must be in `affects_files.declared ∪ inferred`. Out-of-scope touch → stop and ask.
- **Do not** modify `raw/` (wiki Safeguard). Even if codex says it didn't touch raw/, Claude must `git diff --stat raw/` re-check.
- **Do not** silently fix Operations differently from plan. If codex's `###OP<N>-FAIL###` indicates plan-level issue, escalate to /dl-plan (议题 D.1 deep fail).
- **Do not** continue after a Safeguard violation. Stop immediately, report file(s) touched.
- **Do not** overwrite `execute-log.md`. Append only (议题 D.2).
- **Do not** auto-retry deep failures. Shallow failures: max 2 attempts (议题 D.3).
- **Do not** trust codex's "done" without Claude-side verification (议题 C.2 — codex 是审计器视角的对侧，Claude 在 execute 阶段反过来审计 codex 的实际产出).
- **Do not** continue if `git status` shows pre-existing working tree changes that overlap with `affects_files.declared` (议题 D.5).
- **Do not** trust that the codex session from red-team is still mentally in "review mode" — always send the mode-switch preamble before first Op (议题 C.3).
- **Do not** write to wiki promotion locations (`wiki/synthesis/`, `wiki/concepts/`, etc.) unless explicitly part of an Op AND project_type supports it.
- **Never call `terminal_send_text` / `terminal_press_key` / `terminal_kill` on any session where `origin !== 'agent'`** (2026-05-27 patch). origin='user' terminals may host Claude itself / user shell / editor / ssh / production commands — agents must not touch them.
- **Do not use output banner grep to identify session ownership** (2026-05-27 patch). Identity comes from continuo metadata (`origin` + `agent_label`), not from terminal stdout content.

## Failure modes (议题 D)

- Working tree has unrelated changes → ask user to stash/commit/proceed.
- Working tree overlaps `affects_files.declared` → abort, fix or rerun /dl-plan.
- Shallow Op failure → self-fix max 2 times → if still failing, escalate as deep.
- Deep Op failure → stop, `status: blocked`, `execute_retry += 1`, suggest /dl-plan.
- Safeguard violation → stop, `status: blocked`, suggest /dl-req re-confirm boundaries.
- New cross-topic conflict (议题 F.2 scan #4) → abort, `status: blocked`, rerun /dl-integrate.
- cwd mismatch (议题 F.4) → abort.
- plan.md not matching latest plan-vN.md (议题 D.5) → abort, fix state pointer first.
- User aborts mid-execute → `status: aborted`, `last_stage: execute`, append abort summary to execute-log.md, **report what files were already changed** (议题 D.4).
- `execute_retry` reaches 2 → escalate, do not silently try a third time.
