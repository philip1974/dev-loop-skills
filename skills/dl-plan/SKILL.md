---
name: dl-plan
description: Stage 2/6 of the dev-loop workflow. Use only when the user explicitly asks to run the dev-loop plan stage via phrases like "/dl-plan", "dev-loop:plan", "进入 plan 阶段", or "为 topic NN 写 plan". Reads req.md, fills in Approach + Operations + detailed Entities, declares affects_files, and produces plan-vN.md plus the required-questions list for /dl-red-team to attack. Do NOT invoke for casual planning, brainstorming, or any request that does not reference an existing tracked topic.
---

# /dl-plan — Dev-Loop Plan (Stage 2/6)

## Do NOT run this skill when

- The user is merely asking a question or wants casual planning advice.
- No tracked topic exists yet (run /dl-req first).
- The user is mid-execute and wants a "quick replan" without going back through red-team — that's a /dl-integrate concern.
- The user says "plan" in ordinary language without referencing a topic.
- Another dev-loop stage is already active and this stage was not requested.

If any match, decline and offer the direct path.

## Purpose

Stage 2 of 6. Take req.md, produce a structured `plan-vN.md` ready for /dl-red-team. The plan:

- Fills the Approach + Operations canvas fields (left TBD by /dl-req)
- Declares `affects_files.declared` (议题 F.2)
- Writes a Reads citation list (议题 1 original SOP) — gives red-team grep starting points
- Writes a 必答问题清单 (5-10 concrete questions) — forces red-team to attack specifics, not just "please review"
- Includes a test/verification matrix (议题 G — machine-parseable for /dl-verify later)

Stops at plan-vN.md — does not auto-invoke /dl-red-team.

## Shared assets

- `~/.claude/skills/dev-loop-shared/project-detect.sh`
- `~/.claude/skills/dev-loop-shared/topic-metadata-template.yaml`
- `~/.claude/skills/dev-loop-shared/reasons-takeaways.md`

## Behavior

### Phase A — Locate topic

If user specifies topic id (e.g. "for 03-fix-auth"): use it. Validate `(project_root, topic_id)` per 议题 F.4.

Else: list active topics under `<plans_dir>/` where `status: planning`. If exactly one, use it. If multiple, show each topic's `replan_reason`, `blocked_plan`, and latest `plan-vN.md` version (if present), then ask user to pick. If none, abort: "no planning-status topic, run /dl-req first."

Planning topics include both fresh req topics and red-team BLOCK replans. A replan topic carries `replan_reason` / `blocked_plan`; when multiple planning topics exist, never auto-select without showing those fields.

### Phase B — Validate prerequisites

Read `<topic_dir>/req.md`. Check:

- File exists and parses (valid frontmatter + body)
- Frontmatter `status: planning` (议题 D.2)
- `complexity:` set to micro / standard / major
- Body parses (frontmatter + sections); profile-aware heading non-empty checks happen in **Phase B.5** (议题 J)
- `## Approach` and `## Operations` must still say `TBD by /dl-plan` (i.e. req skill obeyed its contract)

If any check fails, abort and tell the user which check failed. **Do not** auto-fix req.md — go back to the right req skill (/dl-req for standard,/dl-req-mvp for mvp).

### Phase B.5 — Validate req contract (议题 J,profile-aware,2026-05-18)

After Phase B parses req.md but before Phase C re-detects project:

**Step 1 — Contract version + profile**
- `req_contract_version` exists and == 1. Missing/older → abort: "req.md 来自旧版,请重跑 req 阶段(/dl-req 或 /dl-req-mvp)"。
- `req_profile` ∈ {standard, mvp}. Unknown → abort.

**Step 2 — Profile-aware heading non-empty check**

If `req_profile == standard`:
- Required non-empty sections: `## Requirements`, `## Scope`, `## Safeguards`
- (this preserves the original dl-plan Phase B check,只是 gated by profile)

If `req_profile == mvp`:
- Required non-empty sections: `## MVP Scope`, `## Acceptance Signals`, `## Design System Anchor`, `## Safeguards`, `## Requirements` (3-line summary)
- `## Scope` is **NOT** required for mvp(MVP Scope 替代它的角色)

**Step 3 — mvp-only contract validation**

If `req_profile == mvp`:
- `profile_status` must == `complete`. If `partial`:
  - List `locked_field_status` entries with value `missing`
  - Abort with: "/dl-req-mvp 未完成,缺失字段: <list>。请运行 `/dl-req-mvp resume <NN>` 补齐"
