# intervals.icu API Field Name Mapping

The intervals.icu REST API returns fields with `icu_` prefixed names for
custom/derived data. The plugin (`intervals_icu.py`) must request and read
these using the **correct names** — using Strava-style field names returns
`null` silently.

## Known correct field names

### Zone data (critical — most common bug)

| Plugin requests (WRONG) | API returns (CORRECT) | Contents |
|-------------------------|----------------------|----------|
| `heartrate_zones` | `icu_hr_zones` | Array of HR zone boundary bpm: `[131, 146, 153, 163, 167, 172, 181]` |
| `heartrate_zone_times` | `icu_hr_zone_times` | Array of seconds in each HR zone |
| `power_zones` | `icu_power_zones` | Array of power zone boundaries as % FTP: `[55, 75, 90, 105, 120, 150, 999]` |
| `power_zone_times` | `icu_zone_times` | Array of `{id: "Z1", secs: N}` objects — note: objects, not plain ints |

### Power data

| Correct name | Type | Example |
|-------------|------|---------|
| `icu_weighted_avg_watts` | int | 188 (Normalized Power) |
| `icu_average_watts` | int | 164 (raw average power) |
| `icu_ftp` | int | 265 |
| `icu_joules_above_ftp` | int | 33876 (kJ above FTP) |

### HR and cadence

| Correct name | Type | Example |
|-------------|------|---------|
| `avg_heartrate` | int | 125 (note: Strava-style, not `icu_` prefixed) |
| `max_heartrate` | int | 156 |
| `lthr` | int | 164 |
| `average_cadence` | float | 70.5 (Strava-style) |
| `icu_cadence_z2` | int | 73 (cadence in Z2 power) |

### Additional useful fields not in original plugin

| Correct name | Type | What it tells you |
|-------------|------|-------------------|
| `calories` | int | Total kcal burned |
| `carbs_used` | int | Grams carbohydrate oxidised |
| `coasting_time` | int | Seconds spent not pedalling |
| `decoupling` | float | HR/power decoupling %, <5% = good |
| `icu_variability_index` | float | NP/AP ratio, 1.0 = steady |
| `icu_efficiency_factor` | float | W per bpm, aerobic efficiency proxy |
| `icu_power_hr` | float | Power-to-HR ratio |
| `icu_power_hr_z2_mins` | int | Minutes where power:HR was in Z2 relationship |
| `icu_sweet_spot_min` | int | Sweet spot zone lower bound (% FTP) |
| `icu_sweet_spot_max` | int | Sweet spot zone upper bound (% FTP) |
| `icu_warmup_time` | int | Seconds auto-detected as warm-up |
| `icu_cooldown_time` | int | Seconds auto-detected as cool-down |
| `icu_lap_count` | int | Number of laps |
| `interval_summary` | list | Garmin auto-detected efforts, e.g. `["1x 12s 464w", ...]` |

## Debugging technique

When zone data comes back null, make a raw API call listing all returned
keys to discover the correct field names:

```python
import urllib.request, urllib.parse, base64, json

def api_request(athlete_id, api_key, path, params=None):
    url = f"https://intervals.icu/api/v1{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    token = base64.b64encode(f"API_KEY:{api_key}".encode()).decode()
    req = urllib.request.Request(url, headers={
        "Authorization": f"Basic {token}",
        "Accept": "application/json",
    })
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))

data = api_request(athlete_id, api_key,
    f"/athlete/{athlete_id}/activities/{activity_id}",
    {"fields": "id,name,icu_hr_zones,icu_hr_zone_times,icu_power_zones,icu_zone_times"})

for key in sorted(data.keys()):
    val = data.get(key)
    if val is not None:
        print(f"  {key}: {type(val).__name__} = {str(val)[:100]}")
```

## Plugin fix (applied 2026-07-04)

The `get_activity_detail` function in `intervals_icu.py` was patched:
- Fields parameter: replaced Strava-style names with `icu_` prefixed names
- Result dict: reads `act.get("icu_hr_zones")` instead of `act.get("heartrate_zones")`, etc.
- Added new fields: `avg_power_w`, `calories`, `carbs_used_g`, `coasting_time_s`,
  `decoupling_pct`, `variability_index`, `efficiency_factor`, `interval_summary`,
  `lthr`, `rpe`, `sweet_spot_min/max`, `joules_above_ftp`, `warmup/cooldown_time`

Note: this fix is applied to the live pod filesystem. To make it permanent,
create a PR via `/opt/data/scripts/create-pr.sh`.