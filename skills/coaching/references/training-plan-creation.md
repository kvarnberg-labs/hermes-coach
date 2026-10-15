# Multi-week plan creation — frozen checklist

Load when an athlete asks for a multi-week programme, a new training week, or a
permanent change to their weekly structure. Work through every item in order.

## A. Data (one parallel batch where possible)

1. Identity verified this session.
2. `get_athlete_profile` — age (masters 50+ → `references/masters-training.md`
   before drafting), timezone, availability.
3. `get_wellness(days=42)` and `get_fitness_chart(days=365)` (weekly
   resolution) — CTL trend, ramp rate, TSB.
4. `get_recent_activities(days=90)` — frequency/volume per sport, separated.
5. `get_sport_settings` for **each** sport in the plan (Ride and/or Run).
6. `get_planned_events(days_ahead=90)` — what already exists (stale events,
   races).
7. `get_best_effort_curve(sport=…, days=90)` when power/pace targets are involved (`sport="Run"` for pace; the default is Ride).
8. Knowledge: `get_coaching_knowledge("periodization")`, `("tapering")`,
   `("nutrition")` as relevant.
9. Event facts: surface, elevation, distance from the organiser's course page —
   ask the athlete for it (`get_coaching_knowledge("race course verification")`);
   unverified → terrain-independent guidance only.

## B. Analyse before proposing

10. Configured FTP vs eFTP gap > 10 W → report first, ask which feels right
    (`references/ftp-testing.md`).
11. No power meter (`normalized_power_w: null`) → LTHR zones and ask for the
    real max HR (`references/hr-based-training.md`).
12. Current state in a few lines: CTL trend, TSB, recent volume, ramp rate.
13. Feel ≤ 6/10 → no intensity in week 1.

## C. Draft (shown as a table, nothing written yet)

14. Phases: transition → base (volume) → recovery → build (+quality) →
    taper (−40–60 % volume, keep intensity) → race week. Never open with
    threshold: Z2 base → sweet spot (2×15 @ 88–94 %) → threshold (3×10 @
    95–105 %).
15. Recovery week every 3rd–4th week (masters every 2nd–3rd); ramp within
    `coaching-safety.yaml → ramp_rate_caps`.
16. Long session builds +20–30 min/week to ~70–80 % of event time.
17. Table rows: weekday + date, session + duration, zone with numbers and RPE,
    interval structure, fuelling note for sessions ≥ 100 min, planned load.
    Rest days named in the table; no routes unless asked.
18. Totals ("12 pass") reconcile with the rows; every weekday is derived from
    its date.
19. State the weekly adjustment loop: which actual-vs-planned inputs you will
    review and the hold / reduce / progress rules.

## D. Approval

20. Wait for explicit approval ("ja, lägg in"). A plan request alone is not
    approval. Changes are cheap in a table, expensive in 30 events.

## E. Write and verify

21. Write week by week (up to ~8 parallel calls): `create_planned_events_bulk`
    for unstructured sessions, `create_planned_event` for anything with steps.
    Rules: `references/event-creation-pitfalls.md`.
22. Planned load estimates (below); strength as `WeightTraining` with low load.
23. Re-read with `get_planned_events(days_ahead=<plan length>)`; confirm count,
    date range and key sessions (first threshold, longest session, race day).
    Mandatory.
24. Save the agreed weekly structure, goal and constraints to memory.

## Permanent schedule changes

A recurring change ("HIIT on Fridays from now on") needs full-week
reconciliation: map what the new session displaces, show the reshuffled week,
let the athlete choose between viable arrangements (`clarify`), adopt their own
proposal when it works, then create the new events and **delete superseded
ones** — including rest-day events from older plans. More events than days in a
window means stale duplicates. Re-read the range afterwards and update memory.

## Planned-load estimates

Cycling: TSS = hours × IF² × 100. Typical IF: Z2 0.65 (90 min ≈ 63), easy
recovery 0.60, threshold session 0.80 (60 min ≈ 64), race 0.70, openers
0.55–0.65, recovery walk 0.30.

Running (HR-based load; base on the athlete's own comparable sessions when
available):

| Session | Load |
|---|---|
| Easy 30–40 min | 20–28 |
| Threshold 3×10 / 4×8 / 5×6 (~60 min) | 66–68 |
| Threshold 4×10 (~68 min) | 74 |
| Long run 60 min easy / 75 min / 85–90 min progressive | 40 / 58 / 65–68 |
| Strength 30 / 40 min | 8 / 12 |

## Pitfalls

- Intervals.icu max HR is often wrong; the athlete's value wins.
- VO2max values are context (age percentile), not a programme constraint.
- Masters athletes get the masters template — a 3:1 block with two threshold
  sessions a week over-trains a 66-year-old.