- For each `locked_fields` entry where `locked_field_status` value is `filled`,对应 body section 必须非空
- For each entry where value is `intentionally_empty`,section 内容允许为空或仅含 `(user reviewed and kept none)` 等价标记
- `qa_rounds_done` ≤ 3 (consistency check)

**Step 4 — `deferred_to_plan` input registration**

Read `deferred_to_plan` list from frontmatter. These are the fields Phase E MUST populate. Current expected lists:
- `standard` profile: `[approach, operations, entities_detailed]`
- `mvp` profile: `[approach, operations, entities_detailed, data_types, interfaces]`

Phase E must produce content for every entry in this list. Unknown entries → abort (likely contract drift).

**Step 5 — mvp-specific consumption rules (constraints on Phase E)**

If `req_profile == mvp`, Phase E MUST honor:

- **Operations 只在 `## MVP Scope ### V1 in` 列出的范围内做事**。任何 `V1 out` / `Anti-scope` 条目出现在 Operations → red-team 标 P0。
- **`## Acceptance Signals` 进 Test/Verification matrix** (Phase I)。这些是 V1 的验收。
- **`locked_fields` 内容只读**。/dl-plan **不得**修改 mvp_scope / acceptance_signals / design_system_anchor / reference_candidates / product_benchmarks / design_system_references 的内容。
- **`## Open-source Reference Candidates (user-confirmed)` + `## Product Benchmark Candidates (user-confirmed)` + `## Design System Reference Candidates (user-confirmed)`** 作为 inspiration input:
  - 每个 kept candidate 的 `adoption_points`(允许值:layout / interaction / tone / none)是**硬约束**
  - 每个候选的 `inspect_points`(architecture / scope / performance / error_handling / data_model / deployment / none)是**软提示**(看,不强制)
  - `forbidden_mimic_points` 是**硬禁**
- **`## Manual suggestion list`** 仅供阅读,**不**视为 reference(未验证)。
- **benchmark 永不进 Acceptance Signals**(议题 J:benchmark != requirement)。
- **`design_system_anchor.visual_tone`** 作为视觉风格约束。具体 component / token / API 选择是 plan 的责任(写进 Operations)。

### Phase B.6 — Intent Lock contract

Read `## Intent Lock` from req.md. Format authority: `~/.claude/dev-loop-shared/intent-lock-template.md`; do not inline it here.

- If missing and `complexity ∈ {micro, standard}`: set/keep `autonomy_readiness: low`, warn "建议补 Intent Lock，继续".
- If missing and `complexity == major`: block and route back to `/dl-req`, unless the user explicitly overrides.
- If major override is explicit: plan-vN.md MUST include `## Intent Lock (inferred) [unverified]` and mark it risk-bearing.
- If present: plan-vN.md MUST include a **verbatim Intent Lock excerpt** copied from req.md: Outcome / Positive or Anti-examples / Acceptance samples / Kill criteria / autonomy_readiness. Red-team reads plan only, not req.md.

### Phase C — Re-detect project context

Run `bash ~/.claude/skills/dev-loop-shared/project-detect.sh` again. Compare current `project_root` with `topic.project_root` from metadata. **If mismatch, abort** (议题 F.4 invariant): user is in wrong repo, must `cd` to correct project_root first.

Re-read CLAUDE.md / AGENTS.md — rules may have changed since /dl-req. If any new safeguard contradicts canvas, flag for user.

### Phase D — Determine plan version N

Scan `<topic_dir>/plan-v*.md`. `N := max(existing version numbers) + 1`. If no existing files, `N = 1`.

If `N > 3`, abort: "plan↔red-team round limit (3) reached. Per 议题 D.3, generate blocked summary and request user adjudication. Do not proceed to write plan-v4."

### Phase E — Fill canvas (Approach / Operations / Entities-detailed)

Take req.md as input. Fill the gaps:

#### Approach

Pick **one** strategy. If 2-3 alternatives exist, list them with explicit tradeoffs, then commit to one. Don't write hand-wavy "we'll figure it out".

For `wiki` projects: Approach is the ingestion/synthesis strategy (e.g., "create new source card under wiki/sources/, extract 3 entities, update 2 synthesis pages, append log").

For `code` projects: Approach is the architecture/algorithm strategy (e.g., "add middleware layer, refactor X to Y pattern, introduce table Z").

