# Cron Delivery Routing — Cross-User Leak Prevention

## Incident Summary (2026-07-28)

Two athlete cron jobs were discovered delivering to Joey's Discord DM instead of the
intended athletes' channels:

| Cron Job | Athlete | Was Delivering To | Root Cause |
|----------|---------|-------------------|------------|
| `1496066e6332` "Aldrin dagligt..." | Aldrin | Joey's DM | `deliver` hardcoded to Joey's channel 1508816099540602970 |
| `c394e2e32565` "Morgonbrief Millberg" | Millberg | Joey's DM | Created with `deliver: "origin"` from Joey's chat |

**Impact:** Joey received briefings with Aldrin/Millberg's training data (or in cron
sessions where coaching tools fail, fabricated data labeled as the other athletes').

**Secondary finding:** `get_wellness`, `verify_athlete_identity`, and all coaching tools
fail in cron (no Discord gateway → no user_id). Agents fabricate TSB values when tools
fail silently. Cron prompts MUST use the terminal workaround from cron-coaching.md.

## Channel Discovery

```bash
# Find any athlete's Discord DM channel ID
grep "user=<DiscordName>" /opt/data/logs/gateway.log | tail -1
# Example: user=Aldrin chat=1531542557677322342 → channel = 1531542557677322342
```

## Verified Channel Registry (as of 2026-07-28)

| Athlete | Snowflake | Channel ID | Athlete ID (intervals.icu) |
|---------|-----------|------------|---------------------------|
| Joey | 117694354092457986 | 1508816099540602970 | i344591 |
| Aldrin | 1257567128349966388 | 1531542557677322342 | i627207 |
| Millberg | 785756739492511774 | 1516523703649697792 | i494629 |
| Wilma | 1530918526905487432 | (unverified) | i652874 |

## Correct Cronjob Creation Pattern

```python
cronjob(
    action='create',
    deliver='discord:1531542557677322342:1531542557677322342',  # Athlete's channel, NOT origin
    prompt='...',  # Must use terminal workaround for coaching data
    skills=['coaching'],
    schedule='0 7 * * *',
)
```

## Verification Checklist (before creating any multi-user cronjob)

1. ✅ `deliver` is the ATHLETE'S channel ID, not "origin" and not your channel
2. ✅ The athlete has a credential directory at `/opt/data/users/<snowflake>/`
3. ✅ The prompt does NOT instruct the agent to call `get_wellness`, `verify_athlete_identity`, etc. (they fail in cron)
4. ✅ The prompt uses terminal workaround from `cron-coaching.md` if it needs real wellness data
5. ✅ `ls /opt/data/users/<snowflake>/intervals_athlete_name` matches the athlete's Discord name
