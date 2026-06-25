#!/usr/bin/env bash
# Install helper for loop-scout launchd plist.
#
# This script is a user-invoked install step. It only copies the plist into
# ~/Library/LaunchAgents and prints the launchctl commands the user may run
# manually. It does not bootstrap/load/enable the job.
#
# If needed after sync/install, make executable with:
#   chmod +x ~/.claude/dev-loop-shared/install-launchd.sh

set -euo pipefail

SRC="$HOME/.claude/dev-loop-shared/com.devloop.loop-scout.plist"
DEST_DIR="$HOME/Library/LaunchAgents"
DEST="$DEST_DIR/com.devloop.loop-scout.plist"

mkdir -p "$DEST_DIR"
cp "$SRC" "$DEST"

cat <<EOF
Copied:
  $SRC
to:
  $DEST

To load it manually, inspect the plist first, then run:
  launchctl bootstrap gui/$(id -u) "$DEST"
  launchctl enable gui/$(id -u)/com.devloop.loop-scout

This script did not run launchctl.
EOF