#### Operations

Concrete steps, ordered. Granular enough that /dl-red-team can find P0 issues.

- `code`: function-signature level + test cases (BDD: `it("should X when Y")` / TDD unit). Order matters (e.g., write test → write impl → wire route).
- `wiki`: page-level actions: create source card at `wiki/sources/foo.md` / update frontmatter on `wiki/concepts/bar.md` / add wikilink in `wiki/synthesis/baz.md` / append to `wiki/log.md` / update `wiki/index.md`.

Number each step (Op1, Op2, ...). Steps must be small enough to fail individually (议题 D.1: /execute lint fail returns to /execute self-fix; deep failure to /plan).

#### Entities (detailed)

Take req.md Entities (草层) and expand. For wiki: list specific page paths and their relationships (which page links to which). For code: list classes / modules / data structures and their connections.

### Phase F — Declare affects_files

Extract from Operations: every file path that will be created / modified / deleted. Put into `affects_files.declared` list in topic metadata (议题 F.2 first scan).

**Do not** include files that are only read (those are in Reads section, not affects_files).

**Wiki special**: if Operations touches `wiki/index.md` or `wiki/log.md`, include them, but mark with `(shared-append)` suffix — these don't block parallel topics but require serialized append (议题 F.2 wiki special).

### Phase F.5 — Declare `real_test` (议题 H)

Decide whether the topic needs a real-test gate at /dl-verify. **This is mandatory** — `/dl-plan` cannot skip declaring it; missing → /dl-verify aborts and bounces back to /dl-plan.

Choose exactly one of:

- `required` — topic changes user-visible behavior (CLI output / TUI / GUI / browser / mobile). Must list `scenarios`.
- `skipped` — real-test would be appropriate but is deferred (e.g. environment not available yet, follow-up topic will cover). Must give `reason`. Red-team will challenge it.
- `inapplicable` — the topic does not change any user-visible behavior (pure wiki / internal refactor / docs / config). Must give `reason`.

Write to plan-vN.md body (Phase I schema below). Required schema for `status: required`:

```yaml
real_test:
  status: required
  skill: cli-visual-debugger          # DEFAULT skill (议题 H Patch H.2-bis); per-scenario `scenario.skill` can override
  reason: "<1-line why a real-test is needed for this topic>"
  scenarios:
    - name: <short identifier>
      skill: gui-visual-debugger      # OPTIONAL — overrides top-level default for this scenario only
      command: <command to run>       # CLI: command to invoke; GUI: optional launch command
      app:                            # GUI only: window targeting
        bundle_id: <com.foo.bar>      # OR app_name OR launch_command
        window_title_pattern: <regex>
        display_index: 0              # default 0 = primary
        require_frontmost: true
      cwd: <working dir, absolute or repo-relative>
      terminal: { cols: 100, rows: 30 }     # CLI/TUI tier
      viewport: { width: 1280, height: 800, scale_factor_expected: 2, appearance: light|dark|either }   # GUI tier (logical pixels)
      profile_dir: <path>             # OPTIONAL state isolation (议题 H Patch H.7.4); missing → verify warns INCONCLUSIVE-risk: state-not-isolated
      setup:                          # OPTIONAL: pre-scenario steps (close stale instances, clear caches)
        - <step>
      steps:
        - <keystroke / input / a11y action / navigation>
      expected:
        - <user-visible observation that must be present>
      forbidden:                      # MUST classify per tier (议题 H.4 + H Patch H.7.5)
        read_only:                    # default-allowed
          - capture_screenshots
          - read_a11y
        local_only:                   # must be explicitly allowed
          - write_file:<path-pattern>
          - mutate_app_state
        externally_visible:           # default-forbidden; any trigger → INCONCLUSIVE: needs-second-confirmation
          - submit_form / delete / send_message / oauth_authorize / production_api_call
          - grant_system_permission / click_allow_on_system_dialog       # H Patch H.7.5
      evidence:                       # MUST be structured (议题 H.7.1 + brief P0): id + type + path + timestamp + step_ref + sanitize_policy
        - id: <stable-id>
          type: screenshot | a11y_tree | command_transcript | exit_code | final_screen
          step_ref: <step-index>
          sanitize_policy:                                                # H Patch H.7.5 + sanitize-by-default
            - crop_to_app_window
            - redact_notifications
            - exclude_other_apps
      cleanup:                        # OPTIONAL: post-scenario cleanup (close launched apps, dev servers, browser windows)
        - <step>
      timeouts:                       # GUI: 3-tier; CLI: single `timeout_seconds` still accepted
        launch_seconds: 30
        step_seconds: 10
        wait_seconds: 20
      verdict_schema: PASS|FAIL|INCONCLUSIVE with evidence ids
```

