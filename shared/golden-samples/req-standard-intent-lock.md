---
title: Standard Req Intent Lock Golden Sample
type: golden
profile: standard
created: 2026-06-26
template: ~/.claude/dev-loop-shared/intent-lock-template.md
---

<!-- Standard profile live sample for a `## Intent Lock` section. Use this as a reference when /dl-req writes Intent Lock and when /dl-plan copies a verbatim Intent Lock excerpt. -->

## Intent Lock

### User-facing outcome

Using `/dl-req` produces a lightweight calibration at the end: the agent plays back its concrete understanding of the user's intent with a brief outcome, examples, anti-examples, and acceptance samples. The user reacts to a specific object instead of abstract scope prose.

### This should feel like

"The agent shows what it thinks I mean, and I can quickly say yes or correct the 1-3 important misses."

### This should NOT become

Another long abstract questionnaire, a new heavyweight skill, a complete form-filling ritual, or a process that makes micro topics feel heavy.

### Positive / Anti-examples

- Positive: `/dl-req` asks one final calibration question for a standard topic, then writes a compact Intent Lock with concrete examples.
- Positive: `/dl-plan` copies the Intent Lock excerpt verbatim and maps every acceptance sample to a Test matrix row, real_test scenario, or wiki-check.
- Anti-example: Creating a separate `dl-intent-lock` skill because it adds another entry point instead of improving the existing req flow.
- Anti-example: Putting the first Intent Lock work in `/dl-plan` because plan already starts solidifying drift into implementation choices.
- Anti-example: Writing only a design note while leaving skill behavior unchanged because the pain is in the actual `/dl-req` interaction.

### Acceptance samples

1. Given a standard topic runs `/dl-req`
   When Phase D.5 Intent Lock calibration completes
   Then `req.md` contains `## Intent Lock` with the five required blocks, at least one Given/When/Then acceptance sample, and at least one anti-example with `because`, with no more than one extra user turn.

2. Given `complexity=micro`
   When `/dl-req` reaches the Intent Lock branch
   Then it writes only the 3-line micro form: Intent, Not-doing, and Acceptance, without forcing the full five-block Intent Lock.

3. Given `/dl-plan` reads a req with `## Intent Lock`
   When it writes `plan-vN.md`
   Then the plan includes a verbatim Intent Lock excerpt and maps every acceptance sample to a Test matrix row, real_test scenario, or wiki-check; unmapped samples are marked Unknown or routed back to `/dl-req`.

4. Given `/dl-red-team` reviews a plan
   When Operations violate an anti-example or kill criterion from the plan's Intent Lock excerpt
   Then the review marks the issue P0.

5. Given every acceptance sample maps to an executable command or owner gate
   When `/dl-plan` scores autonomy readiness
   Then `autonomy_readiness` can be `high`; otherwise it is downgraded to `medium` or `low`.

### Kill criteria

- micro topics are forced through the full Intent Lock section.
- A third req-like skill is added for intent calibration.
- standard topics require more than one extra calibration turn.
- acceptance samples stay as abstract prose rather than Given/When/Then checks.
- `/dl-red-team` must read `req.md` instead of auditing the plan's verbatim Intent Lock excerpt.
