---
name: dl-red-team
description: Stage 3/6 of the dev-loop workflow. Use only when the user explicitly asks to red-team a plan via phrases like "/dl-red-team", "dev-loop:red-team", "红队 plan", or "进入 red-team 阶段". Drives an independent codex agent through the continuo MCP terminal to critique the current plan-vN.md, produces red-team-vN.md, updates topic metadata. Has external side effects (writes to a codex terminal, schedules wakeups). Do NOT invoke automatically; only on explicit user request.
---

# /dl-red-team — Dev-Loop Red-Team (Stage 3/6)

## Do NOT run this skill when

- The user asks for self-review or generic code review (use a different skill).
- No plan-vN.md exists yet (run /dl-plan first).
- Topic `complexity: micro` (skip red-team per 议题 G — go straight to /dl-integrate or /dl-execute).
- The user says "review" or "critique" in ordinary language without naming a topic.
- Another dev-loop stage is already active and this stage was not requested.

If matched, decline and offer the direct path.

## Purpose

Stage 3 of 6. Drive an independent agent (codex via continuo MCP terminal) to critique `plan-vN.md`. Produce `red-team-vN.md` with `Verdict: BLOCK | REVISE | PASS` + P0/P1/P2 + Integration Notes. **Independence is the value** — Claude wrote the plan, codex critiques; we must not let codex see Claude's prior analysis or other dev-loop drafts.

## Shared assets

- `~/.claude/dev-loop-shared/project-detect.sh`
- `~/.claude/dev-loop-shared/codex-red-team-prompt-template.md`
- `~/.claude/dev-loop-shared/wiki-red-team-checklist.md`
- `~/.claude/dev-loop-shared/reasons-takeaways.md`

## Required MCP / tools

- continuo: `terminal_create_session`, `terminal_send_text`, `terminal_press_key`, `terminal_read_output`, `terminal_list_sessions`
- ScheduleWakeup (for async waiting on codex sentinel)
- Bash (project detect + state IO)
- Read / Edit / Write (state files)

If continuo MCP is unavailable, fall back to degraded path: Claude self-reviews and marks `manual_override: true` in red-team-vN.md (议题 D.5). Warn user that independence guarantee is lost.

## Behavior

### Phase A — Locate topic and validate prerequisites

1. Resolve topic (user-specified, or single `status: pending-red-team` topic in plans_dir; if multiple, ask).
2. Verify `(project_root, topic_id)` matches current cwd (议题 F.4); else abort.
3. Read latest `plan-vN.md`. N = `red_team_round + 1` (议题 D.3 — paired versioning).
4. Verify `complexity ∈ {standard, major}`. For `micro`, abort with: "micro tier skips red-team per 议题 G; advance to /dl-integrate directly."
5. Verify `red_team_round < 3` (议题 D.3). If at limit, abort: "plan↔red-team limit reached; rewrite req or manual override."

### Phase B — Session strategy (议题 A.1 + C.3 patch)

Read `topic.codex_sessions` from metadata. Decision:

**Lookup order (prefer reuse, never blindly create new)**:

1. **Topic-bound session (best match)** — look in topic metadata `codex_sessions[]` for an entry with `stage: red-team` and `status: active`. Verify it's alive via `terminal_list_sessions`. If alive → **reuse**.
2. **Any existing codex terminal (host-wide)** — call `terminal_list_sessions`. For each session, **ALL 4 hard rules must pass** (no output-grep heuristic — 2026-05-27 patch after Claude+codex design discussion):
   - `session.origin === 'agent'` — **security boundary**, never reuse origin='user' (it may carry Claude itself / user shell / editor / ssh / production commands)
   - `String(session.agent_label).toLowerCase() === 'codex'` — exact match on the snake_case returned field. **API asymmetry**: `terminal_create_session` input parameter is `agentLabel` (camelCase) but `terminal_list_sessions` returns `agent_label` (snake_case); always read from the returned field name
   - `session.exit_code === null` — liveness check
   - `session.cwd === <topic.project_root>` — cross-project isolation (避免复用到别项目里的 codex)

   **Output banner grep is FORBIDDEN** — Claude's own conversation prints "codex" / "gpt-5-codex" frequently when discussing this work; reading T1's stdout (the terminal hosting Claude itself) will match the grep and lead Claude to misidentify its own PTY as a codex session, then `send_text` to itself.

   Multiple matches → pick latest `created_at`. Record session_id into topic metadata so future lookups hit step 1.
   Zero matches → fall through to step 3/4.

   **Legacy Continuo compatibility**: if `terminal_list_sessions` returns sessions without `origin` or `agent_label` fields (older Continuo version), default to creating a new session (step 4). Never fallback to output grep.
3. **Topic-bound session marked `stale`/`closed`** — mark prior entry as inactive; fall through to step 4.
4. **No reusable session anywhere** → only now create new via `terminal_create_session` with `agentLabel: "codex"` and `autorun: "codex"`. Wait for codex banner before sending prompt.

