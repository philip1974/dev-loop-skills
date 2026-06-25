---
name: dl-req-mvp
description: Stage 1/6 of the dev-loop workflow (MVP + visual/product anchors profile). Use only when the user explicitly asks to start the heavy req variant via phrases like "/dl-req-mvp", "dev-loop:req:mvp", "进入 mvp req 阶段". Same stage slot as /dl-req but locks down product-level anchors early — MVP scope, design system visual tone (NOT components or APIs), user-confirmed open-source references, user-confirmed product benchmarks, user-confirmed design system references. Does NOT touch data types, interfaces, or detailed entities — those stay in /dl-plan (议题 G boundary). Produces req.md with req_contract_version=1, req_profile=mvp, plus profile-specific sections. Supports resume mode for profile_status=partial topics. Do NOT invoke for ordinary /dl-req requests, simple feature ideas, wiki ingestion, or any request that does not reference an external product surface to lock.
---

# /dl-req-mvp — Dev-Loop Requirements (MVP + Product Anchors Profile, Stage 1/6)

## Relationship to /dl-req

`/dl-req` and `/dl-req-mvp` are **sibling skills** occupying the same Stage 1 slot. Both produce `<plans-dir>/<NN>-<topic>/req.md`. Both stamp `req_contract_version: 1`. `/dl-plan` consumes them identically (它只看 contract version + req_profile,不读 skill 名字)。两者差异:

| Aspect | /dl-req (standard) | /dl-req-mvp |
|---|---|---|
| Focus | REASONS canvas | Product-level anchors |
| MVP scope explicit | implicit in `## Scope` | dedicated `## MVP Scope` |
| Design system anchor | not collected | visual tone + (optional) candidate refs |
| Open-source references | not collected | user-reviewed candidate queue |
| Product benchmarks | not collected | user-reviewed candidate queue |
| `data_types` / `interfaces` / `entities_detailed` | left to /dl-plan | left to /dl-plan (same) |
| Round cap | as-needed | **hard cap: 3 Q&A + 1 candidate review** |
| Resume mode | n/a | yes (for `profile_status: partial`) |

The user picks which sibling to invoke. **No** auto-routing.

> Field-name authority lives in `~/.claude/dev-loop-shared/req-contract-v1.yaml`. Both sibling skills MUST conform to it — any drift = bug.

## Do NOT run this skill when

- The user typed `/dl-req` — run that instead.
- The topic has no external product surface (backend refactor, internal lib, wiki ingestion, doc edit).
- The user wants a quick brainstorm — too heavy for that.
- Another dev-loop stage is already active for this topic AND it is not a `partial` mvp resume case.
- The user is mid-execute / mid-verify and asks to "redo req" — /dl-integrate or red-team-back territory.

If any match, decline and suggest the correct path.

## Purpose

Lock 4 product-level anchors **before** /dl-plan, with explicit safeguards against four common traps:

1. **Reference anchoring** — user sees a candidate and demands "build this", but license / architecture / quality unvetted.
2. **Benchmark as pseudo-requirement** — competitor product gets treated as acceptance criterion instead of context.
3. **Design system over-locking** — visual tone locked too tightly, prematurely dictating implementation choices that belong to /dl-plan.
4. **Agent fake-research** — search-result links written into req as "approved reference" without the user actually reading them OR without agent verifying the link.

The skill mitigates all four via the **candidate queue pattern** (Phase E + F): agent generates verified, labelled candidates; user explicitly keeps/rejects; only `user_kept` items with verified reachability enter req.md.

## Shared assets

- `~/.claude/dev-loop-shared/project-detect.sh`
- `~/.claude/dev-loop-shared/topic-metadata-template.yaml` (must be v2 — includes contract fields; see companion edit)
- `~/.claude/dev-loop-shared/reasons-takeaways.md`
- `~/.claude/dev-loop-shared/req-contract-v1.yaml` (authority for field names + golden req sample)

## Behavior

### Phase 0 — Resume detection (新增)

Before allocating a new topic, check: did the user say "继续 NN topic" / "resume 03-something" / 提到一个已有 topic id?

