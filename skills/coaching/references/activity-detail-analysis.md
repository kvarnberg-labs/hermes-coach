# Activity Detail Analysis

How to extract actual interval paces from an intervals.icu activity — the
only reliable way to get work-interval pace from recorded data.

## Critical fields

When you call `get_activity_detail(activity_id)` (or curl the equivalent
API endpoint), three fields are essential for interval analysis:

### `interval_summary`

Garmin's auto-detected effort segments. Each entry has the format:

```
"Nx XmXs X:XX"
```

Examples:
- `"6x 4m43s 4:44"` → 6 segments averaging 4:43 at 4:44/km pace
- `"3x 10m12s 4:51"` → 3 segments averaging 10:12 at 4:51/km pace
- `"1x 5m42s 5:41"` → single warmup segment: 5:42 at 5:41/km

**This is the BEST field for determining actual interval pace.** It directly
reports the pace the athlete held during their work intervals, stripped of
warm-up, recovery jogs, and cool-down.

### `pace_zone_times`

Array of seconds spent in each pace zone, indexed against `pace_zones` array.
Example:
```
pace_zones: [77.5, 87.7, 94.3, 100.0, 103.4, 111.5, 999.0]
pace_zone_times: [1008, 540, 1041, 417, 70, 25, 0]
```

Where zone boundaries are percentages of `threshold_pace`:
- Z1: < 77.5% of threshold → slowest
- Z2: 77.5–87.7%
- Z3: 87.7–94.3%
- Z4: 94.3–100.0% (threshold zone)
- Z5: 100.0–103.4%
- Z6: 103.4–111.5%
- Z7: > 111.5% → fastest

### `threshold_pace`

The athlete's calculated threshold pace in **meters per second** (m/s).
intervals.icu derives this from critical speed modeling. It's a reference
value — the athlete's actual lactate-tested threshold may differ.

Convert to min/km:
```python
sec_per_km = 1000 / threshold_pace_mps
pace_str = f"{int(sec_per_km // 60)}:{int(sec_per_km % 60):02d}"
```

## Direct API access (when tool is unavailable)

If `get_activity_detail` isn't registered as a tool, use curl directly:

```bash
curl -s -u "API_KEY:<key>" \
  "https://intervals.icu/api/v1/athlete/<athlete_id>/activities/<activity_id>?fields=id,name,start_date_local,type,moving_time,distance,laps,pace,pace_zones,pace_zone_times,interval_summary,threshold_pace,heartrate_zones,heartrate_zone_times"
```

Credentials are stored at `$HERMES_HOME/users/discord_dm/intervals_key` and
`$HERMES_HOME/users/discord_dm/intervals_athlete_id`.

## Example: July 1 threshold run analysis

Session: "Mellerud - 3 x 10 min", 10.03 km, 51:42

| Metric | Value |
|--------|-------|
| Session average pace | 5:09/km (misleading!) |
| interval_summary | `"6x 4m43s 4:44"` |
| Actual interval pace | **4:44/km** |
| threshold_pace (calc) | 4:22/km (3.817 m/s) |
| Time in Z3+Z4 (threshold) | 24:18 of 51:42 (47%) |

The session average (5:09/km) was **25 sec/km slower** than the actual
interval pace (4:44/km). The "subtract 5-10 sec/km" heuristic fails badly
for structured interval sessions with significant warm-up/cooldown volume.

## Pitfall

- **Never use session average pace for interval prescriptions.** Always
  pull `interval_summary` from the activity detail. The gap between average
  and interval pace grows with longer warm-ups and cooldowns.
