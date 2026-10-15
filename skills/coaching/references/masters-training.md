# Masters athletes (50+)

Load before building or changing any plan for an athlete aged 50 or older
(`get_athlete_profile → date_of_birth`; if null, ask). Apply these adjustments
before the plan is drafted — a template built for a 30-year-old over-trains a
masters athlete.

Hard limits are in coach-brain and win on conflict:
`coach-brain/coaching-safety.yaml` (`ramp_rate_caps.conservative`,
`recovery_weeks.masters_50_plus`, `hard_stops`),
`coach-brain/recovery-heuristics.yaml`, and
`coach-brain/strength-training.yaml → masters_athletes_50_plus`.

## Load parameters

| Parameter | Standard | Masters 50+ |
|---|---|---|
| Ramp rate (CTL/week) | +3–8 | **+3–5** |
| Recovery week | every 3rd–4th | **every 2nd–3rd** (2:1 rhythm) |
| Intensity sessions/week | 2 | **1** |
| Consecutive hard days | max 2 | **never — ≥ 1 easy day between** |
| Warm-up before intensity | 10 min | **15+ min** |
| Strength | seasonal | **year-round, 1–2×/week; never below 1** |
| Weekly volume ceiling | 8–12 h | ~5.5 h (practice guideline) |

Intensity distribution: ~80–85 % Z1–Z2, 10–15 % Z3–Z4 (threshold max 1×/week),
< 5 % Z5+ only when fresh. Protein 2.0–2.4 g/kg/day (`nutrition.yaml`).

## Building the plan (planned → actual → adjust)

1. Age from the profile; ask if missing.
2. `get_wellness(days=42)`: if the ramp is already > +5 CTL/week, start with a
   recovery week.
3. Ask for the real max HR — age formulas are unreliable (one athlete: formula
   154, actual 162).
4. Use 2:1 build:recovery, never 3:1 or 4:1; no threshold sessions in
   back-to-back weeks without a recovery week between.
5. Cap the longest ride near 3.5 h unless the event is longer (3.5 h is
   enough for a 90 km gran fondo).
6. Strength every week except the final taper week: 8–12 reps, submaximal
   loads moved fast; avoid ≥ 90 % 1RM.
7. Each recovery week, compare planned vs actual load and the ramp; hold or
   reduce when the ramp exceeded +5 or recovery markers worsened.

## Example: 7.5-week gran fondo block (age 66)

```
W1 Soft start      3 rides, 60–90 min, all Z2
W2 Build 1         3 rides, 75–120 min, all Z2
W3 RECOVERY        3 rides, 50–90 min, low Z2
W4 Build 2         3 rides, 75–150 min, all Z2
W5 Build 3         3 rides, 60–180 min, 1 threshold
W6 RECOVERY        3 rides, 50–100 min, low Z2
W7 Peak + sim      3 rides, 50–210 min, 1 threshold + race simulation
W8 Race week       2 short rides + 2 rest days + race
```

Two threshold sessions in the whole block. A VO2max ratio such as 38.5 at 66 is
context ("excellent for age"), not a programme limiter.
