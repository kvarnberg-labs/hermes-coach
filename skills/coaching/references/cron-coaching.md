# Running Coaching Tools from Cron / Headless Sessions

## ⚠️ CRITICAL: Delivery routing for multi-user cron jobs

When creating a cron job for a DIFFERENT athlete than the one you're currently talking to:

1. **NEVER use `deliver: "origin"`** — it resolves to YOUR chat, not the athlete's. The athlete will never see it; you'll get their briefings forever.
2. **Always set `deliver: "discord:<channel_id>:<channel_id>"`** using the athlete's actual Discord DM channel ID.
3. **Find the channel ID:** `grep "user=<Name>" /opt/data/logs/gateway.log | tail -1` — the `chat=<id>` field is the channel.
4. **Verify before creating:** run `ls /opt/data/users/*/intervals_athlete_name` to confirm the athlete's snowflake and credential directory exist.
5. **Coaching tools fail in cron** — there is no Discord gateway. Any cron prompt that says "Anropa `get_wellness(days=1)`" will fail silently and the model will fabricate data. Use the terminal workaround below instead.

**Example — correct setup for Aldrin (snowflake 1257567128349966388, channel 1531542557677322342):**
```
cronjob(action='create', 
  deliver='discord:1531542557677322342:1531542557677322342',
  ...
)
```

**Example — WRONG (cross-user leak):**
```
cronjob(action='create', 
  deliver='origin',  # ❌ Delivers to YOU, not the athlete!
  ...
)
```

## Why coaching tools fail in cron

Cron sessions lack a Discord gateway, so every coaching tool returns:
`"User identity not available — the Discord gateway did not provide a valid user ID."`

The `verify_athlete_identity`, `get_wellness`, `get_recent_activities`, etc. tools
all route through `_require_user_id(kw)` which needs `kw["user_id"]` to be a valid
Discord snowflake. In cron, `kw` is empty → error.

## Workaround: Direct Terminal Invocation

Call the plugin's internal functions directly via `terminal()` with the athlete's
snowflake hard-coded. The functions take `discord_id` as their first positional
argument and bypass the `_require_user_id` guard (it checks `kw`, not positional args).

### One-liner for all data at once

**CRITICAL:** Use `PYTHONPATH=/opt/hermes` and import as `from plugins.training import
intervals_icu`. The `sys.path.insert(0, 'plugins/training')` hack fails because
`intervals_icu.py` uses package-relative imports (`from ._credentials import ...`) which
require the parent package `plugins.training` to be importable.

```bash
cd /opt/hermes && HERMES_HOME=/opt/data PYTHONPATH=/opt/hermes python3 -c "
import sys, json
from plugins.training import intervals_icu
uid = 'SNOWFLAKE_HERE'

# Print each result as a labeled JSON block
def show(label, fn, *args):
    print(f'=== {label} ===')
    print(fn(uid, *args))

show('PROFILE', intervals_icu.get_athlete_profile)
show('WELLNESS', intervals_icu.get_wellness, 3)
show('EVENTS', intervals_icu.get_planned_events, 1)
show('SPORT_SETTINGS', intervals_icu.get_sport_settings, 'Ride')
show('RECENT_ACTIVITIES', intervals_icu.get_recent_activities, 14)
show('POWER_CURVE', intervals_icu.get_power_curve, 'Ride', 42)
show('FITNESS', intervals_icu.get_fitness_chart, 365)
" 2>&1
```

### Function signatures (all take `discord_id` as first arg)

| Function | Args after discord_id | Returns |
|---|---|---|
| `get_athlete_profile(uid)` | — | JSON string |
| `get_wellness(uid, days=7)` | `days` (int) | JSON string |
| `get_planned_events(uid, days_ahead=14)` | `days_ahead` (int) | JSON string |
| `get_sport_settings(uid, sport="Ride")` | `sport` (str) | JSON string |
| `get_recent_activities(uid, days=14, sport=None)` | `days`, `sport` | JSON string |
| `get_power_curve(uid, sport="Ride", days=42)` | `sport`, `days` | JSON string |
| `get_fitness_chart(uid, days=365)` | `days` | JSON string |
| `get_activity_detail(uid, activity_id)` | `activity_id` (str) | JSON string |
| `get_activity_streams(uid, activity_id)` | `activity_id` (str) | JSON string |

### Finding the athlete's snowflake

```bash
# List all user directories with credential files
ls -d /opt/data/users/*/intervals_athlete_name | while read f; do
  dir=$(dirname "$f")
  snowflake=$(basename "$dir")
  name=$(cat "$f")
  echo "$snowflake → $name"
done
```

The snowflake is the 17-20 digit directory name under `/opt/data/users/`.

### Weather (no user_id needed)

The `get_weather` tool does NOT require a user identity. Call it normally:

```
get_weather(latitude=58.238, longitude=11.93, location_name="Ljungskile")
```

### What NOT to do

- Do NOT call `verify_athlete_identity` — it uses the same `_require_user_id` guard and will fail.
- Do NOT attempt credential recovery — credentials are fine, the gateway is simply absent.
- Do NOT add the `discord_dm` fallback directory — it was removed in PR #32 for good reason.
  The terminal workaround above is the sanctioned cron path.
- Do NOT use raw `curl` for intervals.icu data — the plugin functions handle auth, caching,
  and field-name normalisation. Call them directly.
- Do NOT use `sys.path.insert(0, 'plugins/training')` — the plugin uses package-relative
  imports (`from ._credentials import ...`) which fail without the parent package. Always
  use `PYTHONPATH=/opt/hermes` + `from plugins.training import intervals_icu`.

### Pitfall: Cron prompt hard-coded values may be stale

The cron prompt often includes frozen athlete metadata from when the job was created
(e.g. "FTP 252W", "weight ~90.6 kg"). These values become stale as the athlete's
profile changes. **Always cross-reference with live API data before using prompt values:**

- `get_sport_settings` → actual configured FTP (may differ from prompt's hard-coded FTP)
- `get_athlete_profile` → current weight (may differ from prompt)
- `get_wellness` → actual eFTP (may differ from both configured FTP and prompt)

When the prompt's FTP conflicts with the API's configured FTP, **trust the API and
recalculate all watt targets against the API's FTP.** A Z2 prescription of 148–170W at
252W FTP becomes 146–196W at 261W FTP — use the live number for zone boundaries.
Include the API-derived FTP in your briefing so the athlete sees which baseline you used.
