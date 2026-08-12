# Event Creation Pitfalls

## Datetime format: time component required

The intervals.icu API `POST /api/v1/athlete/{id}/events` requires `start_date_local`
to include a time component. A date-only string like `2026-07-31` returns:

```
HTTP 422: {"status":422,"error":"Invalid start date: java.time.format.DateTimeParseException: Text '2026-07-31' could not be parsed at index 10"}
```

**Correct format:** `2026-07-31T09:00:00` (ISO 8601 with seconds, no timezone suffix needed).
The API appends the athlete's timezone automatically.

## Required fields for POST

```json
{
    "name": "Workout name",
    "type": "Ride",
    "category": "WORKOUT",
    "start_date_local": "2026-07-31T09:00:00",
    "description": "Optional description",
    "icu_training_load": 110,
    "icu_intensity": 100
}
```

Note: `icu_intensity` may appear as `null` in the response even when set — this is a known API quirk.

## Structured workout steps — FIT file via `file_contents_base64`

**The `workout_doc` PUT approach does NOT work for Garmin sync.** The intervals.icu
API parses structured workout data from FIT files uploaded via `file_contents_base64`,
NOT from `workout_doc` in the POST/PUT payload. Steps stored via `workout_doc` are
never converted to proper Garmin workout targets.

### Correct approach: FIT file in a single POST

```python
import base64

# Build a FIT workout file (use fit-tool or the embedded builder)
fit_bytes = _build_fit_file(sport="Run", steps=[...], max_hr=193, ftp=286)

payload = {
    "name": "Easy Run",
    "type": "Run",
    "category": "WORKOUT",
    "start_date_local": "2026-08-05T09:00:00",
    "description": "35-50 min easy, RPE 2-3.",
    "moving_time": 3600,
    "target": "PACE",
    "file_contents_base64": base64.b64encode(fit_bytes).decode(),
    "filename": "workout.fit",
}

event = post_json(athlete_id, api_key, f"/athlete/{athlete_id}/events", payload)
# Steps are parsed automatically — no PUT needed
```

The `create_planned_event` tool handles all of this automatically when you
pass the `steps` parameter. Just provide reasonable step dicts with
`hr_min/hr_max`, `power_min/power_max`, `power_pct_min/power_pct_max`,
or `pace_min/pace_max`.

See `references/fit-workout-generation.md` for the full FIT encoding details.

### Step format for the tool

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Step name (informational) |
| `duration_sec` | integer | Duration in seconds |
| `type` | string | `WARMUP`, `ACTIVE`, `REST`, or `COOLDOWN` |
| `hr_min`, `hr_max` | integer | Heart rate bounds in BPM (auto-converted to %max HR for FIT) |
| `power_min`, `power_max` | integer | Power bounds in watts (auto-converted to %FTP if >20) |
| `power_pct_min`, `power_pct_max` | number | Power bounds as % FTP |
| `pace_min`, `pace_max` | string/number | Pace bounds: `"5:40"` (min:sec/km) or m/s |
| `description` | string | Optional step description |

### Easy runs should NOT have warmup/cooldown

Athletes explicitly prefer this. An easy run is one steady block — not
warmup + main + cooldown. Example:

```json
{"steps": [{"duration_sec": 3600, "type": "ACTIVE", "pace_min": "5:40", "pace_max": "6:00", "name": "Easy Run"}]}
```

Only add warmup/cooldown steps when the workout involves a meaningful
intensity change (intervals, threshold, VO2max). For Z1/Z2 steady runs,
a single step is cleaner and more usable on Garmin.

### power_pct uses configured FTP, NOT eFTP

**This is the #1 cause of incorrect power targets on planned events.**
The `create_planned_event` tool calculates actual watts from `power_pct_min/max`
against the athlete's **configured FTP** in intervals.icu (from `get_sport_settings`),
NOT the eFTP from wellness data. If configured FTP is 286W and eFTP is 274W:

| Desired real target | Must set power_pct | NOT |
|---------------------|-------------------|-----|
| 240-257W sweet spot (88-94% eFTP) | **84-90%** | 88-94% |
| 260-274W threshold (95-100% eFTP) | **91-96%** | 95-100% |

93% of 286W = 266W, not 255W. When the athlete says the power is wrong on
Zwift/Garmin, check whether you calculated against eFTP or configured FTP.

**Always cross-reference before creating an event:**
1. Pull `get_sport_settings(sport="Ride")` → `ftp` (configured)
2. Pull `get_wellness(days=1)` → `sport_info[].eftp` (estimated)
3. If gap >10W: calculate BOTH the trainer-displayed watts and the real physiological zone
4. Set `power_pct` against configured FTP so the trainer shows the right number
5. But verify the resulting watts fall in the intended zone when mapped against eFTP

