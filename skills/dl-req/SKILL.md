---
name: dl-req
description: Stage 1/6 of the dev-loop workflow. Use only when the user explicitly asks to start the dev-loop requirements stage via phrases like "/dl-req", "dev-loop:req", "开始 dev-loop 需求确认", or "进入 req 阶段". Creates a topic directory and a structured req.md (REASONS-inspired canvas) by asking 2-3 clarifying questions per round. Do NOT invoke for ordinary "I want to..." requests, casual feature ideas, simple questions, or direct implementation requests.
---

# /dl-req — Dev-Loop Requirements Confirmation (Stage 1/6)

## Do NOT run this skill when

- The user is merely asking a question.
- The user asks for a normal code edit without mentioning dev-loop.
- The user says "plan", "requirements", or "verify" in ordinary language.
- The request is trivial and can be handled directly without workflow state.
- Another dev-loop stage is already active and this stage was not requested.

If any of the above match, decline politely and offer the direct solution instead.

## Purpose

Stage 1 of 6. Produce `<plans-dir>/<NN>-<topic>/req.md` containing the
requirements canvas (Requirements / Entities / Scope / Norms / Safeguards /
Unknowns; Approach and Operations explicitly left to /dl-plan) plus topic
metadata. The user collaborates via short Q&A rounds. Stops at req.md — does
not auto-invoke /dl-plan.

## Shared assets (read, do not duplicate inline)

- `~/.claude/dev-loop-shared/project-detect.sh` — project_root / project_type / plans-dir detector
- `~/.claude/dev-loop-shared/topic-metadata-template.yaml` — req.md frontmatter schema
- `~/.claude/dev-loop-shared/reasons-takeaways.md` — REASONS adoption rules + 3-tier complexity

## Behavior

### Phase A — Detect project

Run `bash ~/.claude/dev-loop-shared/project-detect.sh`. Capture:
- `project_root`
- `project_type` (code / wiki / mixed / unknown)
- `has_project_doc` (yes / no)
- `plans_dir`

If `project_type=unknown`, ask the user whether to treat as code or wiki before continuing.

If `has_project_doc=yes`, read `<project_root>/CLAUDE.md` and `<project_root>/AGENTS.md` (whichever exist). Build a **project rules digest**: first 50 lines + any paragraph containing 禁止 / 必须 / 不要 / 铁律 / safety / safeguard. Keep digest in working memory for Phase D and embed it at the bottom of req.md.

### Phase B — Allocate NN and create topic dir (atomic)

1. **Try acquire alloc-lock**: `mkdir <plans_dir>/.alloc.lock`. If it fails, wait up to 60s with periodic retry. After 60s check for stale lock — read `<plans_dir>/.alloc.lock/info` (format: `<pid> <started_at>`), if `started_at > 10 min ago` then `rm -f <plans_dir>/.alloc.lock/info; rmdir <plans_dir>/.alloc.lock` and retry once. On final failure, abort and tell the user (do not bypass).

2. **Inside lock**: scan `<plans_dir>/` for existing `NN-*` directories. `NN := max(existing) + 1`, zero-padded to 2 digits. Default to `01` if empty.

3. **Get slug from user**: ask for a short kebab-case slug (≤6 words). Kebab-case any non-conforming input. Do NOT auto-generate a slug (no `task-1` style placeholders).

4. **Atomic mkdir**: `mkdir <plans_dir>/<NN>-<slug>`. If EEXIST (race), rescan from step 2 once. If slug also collides under same NN, append a short hash: `<NN>-<slug>-<hex4>`.

5. **Write pid + started_at into lock info**: `echo "$$ $(date -Iseconds)" > <plans_dir>/.alloc.lock/info` (helps stale detection by other runs).

6. **Write placeholder frontmatter** to `<topic_dir>/req.md`:

   ```yaml
   ---
   type: req
   req_contract_version: 1
   req_profile: standard
   profile_status: complete       # /dl-req 固定 complete
   topic_id: <NN-slug>
   project_root: <abs>
   project_type: <from Phase A>
   status: planning
   created_at: <now>
   created_cwd: <now>
   deferred_to_plan: [approach, operations, entities_detailed]
   locked_fields: []
   ---
   # (req body filled by /dl-req Phases C-E)
   ```

7. **Release lock (immediate, short-lock pattern — 议题 J)**: `rm -f <plans_dir>/.alloc.lock/info; rmdir <plans_dir>/.alloc.lock`. Lock hold time = single-digit seconds. Subsequent Phase D failures use `<topic_dir>/req.md` frontmatter `status: aborted` for rollback, **not** lock-held-throughout.

### Phase C — Assess complexity tier

Show the user the 3-tier table from `~/.claude/dev-loop-shared/reasons-takeaways.md` and ask:

> 这个改动属于哪一档？
> - **micro**：typo / 单 wikilink / 格式小修
> - **standard**：普通改动
> - **major**：跨模块 / 改规范 / 影响数据-安全-性能 / 写长期 wiki 结论

