# Norwegian Singles (running) — formats, progression, paces

Load when planning or reviewing threshold running for a single-session-per-day
runner (Norwegian Singles, sub-threshold, "Norska modellen"), or when deriving
running training paces.

The rules come from coach-brain
(`get_coaching_knowledge("norwegian singles")` → `training_philosophies.norwegian_singles`);
this file applies them. If the two ever disagree, the YAML wins.

## Core rules

- 2–3 threshold sessions per week; beginners start with 2. Never two
  threshold days in a row: Threshold → Easy → (Easy or Threshold) → repeat.
- Threshold session: **1–2 × 4–10 min** at lactate-threshold pace/HR,
  60–90 s rest between reps. Reps are sub-maximal — finish feeling one more
  rep was possible, not a time trial.
- Easy days are truly easy — Zone 1, conversational, no grey zone. Running
  easy days too fast is the most common mistake.
- Build volume first; add threshold sessions only once the base is established.

## Progression (planned → actual → adjust)

Within those bounds: 1×4 → 2×4 → 2×6 → 2×8 → 2×10 min, then add the third
weekly session (non-beginners only).

- Move **one step** at a time and change one variable per step.
- Advance only when the athlete repeatedly finishes with a rep in hand.
- **Failed step** (pauses, HR drifting above zone, RPE over target): drop back
  one step and rebuild — this is a dosing error, not the athlete's fault.
- After each session compare planned format/pace with the actual work
  intervals (`get_activity_intervals`) before choosing the next step.

## Threshold pace — source priority

1. **Lactate test data** (lab or lactate-strip test: paces at measured mmol/L,
   LT2 ≈ 4 mmol/L). Ask whether it exists before giving generic paces; tested
   paces override everything below.
2. **`get_sport_settings(sport="Run")` → `threshold_pace_mps`** (m/s). The
   `ftp` field is power, not pace. Running threshold has no relation to
   cycling FTP.
3. **Recent threshold sessions:** find them in
   `get_recent_activities(sport="Run")` (by name or `intensity_factor` ≥ 0.85),
   then use `get_activity_intervals(id)` work intervals: pace =
   `moving_time_s / distance_m × 1000` s/km. `interval_summary` in
   `get_activity_detail` is a fallback. Never use session-average `pace_mps`
   (it includes warm-up and recoveries; often 20–30 s/km slower).

Convert m/s → min/km: `sec_per_km = 1000 / mps`; 3.235 m/s → 309 s → 5:09/km.

## Pace zones from threshold pace (T)

| Zone | Offset | Example T = 5:09 | Use |
|---|---|---|---|
| Easy/recovery | T + 60–90 s | 6:09–6:39 | Most days |
| Moderate | T + 30–45 s | 5:39–5:54 | Sparingly |
| Threshold | T | 5:09 | Quality sessions |
| 10K pace | T − 15–20 s | 4:49–4:54 | Rare test / race-specific |

HR cross-check with run LTHR (`get_sport_settings(sport="Run").lthr`): easy
< ~85 % LTHR, threshold reps 95–100 % LTHR. Threshold-rep HR consistently
< 90 % LTHR suggests the pace estimate is too conservative. Running IF depends
on the configured threshold pace — trust HR + RPE over IF alone.

## Weekly templates

With strength (weekday sessions ≤ ~60 min):

```
Mon: Easy run 35–40 min + Strength A (legs) 25 min
Tue: Threshold #1 (e.g. 2×8)
Wed: Easy run 35–40 min
Thu: Rest (named in the plan table, no calendar event) — or Threshold #3 for non-beginners
Fri: Strength B (upper body + core + plyo) 25 min
Sat: Threshold #2 (e.g. 2×6)
Sun: Long run 60–90 min, easy
```

Without strength: Mon easy 35–45 · Tue threshold · Wed easy 40 or rest · Thu
rest, easy 30–40 or threshold #3 · Fri easy 35–45 · Sat threshold · Sun long
60–90 easy.

Strength A/B content and rotation: `references/strength-for-runners.md`.
