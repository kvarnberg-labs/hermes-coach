# Running activity detail — interval pace and pace zones

Load when analysing a structured run (intervals, threshold) or when you need
the pace the athlete actually held on work reps.

## Rule

Session-average pace is not interval pace. `pace_mps` and distance/duration
from `get_recent_activities` include warm-up, recovery jogs and cool-down —
often 20–30 s/km slower than the reps (one 3×10 min session: average 5:09/km,
reps 4:44/km). Never prescribe today's interval pace from a previous session's
average.

## Sources, in order

1. **`get_activity_intervals(id)`** — the athlete's detected intervals with per
   interval `type`, `moving_time_s`, `distance_m`, `average_hr`, `max_hr`,
   `average_cadence`, `intensity_pct`, `zone`. Use the `WORK` intervals:
   pace = `moving_time_s / distance_m × 1000` s/km. Not returned by
   `get_activity_detail`.
2. **`get_activity_detail(id)` → `interval_summary`** — Garmin auto-detected
   efforts as `"Nx XmXs X:XX"`, e.g. `"6x 4m43s 4:44"` = 6 segments of ~4:43 at
   4:44/km. Good fallback.
3. **`pace_zone_times`** against **`pace_zones`** (same response) — seconds per
   pace zone; boundaries are % of threshold pace. Example
   `pace_zones: [77.5, 87.7, 94.3, 100.0, 103.4, 111.5, 999]` → Z4 =
   94.3–100 % (threshold), Z5+ faster.
4. **`threshold_pace_mps`** — intervals.icu's threshold (critical-speed)
   estimate in m/s. Reference only; a lactate-tested threshold wins.
   `min/km = 1000 / threshold_pace_mps / 60`.

If a field is missing from the response, say it is unavailable — do not
reconstruct it from averages.
