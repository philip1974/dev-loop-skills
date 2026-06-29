---
name: dl-integrate
description: Stage 4/6 of the dev-loop workflow. Use only when the user explicitly asks to integrate red-team feedback via phrases like "/dl-integrate", "dev-loop:integrate", "整合 red-team", or "merge red-team feedback". Reads red-team-vN.md + plan-vN.md, decides accept/reject/defer per P0/P1/P2 item, writes plan-v(N+1).md with a changelog, and runs the cross-topic conflict check. Do NOT invoke for ordinary git-merge or cherry-pick tasks unrelated to dev-loop.
---

# /dl-integrate — Dev-Loop Integrate (Stage 4/6)

## Do NOT run this skill when

- No red-team-vN.md exists (run /dl-red-team first).
- The user is doing an ordinary code merge (git merge / cherry-pick).
- The user says "integrate" or "merge feedback" in ordinary language without a topic id.
- Topic status is not `ready-for-integrate` (e.g. red-team verdict was BLOCK — go to /dl-plan).
- Another dev-loop stage is already active and this stage was not requested.

If matched, decline.

## Purpose

Stage 4 of 6. Apply the red-team's P0/P1/P2 verdict and Integration Notes to plan-vN.md, producing plan-v(N+1).md. Claude is the **integrator** — codex's red-team output is input, not the integration itself (议题 C.2). Also runs the cross-topic conflict check (议题 F.2 mandatory scan #3).

## Shared assets

- `~/.claude/skills/dev-loop-shared/project-detect.sh`
- `~/.claude/skills/dev-loop-shared/topic-metadata-template.yaml`

## Behavior

### Phase A — Locate topic and validate

1. Resolve topic; verify `(project_root, topic_id)` against cwd (议题 F.4).
2. Load latest `plan-vN.md` and matching `red-team-vN.md`.
3. Verify topic `status: ready-for-integrate`.
4. Verify red-team `verdict ∈ {REVISE, PASS}`. If `BLOCK`, abort: "BLOCK should go back to /dl-plan, not /dl-integrate."
5. Verify `integrate_retry < 2` (议题 D.3). If at limit, abort and escalate to user: "integrate has failed to converge twice; rewrite req or select adjudication principle."

### Phase B — Cross-topic conflict check (议题 F.2 mandatory scan #3)

Scan all other `status ∈ active_conflict_states {planning, pending-red-team, ready-for-integrate, ready-for-execute, executed}` topics under `<plans_dir>/`. For each, read their `affects_files.declared ∪ inferred`.

# 见 ~/.claude/dev-loop-shared/canonical-state-machine-v1.yaml active_conflict_states（去除虚构词 executing，加 executed）

Compute intersection with current topic's `affects_files.declared ∪ inferred`.

**Wiki special** (议题 F.2): if overlap is **only** `wiki/index.md` or `wiki/log.md`, mark as `(shared-append)` — does not block; integrate ordering required but topic can proceed.

For other overlaps:

- Same concept/synthesis/source/entity page in wiki
- Same code file (unless plan-vN.md explicitly declares disjoint regions)

→ set `conflicts_with: [<other-topic-ids>]` in current metadata. Status → `blocked`. Stop and report.

If no blocking overlaps, proceed.

### Phase C — Read red-team verdict and items

Parse red-team-vN.md. Extract:

- `Verdict` (BLOCK / REVISE / PASS — must be REVISE or PASS at this point)
- `P0 Blockers`: list of items with problem / why-blocking / suggested-fix / scope
- `P1 Major Risks`
- `P2 Improvements`
- `Answers To Required Questions`: paired with plan's 必答清单
- `NEED-INFO`: items requiring more info
- `Integration Notes`: codex's hints on what to keep / change / not-execute

If `NEED-INFO` non-empty: pause and ask user to provide info. Do not silently integrate around missing info.

### Phase D — Decision matrix per item

For each P0 / P1 / P2 item, record a decision:

| Item type | Default decision | Override conditions |
|---|---|---|
| P0 | **MUST accept** (block otherwise) | If P0 misreads plan, mark as `[disputed]` with rationale; do not silently reject |
| P1 | **Accept** | Reject if: (a) clearly out-of-scope (b) contradicts user-confirmed Safeguards (c) red-team misread |
| P2 | **Defer** | Accept if: low cost + ready-fix available; otherwise queue to topic `unknowns:` for later |

For each decision, write a one-line rationale. Do not silently drop items.

### Phase E — Generate plan-v(N+1).md

Base: plan-vN.md.

Apply accepted changes per Integration Notes (codex's "应保留 / 应改写" hints). Reject items get a `[rejected-rationale]` annotation in the plan body where the issue would have been.

Bump version: `version: N+1`.

Add `## Changelog v(N) → v(N+1)` section (议题 G — 5th pit: integrate must record what changed):

```markdown
## Changelog v(N) → v(N+1)
### Accepted
- [P0-1] <description> → applied to Op3 / Approach paragraph 2
- [P1-2] <description> → applied to test matrix T4
### Rejected
- [P1-5] <description> — rationale: contradicts Safeguard "raw/ readonly"
### Deferred
- [P2-3] <description> — queued to topic.unknowns for follow-up
```

Update `affects_files.declared` if Operations changed.

Update `必答问题清单`:

- Remove questions codex already answered satisfactorily
- Add new questions arising from integration changes (if any)

Write to `<topic_dir>/plan-v(N+1).md`.

Mark previous `plan-vN.md` frontmatter: add `status: superseded` (议题 D.2).

### Phase F — Hard-copy to plan.md

`cp <topic_dir>/plan-v(N+1).md <topic_dir>/plan.md` (议题 B.3 no symlink).

### Phase G — Update topic metadata

- `updated_at`: now
- `status`:
  - **Default**: `ready-for-execute` (most common path)
  - **If** more than 50% of P1 items were rejected OR new Operations were added that weren't in plan-vN: ask user — "substantial changes; another red-team round?" If yes, status → `pending-red-team` (will trigger plan-v(N+2) ↔ red-team-v(N+1) pairing; check red_team_round still < 3).
- If integrate produces plan-vK and sends it back to red-team (`status: pending-red-team`), keep `red_team_round = K-1` and do not increment it; the previous red-team already completed round K-1. See SSOT red_team_round semantics.
- `canvas.changelog`: append v(N)→v(N+1) summary
- `affects_files.declared`: refreshed from new Operations
- `conflicts_with`: empty (since we passed Phase B)
- `integrate_retry`: same (only bumps if integrate itself fails)

### Phase H — Handoff

Report:

1. New plan path: `<topic_dir>/plan-v(N+1).md` (+ `plan.md` mirror)
2. Changelog summary: X accepted / Y rejected / Z deferred
3. Conflict check result (no conflicts | shared-append on index/log | etc.)
4. Topic status:
   - `ready-for-execute` → next: `/dl-execute`
   - `pending-red-team` → next: `/dl-red-team` (round N+1)
   - `blocked` (only if Phase B blocked) → must resolve other topic first
5. **Do not auto-invoke** next stage.

Stop.

## Guardrails

- **Do not auto-invoke** /dl-execute or /dl-red-team.
- **Do not silently drop** any P0/P1/P2 item — every item gets a decision + rationale.
- **Do not** accept a P0 that contradicts user-confirmed Safeguards without flagging. Flag as `[disputed]` and ask user.
- **Do not** rewrite red-team-vN.md — it is immutable evidence.
- **Do not** skip the cross-topic conflict check — it is mandatory at this stage (议题 F.2).
- **Do not** treat `wiki/index.md` / `wiki/log.md` overlap as blocking — they are shared-append per 议题 F.2.
- **Do not** generate plan-v(N+1) without changelog. Changelog is required (议题 G 5th pit).
- **Do not** answer the user's NEED-INFO items on their behalf — pause and ask.
- If `integrate_retry` reaches 2, escalate to user (议题 D.3); do not silently retry a third time.

## Failure modes (议题 D)

- Red-team verdict was BLOCK at entry → abort, redirect to /dl-plan.
- NEED-INFO present → pause; record `status: blocked-on-info`; resume when user provides.
- Cross-topic blocking conflict → `status: blocked`, `conflicts_with: [...]`; user must complete blocker topic first or manually override.
- Item decision impossible (P0 and Safeguards mutually contradict) → escalate to user with `status: blocked`, `integrate_retry += 1`.
- cwd mismatch with topic.project_root → abort (议题 F.4).
- User aborts mid-integrate → write partial plan-v(N+1).md with `status: aborted` if any changes already applied; otherwise leave plan-vN.md untouched.
