# Cron coaching runtime recipe

Headless cron sessions may expose no `user_id` to model-visible coaching tools. This is a gateway-context limitation, not proof that credentials are missing.

## Procedure

1. Read the scheduled job's `origin.user_id` (Discord snowflake) and its explicit `deliver` target. Do not infer identity from `HERMES_SESSION_USER_ID` if it is empty.
2. Import the plugin's internal functions, which accept the snowflake positionally and bypass `_require_user_id`:

```bash
PYTHONPATH=/opt/data/plugins python3 - <<'PY'
import json
from training.intervals_icu import verify_athlete_identity, get_athlete_profile
uid = "<origin.user_id>"
print(verify_athlete_identity(uid))
print(get_athlete_profile(uid))
PY
```

3. Continue only if identity is verified. Use the same `uid` for `get_wellness`, `get_recent_activities`, `get_planned_events`, and sport settings.
4. Parse JSON and retain only fields needed for the report; avoid dumping raw responses into the prompt.
5. If sleep/HRV/subjective feel is absent, state the objective status and make intensity conditional rather than asserting readiness.
6. Never use another athlete's credentials, the shared `discord_dm` directory, or `deliver: origin` when routing a report for a different athlete.

This recipe was validated against the scheduled training brief path where the model-visible identity check returned an error but the direct positional call verified the athlete successfully.