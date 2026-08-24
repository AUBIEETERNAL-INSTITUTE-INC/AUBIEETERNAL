#!/bin/bash
# Runs frequently via cron on the Ryzen machine. Pulls a fixed read-only
# diagnostic bundle from the robot over the locked-down aubie_suggest_key -
# authorized_keys on the robot forces it to always run
# aubie_diag_readonly.sh regardless of what command is actually sent here,
# so this can never execute anything destructive on the robot.
#
# Saves every snapshot, healthy or not - this is the "we missed a month and
# everything's dead" safety net. Even total robot failure still leaves a
# trail of its last known states on THIS machine, not just on the robot's
# own (possibly now-unreachable) disk. No automatic deletion: plain-text
# snapshots at this size/interval run well under 50MB/month, so retention
# just isn't worth trading away backtrack-ability for.
set -u
DIR=/home/aubieeternal/AUBIEETERNAL/spotmicro_dog
SNAP_DIR="$DIR/diag_snapshots"
TS=$(date -u +%Y-%m-%dT%H%M%SZ)
SNAP_FILE="$SNAP_DIR/$TS.log"
LATEST_LINK="$SNAP_DIR/latest.log"
PREV_FILE=""
[ -L "$LATEST_LINK" ] && PREV_FILE=$(readlink -f "$LATEST_LINK" 2>/dev/null || true)

# The argument here is ignored server-side (forced command in
# authorized_keys) - kept only for readability of what this connection is for.
RESULT=$(timeout 20 ssh -i "$HOME/.ssh/aubie_suggest_key" -o ConnectTimeout=8 -o BatchMode=yes arduino@100.66.110.65 "diag" 2>&1)
RC=$?

{
  echo "# snapshot_time_utc: $TS"
  echo "# ssh_exit_code: $RC"
  echo "$RESULT"
} > "$SNAP_FILE"

ln -sf "$SNAP_FILE" "$LATEST_LINK"

# Cheap trigger check for aubie_suggest.sh: is there something NEW worth
# spending an actual Claude API call to diagnose? Writes the new lines to
# .trigger_reason and exits 0 if so; exits 1 (and clears the file) if this
# snapshot looks like more of the same as last time.
if [ "$RC" -ne 0 ]; then
  echo "robot unreachable over SSH (exit $RC) - see $SNAP_FILE" > "$SNAP_DIR/.trigger_reason"
  exit 0
fi

if [ -n "$PREV_FILE" ] && [ -f "$PREV_FILE" ]; then
  PATTERN='TimeoutError|unhealthy-attempting-remediation|repair-failed|repair-command-exited-nonzero|ERROR|Traceback'
  NEW_ERRORS=$(comm -13 \
    <(grep -E "$PATTERN" "$PREV_FILE" 2>/dev/null | sort -u) \
    <(grep -E "$PATTERN" "$SNAP_FILE" 2>/dev/null | sort -u))
  if [ -n "$NEW_ERRORS" ]; then
    echo "$NEW_ERRORS" > "$SNAP_DIR/.trigger_reason"
    exit 0
  fi
fi
rm -f "$SNAP_DIR/.trigger_reason"
exit 1
