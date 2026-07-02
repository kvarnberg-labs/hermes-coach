# Self-Improvement Worklog

Append-only log of self-improvement loop activity.
Read the last 10 entries before starting a run.

---

<!-- entries added by the loop agent below this line -->

## 2026-07-02 14:10 UTC
- Signal: "pod is live, logs are missing" — scan-signals.sh only read YAML files, never the conversation history
- Action: (1) Rewrote scan-signals.sh to mine the Hermes SQLite memory DB ($HERMES_HOME/hermes.db) for athlete frustration signals, tool errors ("error" JSON, 401s, credential missing), and coach-brain misses (matched:false). Gracefully skips if DB absent. (2) Added LOG_LEVEL=WARNING to configmap so pod stderr surfaces real issues. (3) Added recent worklog tail to scan output so the loop avoids re-doing recent work.
- PR: N/A — direct edit session
- Outcome: submitted; pending deploy. NOTE: hermes.db path is inferred — if the memory DB lives elsewhere on the PVC, update DB= in scan-signals.sh. Verify with: kubectl exec deploy/hermes -n hermes -- find /opt/data -name '*.db' -o -name '*.sqlite'

- Signal: backlog item — "Add response-parser unit tests for get_wellness and get_recent_activities" + "Add altitude acclimatization knowledge"
- Action: (1) Added 30 response-parser tests covering all six get_* tools in tests/test_intervals_icu.py — full field mapping, edge cases (TSB zero, RPE fallback chain, null distance/duration, empty responses, credential errors, capped days). (2) Added coach-brain/altitude.yaml with evidence-based altitude acclimatization guidance (elevation zones, AMS symptoms + red flags, live-high train-low protocol, sea-level performance window, training adjustments by day).
- PR: N/A — direct edit session (not cron loop)
- Outcome: submitted; 101 tests pass (was 73)
