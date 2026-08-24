#!/bin/bash
# Runs after aubie_snapshot.sh (chained in the same cron entry) - only does
# anything if that script found something new (.trigger_reason exists).
#
# Invokes Claude Code itself, headless, to draft a suggested diagnosis -
# mirroring what a live session would do, but strictly read-only and
# review-only: --permission-mode dontAsk (NOT --dangerously-skip-permissions,
# which would silently bypass --allowedTools entirely and grant full Bash)
# means only the tools listed in --allowedTools can run; anything else is
# auto-denied instead of hanging or being silently permitted. It's never
# given Write/Edit access at all - its analysis is just its final printed
# response, captured here via shell redirection, so there's no path for it
# to touch the filesystem beyond the one pre-approved SSH command.
set -u
DIR=/home/aubieeternal/AUBIEETERNAL/spotmicro_dog
SNAP_DIR="$DIR/diag_snapshots"
RUN_DIR="$DIR/suggestion_runs"
TRIGGER_FILE="$SNAP_DIR/.trigger_reason"
INDEX_FILE="$DIR/suggestions_index.log"

[ -f "$TRIGGER_FILE" ] || exit 0

TS=$(date -u +%Y-%m-%dT%H%M%SZ)
RUN_LOG="$RUN_DIR/$TS.log"
TRIGGER_REASON=$(cat "$TRIGGER_FILE")
rm -f "$TRIGGER_FILE"  # consumed - prevents a stale reason re-firing on a later tick
LATEST_SNAPSHOT="$SNAP_DIR/latest.log"
SSH_KEY="$HOME/.ssh/aubie_suggest_key"

PROMPT="You are reviewing a diagnostic snapshot from an automated monitor for a home robot (SpotMicro quadruped, 'Aubie'). This is an UNATTENDED run with no human present - do not attempt any remediation (no restarts, no commands to the robot's servos/movement, nothing destructive). You only have read-only tools.

New error-pattern lines detected since the last check:
$TRIGGER_REASON

Full latest diagnostic snapshot is at: $LATEST_SNAPSHOT - read it with the Read tool. It contains: robot uptime/load, docker container status, last 60 lines of the app container's logs, last 20 lines of each of the two on-robot watchdog logs, and a live diag_info health check.

If you want a fresher live check, you may run exactly this via Bash (this is the only Bash command that will actually execute regardless of what's requested - the robot's SSH server forces it): ssh -i $SSH_KEY -o ConnectTimeout=8 -o BatchMode=yes arduino@100.66.110.65 diag

Respond with a plain-language diagnosis (what likely happened, citing the actual evidence) and a concrete suggested next step, as your final answer text - do not attempt to write any files yourself, you have no file-write access. Keep it under 300 words. If the evidence doesn't clearly point to a cause, say so honestly rather than guessing."

{
  echo "# suggestion_run_time_utc: $TS"
  echo "# trigger_reason:"
  echo "$TRIGGER_REASON"
  echo "# --- claude analysis below ---"
} > "$RUN_LOG"

/home/aubieeternal/.local/bin/claude -p "$PROMPT" \
  --permission-mode dontAsk \
  --allowedTools "Read,Grep,Bash(ssh -i $SSH_KEY*)" \
  >> "$RUN_LOG" 2>&1

echo "$TS  new-incident  see $RUN_LOG" >> "$INDEX_FILE"