For `status: skipped` or `inapplicable`, only `status` and `reason` are required; omit `scenarios`.

Sanity check before moving on:
- For `required`: at least one scenario; each scenario has all of {name, expected, evidence, timeouts}.
- **Per-scenario skill resolution (议题 H Patch H.2-bis)**: each scenario's effective skill = `scenario.skill` if set, else `real_test.skill`. At least one of the two MUST be set; if both missing the plan is invalid.
- `forbidden.externally_visible` must list any system permission grants / OAuth / form submits / production API calls explicitly. System dialog Allow/OK clicks ALWAYS count as `externally_visible` (议题 H Patch H.7.5) — they cannot live in `local_only`.
- `evidence` entries must each have `id` + `type` + `step_ref` + `sanitize_policy`. Skill-default sanitize (e.g. `crop_to_app_window`) may be elided only if scenario explicitly inherits it.
- `profile_dir` is optional but recommended for GUI scenarios — its absence will trigger a verify-time `INCONCLUSIVE-risk: state-not-isolated` warning (议题 H Patch H.7.4).
- For wiki / pure-docs topics, prefer `inapplicable` unless the topic ships a tool the user runs (e.g. lint script changes).
- Each resolved skill must exist either project-local (`<project_root>/.codex/skills/<skill>/`) or global (`~/.codex/skills/<skill>/`). If neither, the plan is still allowed (red-team will flag), but /dl-verify will fail-gate the topic until installed.

### Phase F.6 — Map Intent Lock acceptance samples

For each Acceptance sample in the Intent Lock excerpt, create a matching Test/Verification matrix row, `real_test` scenario, or wiki-check row. For wiki-check types, use `intent-lock-template.md` (source card linked, source coverage, index/log, wikilink, no raw diff, lint, grep expected statement).

If a sample cannot be mapped, record it as an Unknown and ask whether to return to `/dl-req`; do not silently drop it.

### Phase G — Write Reads citation list

List source files the plan reads (for red-team to verify against). Format:

```
Reads:
  - <path>:<L1-L2>     # what we used from it
  - CLAUDE.md:1-50     # project rules
  - wiki/sources/foo.md  # source we are extending
```

This gives codex red-team grep starting points (议题 1 original SOP).

### Phase H — Generate 必答问题清单

5-10 concrete questions for codex red-team. **Not** generic "please review" prompts. Examples:

- "Op3 创建 source card foo.md，但没有定义 foo.md 与现有 wiki/sources/bar.md 的关系。会不会重复？"
- "affects_files 没有列 wiki/entities/X.md，但 Op5 隐含会更新它的反向链接。是否漏了？"
- "Approach 选 A 而非 B 的理由 ‘性能更好’ 是否有数据支撑？"
- "test matrix 覆盖了 happy path，但 micro 档允许跳过 edge case 吗？"

Tier-scale: micro → 3-5 questions; standard → 5-8; major → 8-10.

### Phase I — Write plan-vN.md

Path: `<topic_dir>/plan-vN.md` (N from Phase D).

Frontmatter:

```yaml
---
type: plan
version: N
parent_req: req.md
plan_round: N           # plan-vN paired with red-team-vN
status: pending-red-team
created_at: YYYY-MM-DD HH:mm:ss
complexity: <from req>
project_type: <from req>
---
```

Body (stable machine-parseable headings):

```markdown
## Overview
<2-4 lines: what this plan does, in plain language>

## Approach
<single chosen strategy + tradeoffs (if alternatives existed)>

## Entities (detailed)
- ...

## Operations
- Op1: ...
- Op2: ...
- ...

## Intent Lock excerpt
<verbatim from req.md, OR "## Intent Lock (inferred) [unverified]" for explicit major override>

## affects_files.declared
- <path>            # action: create | modify | delete | shared-append
- ...

## real_test (议题 H)
<YAML block from Phase F.5 — status + skill + scenarios OR status + reason>

## Test/Verification matrix
| Test ID | What | Type (BDD/TDD/wiki-check) | Expected |
|---|---|---|---|
| T1 | ... | ... | ... |

## Reads
- <path>:<lines> — <why>

## 必答问题清单 (red-team must answer)
1. ...
2. ...

## Project rules digest (refreshed)
<from Phase C re-read>
```