- If user references existing topic NN:
  - Read `<plans_dir>/<NN>-*/req.md`. Parse frontmatter.
  - If `req_profile != mvp` → abort: "topic NN 不是 mvp profile,请用 /dl-req"。
  - If `profile_status == complete` → abort: "topic NN 已 complete,直接跑 /dl-plan"。
  - If `status != planning` → abort with current status: "topic NN 状态为 <status>,不能 resume"。
  - If `req_profile == mvp && profile_status == partial && status == planning` → **enter resume mode**:
    - Skip Phase A (already detected), B (NN allocated), C (mvp intent already recorded).
    - Load existing frontmatter into working memory.
    - In Phase D and onwards, only **fill missing `locked_field_status` slots** (status `missing`); never modify slots with status `filled` or `intentionally_empty`.
    - Resume mode does NOT reset round counter — it adds rounds. Hard cap remains 3 Q&A + 1 review, but state across sessions; if cap already exhausted in original run, only single-shot fills are allowed (no new Q&A round).
- Else: fall through to Phase A (new topic).

### Phase A — Detect project

Same as /dl-req Phase A. Run `project-detect.sh`. Build CLAUDE.md / AGENTS.md digest.

If `project_type == wiki`, **abort** with: "本 skill 针对产品类 topic;wiki 摄取请用 /dl-req." Do not allocate NN.

### Phase B — Allocate NN + create topic dir (atomic, short-lock)

**Lock semantics changed from /dl-req** (P0-3 fix): alloc-lock is held only across the small atomic init, NOT through the entire skill run.

Steps:

1. `mkdir <plans_dir>/.alloc.lock` (acquire). Retry up to 60s. Stale check: read `<plans_dir>/.alloc.lock/info` (format: `<pid> <started_at>`); if `started_at > 10 min ago`, `rm -f <plans_dir>/.alloc.lock/info; rmdir <plans_dir>/.alloc.lock` and retry once. On final failure, abort.
2. Inside lock:
   - Write `echo "$$ $(date -Iseconds)" > <plans_dir>/.alloc.lock/info` (pid + started_at, for stale detection by other runs).
   - Scan existing `NN-*` dirs. `NN := max + 1`, zero-padded.
   - Get slug from user (kebab, ≤6 words). No auto-generation.
   - `mkdir <plans_dir>/<NN>-<slug>`. On EEXIST race, rescan once; on slug collision, append `-<hex4>`.
   - Write a **placeholder frontmatter** to `<topic_dir>/req.md`:
     ```yaml
     ---
     type: req
     req_contract_version: 1
     req_profile: mvp
     profile_status: partial         # will flip to complete at Phase H success
     topic_id: <NN-slug>
     project_root: <abs>
     project_type: <from Phase A>
     status: planning
     created_at: <now>
     created_cwd: <now>
     locked_field_status:
       mvp_scope: missing
       acceptance_signals: missing
       design_system_anchor: missing
       reference_candidates: missing
       product_benchmarks: missing
       design_system_references: missing
     ---
     # (req body to be filled by /dl-req-mvp Phases C-H)
     ```
3. **Release lock**: `rm -f <plans_dir>/.alloc.lock/info; rmdir <plans_dir>/.alloc.lock`. Total lock hold time = single-digit seconds.

Subsequent failures (user abandons mid-flow) do NOT need the lock — they update `<topic_dir>/req.md` frontmatter `status: aborted` and stop. Lock is **not** the rollback mechanism.

### Phase C — MVP intent confirmation (one turn)

Ask 3 short questions **in a single turn**:

1. **Product surface** — web app / mobile / CLI / library SDK / browser extension / other?
2. **One-sentence pitch** — who, what, why-now.
3. **V1 ship target** — date,或硬范围上限(例:"功能 ≤ 5 个"、"两周内能 demo")。

If user answers TBD / 随便 / 你定 to **all three**: set frontmatter `status: aborted, reason: no_mvp_anchor_possible`, suggest /dl-req. Do NOT delete the topic dir (议题 D.4 — keep for audit). User can manually `rm` later.

Record into `mvp` frontmatter block.

### Phase D — Bounded Q&A (hard cap 3 rounds, state-preserving across resume)

