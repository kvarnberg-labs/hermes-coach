#!/bin/sh
# scan-signals.sh — discovery script for the self-improvement cron loop.
# Stdout is injected into the cron agent prompt as the "discover" step.
# Exit 0 always; empty output is valid (no open signals).

HERMES_HOME="${HERMES_HOME:-/opt/data}"
SIGNALS_DIR="${HERMES_HOME}/loops/signals"

# ---------------------------------------------------------------------------
# 1. Open signal files
# ---------------------------------------------------------------------------
open_files=""
if [ -d "$SIGNALS_DIR" ]; then
    open_files=$(grep -rl "^status: open" "$SIGNALS_DIR" 2>/dev/null)
fi

if [ -n "$open_files" ]; then
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
else
    echo "No open signals."
    echo ""
fi

# ---------------------------------------------------------------------------
# 2. Conversation gap scan — mine the Hermes memory DB for recent frustration
#    signals: tool errors, athlete confusion, unanswered questions.
#
#    The Hermes SQLite memory lives at $HERMES_HOME/hermes.db.
#    Messages are in the `messages` table; role is 'user' or 'assistant'.
#    We scan the last 7 days for patterns that indicate coaching gaps.
# ---------------------------------------------------------------------------
DB="${HERMES_HOME}/state.db"

if [ ! -f "$DB" ]; then
    echo "CONVERSATION SCAN: no memory DB found at $DB (no conversations yet, or DB path differs)."
    echo ""
else
    echo "CONVERSATION SCAN (last 7 days):"
    echo ""

    # Frustration / confusion patterns in athlete messages
    FRUSTRATION=$(sqlite3 "$DB" \
      "SELECT datetime(created_at,'localtime'), substr(content,1,200)
       FROM messages
       WHERE role='user'
         AND created_at >= datetime('now','-7 days')
         AND (
           content LIKE '%don''t understand%'
           OR content LIKE '%doesn''t work%'
           OR content LIKE '%not working%'
           OR content LIKE '%wrong%'
           OR content LIKE '%confused%'
           OR content LIKE '%why%'
           OR content LIKE '%what does%'
           OR content LIKE '%what is%'
           OR content LIKE '%can''t%'
           OR content LIKE '%cannot%'
           OR content LIKE '%never%'
           OR content LIKE '%always%'
           OR content LIKE '%still%'
           OR content LIKE '%again%'
           OR content LIKE '%still not%'
           OR content LIKE '%no idea%'
           OR content LIKE '%help%'
         )
       ORDER BY created_at DESC
       LIMIT 10;" 2>/dev/null)

    if [ -n "$FRUSTRATION" ]; then
        echo "  Athlete messages suggesting confusion or unmet needs:"
        echo "$FRUSTRATION" | while IFS='|' read -r ts snippet; do
            printf "    [%s] %s\n" "$ts" "$snippet"
        done
        echo ""
    fi

    # Tool errors returned to the agent (assistant messages containing error JSON)
    TOOL_ERRORS=$(sqlite3 "$DB" \
      "SELECT datetime(created_at,'localtime'), substr(content,1,300)
       FROM messages
       WHERE role='tool'
         AND created_at >= datetime('now','-7 days')
         AND (
           content LIKE '%\"error\"%'
           OR content LIKE '%No intervals.icu credentials%'
           OR content LIKE '%Could not reach%'
           OR content LIKE '%401%'
           OR content LIKE '%No direct match found%'
           OR content LIKE '%coach-brain not loaded%'
         )
       ORDER BY created_at DESC
       LIMIT 10;" 2>/dev/null)

    if [ -n "$TOOL_ERRORS" ]; then
        echo "  Tool errors observed in recent sessions:"
        echo "$TOOL_ERRORS" | while IFS='|' read -r ts snippet; do
            printf "    [%s] %s\n" "$ts" "$snippet"
        done
        echo ""
    fi

    # Topics athletes asked about that may not be in coach-brain
    # (get_coaching_knowledge returned matched:false)
    MISSING_TOPICS=$(sqlite3 "$DB" \
      "SELECT datetime(created_at,'localtime'), substr(content,1,300)
       FROM messages
       WHERE role='tool'
         AND created_at >= datetime('now','-7 days')
         AND content LIKE '%\"matched\": false%'
       ORDER BY created_at DESC
       LIMIT 10;" 2>/dev/null)

    if [ -n "$MISSING_TOPICS" ]; then
        echo "  Knowledge gaps (get_coaching_knowledge returned no match):"
        echo "$MISSING_TOPICS" | while IFS='|' read -r ts snippet; do
            printf "    [%s] %s\n" "$ts" "$snippet"
        done
        echo ""
    fi

    if [ -z "$FRUSTRATION" ] && [ -z "$TOOL_ERRORS" ] && [ -z "$MISSING_TOPICS" ]; then
        echo "  No frustration signals or tool errors in the last 7 days."
        echo ""
    fi
fi

# ---------------------------------------------------------------------------
# 3. Recent worklog summary (last 3 entries) — avoid re-doing recent work
# ---------------------------------------------------------------------------
WORKLOG="${HERMES_HOME}/loops/worklog.md"
if [ -f "$WORKLOG" ]; then
    recent=$(grep -c "^## 20" "$WORKLOG" 2>/dev/null || echo 0)
    if [ "$recent" -gt 0 ]; then
        echo "RECENT WORKLOG (last 3 entries — avoid duplicating these):"
        # Print from the last 3 '## 20' headings to end of file
        awk '/^## 20/{c++} c>=1{print}' "$WORKLOG" | tail -40
        echo ""
    fi
fi

echo "Review the CONTRACT.md backlog alongside these signals to pick the highest-value improvement."
