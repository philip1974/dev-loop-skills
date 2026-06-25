#!/usr/bin/env bash
# sync.sh — keep this repo and the live ~/.claude install in sync.
#
# The live skills run from ~/.claude (independent copies, NOT symlinks), so the
# repo and live drift unless synced. This script makes sync one command.
#
#   ./sync.sh status    # show per-file SAME / DIFFERENT / MISSING (default)
#   ./sync.sh capture   # live  -> repo   (capture edits made in ~/.claude)
#   ./sync.sh install   # repo  -> live   (deploy repo as the source of truth)
#
# Authoritative file list = whatever exists under repo skills/ and shared/.
# Add a new skill/shared file to the repo once; this script then tracks it.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LIVE_SKILLS="$HOME/.claude/skills"
LIVE_SHARED="$HOME/.claude/dev-loop-shared"

CMD="${1:-status}"

# Build the (repo_path, live_path) pairs from what the repo tracks.
pairs() {
  # skills: repo/skills/<name>/<file>  <->  ~/.claude/skills/<name>/<file>
  if [ -d "$REPO_DIR/skills" ]; then
    while IFS= read -r f; do
      rel="${f#"$REPO_DIR/skills/"}"
      printf '%s\t%s\n' "$f" "$LIVE_SKILLS/$rel"
    done < <(find "$REPO_DIR/skills" -type f)
  fi
  # shared: repo/shared/<file>  <->  ~/.claude/dev-loop-shared/<file>
  if [ -d "$REPO_DIR/shared" ]; then
    while IFS= read -r f; do
      rel="${f#"$REPO_DIR/shared/"}"
      printf '%s\t%s\n' "$f" "$LIVE_SHARED/$rel"
    done < <(find "$REPO_DIR/shared" -type f)
  fi
}

same=0; diff_n=0; miss=0
while IFS=$'\t' read -r repo live; do
  case "$CMD" in
    status)
      if [ ! -f "$live" ]; then echo "MISSING(live)  ${repo#"$REPO_DIR/"}"; miss=$((miss+1))
      elif cmp -s "$repo" "$live"; then echo "SAME           ${repo#"$REPO_DIR/"}"; same=$((same+1))
      else echo "DIFFERENT      ${repo#"$REPO_DIR/"}"; diff_n=$((diff_n+1)); fi
      ;;
    capture)  # live -> repo
      if [ -f "$live" ]; then mkdir -p "$(dirname "$repo")"; cp "$live" "$repo"; fi
      ;;
    install)  # repo -> live
      mkdir -p "$(dirname "$live")"; cp "$repo" "$live"
      ;;
    *) echo "usage: ./sync.sh [status|capture|install]" >&2; exit 2;;
  esac
done < <(pairs)

if [ "$CMD" = status ]; then
  echo "----"
  echo "SAME=$same DIFFERENT=$diff_n MISSING=$miss"
  [ $((diff_n+miss)) -eq 0 ] && echo "repo and live are in sync." || echo "out of sync — run ./sync.sh capture (live->repo) or install (repo->live)."
fi
if [ "$CMD" = capture ]; then echo "captured live -> repo. Review with: git -C \"$REPO_DIR\" status && git diff"; fi
if [ "$CMD" = install ]; then echo "installed repo -> live (~/.claude)."; fi
exit 0
