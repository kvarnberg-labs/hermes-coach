# Cron Prompt Templates for Scheduled Coaching Briefs

## Why this exists

Old cron jobs for morning briefs and weekly plans failed silently because their
prompts were too vague — they said "analyze wellness data" without embedding the
terminal workaround. In cron sessions there is no Discord gateway, so
model-visible coaching tools (`get_wellness`, `verify_athlete_identity`, etc.)
return "User identity not available." The agent then either fabricates data or
reports a failure.

**The fix:** the cron prompt itself must contain the exact terminal command with
the athlete's snowflake hard-coded, the analysis structure, and the output format.
The prompt is the entire instruction set — there is no conversation context to
fall back on.

## Template: Daily Morning Brief

```
Du är [Athlete name]s svenska löpcoach. [Athlete bio: name, age, weight, location,
sport, goal, LTHR, max HR, training structure].

Detta är en AUTOMATISK morgonbrief som körs kl [HH:MM] Stockholmstid varje dag.
Du har ingen Discord-gateway, så coaching-verktygen fungerar INTE direkt.
Använd terminal-workaround:

## STEG 1 — Hämta data via terminal
Kör detta i terminalen:

```bash
cd /opt/hermes && HERMES_HOME=/opt/data PYTHONPATH=/opt/hermes python3 -c "
import json
from plugins.training import intervals_icu
uid = '<SNOWFLAKE>'
print('PROFILE:', intervals_icu.get_athlete_profile(uid))
print('WELLNESS:', intervals_icu.get_wellness(uid, 3))
print('EVENTS:', intervals_icu.get_planned_events(uid, 2))
print('RECENT:', intervals_icu.get_recent_activities(uid, 3))
print('RUN_SETTINGS:', intervals_icu.get_sport_settings(uid, 'Run'))
"
```

## STEG 2 — Sammanställ morgonbriefen
[Output structure: sleep/recovery comment, CTL/ATL/TSB with arrows,
today's planned session or rest day, 1-2 sentence pep talk tied to goal]

## REGELVERK
- ALLTID datum + veckodag tillsammans. Dubbelkolla veckodag mot datum!
- Om sömndata saknas: säg det rakt, hitta inte på
- Håll briefen KORT — max ~15 rader
- Svenska, rakt, inget fluff
- Inga relativa dagsreferenser utan verifiering
```

## Template: Weekly Plan (Sunday evening)

Same structure but with 7-day wellness + 14-day planned events + 7-day recent
activities, and a full week-by-week table output with:

- Previous week analysis (planned vs actual)
- CTL/ATL/TSB trend and ramp rate assessment
- Next week's plan as a day-by-day table (dag, datum, pass, detaljer, load)
- Recovery week detection (every 3rd–4th week)
- Calendar event creation via `create_planned_event` (import from
  `plugins.training.create_planned_event`)

## Critical prompt elements

| Element | Why it matters |
|---------|---------------|
| Snowflake hard-coded in terminal command | Without it, the agent cannot fetch any data |
| `PYTHONPATH=/opt/hermes` + `from plugins.training import intervals_icu` | Package-relative imports fail without parent package |
| `HERMES_HOME=/opt/data` | Credential directory resolution |
| Analysis structure (STEG 1, STEG 2, REGELVERK) | Prevents the agent from free-form rambling |
| Output format spec (max lines, language, sections) | Keeps the brief scannable for the athlete |
| `attach_to_session: true` on the cronjob | Lets the athlete reply to the brief and get context |
| `deliver: discord:<channel>:<channel>` | Routes to the athlete, not the coach |

## Testing after creation

Always run `cronjob(action='run', job_id=...)` immediately after creating or
updating a scheduled coaching job. Then check:

1. `last_status` is `ok` (not `error`)
2. The athlete received the message in Discord
3. The output contains real data (CTL/ATL/TSB numbers, planned session name) —
   not "identity unavailable" or fabricated placeholder text

If the test run fails, check:
- Snowflake is correct: `ls /opt/data/users/*/intervals_athlete_name`
- Channel ID matches: `grep "user=<Name>" /opt/data/logs/gateway.log | tail -1`
- Terminal command works: run it manually before embedding in the prompt

## Cleanup pattern

When an athlete re-onboards (new API key) or requests new cron jobs:

1. `cronjob(action='list')` to find existing jobs for that athlete
2. Remove stale/failed jobs (`action='remove'`) — don't leave duplicates
3. Create fresh jobs with updated prompts
4. Test with `action='run'`
5. Update the channel registry in `cron-delivery-routing.md`