Record `complexity:` in metadata. Use it to scale Phase D depth:
- `micro`: ask only Requirements / Scope / Safeguards (one round, 1-2 sentences each)
- `standard`: full Phase D
- `major`: full Phase D + extra emphasis on Unknowns and Safeguards

### Phase D — Interactive requirement gathering

**Ask 2-3 questions per round, not all at once**. Wait for user answer before next round.

Required topics (skip 4-5 for `micro`):

1. **Requirements** — "完成后用户能做什么以前做不到的事？给 3 条以内可观测的验收标准。"
2. **Scope** — "这次做什么 / 不做什么？最容易跟它混淆的 2-3 个邻近功能是什么？影响哪些 module 或 wiki 页面？"
3. **Safeguards** (mandatory all tiers) — "哪些不能碰？性能 / 安全 / 兼容性红线？禁止操作？" For wiki projects, **always** confirm these defaults are still in scope:
   - `raw/` 只读
   - 源卡引用必填（事实陈述必须有 `[[sources/...]]`）
   - 不静默覆盖用户内容
   - 矛盾必须 `[conflict]` 标注不静默删除
4. **Norms** — "涉及哪些工程规范？命名 / 测试 / observability / wiki rules（frontmatter type / wikilink / 只追加 log / slug ASCII 等）？"
5. **Entities (草层)** — "涉及哪些业务实体 / wiki 页面（源卡 / 概念页 / 实体页 / synthesis）/ 外部系统？只列名字，关系细节留给 /dl-plan。"
6. **Unknowns** — "你已经感觉到哪些坑或不确定的点？哪些前提是假设的？"

**Do not** answer the user's questions for them. **Do not** invent facts to fill gaps. If user says "不知道" or "你定", record it as an Unknown and proceed.

If a user-stated requirement directly conflicts with a rule in the project digest (e.g., "改 raw/" in a wiki project), flag immediately as a Safeguards entry and ask user to confirm or revise — do not silently include the conflict.

### Phase E — Write req.md (overwrites Phase B placeholder)

Path: `<plans_dir>/<NN>-<slug>/req.md`

Frontmatter: use `~/.claude/dev-loop-shared/topic-metadata-template.yaml` as schema. Phase B already wrote the contract block (`req_contract_version: 1` / `req_profile: standard` / `profile_status: complete` / `deferred_to_plan: [approach, operations, entities_detailed]` / `locked_fields: []`) — **preserve those values** (议题 J). Fill all other known fields; leave `TBD-by-plan` for `approach` / `operations`; leave empty lists `[]` for fields /dl-plan will populate (`affects_files.declared`, `conflicts_with`, `codex_sessions`). Update `updated_at: <now>`.

The body is the substantive write — do NOT modify the contract fields written by Phase B.

Body (machine-parseable stable headings — required by 议题 G takeaway 7):

```markdown
## Requirements
<3 lines max + 3 acceptance criteria>

## Entities
<draft list, names only>

## Scope
### In scope
- ...
### Out of scope
- ...

## Norms
- ...                  # skip section for micro tier

## Safeguards
- ...

## Unknowns / Open Questions
- ...

## Approach
TBD by /dl-plan. Reason: <one line>. Constraints on subsequent plan: <one line>.

## Operations
TBD by /dl-plan.

## Project rules digest
<embed digest from Phase A>
```

After write, set topic `status: planning` in frontmatter (议题 D.2 state machine).

### Phase F — Handoff (do not auto-invoke /dl-plan)

Report to user:

1. Topic directory: `<plans_dir>/<NN>-<slug>/`
2. Complexity tier
3. Any `Unknowns` items the user should be aware of
4. Project rules digest summary (1-2 lines)
5. Next step suggestion: `/dl-plan` — but **do not auto-invoke** (disable-auto)

Then stop.

## Guardrails

- **Do not** write `approach` or `operations` in req.md. They belong to /dl-plan.
- **Do not** auto-invoke /dl-plan, even if the user seems eager to continue.
- **Do not** create the topic dir before NN allocation succeeds.
- **Do not** silently resolve a conflict between user request and CLAUDE.md rules — surface it as a Safeguards entry and ask.
- **Do not** answer Phase D questions on the user's behalf.
- **Do not** invent facts. Unknown → Unknowns section. Conflicting CLAUDE.md rule → Safeguards.
- For `micro` tier, **still** fill Safeguards. Skip Norms/Entities draft.
- If project_type=mixed, set `writeback_policy` in metadata (议题 B.5) — ask user which dirs allow integrate/verify writeback to wiki/.

## Failure modes (议题 D)

- Alloc-lock acquire fails after 60s + stale check → abort with user-visible message; user can manually remove `.alloc.lock` after inspection.
- User aborts mid-Q&A ("算了" / "停" / "abort") → write current partial state with `status: aborted` + `aborted_at` + `last_stage: req` + `reason: user_requested`. Keep topic dir.
- Slug conflict after rescan + hash → ask user for a different slug.
- CLAUDE.md unreadable or missing keywords → digest = "(无项目铁律可提取)"; do not block.
