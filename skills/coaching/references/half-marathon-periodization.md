# Half Marathon Periodization (10-month plan)

A phased approach for an athlete targeting a sub-1:40 half marathon (~4:44/km).

## Session-derived planning notes

- Keep the race goal and season horizon persistent across conversations; do not let a missing transcript detail turn the plan into generic running advice.
- For an athlete currently around 35–37 km/week, CTL ~29, with a recent 10 km around 53 min and a 16 km long run, begin with a stable 3-run structure: two conversational easy runs, one controlled quality session, and a gradual long-run extension. Add a fourth run only after several stable weeks.
- If easy running is comfortable but modestly faster running causes rapid breathlessness while legs remain relatively fresh, preserve one controlled quality stimulus, avoid forcing arbitrary pace targets, and follow up on symptoms if the pattern persists. Normal blood/iron tests and a strong exercise test should be treated as reassuring prior context, not repeatedly re-proposed as the explanation.
- Calendar plans should be shown for approval before bulk creation. After approval, make rest/deload days explicit, use date+weekday labels, and explain the weekly adjustment loop.

## Adjustment loop for future reviews

Weekly review: compare actual vs planned run count, duration, distance, session-RPE/load, long-run duration, quality completion, CTL/ATL/TSB, ramp rate, HRV, sleep, resting HR, and breathing symptoms. Hold progression when subjective fatigue or breathlessness worsens, resting HR is persistently elevated, HRV is suppressed, or quality degrades. Reduce intensity/volume and add recovery when multiple signals agree; progress one variable at a time (usually duration before pace) when recovery is stable. Reassess the phase every 3–4 weeks rather than changing the whole plan after one difficult run.
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

---

## Moved from SKILL.md (2026-09-14)

- **Never invent, upgrade, or inflate an athlete's race goal.** The athlete's goal is a durable coaching anchor stored in memory, cron prompts, and conversation history. Do NOT infer a more ambitious target than what is recorded. For example, if the recorded goal is "halvmaraton under 1:40 (4:44/km)", do NOT write "sub-1:38 (4:39/km)" or "elit-aktigt halvmaramål" unless the athlete has explicitly stated a new goal in the current conversation. Goal inflation is a fabrication — the athlete did not say it, and it shifts all training prescriptions toward intensities the athlete has not targeted. If you are unsure of the exact goal, retrieve it from saved memory or the verified profile, and if still unclear, ask the athlete directly. When an athlete DOES state a new or revised goal, save it to memory immediately and update any cron prompts that reference the old goal.
### Goal-anchored half-marathon planning
For a runner targeting a spring 2027 half-marathon under 1:40 (4:44/km), keep the goal as the persistent anchor while adapting the current week. **Continuity requirement:** if the goal was already confirmed and saved, do not ask the athlete to repeat it. Retrieve/use saved memory and the verified profile, then acknowledge the goal briefly before planning. If the athlete says the same discussion has happened repeatedly or expresses frustration, stop the loop: state the known goal and constraints, give the concrete next-step plan, and do not ask another generic intake question unless a genuinely blocking detail is missing.

**Plan quality requirement:** a practical plan must explain the causal hypothesis it is testing (for example, reducing accumulated fatigue while preserving one controlled quality stimulus), define a short initial block with exact weekly structure, and specify what observation will trigger progression or reduction. Do not present a generic multi-phase outline as if it were a sufficient answer when the athlete asks "what do you think?" Use current sport-specific data only as evidence: recent TSB/ATL can support current fatigue, but cannot explain a decline that began years earlier. Avoid overclaiming that a recent load spike is the root cause.

Do not prescribe goal pace as everyday training pace when current data is substantially slower; use phases: aerobic consistency and easy-volume tolerance first, threshold/volume development next, race-specific pace later, then taper. A suitable early template is 3 runs/week (two easy, one controlled quality) plus 1–2 short strength sessions, with the long run on the weekend. Progress toward four runs and 40–50 km/week only when recovery and breathing tolerate it; build the long run gradually toward 18–22 km. Schedule a deload every 3rd–4th week, and use actual-vs-planned load, CTL/ATL/TSB, HRV, sleep, resting HR, RPE, and breathing—not pace alone—to decide whether to hold, progress, or reduce.

### Time and cross-training constraints

Treat a weekday availability of about 60 minutes as a hard practical constraint. Keep weekday runs, quality sessions, and combined sessions within that limit; place longer long runs on weekends. Strength is support work for the half-marathon: early phases may use two controlled sets at RPE 6–7 to limit DOMS and interference with running, progressing to three sets only after stable tolerance. A 15–25 minute easy crosstrainer block at RPE 3–4 may be added before or after short strength as low-intensity aerobic volume, but it is not a replacement for the key running stimulus and should not compromise the next run.

### Trust and continuity

If the athlete asks whether the plan has a purpose, explicitly connect every component to the race goal (easy running = aerobic base, quality = threshold/fart, long run = durability, strength = economy/resilience, recovery = adaptation). Never promise perfect recall of every conversation: state what is saved, use fresh intervals.icu data, and say when a detail is missing instead of guessing. If a goal is confirmed, save the goal and key constraints, but still re-check current data before each progression.

