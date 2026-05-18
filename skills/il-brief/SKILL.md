---
name: il-brief
description: Stage 2/4 of the il-loop workflow. Use only when the user explicitly asks to write a brief for a triaged normal-path issue via phrases like "/il-brief", "il-loop:brief", "为 issue NN 写 brief". Writes a design brief, spawns a per-issue codex session via continuo, runs a single-round red-team, and integrates feedback in place with an auditable changelog. Skips itself for trivial-path issues (those go directly from triage to fix). Do NOT invoke without a prior /il-triage having written the issue file with path=normal.
---

# /il-brief — Issue-Loop Brief + Red-Team (Stage 2/4)

Canonical design: `.claude/dev-loop/il-loop-design-v2.md` §5.2. The spec is authoritative; this skill executes it.

## Do NOT run this skill when

- The issue file does not yet exist (`/il-triage` was not run).
- The issue's `path` is `trivial` or `escalated` — only `normal` reaches /il-brief.
- The issue's `status` is not `triage` or `brief`.
- Another il-loop command is holding the issue-NN lock.

If any match, decline and suggest the right action.

## Purpose

Stage 2 of 4 (normal path only). Write `## Brief`, snapshot a pre-integration copy, spawn a codex session bound to this issue, run one independent red-team round, integrate feedback in place with a per-item changelog. Stops at status=brief. Does not auto-invoke `/il-fix`.

## Pre-checks

1. File `.claude/issues/<NN_PADDED>-*.md` exists.
2. Frontmatter `path == normal` and `status ∈ {triage, brief}`.
3. TTY present.
4. continuo MCP server reachable (a `terminal_list_sessions` call must succeed).

## Behavior

### Phase A — Acquire issue-NN lock

Same algorithm as `/il-triage` Phase A. Lock content's `command` field is `/il-brief`.

### Phase B — Claude writes the Brief

Read the issue file's `## Issue` and `## Triage decision`. Then draft the Brief with four subsections:

```markdown
## Brief

### 背景 / Background
<1-3 paragraphs summarizing the issue and existing context Claude verified>

### 方案 / Approach
<1-2 paragraphs describing the chosen approach, NOT alternatives>

### 操作清单 / Operations
1. <file path>: <one-line change>
2. <file path>: <one-line change>
...

### Risks
- <known unknowns and rollback notes>
```

Operations MUST be ordered, file-scoped, and concrete enough that another agent could execute them.

### Phase C — Snapshot pre-integration Brief

Per spec §12 default 2: snapshot only on first integration. Before sending to codex, copy the entire Brief block into a collapsed details block placed ABOVE `## Brief`:

```markdown
## Brief (pre-integration)

<details>
<summary>Original Brief written by Claude before red-team integration (immutable)</summary>

<verbatim Brief content>

</details>
```

This block is never edited again. Subsequent changelog rounds amend `## Brief` only.

### Phase D — Spawn codex session

Use the continuo MCP tool `terminal_create_session`:
- `name`: `il-<NN>`
- `agentLabel`: `il-<NN>`
- `cwd`: current project root
- `autorun`: `codex`

Record returned `session_id` in the issue file's frontmatter. Wait for codex to finish startup (look for prompt; max 30s). If startup fails, abort, release lock, message user.

### Phase E — Send neutral red-team prompt

Build a prompt containing ONLY:
- The verbatim `## Issue` body
- The current `## Brief` body
- A request for P0/P1/P2 findings with reasons

Do NOT include:
- Claude's rationale for the approach
- Alternatives considered but rejected
- Any phrase suggesting Claude's preference
- The pre-integration snapshot

Send via continuo `terminal_send_text` followed by `terminal_press_key enter`.

Wait for codex to finish (poll `terminal_read_output` with cursor). Heuristic: 90s initial, then 60s polls; abort after 5 min of no new output.

### Phase F — Parse and integrate

Strip ANSI noise from the codex response. Extract items into P0/P1/P2 buckets.

For each item, Claude decides accept / reject / defer with a one-line reason. Apply:
- **accept**: edit the relevant operation in `## Brief` in place (do NOT add a new section)
- **reject**: do not modify Brief; note in changelog with reason
- **defer**: move to a `### Deferred` subsection at bottom of Brief

Append to (create if missing) `## Brief changelog`:

```markdown
## Brief changelog
- v1 → v2 (2026-05-12T10:15:00Z): accepted [P0.1, P0.3], rejected [P1.2: <reason>], deferred [P2.4]
```

Increment vN. If this is the first changelog entry, use `v1 → v2`.

### Phase G — Write Red-team section

```markdown
## Red-team (codex)
- session_id: term-xxx
- transcript ref: seq=[<start>, <end>]
- P0: ...
- P1: ...
- P2: ...
```

`start_seq` and `end_seq` come from continuo's cursor. This makes the raw transcript reproducible.

### Phase H — Update frontmatter, release lock

- `status: brief`
- `session_id: term-xxx` (set in Phase D)
- `updated_at: <now ISO>`

Release lock. Session is kept alive for `/il-fix`.

Report to user:
1. Brief integration summary (counts of accept/reject/defer)
2. Suggested next step: `/il-fix <NN>` (do NOT auto-invoke)

## Guardrails

- Do not include any Claude立场 / rationale in the prompt sent to codex.
- Do not edit `## Brief (pre-integration)` after first write.
- Do not skip the changelog row, even if 0 items were accepted (record "accepted [], rejected all" with reasons).
- Do not reuse a codex session from another issue.
- If codex returns no items at all, treat as suspicious — ask user to confirm or retry rather than auto-accept the Brief.
- Lock release on EXIT/INT/TERM must include a check: if status was bumped to `brief` in this run, keep the session alive; if not, leave session as-is.

## Failure modes

- continuo unreachable → abort, release lock; do NOT spawn session
- codex session creation fails → abort, release lock
- codex session times out (no output 5 min) → ask user: extend wait, kill session and abort, or accept partial output
- Parsing red-team output fails → keep raw output in `## Red-team (codex).raw_block` for human review; status stays `triage`; release lock
- User abort during integration → preserve pre-integration Brief; if no changelog row was written, status stays `triage`
