# intervals.icu API Coverage

Current toolset → API endpoint mapping and known gaps.

## Current tools

| Tool | API Endpoint | Covers |
|---|---|---|
| `get_athlete_profile` | `/athlete/{id}` | name, weight, timezone, resting HR, sex, DOB |
| `get_sport_settings` | `/athlete/{id}/sport-settings/{sport}` | FTP, indoor FTP, zones, LTHR, max HR, W' |
| `get_recent_activities` | `/athlete/{id}/activities` | activity list with key fields (see plugin source `fields=` param) |
| `get_activity_detail` | `/athlete/{id}/activities/{id}` | full detail: zones, intervals, laps, decoupling, VI, EF, etc. |
| `get_wellness` | `/athlete/{id}/wellness` | CTL/ATL/TSB, HRV, sleep, RHR, weight, sport eFTP/W'/Pmax |
| `get_planned_events` | `/athlete/{id}/events` | upcoming events (forward-looking only) |
| `get_power_curve` | `/athlete/{id}/power-curves` | peak power at 5s, 1min, 5min, 20min, 60min |
| `create_planned_event` | `/athlete/{id}/events` (POST) | create new planned workouts on calendar |
| `delete_planned_event` | `/athlete/{id}/events/{id}` (DELETE) | remove planned events by ID |

## Implemented (was gap)

### 1. Activity streams — `get_activity_streams` ✅
**Endpoint:** `/api/v1/activity/{id}/streams` (NOT `/athlete/{id}/activities/{id}/streams` — the streams endpoint uses `/activity/` prefix, not `/athlete/`).
**What it gives:** Per-second arrays for time, watts, cadence, heartrate, distance, altitude, latlng, velocity, temp, torque, L/R balance, respiration (varies by activity). **The tool returns computed peak power (5s, 1min, 5min, 20min, 60min) and an eFTP estimate (95% of best 20-min) — NOT raw 10K+ element arrays.** Per-stream sample points (first 5, last 5) and data-point counts are included for validation. Raw arrays are processed server-side by a sliding-window peak-extraction algorithm to keep responses compact (~2KB vs 838KB raw).
**Verified on real data:** 11,611 data points for an 86km ride across 12 stream types. Response: ~1,754 chars.
**Caching:** 15-min TTL (same as other activity endpoints).
**Use case:** Validate eFTP from actual 20-minute peak extraction, compare peak power against configured FTP, compute power-to-weight at standard durations without loading raw data into the context window.

### 2. Fitness chart — `get_fitness_chart` ✅
**Endpoint:** `/api/v1/athlete/{id}/wellness` with `oldest`/`newest` params (up to 365 days). There is no separate `/fitness` endpoint — wellness already supports long date ranges.
**What it gives:** Daily CTL/ATL/TSB, ramp rate, per-sport eFTP for season-long trend analysis (496 records from Feb 2025 to present for this athlete).
**Caching:** 30-min TTL.
**Use case:** Track eFTP progression over months, identify peak fitness periods, season load trends.

### 3. Event creation/deletion — `create_planned_event` / `delete_planned_event` ✅
**Endpoint:** `/api/v1/athlete/{id}/events` (POST to create, DELETE `/events/{id}` to remove).
**What it gives:** Ability to create new planned workouts with name, date, type, description, planned training load, intensity, duration, indoor flag, and start time. Delete removes events by numeric ID.
**Created via:** `develop_tool` — lives as a standalone plugin at `/opt/data/plugins/create_planned_event/` with its own `tool.py` and `register_tools(ctx)` function. Follows the same credential-loading and auth-header patterns as `intervals_icu.py`.
**Fields accepted on POST:** `name`, `type`, `category`, `start_date_local`, `description`, `icu_training_load`, `icu_intensity`, `moving_time` (seconds), `indoor` (bool).
**Pitfall:** DELETE requires a `User-Agent` header; Cloudflare may block requests without one.
**Use case:** Programmatically populate an athlete's training calendar, deleting stale sessions and creating new ones in a single session.

## Remaining gaps

### 4. Calendar (past) — same `/athlete/{id}/events` but with historical date range
**What it gives:** Past events and planned workouts, not just future.
**Why it matters:** Training plan adherence tracking, comparing planned vs actual execution.
**Blocked by:** `get_planned_events` only queries forward from today. Trivial fix — just extend the date range backward.

### 4. Calendar (past) — same `/athlete/{id}/events` but with historical date range
**What it gives:** Past events and planned workouts, not just future.
**Why it matters:** Training plan adherence tracking, comparing planned vs actual execution.
**Blocked by:** `get_planned_events` only queries forward from today. Trivial fix — just extend the date range backward.

### 5. Workouts / training plans
**What it gives:** Structured workout definitions if intervals.icu training plan builder is used.
**Why it matters:** Could pull prescribed workouts to compare against actual execution.
**Unknown:** Unclear if a public API endpoint exists for this.

## Priority

1. **Past events** — trivial fix, low effort for history.
2. **Training plans** — uncertain if endpoint exists.