On reuse, **always send the mode-switch preamble first** (议题 C.3): "你现在仍在 dev-loop red-team 模式，topic={{TOPIC_ID}}, plan-v{{N}}. 之前的对话仅作上下文参考。"

Record/update topic metadata after either reuse or create:

```yaml
codex_sessions:
  - stage: red-team
    session_id: <returned id>
    created_at: <now>           # only set on create; preserve on reuse
    reused_from_existing: true  # only if step 2 hit
    status: active
```

**Note** (议题 F.5 revision): the original "every topic gets its own codex session" rule is relaxed in favor of "prefer reuse". Cross-topic contamination is mitigated by (a) the mode-switch preamble explicitly stating the new topic_id, and (b) the iron-rule prompt isolating codex from prior dev-loop files. If contamination concern is high (e.g. `major` complexity AND prior session was for a sensitive topic), the skill may still prompt the user "force-new session?"

### Phase C — Build red-team prompt

Load `~/.claude/dev-loop-shared/codex-red-team-prompt-template.md`. Fill placeholders:

- `{{PROJECT_ROOT}}`: from project-detect
- `{{PROJECT_TYPE}}`: code / wiki / mixed
- `{{COMPLEXITY}}`: standard / major
- `{{TOPIC_ID}}`: from metadata
- `{{N}}`: plan version
- `{{PLAN_CONTENT}}`: read `<topic_dir>/plan-vN.md` body (NOT frontmatter — keep prompt focused)
- `{{PROJECT_RULES_DIGEST}}`: re-extract from CLAUDE.md / AGENTS.md (digest rules in shared template)
- `{{WIKI_CHECKLIST_BLOCK}}`: inject only if `project_type ∈ {wiki, mixed}`; load 14 items from `wiki-red-team-checklist.md`
- For `major` tier: append "逐维审查" instruction (force codex to comment on each of 7 REASONS dimensions)

Intent Lock check: plan-vN.md should already include the Intent Lock excerpt; do not send req.md. Instruct codex to compare that excerpt against Approach / Operations / Test matrix using `~/.claude/dev-loop-shared/intent-lock-template.md` as format authority (do not inline it).

Required findings:
- every Acceptance sample must map to a Test matrix row / real_test scenario / wiki-check with command/check/evidence;
- Operations touching an anti-example are P0;
- violated Kill criteria are P0;
- `autonomy_readiness: high` with manual-only samples is P1 (P0 if it affects scope/safety);
- inferred `[unverified]` Intent Lock is a P1 risk on major override paths.

**Critical**: prompt must contain the iron rules verbatim:

1. 不读取/修改任何 dev-loop 草稿/设计文件
2. 不写任何文件
3. 只在 chat 中输出
4. 结束时另起一行打印 `###CODEX-DONE###`

### Phase D — Send prompt and wait for sentinel

1. `terminal_send_text(session_id, prompt)`
2. `terminal_press_key(session_id, "enter")`
3. Brief `terminal_read_output` after ~5s to confirm codex started (look for "Working" indicator).
4. `ScheduleWakeup` 270s with prompt to re-read terminal (议题 A.4).

On wake:
- `terminal_read_output` with `since_seq` from last read
- Search for line containing `###CODEX-DONE###` (sentinel — must be alone on a line per 议题 A.2)
- Found → Phase E
- Not found → `ScheduleWakeup` 270s again (max 3 iterations ≈ 13.5min)

After 3 timeouts (议题 D.3 + D.5):

| Round | Action |
|---|---|
| Timeout round 1 | Resend prompt once (议题 D.5 — "allow 1 retry") |
| Timeout round 2 (after retry) | Mark `red-team status: incomplete` + degraded path |

Degraded path: Claude does self-review (clearly mark `manual_override: true` in red-team-vN.md), warn user that independence guarantee is lost.

### Phase E — Extract codex output

Read terminal output from the seq right after the prompt was sent. Filter:

- Strip ANSI escapes (already done by `strip_ansi: true` default)
- Skip echoed prompt
- Find block from first `## Codex Red-Team` (or `### Verdict` if no header) up to `###CODEX-DONE###`
- Clean codex's "Explored" / "Worked for Xs" status lines

If sentinel found but block empty or malformed (no Verdict line): treat as `verification-inconclusive`, ask user to inspect terminal.

### Phase F — Write red-team-vN.md

Path: `<topic_dir>/red-team-vN.md` (N matches plan-vN).

Frontmatter:

```yaml
---
type: red-team
version: N
parent_plan: plan-vN.md
status: complete | incomplete | manual_override
verdict: BLOCK | REVISE | PASS | UNKNOWN
codex_session_id: <id>
created_at: <now>
duration_sec: <time from send to sentinel>
---
```

