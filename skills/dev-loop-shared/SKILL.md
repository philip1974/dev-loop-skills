---
name: dev-loop-shared
description: Dependency bundle, NOT a user-invoked workflow — never invoke directly. Holds the shared support files (project-detect.sh, topic-metadata-template.yaml, reasons-takeaways.md, codex-red-team-prompt-template.md, wiki-red-team-checklist.md, req-contract-v1.yaml) that the dev-loop (dl-*) and il-loop (il-*) skills read from ~/.claude/skills/dev-loop-shared/. Install this once alongside any dl-* / il-* skill.
metadata:
  author: philip1974
  version: "1.0.0"
---

# dev-loop-shared

Shared support files for the **dev-loop** (`dl-*`) and **il-loop** (`il-*`) skills.
This is a **dependency bundle**, not a workflow — there is nothing to invoke here.

When installed through the Continuo skills manager it lands at
`~/.claude/skills/dev-loop-shared/`, which is exactly where the sibling skills
expect to find these files.

## Contents

| File | Used by | Purpose |
|---|---|---|
| `project-detect.sh` | dl-req, dl-plan, dl-execute, dl-integrate, dl-verify, dl-red-team | Detect `project_root` / `project_type` / plans-dir |
| `topic-metadata-template.yaml` | dl-req, dl-plan, dl-execute, dl-integrate, dl-verify | Topic frontmatter schema (incl. req-contract fields) |
| `reasons-takeaways.md` | dl-req, dl-plan, dl-red-team | REASONS adoption rules + 3-tier complexity |
| `codex-red-team-prompt-template.md` | dl-red-team | Codex red-team prompt template |
| `wiki-red-team-checklist.md` | dl-red-team, dl-verify | Wiki structure red-team checklist |
| `req-contract-v1.yaml` | dl-req, dl-req-mvp | Authority for req field names + golden req sample |

## Install

Install this entry once. Any `dl-*` / `il-*` skill that references
`~/.claude/skills/dev-loop-shared/...` will then resolve its dependencies.
