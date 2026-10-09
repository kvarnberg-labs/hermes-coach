#!/bin/sh
# scan-signals.sh — discovery script for the self-improvement cron loop.
# Stdout is injected into the cron agent prompt as the "discover" step.
# Exit 0 always; empty output is valid (no open signals).

HERMES_HOME="${HERMES_HOME:-/opt/data}"
SIGNALS_DIR="${HERMES_HOME}/loops/signals"
DB="${HERMES_HOME}/state.db"

# ---------------------------------------------------------------------------
# 1. Open signal files
# ---------------------------------------------------------------------------
open_files=""
if [ -d "$SIGNALS_DIR" ]; then
    open_files=$(grep -rl "^status: open" "$SIGNALS_DIR" 2>/dev/null)
fi

if [ -n "$open_files" ]; then
    echo "OPEN SIGNALS:"
    echo ""
    echo "$open_files" | while IFS= read -r f; do
        title=$(grep "^title:" "$f" 2>/dev/null | head -1 | sed 's/^title:[[:space:]]*//')
        prio=$(grep "^priority:" "$f" 2>/dev/null | head -1 | sed 's/^priority:[[:space:]]*//')
        date_filed=$(grep "^date:" "$f" 2>/dev/null | head -1 | sed 's/^date:[[:space:]]*//')
        echo "  [${prio:-?}] ${title:-$(basename "$f")}  (filed: ${date_filed:-unknown})"
        echo "      File: $f"
    done
    echo ""
else
    echo "No open signals."
    echo ""
fi

# ---------------------------------------------------------------------------
# 2. Conversation gap scan — mine state.db for recent coaching friction.
#    Helper: query_db <label> <sql>  — prints label + results if any rows found.
# ---------------------------------------------------------------------------
query_db() {
    label="$1"; sql="$2"
    rows=$(sqlite3 "$DB" "$sql" 2>/dev/null)
    [ -z "$rows" ] && return
    echo "  $label"
    echo "$rows" | while IFS='|' read -r ts snippet; do
        printf "    [%s] %s\n" "$ts" "$snippet"
    done
    echo ""
}

if [ ! -f "$DB" ]; then
    echo "CONVERSATION SCAN: no DB at $DB (no conversations yet)."
    echo ""
else
    echo "CONVERSATION SCAN (last 7 days):"
    echo ""

    query_db "Athlete frustration / confusion:" \
        "SELECT datetime(timestamp,'unixepoch','localtime'), substr(content,1,200)
         FROM messages
         WHERE role='user'
           AND timestamp >= strftime('%s','now','-7 days')
           AND (content LIKE '%don''t understand%' OR content LIKE '%not working%'
             OR content LIKE '%confused%' OR content LIKE '%can''t%'
             OR content LIKE '%still not%' OR content LIKE '%again%'
             OR content LIKE '%wrong%' OR content LIKE '%help%')
         ORDER BY timestamp DESC LIMIT 10;"

    query_db "Tool errors:" \
        "SELECT datetime(timestamp,'unixepoch','localtime'), substr(content,1,300)
         FROM messages
         WHERE role='tool'
           AND timestamp >= strftime('%s','now','-7 days')
           AND (content LIKE '%\"error\"%' OR content LIKE '%No intervals.icu credentials%'
             OR content LIKE '%Could not reach%' OR content LIKE '%401%'
             OR content LIKE '%coach-brain not loaded%')
         ORDER BY timestamp DESC LIMIT 10;"

    query_db "Knowledge gaps (coach-brain matched:false):" \
        "SELECT datetime(timestamp,'unixepoch','localtime'), substr(content,1,300)
         FROM messages
         WHERE role='tool'
           AND timestamp >= strftime('%s','now','-7 days')
           AND content LIKE '%\"matched\": false%'
         ORDER BY timestamp DESC LIMIT 10;"

    echo "  (no further friction signals in last 7 days)" 2>/dev/null || true
    echo ""
fi

query_db "Kept-alive system msgs (corruption/duplicate markers):" \
    "SELECT datetime(timestamp,'unixepoch'), substr(content,1,200)
     FROM messages
     WHERE role='system'
       AND timestamp >= strftime('%s','now','-7 days')
       AND (content LIKE '%duplicate%' OR content LIKE '%keep-alive%' OR content LIKE '%corrupt%')
     ORDER BY timestamp DESC LIMIT 5;"

# ---------------------------------------------------------------------------
# 2b. Cron job health — failed cron runs are silent gaps (no conversation
#     row to mine when the run dies pre-agent, e.g. provider timeouts).
#     Surface last_status=error and failure_streak>=2 from jobs.json.
# ---------------------------------------------------------------------------
JOBS_FILE="${HERMES_HOME}/cron/jobs.json"
if [ -f "$JOBS_FILE" ] && command -v python3 >/dev/null 2>&1; then
    job_health=$(python3 -c "
import json, sys
try:
    jobs = json.load(open('$JOBS_FILE'))['jobs']
except Exception as e:
    print(f'unreadable jobs.json: {e}'); sys.exit(0)
alerts = []
for j in jobs:
    streak = j.get('failure_streak') or 0
    last_status = j.get('last_status')
    if last_status == 'error' or streak >= 2:
        alerts.append((j.get('name','?'), streak or 1,
                       (j.get('last_error') or '?')[:120],
                       (j.get('last_run_at') or '?')[:10]))
for name, streak, err, when in sorted(alerts, key=lambda a: -a[1]):
    print(f'  [-] {name}: last_status=error, failure_streak={streak} (last run {when}): {err}')
if not alerts:
    print('none')
" 2>/dev/null)
    if [ -n "$job_health" ]; then
        echo "CRON JOB HEALTH (jobs.json):"
        if [ "$job_health" != "none" ]; then
            echo "$job_health"
            echo ""
            echo "  -> Failed cron runs are silent gaps. If a coaching job is failing,"
            echo "     check its cron output dir and escalate; if this self-improve job"
            echo "     itself shows failure_streak >= 2, note it as an operator-level"
            echo "     scheduler/retry problem (nonce-based retries are not configured)."
        else
            echo "  all jobs last_status=ok"
        fi
        echo ""
    fi
fi

# ---------------------------------------------------------------------------
# 3. Recent worklog (last 3 entries) — avoid re-doing recent work
# ---------------------------------------------------------------------------
WORKLOG="${HERMES_HOME}/loops/worklog.md"
if [ -f "$WORKLOG" ] && grep -q "^## 20" "$WORKLOG" 2>/dev/null; then
    echo "RECENT WORKLOG (last 3 entries):"
    awk '/^## 20/{c++} c>=1{print}' "$WORKLOG" | tail -40
    echo ""
fi

echo "Review the CONTRACT.md backlog alongside these signals to pick the highest-value improvement."
