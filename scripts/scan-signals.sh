#!/bin/sh
# scan-signals.sh — discovery script for the self-improvement cron loop.
# Stdout is injected into the cron agent prompt as the "discover" step.
# Exit 0 always; empty output is valid (no open signals).

HERMES_HOME="${HERMES_HOME:-/opt/data}"
SIGNALS_DIR="${HERMES_HOME}/loops/signals"

[ -d "$SIGNALS_DIR" ] || exit 0

# Find markdown files with status: open
open_files=$(grep -rl "^status: open" "$SIGNALS_DIR" 2>/dev/null)

if [ -z "$open_files" ]; then
    echo "No open signals."
    exit 0
fi

count=$(echo "$open_files" | wc -l | tr -d ' ')
echo "OPEN SIGNALS (${count}):"
echo ""

echo "$open_files" | while IFS= read -r f; do
    title=$(grep "^title:" "$f" 2>/dev/null | head -1 | sed 's/^title:[[:space:]]*//')
    prio=$(grep "^priority:" "$f" 2>/dev/null | head -1 | sed 's/^priority:[[:space:]]*//')
    date_filed=$(grep "^date:" "$f" 2>/dev/null | head -1 | sed 's/^date:[[:space:]]*//')
    echo "  [${prio:-?}] ${title:-$(basename "$f")}  (filed: ${date_filed:-unknown})"
    echo "      File: $f"
done

echo ""
echo "Review the CONTRACT.md backlog alongside these signals to pick the highest-value improvement."
