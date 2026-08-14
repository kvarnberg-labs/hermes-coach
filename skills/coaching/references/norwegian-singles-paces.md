# Norwegian Singles Pace Calculation

How to derive an athlete's running threshold pace and compute all training
zones from intervals.icu activity data.

## Where to get the data

Four sources, in priority order:

1. **Lactate testing data (lactrace, InnoSport, etc.)** — **highest priority.**
   If the athlete has done lactate testing and has actual threshold paces from
   blood lactate measurements, those are the authoritative source. Common formats:
   - Lactrace: shows paces at measured lactate levels (mmol/L), with LT1 (~2 mmol/L)
     and LT2 (~4 mmol/L) turnpoints marked
   - Lab report: usually lists paces at 2.0, 2.5, 3.0, 3.5, 4.0 mmol/L
   - **Always ask the athlete if they have lactate data before giving generic
     pace estimates.** Trust tested paces over any computed zone.

2. **`get_sport_settings(sport="Run")`** — if the athlete has configured a running
   FTP (threshold pace) in intervals.icu, it will be returned as `ftp`. Use this
   when lactate data is unavailable.

3. **`get_recent_activities(sport="Run")`** — use for identifying WHICH runs were
   threshold sessions (filter by `intensity_factor` ≥ 85, name, or date). The
   `pace_mps` field is the SESSION AVERAGE (includes warmup, recovery jogs,
   cool-down) — **never use it to estimate interval pace.** The gap between
   session average and actual interval pace can easily be 20-30 sec/km, not the
   5-10 one might assume. Always follow up with source #4 for real interval data.

4. **`get_activity_detail(activity_id)`** — **the authoritative source** for actual
   interval paces from activity data. Returns three critical fields:
   - **`interval_summary`**: Garmin's auto-detected effort segments. Format is
     `"Nx XmXs X:XX"` (e.g. `"6x 4m43s 4:44"` = 6 segments averaging 4:43 at
     4:44/km pace). This is the BEST field for determining what pace the athlete
     actually held during their work intervals.
   - **`pace_zone_times`**: seconds spent in each pace zone (indexed against
     `pace_zones` array). Use to understand intensity distribution.
   - **`threshold_pace`**: the athlete's calculated threshold pace in m/s
     (intervals.icu's critical speed estimate). Reference value, not ground truth.

## Pace computation from m/s

intervals.icu returns pace in meters per second (m/s). Convert to min/km:

```
sec_per_km = 1000 / pace_mps
pace_minkm = f"{int(sec_per_km // 60)}:{int(sec_per_km % 60):02d}"
```

Example: `pace_mps = 3.235` → `1000/3.235 = 309.1 sec/km` → `5:09 /km`

## Zone derivation from threshold pace

All zones are offsets from threshold pace (T-pace), in seconds/km:

| Zone | Offset | Example (T=5:09/km) | Use |
|---|---|---|---|
| Easy/Recovery | T + 60–90s | 6:09–6:39 /km | Most days. Conversational. Zone 1 HR. |
| Moderate | T + 30–45s | 5:39–5:54 /km | Optional bridge. Use sparingly. |
| Threshold | T ± 0 | 5:09 /km | Quality sessions. 3-5 × 6-10 min, 60s rest. Controlled. |
| 10K pace | T − 15–20s | 4:49–4:54 /km | Rare progression test or race-specific. |

## HR cross-check

If run LTHR is available from `get_sport_settings(sport="Run").lthr`:
- Easy runs should stay below ~85% LTHR
- Threshold intervals should be at 95–100% LTHR
- If the athlete's HR on threshold intervals is consistently low (< 90% LTHR),
  the threshold pace estimate may be too conservative

## Pitfalls

- **Session average pace ≠ threshold pace.** Warmup and cooldown pull the average
  down significantly. A 3×10 min session with 15 min warmup/cooldown at easy pace
  can have an average 20-30 sec/km slower than the work intervals. NEVER estimate
  interval pace from session average — always pull `interval_summary` from
  `get_activity_detail` for the actual work-interval paces.
- **IF is cycling-biased.** intervals.icu's intensity factor for running is derived
  from pace relative to configured threshold, which may differ from the athlete's
  true lactate threshold. Trust HR + RPE over IF alone.
- **Don't extrapolate from cycling FTP.** Running threshold has no relationship to
  cycling FTP. Get it from run data or run settings only.
