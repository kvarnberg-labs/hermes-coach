# Masters Athlete Training Adaptations (60+)

## Evidence Base

Masters athletes (>60) have different recovery kinetics, hormone profiles, and
injury risk compared to younger athletes. The standard polarized/pyramidal
templates designed for 30-year-olds will cause overtraining if applied directly.

### Key physiological differences

| System | Young (20–40) | Masters (60+) | Program impact |
|--------|--------------|---------------|----------------|
| Recovery rate | 24–48h post-intensity | 48–72h post-intensity | Never stack quality days |
| Muscle protein synthesis | Robust | Blunted (anabolic resistance) | Higher protein: 2.0–2.4 g/kg/day |
| Tendon/connective tissue | Elastic, fast repair | Stiffer, slower repair | Longer warm-ups, lower peak loads |
| VO2max decline | Baseline | ~10% per decade after 30 | Lower intensity ceilings |
| HRmax | Age-predicted | Lower, more variable | Verify individually — don't use formulas |
| Testosterone | Normal | Lower (gradual decline) | Recovery takes longer |
| Bone density | Stable | Declining if no impact loading | Strength training NON-NEGOTIABLE |

## Program Template: 2:1 Rhythm

```
Week 1: BUILD — normal volume, moderate intensity
Week 2: BUILD — progressive overload from week 1
Week 3: RECOVERY — 30–40% volume reduction, no intensity above Z2
Week 4: BUILD — resume from week 2 level
Week 5: BUILD — progressive overload
Week 6: RECOVERY
...repeat
```

### Load parameters

| Parameter | Standard | Masters |
|-----------|----------|---------|
| Ramp rate (CTL/week) | +3–8 | **+3–5** |
| Recovery week frequency | Every 3rd–4th | **Every 2nd–3rd** |
| Max intensity sessions/week | 2 | **1** |
| Consecutive hard days | 2 max | **0 — always separate by ≥1 easy day** |
| Weekly volume ceiling | 8–12h | **~5.5h** |
| Warm-up before intensity | 10 min | **15+ min** |
| Strength training | Seasonal (off/build only) | **Year-round, 1–2x/week** |

### Intensity distribution

- **80–85% Z1–Z2** (slightly more Z1 than younger athletes)
- **10–15% Z3–Z4** (threshold work, max 1x/week)
- **<5% Z5+** (VO2max — only when fresh and well into a block)

### Strength training for masters

- 1–2 sessions/week, year-round. Do not drop below 1/week even in race season.
- Reps: 8–12 (moderate load). Avoid maximal loads (90%+ 1RM) — higher injury risk.
- Focus: power output (move submaximal loads fast) over 1RM chasing.
- Bone density preservation is arguably more important than any wattage gain.

## When Building a Program for a Masters Athlete

1. **Get age from `get_athlete_profile` → `date_of_birth`.** If null, ASK the athlete.
2. **Pull `get_wellness(days=42)`** — check ramp rate trend. If already >+5/week, start with a recovery week.
3. **Verify max HR** — age-predicted formulas (220−age) are unreliable. Ask the athlete.
4. **Build with 2:1 rhythm** — never 3:1 or 4:1.
5. **Cap the longest ride at ~3.5h** unless the event is longer. For a 90 km gran fondo, 3.5h (210 min) is sufficient.
6. **Include strength training** in every week of the program except the final taper week.

## Common Mistakes

- Applying a 4-week linear block (3 build + 1 recovery) — too aggressive.
- Scheduling threshold sessions on consecutive weeks without a recovery week between them.
- Using age-predicted HRmax (e.g. 220−66=154) when the athlete's actual max is 162.
- Dropping strength work during build/race phases.
- Long rides >4h for a 90 km event — unnecessary fatigue for limited additional adaptation.

## Example: 7.5-Week Gran Fondo Program (66-year-old)

```
W31: Mjukstart       — 3 rides, 60–90 min, all Z2
W32: Bygg 1          — 3 rides, 75–120 min, all Z2
W33: ÅTERHÄMTNING    — 3 rides, 50–90 min, all Z2 low
W34: Bygg 2          — 3 rides, 75–150 min, all Z2
W35: Bygg 3          — 3 rides, 60–180 min, 1 threshold session
W36: ÅTERHÄMTNING    — 3 rides, 50–100 min, all Z2 low
W37: Peak + simulering — 3 rides, 50–210 min, 1 threshold + loppsimulering
W38: RACE WEEK       — 2 short rides + 2 rest days + RACE
```

Total intensity sessions: 2 threshold workouts across the entire program.