Body: cleaned codex output. Preserve all P0/P1/P2/NEED-INFO/Integration Notes sections verbatim — Claude is custodian, not editor (议题 C.2: codex's role is "执行前审计器"; integrate is where editing happens).

### Phase G — Update topic metadata

In req.md (or topic metadata file):

# topic.status 转移见 ~/.claude/dev-loop-shared/canonical-state-machine-v1.yaml

- `updated_at`: now
- `status` transition:
  - Verdict `PASS` → `ready-for-integrate`
  - Verdict `REVISE` → `ready-for-integrate` (P1/P2 to merge)
  - Verdict `BLOCK` → `planning` (write `replan_reason: red-team-block` + `blocked_plan: plan-vN.md`; no `pending-plan-revision`, per SSOT / 议题 K)
  - Verdict `UNKNOWN` (degraded path / inconclusive) → `red-team-incomplete`
- `red_team_round`: N（= 本轮号，已完成 red-team 轮数；见 SSOT）
- `codex_sessions[<this one>].status`: `active` (keep open for potential round 2)
- `affects_files.inferred`: extract from red-team P0/P1 hints + NEED-INFO items mentioning specific file paths (议题 F.2 second scan: red-team补 inferred)
- `conflicts_with`: scan other active topics' `affects_files.declared` ∩ this topic's `affects_files.declared ∪ inferred` (议题 F.2)

### Phase H — Wiki post-check (project_type ∈ {wiki, mixed})

Verify that codex addressed all 14 wiki checklist items (from `wiki-red-team-checklist.md`). If any of C1-C14 is not visibly addressed in codex's response, add a Claude-side note in red-team-vN.md:

```
> **Coverage gap**: codex did not explicitly address C5 (page type). Manual check recommended at /dl-integrate.
```

This is meta-commentary, not a re-write of codex's output.

### Phase I — Handoff

Report:

1. Verdict: BLOCK / REVISE / PASS / UNKNOWN
2. P0 count, P1 count, P2 count
3. NEED-INFO items (if any) — user may need to provide info
4. Wiki coverage gaps (if any)
5. conflicts_with new entries (if any)
6. Next step suggestion:
   - PASS / REVISE → `/dl-integrate`
   - BLOCK → `/dl-plan` (for plan-v(N+1))
   - UNKNOWN → manual inspection + user decision
7. **Do not auto-invoke** next stage.

Stop.

## Guardrails

- **Do not auto-invoke** /dl-integrate or /dl-plan.
- **Do not feed Claude's analysis to codex** — codex must only see plan-vN.md body + project rules digest + iron rules. No req.md, no dev-loop-design.md, no prior red-team-v(N-1).md.
- **Do not read req.md** for Intent Lock review; only audit the plan's verbatim/inferred excerpt against Approach, Operations, Test matrix, and autonomy_readiness.
- **Do not inline the full Intent Lock template; reference `~/.claude/dev-loop-shared/intent-lock-template.md` if needed.**
- **Do not edit codex's output** — copy verbatim into red-team-vN.md. Editing belongs to /dl-integrate.
- **Do not block on missing sentinel** indefinitely — 13.5min cap then degraded path.
- **Do not reuse a codex session across topics** (议题 F.5 invariant).
- **Never call `terminal_send_text` / `terminal_press_key` / `terminal_kill` on any session where `origin !== 'agent'`** (2026-05-27 patch). origin='user' terminals may host Claude itself / user shell / editor / ssh / production commands — agents must not touch them. Exception only via explicit user attach mode (out of scope for this skill).
- **Do not use output banner grep to identify session ownership** (2026-05-27 patch). Identity comes from continuo metadata (`origin` + `agent_label`), not from terminal stdout content. Output content is debug-only, never a control-plane signal.
- **Do not read terminal by "most recent active"** — always read by stored `session_id` (议题 F.5).
- For `micro` complexity, **abort immediately** (red-team is skipped). Do not lower the bar.
- If continuo MCP unavailable, do not silently fall back — explicitly warn user and ask whether to proceed in degraded mode.

## Failure modes (议题 D)

- continuo MCP unavailable → ask user; if yes, degraded self-review + `manual_override: true`.
- codex session creation fails → abort with clear error; user can manually start `codex` then retry.
- Sentinel never appears (3 wakeups + 1 retry) → degraded path with warning.
- Codex outputs sentinel but no parseable Verdict → status `red-team-incomplete`, ask user.
- cwd mismatch with topic.project_root → abort (议题 F.4).
- User aborts mid-wait → write partial red-team-vN.md with `status: aborted`, keep session alive (user may resume).
- red_team_round at 3 limit → abort with escalation message.

## Notes on independence (议题 A.0 / C.2)

The independence value of red-team comes from codex not seeing Claude's reasoning. This skill enforces that by:

1. **Sending only plan body** to codex, never Claude's prior analysis.
2. **Iron rule in prompt**: codex must not read dev-loop draft files.
3. **Codex output is copy-pasted** to red-team-vN.md, not summarized/edited.
4. **Different session per topic** (议题 F.5) — no cross-topic contamination.

If any of these conditions cannot be met, the resulting red-team-vN.md must carry `manual_override: true` and a coverage warning.
