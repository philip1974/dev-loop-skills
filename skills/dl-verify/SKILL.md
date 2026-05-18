---
name: dl-verify
description: Stage 6/6 (final) of the dev-loop workflow. Use only when the user explicitly asks to verify and finalize a tracked topic via phrases like "/dl-verify", "dev-loop:verify", "进入 verify 阶段", or "verify topic NN". Runs acceptance / Norms / Safeguards checks against actual execution, writes verify.md (append-only), optionally promotes decision artifacts to git-tracked locations, and (with user confirmation) creates the final git commit. Highest commit-side-effect risk — NEVER invoke automatically.
---

# /dl-verify — Dev-Loop Verify + Commit (Stage 6/6)

## Do NOT run this skill when

- Topic status is not `executed` (must come through /dl-execute first).
- No `execute-log.md` exists in the topic dir.
- The user is asking for a generic test / lint / commit unrelated to a tracked topic.
- The user says "verify" or "test" in ordinary language without a topic id.
- Another dev-loop stage is already active and this stage was not requested.

If matched, decline.

## Purpose

Stage 6 (final). Verify that execution meets the requirements canvas (Requirements / Norms / Safeguards — 议题 G adoption 5: not just R, also N+S). Append findings to `verify.md`. On pass, optionally promote decision artifacts to git-tracked locations (议题 B.1 "提升机制") and ask user before creating the final git commit.

Has the highest **commit** side-effect — never auto-invoke.

## Shared assets

- `~/.claude/dev-loop-shared/project-detect.sh`
- `~/.claude/dev-loop-shared/topic-metadata-template.yaml`
- `~/.claude/dev-loop-shared/wiki-red-team-checklist.md` (for wiki structure checks)

## Behavior

### Phase A — Locate topic and validate

1. Resolve topic; verify `(project_root, topic_id)` against cwd (议题 F.4).
2. Verify topic `status: executed`.
3. Verify `verify_retry < 2` (议题 D.3). At limit, abort and escalate per 议题 D.1.
4. Read:
   - `req.md` — Requirements / acceptance criteria / Norms / Safeguards / `## Project rules digest`
   - latest `plan-vN.md` — Test/Verification matrix + Operations + affects_files.declared
   - `execute-log.md` — actual execution results
   - topic metadata — `affects_files.executed`

### Phase B — Re-detect project (议题 F.4)

Run `bash ~/.claude/dev-loop-shared/project-detect.sh`. Compare with topic.project_root → mismatch aborts. Also load any `lint-cmd` / `test-cmd` / `typecheck-cmd` declarations from CLAUDE.md.

### Phase C — Build verification matrix

Combine sources:

| Source | Checks |
|---|---|
| req.md acceptance criteria | Each line = one check (議題 1 SOP) |
| plan.md test matrix | Each T<N> row = one check |
| req.md Safeguards | Each item = one check (must NOT be violated) |
| req.md Norms | Each item = one check (议题 G adoption 5) |
| project type | Type-specific automatic checks (see Phase D) |

For each, define how to evaluate (manual inspection vs. command vs. file existence vs. grep).

### Phase D — Type-specific automatic checks

#### `code` project

- Run `<typecheck-cmd>` if declared (e.g. `npm run typecheck`)
- Run `<test-cmd>` if declared (e.g. `npm test`)
- Run `<lint-cmd>` if declared
- Each command's exit code + stderr/stdout summary feeds verify.md

#### `wiki` project