### Phase J — Hard-copy to plan.md

`cp <topic_dir>/plan-vN.md <topic_dir>/plan.md` (no symlink — 议题 B.3 cross-OS safety).

### Phase K — Update topic metadata

In req.md frontmatter (or separate topic metadata file if used):

- `updated_at`: now
- `status`:
  - If `complexity == micro`: `ready-for-execute`
  - Else (`standard` / `major`): `pending-red-team`
  # micro 直达 ready-for-execute，跳 red-team+integrate；见 canonical-state-machine-v1.yaml transitions
- If `complexity == micro`, also write:
  - `red_team.required: false`
  - `integrate.required: false`
  - `skip_reason: micro-tier (议题G; 跳 red-team+integrate)`
- `canvas.approach`: 1-line summary
- `canvas.operations`: count + 1-line summary
- `canvas.entities.detailed`: list
- `affects_files.declared`: list
- `autonomy_readiness`: re-evaluate per `intent-lock-template.md` after mapping Acceptance samples. Downgrade to `medium` if any sample is manual/non-executable; use `high` only when every sample maps to executable test/CI/real_test/wiki-lint command with owner gate.
- `red_team_round: N-1`   # 已完成轮数，见 SSOT

### Phase L — Handoff (do not auto-invoke)

Report:

1. Plan path: `<topic_dir>/plan-vN.md` (+ `plan.md` mirror)
2. Plan summary (3-5 bullets from Overview)
3. `affects_files.declared` count + any wiki shared-append flags
4. 必答清单 count
5. Conflict check preview: scan other active topics' `affects_files.declared` for overlap with this plan's (议题 F.2 — but only warn; actual blocking happens in /dl-integrate)
6. Next step suggestion: `/dl-red-team` — **do not auto-invoke**

Stop.

## Guardrails

- **Do not** auto-invoke /dl-red-team.
- **Do not** overwrite an existing plan-vN.md (always increment N).
- **Do not** edit red-team-vM.md files — red-team is the only writer there.
- **Do not** include red-team output structure (P0/P1/P2, Verdict) in plan — that's red-team's output.
- **Do not** skip 必答清单. If you can't think of 5 questions, the plan is probably too vague — go back and tighten Approach/Operations.
- **Do not** write hand-wavy Approach. Pick one strategy explicitly.
- **Do not** include files only-read in affects_files.declared — those are Reads.
- **Do not** silently absorb new CLAUDE.md rules that conflict with req.md — flag to user, propose Safeguards update via going back to /dl-req.
- **Do not** inline the full Intent Lock template; reference `~/.claude/dev-loop-shared/intent-lock-template.md`.
- **Do not** let a major req without Intent Lock proceed unless the user explicitly overrides; override requires inferred `[unverified]` Intent Lock in plan.
- **Do not** skip Phase F.5 (议题 H). `real_test` declaration is mandatory; missing → /dl-verify will bounce the topic back. For `inapplicable`, still write the block with status + reason.
- **Do not** mark a topic `inapplicable` just to avoid scenario writing. If the topic ships any user-runnable behavior (a CLI tool, a UI element, a script the user invokes), use `required` or `skipped` (with red-team-defensible reason).
- For `micro` tier, still produce Approach + Operations (just shorter). Don't skip Phases E-I.
- For `major` tier, ensure Operations granularity is high enough that each Op can fail/recover independently (议题 D.1 partial recovery).

## Failure modes (议题 D)

- Topic not found / not in `planning` status → abort with clear message.
- cwd mismatch with topic.project_root → abort (议题 F.4 invariant violation).
- `N > 3` → abort with "plan-round limit reached" message; instruct user to either rewrite req or manual override.
- `real_test` block missing or malformed → abort (议题 H invariant). Re-prompt user to declare `status` (required/skipped/inapplicable) + `reason` (if not required) + `scenarios` (if required).
- Conflict preview shows overlap with another active topic's affects_files → **warn** but still proceed (议题 F.2: actual blocking happens at /dl-integrate, not /dl-plan).
- User aborts mid-plan → write current partial plan-vN.md with `status: aborted`, append `last_stage: plan` + reason to topic metadata.
