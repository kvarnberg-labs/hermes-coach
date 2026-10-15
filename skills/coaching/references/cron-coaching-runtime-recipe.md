# Scheduled (cron) coaching runs

Load only in a scheduled/headless run (no athlete in the chat). Interactive DMs
never need this file.

Headless runs have no Discord gateway user, so the model-visible coaching tools
return "User identity not available". That is a context limitation, not proof
that credentials are missing.

## Stage 1 — identity (stop here on failure)

1. Take the athlete's Discord snowflake from the job's `origin.user_id` or its
   explicitly configured athlete identity. Never from an empty session
   variable, another job, a channel ID, or by listing user directories.
2. Call the plugin's internal functions directly with that snowflake
   (positional first argument; they bypass the gateway check):

```bash
cd /opt/data && HERMES_HOME=/opt/data PYTHONPATH=/opt/data/plugins python3 - <<'PY'
from training import intervals_icu as t
uid = "<origin.user_id>"
print(t.verify_athlete_identity(uid))
print(t.get_athlete_profile(uid))
PY
```

3. Continue only if `verified: true` (athlete ID matches and a stored name
   exists; a display-name difference alone is not a failure). Run
   `verify_athlete_identity` this way in every scheduled run.
4. If verification fails or credentials are missing: stop before any other
   training call. Report neutrally that the scheduled brief could not be
   generated and that `/start` onboarding is needed for this Discord identity.
   Do not claim poor recovery or "no new data". Never borrow another user's
   credentials, a cached athlete ID, or a shared directory to fill the gap.

## Stage 2 — data

Use the same `uid` for every call; keep only the fields the report needs.

| Function | Args after uid |
|---|---|
| `get_wellness` | `days` |
| `get_recent_activities` | `days`, `sport` |
| `get_planned_events` | `days_ahead`, `days_back` |
| `get_sport_settings` | `sport` ("Ride" / "Run") |
| `get_activity_detail` / `get_activity_intervals` / `get_activity_streams` | `activity_id` |
| `get_best_effort_curve` | `sport`, `days` |
| `get_fitness_chart` | `days` (weekly resolution above 60) |
| `get_athlete_stats` (`from training.get_athlete_stats import get_athlete_stats`) | `start_date`, `end_date` (YYYY-MM-DD) |

Import as `from training import intervals_icu` with
`PYTHONPATH=/opt/data/plugins` (package-relative imports). No raw `curl` for
intervals.icu data. `get_weather` needs no identity and can be called normally.

Values hard-coded in the job prompt (FTP, weight) go stale: use the live
`get_sport_settings` / `get_athlete_profile` values and state which FTP you used.

## Stage 3 — write the report

- Derive every weekday mechanically, never by recall:
  `python3 /opt/data/plugins/training/iso8601.py <YYYY-MM-DD> [...]` prints
  `DATE (veckodag)` per date (no argument = today and tomorrow). Use each
  record's own date, not the run date.
- Missing overnight data ≠ poor recovery: say sleep/readiness fields are
  unavailable, use the latest dated record only as context, and do not claim
  to have reviewed "last night's" sleep.
- No subjective feel available → give the objective status and a conditional
  recommendation; do not assert readiness or downgrade on missing data alone.
- An empty activity or planned-event result is a data finding ("no entries
  returned for this window"), not proof of rest or a missed session.
- The rules in `coach-brain/recovery-heuristics.yaml → scheduled_brief_gate`
  and `coach-brain/headless-coaching-failures.yaml` apply.
- Do not ask "how do you feel?" as if the athlete were present; give the
  conditional instead.

## Stage 4 — semantic success

"Scheduler ran" and "a usable report reached the athlete" are separate facts.
If the output is identity-unavailable, onboarding-required, empty/placeholder,
tool-error text or an explicit failure, the run failed even when the scheduler
says `ok`. Name the failure class (`headless-coaching-failures.yaml →
failure_classes`): `context_identity_missing` (use Stage 1, do not ask for
`/start`), `onboarding_missing_or_mismatch` (ask for `/start`, make no
training claims), `delivery_failure` (report to the operator — routing is not
proof of credential ownership), or `semantic_failure` / a genuine tool error.
Give one concrete next action.