**Double-check pattern:** after calculating percentages, do the reverse math:
`configured_ftp × pct / 100 = displayed_watts` and verify it's in the right
real-world zone.

### Event-level target field

Set based on sport:

| Sport | Event-level `target` |
|-------|---------------------|
| Run, TrailRun, VirtualRun | `"PACE"` |
| Ride, VirtualRide, GravelRide, MountainBikeRide | `"POWER"` |

### HR values: percentage of max HR in FIT

The FIT format stores HR targets as absolute BPM, but intervals.icu's
internal representation uses %max HR. The `create_planned_event` tool
auto-converts BPM → %max by fetching the athlete's max HR from their
profile. If the profile fetch fails, max HR defaults to 193.

### Pace values: m/s in FIT — PACE TARGETS WORK, DO NOT TELL THE ATHLETE OTHERWISE

Pace in FIT files is stored in m/s (metres per second). The tool's
`_parse_pace_to_ms()` converts human-readable `"5:40"` → 2.94 m/s.

**`pace_min`/`pace_max` in `create_planned_event` steps WORKS for running workouts.**
The tool converts `"4:44"` → m/s and embeds it in the FIT file as a SPEED target.
Garmin displays this as a pace target on the workout screen.

⚠️ **DO NOT confuse the old `workout_doc` pace bug with the current FIT-based tool.**
Before PR #53 (FIT file support), pace targets sent via `workout_doc` were broken —
intervals.icu's internal ZWO/workout_doc parser mangled pace units (s/km, km/h,
min/km, m/s all produced wrong values on Garmin). This was an intervals.icu upstream
bug in the `workout_doc` code path, NOT in the FIT file path.

The `create_planned_event` tool uses `file_contents_base64` with a generated FIT
file — it bypasses `workout_doc` entirely. Pace targets in FIT files are correct.
If an athlete asks "can you include pace targets?", the answer is YES.

⚠️ **ONE target type per step — FIT limitation.** The FIT file format allows
only ONE target type per workout step (HR, power, OR pace — not multiple).
The `create_planned_event` auto-detection prioritizes HR > power > pace when
multiple target fields are present on the same step. **If you include both
`hr_min/hr_max` AND `pace_min/pace_max` on the same step, pace is silently
dropped** — the step gets an HR target only.

**Rule: use pace OR HR per step, never both on the same step.**
- Threshold/interval reps: use **pace** targets (the primary anchor for running)
- Warmup/cooldown/recovery: use **HR** targets (where exact pace matters less)
- If the athlete needs both pace and HR guidance for a work interval, put pace
  on the step and include the HR range in the step `description` field

**Self-correction protocol:** If you recall that "pace is broken on intervals.icu",
STOP and check which code path you're thinking of. The `workout_doc` path was
broken. The `file_contents_base64` FIT path works. The `create_planned_event` tool
uses the FIT path. Do not tell the athlete pace can't be added — it can. But do
NOT mix pace and HR on the same step — pick one per step.

### intervals.icu UI does not render API-created steps

The intervals.icu web UI shows the event on the calendar but does NOT
render `workout_doc` steps from API-created events. This is a UI
limitation — the steps ARE stored correctly (30-second push cycle, `push_errors: null`).
The athlete must check their Garmin device for step-by-step guidance.

## Getting events by ID

GET `/api/v1/athlete/{id}/events/{eventId}` returns a single event including its
`workout_doc`. The events list endpoint (`GET /events?oldest=...&newest=...`) may
not return events created in the current session due to eventual consistency
delays — prefer GET-by-ID after creation.

## Auth header

```
Authorization: Basic base64("API_KEY:{api_key}")
User-Agent: hermes-coach/1.0
```

Cloudflare blocks requests without a `User-Agent` header.

## Direct API call (fallback when create_planned_event tool unavailable)

```bash
cd /opt/data && python3 -c "
import urllib.request, json, base64

base = '/opt/data/users/<snowflake>'
with open(f'{base}/intervals_key') as f:
    api_key = f.read().strip()
with open(f'{base}/intervals_athlete_id') as f:
    athlete_id = f.read().strip()

url = f'https://intervals.icu/api/v1/athlete/{athlete_id}/events'
auth = base64.b64encode(f'API_KEY:{api_key}'.encode()).decode()

payload = {
    'name': 'Workout Name',
    'type': 'Ride',
    'category': 'WORKOUT',
    'start_date_local': '2026-07-31T09:00:00',
    'description': 'Description text.',
    'icu_training_load': 110,
    'icu_intensity': 100
}

req = urllib.request.Request(url, data=json.dumps(payload).encode(),
    headers={'Authorization': f'Basic {auth}', 'Content-Type': 'application/json',
             'User-Agent': 'hermes-coach/1.0'}, method='POST')

resp = urllib.request.urlopen(req)
print(json.loads(resp.read()))
"
```