Ask 2-3 questions per round, max **3 rounds total** (counter persisted in frontmatter `qa_rounds_done`). After round 3, if `locked_field_status` still has `missing` slots, set `profile_status: partial` and move to Phase I — do **NOT** push for more rounds.

Required topics (collect across rounds; scale by complexity tier from /dl-req's Phase C — micro tier skips Norms and reduces Unknowns scope):

1. **MVP Scope (V1 cut)** — V1 必有 3-5 功能 / V1 不做但 V2 可能的 3 件事 / 用户在哪个最具体场景"我现在就要用"
2. **Non-goals (anti-scope)** — 明确不做什么 / 最容易被混淆但不在 V1 的 2 件事
3. **Acceptance Signals** — V1 验收用什么可观测指标 (2-3 条;不是长期 KPI)
4. **Safeguards** (mandatory all tiers) — 性能 / 安全 / 兼容性红线 / 禁止操作 / 用户数据
5. **Unknowns** (mandatory) — 你已感觉到的坑 / 哪些前提是假设

Each filled topic flips its `locked_field_status` to `filled`. If user explicitly skips a topic ("我不需要 acceptance signals,V1 就是能跑就行") → flip to `intentionally_empty` (not the same as `missing`).

User says "不知道" / "你定" → record as Unknown,round 计数照增。

Conflict with CLAUDE.md → Safeguards entry,don't silently absorb。

### Phase E — Candidate research (agent-generated, verified queue)

For each of 3 categories below, agent generates **up to 3 candidates**. If user said "我不参考任何 X" → `locked_field_status[X]: intentionally_empty`, skip generation.

Categories:
1. **Open-source references** — repos solving similar problem
2. **Product benchmarks** — competitor / inspiration products
3. **Design system references** — design systems or visual-tone references

For each candidate, agent emits:

```yaml
- name: <product or repo name>
  link: <https://...>
  category: open-source | product-benchmark | design-system
  why_candidate: <1-line specific reasoning citing a feature>
  what_to_inspect: <2-4 concrete things user should look at>
  risk_note: <license / quality / scope risk>
  license: <if visible>
  verified_at: <YYYY-MM-DD>             # P1-7
  verification_method: web_fetch | search_snippet | memory_only
  reachable: true | false               # P1-7
  status: candidate_only
  not_validated_by_user: true
```

**Hard rules on candidate generation (P1-7 + earlier):**

- **Max 3 per category.** Better 1 strong than 3 weak.
- **`why_candidate` must cite a specific feature**. Generic ("popular", "high-rated") → regen.
- **Agent must attempt verification** (web fetch / search lookup). If `verification_method == memory_only` OR `reachable == false`:
  - Candidate does NOT enter the user-facing queue.
  - Instead, agent adds it to a separate `manual_suggestion_list` shown to the user with explicit "**unverified — please confirm before researching**" warning.
- **If no good candidates found**, say so verbatim: `[no good candidates found in this category; user may add manually]`. Do NOT fabricate, do NOT pad.

Present the queue (verified candidates) + manual_suggestion_list (unverified hints) to the user in **one block**.

### Phase F — User candidate review (single round + optional 1 replacement)

For each candidate, collect:

- **Decision**: `keep` / `reject` / `unsure`
- If `keep`:
  - **adoption_points**: subset of `{layout, interaction, tone, none}` — these are **locked constraints** for /dl-plan (P1-9 fix)
  - **inspect_points**: subset of `{architecture, scope, performance, error_handling, data_model, deployment, none}` — these are **plan-time hints**, NOT locked. /dl-plan reads them but is not constrained.
  - **forbidden_mimic_points**: free-text — what NOT to copy
  - Optional **user_review_note**: 1-line free-text
- If `reject`: optional 1-line reason

**Unsure rule (P1-6 fix, hardened):**
- `unsure` is **never kept silently**. Default treatment: discarded (logged in `## Discarded candidates` for trace, NOT consumed by /dl-plan).
- User may invoke "再调研一轮" once → agent generates a **replacement queue** for the unsure candidates only (same 3-per-category cap, verification rules apply). This **does NOT count as a new Q&A round** but does set `replacement_round_used: true` in frontmatter (one-shot only).
- After replacement round (or if user declines it), any remaining `unsure` → discarded.

Only `keep` candidates with verified `reachable: true` enter the user-confirmed sections in Phase H.

After Phase F, flip:
- `locked_field_status.reference_candidates` → `filled` if ≥1 open-source kept, `intentionally_empty` if user reviewed but kept none, `missing` if Phase E hit zero candidates AND user added nothing manually
- Same logic for `product_benchmarks` and `design_system_references`

### Phase G — Design system anchor (visual tone, narrow)

Even if no design-system candidate kept, ask:

> "V1 的视觉基调用一句话怎么形容?(例:深色 / 数据密集 / 极简白 / 玻璃拟态 / 不在乎好看,功能优先)"

Record as `design_system_anchor.visual_tone` (string). Flip `locked_field_status.design_system_anchor` → `filled` (or `intentionally_empty` if user explicitly skips).

**Do NOT** ask about specific component libraries, design tokens, or component APIs. Those are /dl-plan territory.

### Phase H — Write req.md (final write, replaces placeholder)

Compute `profile_status`:

```python
if all(status in {filled, intentionally_empty} for status in locked_field_status.values()):
    profile_status = "complete"
else:
    profile_status = "partial"   # at least one slot still "missing"
```

(P1-8 fix: `intentionally_empty` does NOT cause partial.)

Path: `<plans_dir>/<NN>-<slug>/req.md` (overwrites the Phase B placeholder).

Frontmatter (req contract v1, authoritative names from `req-contract-v1.yaml`):

```yaml
---
type: req
req_contract_version: 1
req_profile: mvp
profile_status: complete | partial

# === Identity ===
topic_id: NN-slug
project_root: /abs/path
project_type: code | mixed
complexity: micro | standard | major
created_at: YYYY-MM-DD HH:mm:ss
updated_at: YYYY-MM-DD HH:mm:ss
created_cwd: /abs/path/at/creation
status: planning

# === Standard topic fields (same as /dl-req) ===
affects_files:
  declared: []
  inferred: []
  executed: []
conflicts_with: []
codex_sessions: []
red_team_round: 0
execute_retry: 0
integrate_retry: 0
verify_retry: 0

# === Req contract v1 ===
deferred_to_plan:
  - approach
  - operations
  - entities_detailed
  - data_types
  - interfaces
locked_fields:
  - mvp_scope
  - acceptance_signals
  - design_system_anchor
  - reference_candidates
  - product_benchmarks
  - design_system_references

locked_field_status:
  mvp_scope: filled | intentionally_empty | missing
  acceptance_signals: filled | intentionally_empty | missing
  design_system_anchor: filled | intentionally_empty | missing
  reference_candidates: filled | intentionally_empty | missing
  product_benchmarks: filled | intentionally_empty | missing
  design_system_references: filled | intentionally_empty | missing

qa_rounds_done: 0..3
replacement_round_used: false | true

# === mvp profile data ===
mvp:
  product_surface: <from Phase C>
  pitch: <from Phase C>
  ship_target: <from Phase C>
design_system_anchor:
  visual_tone: "<from Phase G>"
---
```

Body (machine-parseable headings — names authoritative, see `req-contract-v1.yaml`):

```markdown
## MVP Scope
### V1 in
- ...
### V1 out (deferred to V2+)
- ...
### Anti-scope (explicitly NOT doing)
- ...

## Acceptance Signals
- <observable indicator>
- ...

## Design System Anchor
- visual_tone: "<Phase G>"
- NOTE: specific components / tokens / APIs are /dl-plan territory.

## Open-source Reference Candidates (user-confirmed)
- name: <name>
  link: <url>
  status: user_kept
  verified_at: <date>
  reachable: true
  adoption_points: [layout, interaction]      # locked constraints
  inspect_points: [architecture]              # plan hints, NOT locked
  forbidden_mimic_points: [...]
  why_candidate: <preserved>
  what_to_inspect: <preserved>
  user_review_note: <verbatim if any>
- ...
<if section's locked_field_status == intentionally_empty: "(user reviewed and kept none)">
<if missing: "(unfilled — see profile_status: partial)">

## Product Benchmark Candidates (user-confirmed)
<same schema; status: user_kept only>

## Design System Reference Candidates (user-confirmed)         <!-- P1-5 fix -->
<same schema; status: user_kept only>

## Safeguards
<from Phase D — mandatory>

## Unknowns / Open Questions
<from Phase D + any partial-locked_fields if profile_status=partial>

## Norms
<short, only if user surfaced any — skip for micro>

## Requirements
<3-line summary derived from MVP Scope + Acceptance Signals — for dl-plan/red-team reference>

## Approach
TBD by /dl-plan.

## Operations
TBD by /dl-plan.

## Entities (detailed)
TBD by /dl-plan.

## Project rules digest
<from Phase A>

## Discarded candidates (trace only — /dl-plan MUST NOT consume)
- name / link / category / user reason (if given) / phase: rejected | unsure_discarded
- ...

## Manual suggestion list (unverified — agent could not verify)
- name / link / category / why_suggested
<if empty: "(none)">
```

After write, ensure frontmatter `status: planning` and `updated_at: <now>`.

### Phase I — Handoff

Report to user:

1. Topic directory + `req_profile: mvp` + `profile_status: complete | partial`
2. If partial: list `locked_field_status` entries with `missing`, tell user `/dl-plan` will refuse and they should `/dl-req-mvp resume <NN>` to fill.
3. Candidate counts per category: `kept / rejected / discarded / manual_suggestions`
4. Unknowns count
5. Reminder: `/dl-plan` will fill `deferred_to_plan` (approach / operations / entities_detailed / data_types / interfaces). It treats `locked_fields` as constraints, NOT re-derive.
6. Next: `/dl-plan` — **do not auto-invoke**.

## Guardrails

- **Do not** ask about data_types, interfaces, or entities_detailed — they belong to /dl-plan.
- **Do not** invoke for wiki / pure-backend / internal-refactor topics.
- **Do not** exceed 3 Q&A rounds + 1 candidate review round (replacement queue is allowed once, not counted as new review round).
- **Do not** generate more than 3 candidates per category per round (including replacement).
- **Do not** produce candidate `why_candidate` text that is generic.
- **Do not** write a candidate as user-confirmed unless user explicitly said `keep`. `unsure` defaults to discarded.
- **Do not** write a candidate as user-confirmed if `reachable == false` or `verification_method == memory_only` — those go to `manual_suggestion_list`.
- **Do not** treat product benchmarks as acceptance criteria.
- **Do not** fabricate candidates.
- **Do not** lock specific design components / tokens / APIs in `design_system_anchor` — only visual tone.
- **Do not** allow `adoption_points` to contain `architecture` or `scope` — those go to `inspect_points` (plan hints only).
- **Do not** auto-invoke /dl-plan.
- **Do not** overwrite a `filled` or `intentionally_empty` `locked_field_status` slot — resume mode can only fill `missing` slots.
- **Resume mode**: only allowed when `req_profile=mvp + profile_status=partial + status=planning`. Anything else: abort with current state.
- For `micro` complexity tier, this skill is probably overkill — suggest /dl-req. If user insists, round cap still applies (and likely exits at 1-2 rounds).

## Failure modes

- `project_type == wiki` → abort, suggest /dl-req. No mkdir done (Phase A precedes Phase B).
- All Phase C answers TBD → set `status: aborted, reason: no_mvp_anchor_possible`, keep topic dir for audit.
- Phase E found zero candidates in **all three** categories AND user has no manual additions → write empty candidate sections with `(no candidates available)` note; if user reviewed (Phase F happened on zero) → `locked_field_status.reference_candidates: intentionally_empty`.
- User aborts mid-flow → write current partial req.md, set `status: aborted`, `aborted_at`, `last_stage: req-mvp`, `reason: user_requested`. Keep topic dir.
- Round cap hit with `missing` slots remaining → write `profile_status: partial`, list missing in `locked_field_status`. /dl-plan will refuse partial → user runs `/dl-req-mvp resume <NN>`.
- User wants to switch to /dl-req mid-flow → set `status: aborted, reason: switched_to_dl_req`, instruct user to run /dl-req fresh on a NEW NN. Old mvp topic dir kept for audit.
- Resume mode entered for non-eligible topic (wrong profile / wrong status) → abort with state explanation, no writes.
