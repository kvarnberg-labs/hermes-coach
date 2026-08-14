# Cycling Activity Detail Analysis

How to analyze a cycling ride from intervals.icu activity data —
power zones, HR zones, and the power-vs-HR comparison that reveals
ride quality on hilly Z2 endurance routes.

## Essential data

Call `get_activity_detail(activity_id)` and extract these fields:

| Field | What it tells you |
|-------|-------------------|
| `normalized_power_w` | NP — stress-weighted average power |
| `avg_power_w` | Raw average power (even lower than NP on variable rides) |
| `ftp_w` | FTP used for zone calculations |
| `intensity_factor` | NP / FTP as % — key ride intensity metric |
| `avg_hr` | Average heart rate (bpm) |
| `max_hr` | Peak HR — check if athlete crossed threshold |
| `lthr` | Lactate threshold HR for zone boundaries |
| `hr_zones` | Array of HR zone boundaries: [131, 146, 153, 163, 167, 172, 181] |
| `hr_zone_times` | Seconds in each HR zone |
| `power_zones` | Array of power zone boundaries as % FTP: [55, 75, 90, 105, 120, 150, 999] |
| `power_zone_times` | Array of {id: "Z1", secs: N} objects |
| `elevation_gain_m` | Total climbing — context for zone interpretation |
| `decoupling_pct` | HR/power decoupling — <5% = good endurance |
| `variability_index` | NP/AP ratio — 1.0 = perfectly steady, 1.15+ = variable |
| `efficiency_factor` | W per bpm — aerobic efficiency proxy |
| `coasting_time_s` | Seconds not pedalling — high on descents |
| `calories` | Total kcal |
| `carbs_used_g` | Grams carbohydrate oxidised |
| `interval_summary` | Garmin auto-detected efforts |
| `avg_cadence` | Average cadence (rpm) — includes coasting (cadence=0) |
| `cadence_z2_rpm` | Cadence when power was in Z2 — excludes coasting/Z1 |

## Zone distribution analysis

### Power zones (Coggan 7-zone, % FTP)

| Zone | % FTP | Watt range (FTP 265) | Purpose |
|------|-------|----------------------|---------|
| Z1 Recovery | <55% | <146W | Active recovery |
| Z2 Endurance | 56-75% | 146-199W | Aerobic base building |
| Z3 Tempo | 76-90% | 199-239W | "Grey zone" — adds fatigue without threshold stimulus |
| Z4 Threshold | 91-105% | 239-278W | FTP-building |
| Z5 VO2max | 106-120% | 278-318W | VO2max |
| Z6 Anaerobic | 121-150% | 318-398W | Anaerobic capacity |
| Z7 Neuromuscular | >150% | >398W | Sprint power |

### HR zones (based on LTHR)

| Zone | bpm range (LTHR 164) |
|------|----------------------|
| Z1 | <131 |
| Z2 | 131-146 |
| Z3 | 146-153 |
| Z4 | 153-163 |
| Z5 | 163-167 |
| Z6 | 167-172 |
| Z7 | >172 |

### Power-vs-HR comparison (key insight for Z2 rides)

The most revealing analysis for a Z2 endurance ride is comparing **time in
power zones** against **time in HR zones**. On hilly routes, these diverge
significantly:

**Example: 4 July 2026, Z2 long ride, 87.7 km, 687m elevation**

| Zone | Power time | HR time | Gap |
|------|-----------|---------|-----|
| Z1 | 59 min (30%) | 166 min (85%) | HR much lower |
| Z2 | 76 min (39%) | 30 min (15%) | HR lower |
| Z3 | 39 min (20%) | 0 min | HR didn't follow |
| Z4 | 19 min (10%) | 0 min | HR didn't follow |

Interpretation:
- 58 min in Z3/Z4 **power** but essentially 0 min in Z3/Z4 **HR** means the
  hills pushed wattage up briefly, but not long enough for HR to rise into
  threshold territory.
- This is **acceptable for a Z2 ride** — the HR response shows aerobic
  demand stayed low even when power spiked on climbs.
- If HR had tracked power (58 min in Z3/Z4 HR), that would indicate the
  ride crossed into genuine threshold stress, defeating the Z2 purpose.
- **Scoring guideline for Z2 rides**: <10% time in Z3+Z4 power = excellent,
  10-20% = good (typical for hilly routes), 20-30% = acceptable but room for
  improvement (lower gearing, higher cadence), >30% = re-evaluate route or
  pacing strategy.

## Cadence analysis

### Coasting effect on average cadence

Average cadence from intervals.icu includes coasting time (cadence = 0).
On hilly rides with significant descending or deliberate HR-recovery sections,
this depresses the average substantially. **Do not interpret raw average
cadence without accounting for coasting.**

Estimate pedaling-only cadence:
```
pedaling_time = recording_time - coasting_time
pedaling_cadence = avg_cadence * recording_time / pedaling_time
```

Example: avg_cadence 70.5 rpm, coasting 1607s (27 min) of 11772s (196 min):
→ pedaling-only cadence ≈ 82 rpm (significantly higher than the raw 70.5).

### Zone-specific cadence

intervals.icu provides `icu_cadence_z2` — cadence specifically when power
was in Z2. This excludes coasting and Z1 descending, making it more useful
than overall average for Z2 ride analysis. No per-zone cadence is
available for Z3/Z4 via the API.

### Coaching guidance

Low cadence (<75 rpm average) on hilly Z2 rides indicates the athlete is
pushing gears too hard in climbs. Higher cadence (85+ rpm) in climbs:
- Reduces per-stroke muscle force, keeping power lower
- Lowers risk of Z3/Z4 power creep
- May reduce post-ride leg stiffness
- Suggest lighter gearing or earlier downshifting in climbs

**Always caveat cadence advice with coasting context.** If the athlete
had 25%+ coasting time, the raw average is misleading. Acknowledge the
downhill/free-wheeling contribution before suggesting cadence changes.
The athlete may push back on low-cadence advice if they know they had
significant coasting — this is a valid question, and the correct response
is to estimate pedaling-only cadence and use `icu_cadence_z2` for a
more accurate picture.

## Decoupling interpretation

| Decoupling % | Interpretation |
|-------------|----------------|
| <5% | Excellent endurance — HR stable relative to power |
| 5-8% | Normal for long rides in heat or hills |
| 8-12% | Fatigue accumulating — watch for premature exhaustion |
| >12% | Significant decoupling — possible glycogen depletion or heat stress |

## Nutrition check

For rides >90 min, compare `carbs_used_g` against intake:
- **442g carbs oxidised** on a 3h ride = ~147g/hr expenditure
- Recommended intake: 60-90g/hr for endurance rides
- If intake < expenditure by a large margin, athlete finishes with
  depleted glycogen — emphasise post-ride carb ingestion (1.5 g/kg within 2h)