#!/usr/bin/env bash
# project-detect.sh — dev-loop project root / type / plans-dir detector
#
# Used by: dl-req, dl-plan, dl-red-team, dl-integrate, dl-execute, dl-verify
# Reference: wiki/synthesis/dev-loop-design.md 议题 B.5 / F.4
#
# Outputs stdout as key=value lines:
#   project_root=/abs/path
#   project_type=code|wiki|mixed|unknown
#   has_project_doc=yes|no
#   plans_dir=/abs/path
#
# Usage:
#   eval "$(bash ~/.claude/dev-loop-shared/project-detect.sh)"
#   echo "$project_root / $project_type / $plans_dir"

set -e

# 1. Project root (议题 F.4)
if root=$(git rev-parse --show-toplevel 2>/dev/null); then
  :
else
  root="$(pwd)"
fi
printf 'project_root=%s\n' "$root"

# 2. Project type (议题 B.5)
has_wiki=no
has_code=no
[[ -f "$root/wiki/index.md" || -f "$root/wiki/log.md" || -d "$root/raw" ]] && has_wiki=yes
for marker in package.json pyproject.toml go.mod Cargo.toml pom.xml build.gradle; do
  [[ -f "$root/$marker" ]] && has_code=yes && break
done

if [[ "$has_wiki" == "yes" && "$has_code" == "yes" ]]; then
  ptype=mixed
elif [[ "$has_wiki" == "yes" ]]; then
  ptype=wiki
elif [[ "$has_code" == "yes" ]]; then
  ptype=code
else
  ptype=unknown
fi
printf 'project_type=%s\n' "$ptype"

# 3. Project doc presence
if [[ -f "$root/CLAUDE.md" || -f "$root/AGENTS.md" ]]; then
  printf 'has_project_doc=yes\n'
else
  printf 'has_project_doc=no\n'
fi

# 4. plans-dir (议题 B.2)
# Priority: project doc explicit declaration > existing standard dirs > default
declared=""
for doc in "$root/CLAUDE.md" "$root/AGENTS.md"; do
  [[ -f "$doc" ]] || continue
  declared=$(grep -E "^[[:space:]]*dev_loop\.plans_dir[[:space:]]*[:=]" "$doc" 2>/dev/null \
    | head -1 \
    | sed -E 's/^[^:=]*[:=][[:space:]]*//' \
    | tr -d '"'"'")
  [[ -n "$declared" ]] && break
done

if [[ -n "$declared" ]]; then
  case "$declared" in
    /*) plans_dir="$declared" ;;
    *)  plans_dir="$root/$declared" ;;
  esac
elif [[ -d "$root/.claude/dev-loop" ]]; then
  plans_dir="$root/.claude/dev-loop"
elif [[ -d "$root/.codex/dev-loop" ]]; then
  plans_dir="$root/.codex/dev-loop"
elif [[ -d "$root/docs/plans" ]]; then
  plans_dir="$root/docs/plans"
else
  plans_dir="$root/.claude/dev-loop"
fi
printf 'plans_dir=%s\n' "$plans_dir"
