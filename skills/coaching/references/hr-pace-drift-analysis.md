# HR-vs-Pace Drift Analysis

When an athlete reports "I'm getting slower at the same heart rate" or "my
heart rate is higher at the same pace," do NOT dismiss it as perception or
tell them to simply run slower. Quantify the drift with a structured
comparison across their recent training window.

## When to use

- Athlete says pace at low HR is declining over weeks
- Athlete says HR at their usual easy pace is creeping up
- Easy runs feel harder at the same pace (RPE rising without pace change)
- Threshold pace stagnates or regresses while max HR at that pace increases

This pattern almost always indicates **accumulated fatigue from chronic
training load**, not lost fitness — but you must prove it with data before
prescribing a fix.

## Method

### Step 1 — Extract easy runs (exclude threshold, walks, strength)

From `get_recent_activities(days=30, sport="Run")`, filter to easy runs only:
- Exclude threshold/interval sessions (name contains "Tröskel", "3x", "5x", or IF > 87%)
- Exclude walks (type = "Walk")
- Exclude strength (type = "WeightTraining")

### Step 2 — Tabulate pace, max HR, RPE, elevation per run

For each easy run, record:
- Date, pace (convert m/s → min:sec/km), max HR, RPE, distance, elevation gain, TL, IF

### Step 3 — Compare early vs late period

Split the window in half (e.g., first 2 weeks vs last 2 weeks) and compute
averages for pace, max HR, RPE, and TL. Look for:

| Pattern | Interpretation |
|---------|---------------|
| Same pace, higher HR (+5–10 bpm) | Cardiovascular efficiency reduced — accumulated fatigue |
| Same HR, slower pace | Same underlying cause — heart works harder at every pace |
| Higher RPE at same pace | Central nervous system fatigue |
| Higher TL at same pace | Sessions are costing more than they should |

**Control for elevation** — a hilly easy run will show higher HR and slower
pace regardless of fatigue. Compare runs with similar elevation gain (±20m)
when possible, or flag elevation as a confound.

### Step 4 — Check threshold sessions too

Compare threshold pace, max HR, and RPE across the period. If threshold pace
is stagnant or declining while max HR rises and RPE increases, the fatigue
is systemic, not just easy-day drift.

### Step 5 — Connect to CTL/ATL/TSB history

Pull `get_fitness_chart(days=90)` and check:

- **CTL ramp rate** — sustained >+8 CTL/week is a red flag; >+10 is dangerous
- **TSB** — how many consecutive days negative? >4–6 weeks of negative TSB
  means the body has had no real recovery
- **Best performance timing** — did the athlete's best session come after a
  temporary TSB improvement? If yes, that proves the issue is recoverable
  fatigue, not permanent decline (e.g., athlete ran their best threshold
  pace after TSB improved from −45 to −18, then regressed when TSB
  dropped again)

### Step 6 — Present the evidence, then prescribe

Show the athlete:
1. A table of easy runs with pace, HR, RPE over time
2. The early-vs-late comparison with the delta
3. The CTL ramp rate and TSB history
4. The key insight: "same pace, +10 bpm, +1 RPE = your heart is working
   harder at every tempo because it hasn't recovered — not because you've
   lost fitness"

Then prescribe: **insert a deload week** (or two consecutive light weeks
if the fatigue is deep). Reduce volume 30–50%, drop threshold to light
fartlek, shorten the long run, lighten strength to RPE 5–6. The body will
supercompensate — HR at given pace will drop back down.

## Pitfalls

- **Don't confuse this with the breathlessness plateau** — that reference
  (`running-plateau-and-breathlessness.md`) covers ventilatory threshold
  issues (easy running comfortable but modest pace increase causes rapid
  breathlessness). HR-pace drift is about cardiovascular efficiency
  regression from chronic load. Both can coexist but have different causes
  and different fixes.
- **Elevation is a confound** — always check elevation gain when comparing
  pace/HR across runs. A 40m elevation run at 5:48/km @ 172 bpm is not
  comparable to a 7m elevation run at 5:55/km @ 164 bpm without adjusting.
- **Don't prescribe more rest than needed** — two light weeks is usually
  sufficient for 8–10 weeks of accumulated fatigue. Don't extend to a
  month unless the athlete is still showing elevated HR after the first
  deload.
- **Weather can confound** — heat increases HR at given pace by 5–15 bpm.
  If the drift coincides with a heat wave, check temperature before
  concluding accumulated fatigue. Use `get_weather` if the athlete's
  location is known.
