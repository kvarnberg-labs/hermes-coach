# Norwegian Singles (running) — formats, progression, paces

Load when planning or reviewing threshold running for a single-session-per-day
runner (Norwegian Singles, sub-threshold, "Norska modellen"), or when deriving
running training paces.

The principle summary lives in coach-brain:
`get_coaching_knowledge("norwegian singles")` → `training_philosophies.norwegian_singles`.
That YAML allows 2–3 threshold sessions/week and describes reps more broadly;
this file is the operational default (2 sessions/week, the progression ladder
below). If they disagree for a specific athlete, say which you are using.

## Core rules

- 2 threshold sessions per week, separated by at least one easy day.
- Reps are **controlled**: at or just below threshold, finish feeling one more
  rep was possible. Short recoveries (~60 s).
- Easy days are truly easy — conversational, no grey zone. Running easy days
  too fast is the most common mistake.

## Progression ladder (planned → actual → adjust)

3×6 → 5×6 → 3×8 → 4×8 → 3×10 → 4×10 → 3×12 min.

- Move **one step** at a time; each step changes one variable. Do not skip
  steps (3×6 → 3×8 raises rep length +33 % and total work +20 % at once).
- Advance only when the athlete repeatedly finishes with a rep in hand.
- **Failed step** (pauses, HR drifting above zone, RPE over target): drop back
  one step and rebuild — this is a dosing error, not the athlete's fault.
- After each session compare planned format/pace with the actual work
  intervals (`get_activity_intervals`) before choosing the next step.

## Format library

| Format | Work | Best when |
|---|---|---|
| 5×6 min | 30 min | Variety; fresher feel |
| 4×8 min | 32 min | Bridge to 3×10 |
| 3×10 min | 30 min | Classic default |
| 3×12 min | 36 min | Ready for a volume bump |
| 2×15 min | 30 min | Prefers fewer, longer reps |
| 6×5 min | 30 min | Sharpening when fresh |

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
Tue: Threshold #1 (e.g. 4×8)
Wed: Easy run 35–40 min
Thu: Rest (named in the plan table, no calendar event) / optional easy 0–25 min
Fri: Strength B (upper body + core + plyo) 25 min
Sat: Threshold #2 (e.g. 5×6)
Sun: Long run 60–90 min, progressive
```

Without strength: Mon easy 35–45 · Tue threshold · Wed easy 40 or rest · Thu
rest or easy 30–40 · Fri easy 35–45 · Sat threshold · Sun long 60–90.

Strength A/B content and rotation: `references/strength-for-runners.md`.
