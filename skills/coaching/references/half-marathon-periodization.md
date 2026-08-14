# Half Marathon Periodization (10-month plan)

A phased approach for an athlete targeting a sub-1:40 half marathon (~4:44/km).
Assumes 5–6 training days/week including running + strength. Based on Norwegian
Singles methodology for threshold work, combined with progressive long runs
and concurrent strength training.

## Goal pace derivation

```
Target time: 1h40min = 100 min
Pace: 100 / 21.1 = 4:44 /km (4.74 min/km)
```

All training paces derive from threshold pace (T-pace), which is approximately
60-minute race pace — typically 10–15 sec/km faster than half marathon pace.

**Pace zones** (from threshold pace, see `norwegian-singles-paces.md`):

| Zone | Offset from T | Example (T=4:30/km) | Use |
|---|---|---|---|
| Easy/Recovery | T + 60–90s | 5:30–6:00 /km | Most days. Conversational. |
| Moderate | T + 30–45s | 5:00–5:15 /km | Optional bridge |
| Threshold | T ± 0 | 4:30 /km | Quality sessions |
| 10K pace | T − 15–20s | 4:10–4:15 /km | Race-specific, rare |

## Phase 1: Base Building + Strength (months 1–4)

**Goal:** Build aerobic base, establish strength foundation, introduce threshold work.

| Element | Prescription |
|---|---|
| Easy runs | 3–4/week, 35–50 min, HR Z1 (<161 bpm), conversational |
| Threshold | 2/week Norwegian Singles, start at 3×6 min → progress |
| Long run | 1/week, start 60 min → build to 90 min, all Z1–Z2 |
| Strength | 2/week compound lifts (squat, deadlift, split squat, hip thrust) |
| Recovery week | Every 3rd–4th week, reduce volume 30–40% |

**Threshold progression:** 3×6 → 5×6 → 3×8 → 4×8 (by end of phase)

**Strength periodization:**
- Weeks 1–3: Anatomical adaptation (12–15 reps, 2 sets, 50–60% 1RM)
- Weeks 4–12: Maximal strength (4–6 reps, 3–4 sets, 80–90% 1RM)
- Weeks 13–16: Power conversion (3–5 explosive reps, 30–40% 1RM)

**Key rule:** Heavy leg day never the day before a threshold run.

## Phase 2: Intensification (months 5–8)

**Goal:** Increase threshold volume, extend long run, introduce race-pace work.

| Element | Prescription |
|---|---|
| Easy runs | 3/week, 40–50 min |
| Threshold | 2/week, progress: 4×8 → 3×10 → 4×10 → 3×12 min |
| Long run | 1/week, 90–120 min, progressive (last 20 min @ moderate) |
| Race-pace inserts | Add 2–3 × 5 min @ HM pace into long runs (month 7+) |
| Strength | 1–2/week maintenance (8–12 reps) |

## Phase 3: Half Marathon Specific (months 9–10)

**Goal:** Race-specific preparation, test pacing, sharpen.

| Element | Prescription |
|---|---|
| Easy runs | 2–3/week, 35–50 min |
| Threshold | 1–2/week, maintain format |
| Long run with HM pace | 1/week, 90–120 min, blocks of 10–20 min @ target HM pace |
| Test race | 10K or half marathon as B-race (month 9) for pacing feedback |
| Strength | 1/week maintenance, stop leg-heavy work 10 days before race |

## Phase 4: Taper (final 10–14 days before race)

| Days out | Prescription |
|---|---|
| D-14 to D-10 | Normal easy runs, last long run (reduced 50% duration) |
| D-9 to D-7 | Short threshold session (3×5 min), 2 easy runs |
| D-6 to D-4 | Easy runs only, include 3–4 × 60 sec @ HM pace surges |
| D-3 | Easy run 30 min or rest |
| D-2 | Rest or very easy 20 min jog |
| D-1 | Rest, light strides optional |
| Race day | 20 min warm-up jog + 3–4 strides |

**TSB target on race day:** +5 to +15

## Data needed before planning

Before prescribing specific paces, determine the athlete's threshold pace:

1. **Lactate testing data** (lactrace, lab) — authoritative if available
2. **`get_sport_settings(sport="Run")`** — running FTP/threshold pace from intervals.icu
3. **Recent race result** — use a 10K time to estimate threshold via Jack Daniels VDOT
4. **`get_activity_detail(id)`** — `interval_summary` field for actual threshold session paces

If none of these are available, prescribe by HR zones from LTHR:
- Threshold HR: 95–100% LTHR
- Easy HR: <85% LTHR

## Pitfalls

- **Don't set target pace as threshold pace.** Half marathon pace is slower than threshold. If the athlete's threshold is 4:30/km, HM pace is ~4:44/km.
- **Long runs shouldn't all be at HM pace.** Most long run volume is Z1–Z2. Race-pace blocks are introduced gradually in Phase 3.
- **Strength isn't optional for runners.** It improves economy, prevents injury, and maintains bone density. Don't drop it entirely.
- **10 months is plenty of time.** Don't rush the progression. The athlete benefits more from consistent 5–6 day weeks than from cramming volume.
- **Female athlete considerations:** Cycle phase affects RPE and recovery. Late follicular (days 6–14) is the best window for key sessions and testing. Luteal phase may require 10–15% intensity reduction. Track ferritin — heavy menstrual bleeding increases iron deficiency risk.
