# Intent Lock Template

Single source for the dev-loop Intent Lock format. Referenced by `dl-req`,
`dl-plan`, `dl-red-team`, and `dl-req-mvp`.

## Section schema

Use this schema for full Intent Lock sections.

### User-facing outcome

1-2 lines describing what the user can do, see, decide, or trust after the
change.

### This should feel like

1 line describing the intended user-facing shape, tone, density, or workflow
feel.

### This should NOT become

1 line naming the most likely wrong shape or overreach.

### Positive / Anti-examples

- Positive examples: concrete examples or references that point toward the
  intended shape.
- Anti-examples: concrete examples or neighboring features that must not be
  copied or implemented.
- Every anti-example MUST include `because <reason>`.

Example:

```markdown
- Anti-example: not an auto-executor because this topic only needs advisory
  discovery and must preserve disable-auto stage boundaries.
```

### Acceptance samples

Use Given / When / Then form. Each sample should map to an executable or
verifiable gate whenever possible.

```markdown
- Given <state/input/context>
  When <action/command/stage>
  Then <observable expected result>
```

### Kill criteria

List conditions that mean the implementation drifted from intent. If any kill
criterion appears, verify should fail or red-team should block.

## 分层（按 complexity）

### micro

Use only 3 lines:

```markdown
Intent: <one sentence>
Not-doing: <one sentence>
Acceptance: <one concrete check>
```

Do not run the B choice prompt. Do not write the full Intent Lock section.

### standard

Use lightweight Intent Lock. It should cost at most 1 extra user turn.

The B choice prompt may be used, but it MUST include the escape option first:

```text
D 都不是，我要…
```

### major

Use full Intent Lock plus the B choice prompt.

Choice candidates must be:
- mutually exclusive;
- short;
- neutral, with no recommended option or leading phrasing.

End with:

```text
哪点不像你脑子里的目标？
```

### mvp

For `dl-req-mvp`, derive `## Intent Lock` from existing 议题 J anchors without
adding another user round:

- Outcome <- pitch + MVP Scope
- Positive examples <- kept references
- Anti-examples <- V1 out + Anti-scope + forbidden_mimic_points
- Acceptance samples <- Acceptance Signals
- Kill criteria <- Safeguards + Anti-scope

## autonomy_readiness rubric

`autonomy_readiness` is an enum. It must be recomputed downstream if mapping
quality changes.

### low

- No acceptance samples; or
- acceptance samples exist but are not mapped to checks.

### medium

- Every acceptance sample maps to a manual, wiki, or real_test check; and
- not every mapped check is executable.

### high

- Every acceptance sample maps to an executable test, CI check, real_test, or
  wiki-lint command; and
- every mapped check has an owner gate.

### blocked

- Intent Lock is internally contradictory; or
- required Intent Lock content is missing for a mode that requires it.

## 下游映射表

| Intent Lock field | Downstream consumer | Required use |
|---|---|---|
| Acceptance samples | Test matrix / real_test scenarios / wiki-check rows | Each sample needs a mapped check or an Unknown / req bounce |
| Anti-examples | red-team P0/P1 checks | Violating anti-scope is P0 if it changes scope or safety; otherwise P1 |
| Kill criteria | verify fail conditions | If observed, verification fails or routes to the right earlier stage |
| This should feel like | UX / interaction / density constraints | Plan must preserve this in Approach and Operations |
| User-facing outcome | PR summary / final report | Use as the plain-language outcome claim |

## wiki-check 映射类型

For wiki projects, acceptance samples may map to these verifiable checks:

- source card exists and is linked;
- every factual claim has `[[sources/...]]` or `[unverified]`;
- `wiki/index.md` contains the new or updated page;
- `wiki/log.md` is append-only;
- wikilink resolves;
- no `raw/` diff;
- lint report is clean;
- grep finds the expected statement.

## 向后兼容 tiering

Old req files may not contain `## Intent Lock`.

### micro / standard old req

Continue with:

- `autonomy_readiness: low`;
- warning: `建议补 Intent Lock`;
- no hard contract failure.

### major old req

Default behavior: block in `dl-plan` and route back to `/dl-req` to add Intent
Lock.

User may explicitly override. If overridden, `dl-plan` must generate:

```markdown
## Intent Lock (inferred) [unverified]
```

The inferred section is risk-bearing context, not user-confirmed truth.
`dl-red-team` must treat it as a risk and check whether plan claims exceed the
inferred intent.