- If `<project_root>/tools/lint_wiki.sh` exists → run it
- Wikilink resolution check: for each new wikilink in `affects_files.executed`, verify target exists
- Source card backlink check (议题 C.5 #6): every new claim's source card must have this page in its `wiki_pages` list
- `wiki/index.md` reachability: every new page must be reachable from index (议题 C.5 #2)
- `wiki/log.md` append-only check: ensure log.md got a new entry (议题 C.5 #2)
- For each new source card: it must reference a `raw/` file (议题 C.4 source rule), and the raw file must be unchanged (議題 C4)
- For each synthesis page change: no direct raw/ reference (議題 C4 — synthesis must go through source cards)

#### `mixed` project

Run both sets of checks above. Use `writeback_policy` from topic metadata to scope wiki checks.

### Phase E — Knowledge-structure checks (议题 C.5 pit #6)

Verify is not just file diff. For wiki/mixed projects:

- New source card has at least one incoming `[[sources/...]]` reference from a synthesis/concept/entity page
- New entity/concept page has incoming wikilinks from related pages
- `wiki/index.md` lists or transitively links to new pages
- No orphan pages introduced

Record gaps as P1 in verify.md (not P0 — orphan can be fixed in a follow-up topic).

### Phase E.5 — Real-test gate (议题 H)

**Run only if** Phase D + Phase E both pass (串联执行 + 并联阻塞 — 议题 H.5). If anything before failed, skip Phase E.5 entirely and go to Phase F.

Read `plan.real_test` from plan-vN.md. Three branches by `status`:

#### Branch 1 — `status: inapplicable`

Verify the `reason` is non-empty and topic genuinely changes no user-visible behavior (cross-check against `affects_files.executed` — if anything under `bin/`, `scripts/`, `src/components/`, `pages/`, or other clearly user-visible paths is touched, escalate to P1 in verify.md: "real_test marked inapplicable but executed files include user-facing paths X, Y"). Record the verdict as `real-test: SKIPPED (inapplicable)` in verify.md and proceed to Phase F.

#### Branch 2 — `status: skipped`

Same as inapplicable but the `reason` should reference deferred follow-up (e.g. "environment not ready, topic NN will cover"). Record as `real-test: SKIPPED (deferred — <reason>)`. Proceed to Phase F.

#### Branch 3 — `status: required` — run the gate

1. **Resolve skill availability per scenario (议题 H Patch H.2-bis)**: for each scenario, compute effective skill = `scenario.skill` if set, else `real_test.skill`. Then check `<project_root>/.codex/skills/<effective_skill>/SKILL.md` and `~/.codex/skills/<effective_skill>/SKILL.md` (project-local takes priority). If any scenario's effective skill is unresolved → **fail gate** with verdict `FAIL-real-test (skill-unavailable: <scenario>:<skill>)`. Per 议题 H.4: do NOT degrade to unit-test-only. Bounce back to /dl-plan or environment setup. Also check `profile_dir` per 议题 H Patch H.7.4: missing on a GUI scenario → record `INCONCLUSIVE-risk: state-not-isolated` warning (advisory only, does not fail).
2. **Open a NEW verifier session** (议题 H.6 — do NOT reuse the execute session). Use `mcp__continuo__terminal_create_session` with `agentLabel: "real-test-verifier-<topic_id>"`. Record `verifier_session_id` to topic metadata.
3. **Send a windowed prompt** to the verifier session. Required content:
   - `MODE: real-test verifier (议题 H). You are not editing project files. You are running the declared real-test skill against the declared scenarios and reporting evidence.`
   - The full `real_test` block from plan-vN.md (yaml verbatim)
   - The execute-log summary + final diff (`git diff --stat` + key file hunks) — file-based context, NOT a chat continuation
   - Explicit rule: "Invoke `$<plan.real_test.skill>`. For each scenario, run the declared command in the declared cwd with the declared terminal/viewport. Execute the declared `steps`. Capture the declared `evidence` (transcript, screenshots, exit code, final screen). Output one block per scenario: `scenario: <name>`, `command: <exact command run>`, `terminal: <cols x rows>`, `steps_executed: [...]`, `observed: [...]`, `evidence_ids: [...]`, `verdict: PASS|FAIL|INCONCLUSIVE`, `verdict_reason: <one line>`. Do NOT modify project files. Do NOT run actions listed under `forbidden` for the scenario. If `forbidden` lists `externally visible` items (form submit / delete / external API) and the scenario nevertheless requires Computer Use, STOP and emit `verdict: INCONCLUSIVE`, `verdict_reason: needs-second-confirmation`."
   - Required sentinel: end with `###REAL-TEST-DONE###` on its own line
4. **Schedule a wakeup** (recommended 270s — within prompt cache TTL).
5. **On wakeup, read the verifier session output**. Look for `###REAL-TEST-DONE###`. If absent within 3 × 270s (≈ 13.5 min, 议题 A.4), mark `real-test: INCONCLUSIVE (no-sentinel)` and proceed to Phase F.
6. **Validate evidence chain** (议题 H.3 — codex is the evidence collector, Claude is the judge):
   - For each declared scenario in `plan.real_test.scenarios`, find the matching verifier output block. **Missing scenario → FAIL**.
   - The block must contain actual execution traces — at minimum: `command`, `terminal` (or viewport), some form of `observed` content. A block with only `verdict: PASS` and no command/output is treated as `INCONCLUSIVE`.
   - For each `expected` item in the scenario, search `observed` (and any cited evidence_id transcripts) for evidence covering it. **Any expected item uncovered → INCONCLUSIVE or FAIL** (FAIL if the observed output contradicts the expected item; INCONCLUSIVE if the evidence is simply absent).
   - For each `forbidden` item, search the transcript for any sign that codex did it anyway. **Forbidden violation → FAIL-safeguard** (this is a Safeguard breach, not a behavior fail — handled per Phase G's FAIL-safeguard row).
   - Check codex did not silently bypass the skill: the transcript must show the skill being invoked (e.g. `$cli-visual-debugger` reference, or skill-specific output markers). **No skill invocation evidence → FAIL** (议题 H.3 越权检测).
   - Check for evidence-of-failure even when codex self-reports PASS: error codes, stack traces, `ERROR`/`FATAL` strings, missing expected text, layout corruption, ANSI reset failures, spinner stuck, exit code ≠ 0. **Self-reported PASS contradicted by evidence → FAIL**. Record in verify.md as `codex verdict contradicted by evidence`.
7. **Aggregate per-scenario verdicts into the gate verdict**:
   - All scenarios PASS (with valid evidence) → gate `PASS`.
   - Any scenario FAIL → gate `FAIL-real-test`.
   - Any scenario INCONCLUSIVE (and no FAIL) → gate `INCONCLUSIVE` (议题 H.7.3 — first-class verdict, also blocks).
   - `INCONCLUSIVE` is permitted to retry once (议题 H.7.3); the next /dl-verify run that produces INCONCLUSIVE on the same scenario set is escalated to `FAIL-real-test`.
8. **Cleanup** (议题 H.7.2): instruct codex to terminate dev servers / background processes / temporary files started during the gate. Record any residue in verify.md. Close the verifier session if no further turns expected (议题 F.5 patch does NOT apply — verifier sessions are short-lived and topic-scoped, do not host-wide reuse).

#### Output of Phase E.5

A `real-test` block ready to be embedded in verify.md (Phase F schema below):

```markdown
### Real-test gate (议题 H)
- Skill: <plan.real_test.skill>  (resolved: project-local / global / unavailable)
- Verifier session: <session_id>
- Per-scenario:
  | Scenario | Verdict | Evidence ids | Notes |
  |---|---|---|---|
  | <name> | PASS / FAIL / INCONCLUSIVE | <ids> | <one line> |
- Gate verdict: PASS | FAIL-real-test | INCONCLUSIVE
- Hallucinated-pass detected: yes / no
- Cleanup: <residue or "clean">
- Artifacts retained (议题 H.7.1): transcript refs, terminal/viewport params, key observations
```

### Phase F — Write verify.md (append-only — 议题 D.2)

Path: `<topic_dir>/verify.md`. If exists, append a new run section; do not overwrite.

Schema:

```markdown
## Verify run <run_index> — <ISO timestamp>

### Acceptance criteria (from req.md)
| AC# | Description | Result | Evidence |
|---|---|---|---|
| AC1 | <criterion> | PASS / FAIL | <command output excerpt / file path / line> |

### Test matrix (from plan-vN.md)
| T# | Test | Result | Evidence |
| T1 | ... | PASS | ... |

### Safeguards check (议题 G adoption 5)
| ID | Safeguard | Status (NOT violated?) | Evidence |
| S1 | raw/ unchanged | OK | git diff --stat raw/ shows nothing |

### Norms check
| N# | Norm | Status | Evidence |

### Type-specific (code / wiki / mixed)
- <typecheck-cmd output / lint result / wikilink check / etc.>

### Knowledge structure (wiki / mixed only)
- Source card backlinks: OK / GAP <details>
- Index reachability: OK / GAP
- Orphan check: OK / GAP

### Real-test gate (议题 H — embed block from Phase E.5)
<from Phase E.5 — skill / verifier session / per-scenario table / gate verdict / cleanup / artifacts>

### Verdict
PASS | FAIL-behavior | FAIL-safeguard | FAIL-norm | FAIL-real-test | INCONCLUSIVE
- Reason: <one line>
```

### Phase G — Handle failure (议题 D.1)

| Failure class | Action |
|---|---|
| **FAIL-behavior** (acceptance criterion fails, but Norms/Safeguards OK) | `status: blocked`, `verify_retry += 1`. Suggest /dl-execute (small fix) or /dl-plan (deep). Per 议题 D.1: small偏差 → execute, 方案性失败 → plan. |
| **FAIL-safeguard** (Safeguard tripped — `raw/` changed, fake source, etc.) | `status: blocked`. **Suggest /dl-req or /dl-plan**, NOT /dl-execute (议题 D.1: 约束违反不绕过执行码). Boundary error → req. Strategy error → plan. |
| **FAIL-norm** (e.g. missing frontmatter, log not appended) | `status: blocked`. Suggest /dl-plan (strategy missing the norm) or /dl-execute (small format fix). |
| **FAIL-real-test** (议题 H — real-test scenarios failed OR codex verdict contradicted by evidence OR forbidden violation) | `status: blocked`, `verify_retry += 1`. Sub-classify: behavior偏差 → /dl-execute；验收场景错 → /dl-plan；越权或 forbidden 触发 → treat as FAIL-safeguard (route to /dl-req or /dl-plan). |
| **INCONCLUSIVE** (verify tool itself failed — 议题 D.5 — OR real-test gate INCONCLUSIVE — 议题 H.7.3) | Mark `verification-inconclusive`. Do not auto-block. For real-test INCONCLUSIVE: allow ONE retry; second consecutive INCONCLUSIVE on the same scenario set escalates to FAIL-real-test. Ask user whether to retry or manually verify. |

On any failure, **do not commit**.

### Phase H — Promotion decision (议题 B.1 提升机制)

If verdict is `PASS`:

Identify candidates for promotion from `.claude/dev-loop/<topic_dir>/` to git-tracked locations:

- **Decision artifacts**: did this topic make a noteworthy architectural / process / wiki-rule decision? → suggest writing to `docs/decisions/<NN>-<slug>.md` or `wiki/synthesis/<slug>.md`.
- **For wiki project**: any new source cards / concept pages / synthesis pages that should remain in `wiki/` (these were already written there during execute — verify just confirms).
- **For code project**: any post-mortem learnings → `docs/decisions/` ADR.

**Ask user explicitly** which promotions to do. Don't auto-promote.

If user confirms a promotion, copy/write the clean version to the chosen path. The original `.claude/dev-loop/` artifacts stay as audit trail (not deleted — 议题 D.2 file-as-truth).

### Phase I — Final commit (with user confirmation)

If verdict is `PASS` and topic has changes in `affects_files.executed` (verify via `git status --porcelain`):

1. Ask user: "ready to commit?"

2. Build commit message:

```
<topic_id>: <one-line summary from req.md Requirements>

<2-4 lines from plan.md Overview>

Touched: <file count> files
Acceptance: <N> criteria PASS
Safeguards: all preserved (raw/, sources, norms)
Refs: <topic_dir>/req.md, plan-vN.md, red-team-vN.md, verify.md
```

3. On user confirm:

   ```bash
   git add <affects_files.executed list — NOT scratch state>
   git commit -m "<message via heredoc>"
   ```

   Do **NOT** include `.claude/dev-loop/` files in commit (议题 B.1 default not入 git).
   Do **NOT** auto `git push`.

4. Record commit hash to `verify.md` and `topic metadata`:
   ```yaml
   committed_at: <ISO>
   commit_hash: <sha>
   status: done
   ```

If user declines commit, leave working tree as-is. Topic stays in `executed` status (not `done`). User can re-run /dl-verify later or commit manually.

### Phase J — Final report

Report:

1. Verdict + summary
2. Files touched
3. Promotions made (if any)
4. Commit hash (if committed)
5. **Topic done**: status `done`, audit trail in `<topic_dir>/`

If failure: which class + suggested next stage + retry counter status.

Stop.

## Guardrails

- **Do not auto-commit**. Always ask user first.
- **Do not include `.claude/dev-loop/` in git** unless promotion explicitly chose a git-tracked path (议题 B.1).
- **Do not `git push`** automatically (议题 E execute side-effects).
- **Do not auto-promote** artifacts. User decides what gets promoted.
- **Do not skip Safeguards / Norms checks** — they are mandatory per 议题 G adoption 5.
- **Do not** overwrite `verify.md`. Append only.
- **Do not** treat verify tool failure as project failure (议题 D.5 distinguish `verification-inconclusive`).
- **Do not** fix issues directly in /dl-verify. This skill is read-only on project files (except for promotion writes). Fixes go back to /dl-execute or /dl-plan.
- **Do not** commit if any FAIL.
- For wiki projects, **do not** skip knowledge-structure checks (议题 C.5 #6) — file diff alone is insufficient.
- **Do not** trust codex's self-reported real-test verdict (议题 H.3). Claude validates the *evidence chain*, not the verdict line. A `verdict: PASS` block with no `command` / `observed` / `evidence_ids` is `INCONCLUSIVE`, not PASS.
- **Do not** reuse the execute session for the real-test gate (议题 H.6). Always open a new verifier session via `mcp__continuo__terminal_create_session`. 议题 F.5 host-wide reuse rule does NOT apply here.
- **Do not** degrade a `FAIL-real-test (skill-unavailable)` to unit-test-only (议题 H.4). The plan declared `real_test.status: required`; missing skill means the verify environment is incomplete, not that the gate is optional.
- **Do not** suppress `INCONCLUSIVE` to PASS just to commit. INCONCLUSIVE blocks verify; only after a second consecutive INCONCLUSIVE on the same scenarios is the gate escalated to FAIL (议题 H.7.3).
- **Do not** skip the real-test cleanup step (议题 H.7.2). Dev servers / open ports / cached credentials started during the gate must be terminated or explicitly marked as residue.

## Failure modes (议题 D)

- Acceptance fail (small) → status: blocked → /dl-execute.
- Acceptance fail (deep) → status: blocked → /dl-plan.
- Safeguard violation → status: blocked → /dl-req (boundary) or /dl-plan (strategy). Not /dl-execute.
- Norm violation → status: blocked → /dl-plan (often missed in plan) or /dl-execute (small fix).
- Verify tool itself fails → `verification-inconclusive`, do not block; ask user.
- Real-test skill unavailable (议题 H.4) → `FAIL-real-test (skill-unavailable)`; bounce to /dl-plan or environment setup; do NOT degrade to unit-test-only.
- Real-test FAIL → status: blocked → /dl-execute (behavior offset) / /dl-plan (scenario error) / /dl-req (Safeguard or forbidden violation).
- Real-test INCONCLUSIVE (议题 H.7.3) → not auto-blocked first time; allow ONE retry; second consecutive INCONCLUSIVE escalates to FAIL-real-test.
- Real-test verdict contradicted by evidence (codex self-reports PASS but transcript shows failure) → Claude overrides to FAIL; record `codex verdict contradicted by evidence` in verify.md.
- Real-test forbidden violation (议题 H.4 — codex performed a `forbidden` action, especially `externally visible`) → treat as FAIL-safeguard; route per safeguard handling.
- `verify_retry` reaches 2 → escalate; do not silently try again.
- User declines commit → leave at `executed` status; user can resume.
- User aborts mid-verify → append partial verify.md section with `aborted: true`; status: `aborted` + `last_stage: verify`.
- cwd mismatch with topic.project_root → abort (议题 F.4).

## Notes

- This is the only skill that touches git for the topic (议题 E disable-auto enforced as a result).
- Promotion writes happen here, not /dl-execute (议题 B.1: integrate or verify generates clean version).
- After /dl-verify success with commit, topic lifecycle is complete. Re-running on the same topic is allowed (re-verify after follow-up fixes) but commit only happens once.
