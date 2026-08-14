# Training Plan Creation & Cron Delivery

When an athlete asks for a complete multi-week training program targeting a
specific event, follow this workflow.

## 1. Data Pull (Full Set)

Before proposing ANY program, pull the complete data set:

```
verify_athlete_identity  →  get_athlete_profile  →  get_wellness(days=42)
get_fitness_chart(days=365)  →  get_recent_activities(days=90)
get_sport_settings(sport="Ride")  [repeat for Run if multi-sport]
get_planned_events(days_ahead=90)  →  get_power_curve(days=90)
get_coaching_knowledge("training periodization")
get_coaching_knowledge("tapering")
get_coaching_knowledge("nutrition during training")
```

## 2. Key Analysis Steps

### FTP/eFTP gap
Present the gap FIRST if >10W. Ask the athlete which feels right. eFTP
underestimates when CTL is rising and no maximal efforts exist — flag this.
Trust the athlete's answer over the model.

### HR zones
If athlete has no power meter (detect: `normalized_power_w: null` on activities),
derive all zones from LTHR (80/89/94/100% for Z1-Z5). Confirm max HR with the
athlete — intervals.icu's configured value is often wrong by 3-8 bpm.

### Current state summary
Present CTL trend, TSB, recent training frequency/volume, and ramp rate before
the program. Athletes need to see WHERE they are before they can understand
WHERE they're going.

## 3. Program Structure

### Periodization for gran fondo / sportive (70-150 km)

**For standard athletes (<60):**

| Phase | Duration | Focus | Key sessions |
|-------|----------|-------|-------------|
| Transition | 1 week | Soft start, establish routine | 2-3 Z2 rides, 1 short long ride |
| Base Build | 2-3 weeks | Volume progression | 2 Z2 + 1 long ride/week. Progressive long ride: 100→130→170 min |
| Recovery | 1 week | Reduce volume 30-40% | 2-3 easy Z2 rides, no intensity |
| Build + Intensity | 2 weeks | Add quality | 1 threshold session + 1 long ride/week. Sweetspot → threshold intervals |
| Taper | 10-14 days | Cut volume 40-60%, keep intensity | 1 short threshold + easy rides + openers |
| Race Week | 7 days | Minimal volume, carb load | Short activation rides, rest day before |

**For masters athletes (60+):** Use 2:1 build:recovery rhythm. See `references/masters-training.md` for the full template.

| Phase | Duration | Focus | Key sessions |
|-------|----------|-------|-------------|
| Transition | 1 week | Soft start, lower volume | 2-3 Z2 rides, 60-90 min max |
| Build 1 | 2 weeks | Conservative progression | 2 Z2 + 1 long ride. Long ride: 90→120 min |
| Recovery | 1 week | 30-40% volume cut | 2-3 easy Z2 rides, 50-90 min |
| Build 2 | 2 weeks | Volume + first quality | 1 threshold (week 2 only) + 1 long ride. Long: 150→180 min |
| Recovery | 1 week | Volume cut | 2-3 easy Z2 rides |
| Peak | 1 week | Final threshold + race simulation | 1 threshold + 1 long simulation (210 min max) |
| Race Week | 7 days | Minimal volume | Short activation rides, rest day before |

Key numbers for masters:
- Max 2 total threshold sessions in the entire program
- Longest ride: 210 min (3.5h) for a 90 km event
- Recovery weeks: every 2nd-3rd, not 3rd-4th
- Ramp rate: +3-5 CTL/week max

### Weekly template (3 rides/week minimum)

```
Tue: Quality (threshold/sweetspot in build phase, Z2 in base phase)
Thu: Z2 distance
Sun: Long ride (progressive: +20-30 min/week until 70-80% of target event time)
```

### Intensity progression

Never start with threshold intervals. Build:
1. Base: All Z2
2. Sweetspot introduction: 2×15 min @ 88-94% (of FTP or LTHR)
3. Threshold: 3×10 min @ 95-105%
4. Peak week: 3×10-12 min @ threshold

## 4. Program Delivery Format

Present as a clear weekly table with:
- Day + date
- Session type + duration
- HR zone (with numbers AND RPE description)
- Interval structure for quality sessions
- Nutrition reminder for rides ≥ 100 min
- Route suggestion only if athlete asks

**Example:**
```
Tis 26 aug — Tröskel 75 min
15' uppv → 2×15' @ Z4 (141-149), RPE 7-8 → nedv
```

## 5. Saving & Automating (Cron Check-in)

### Save the plan
Write the complete program to a markdown file at a known path:

```
/opt/data/training-plan-{athlete}.md
```

Include: pulszoner, weekly tables, rules for TSB adjustment, nutrition notes.
Reference this file from the cron prompt so the daily agent can read it.

### Create the daily check-in cron

```
cronjob create:
  schedule: "0 7 * * *"     (09:00 CEST)
  skills: ["coaching"]
  deliver: "discord:<channel_id>:<channel_id>"  # explicit — NEVER 'origin'
  prompt: |
    Du är {athlete}s dagliga coach.
    1. Läs /opt/data/training-plan-{athlete}.md
    2. Hitta dagens pass (Europe/Stockholm)
    3. get_wellness(days=1) — kolla TSB
    4. Leverera kort (max 4 rader):
       - Dag + pass + puls
       - TSB-varning/justering vid behov
       - Nutrition för långpass
    Föreslå inte rutter om du inte blir ombedd.
```

### Cron TSB rules
- TSB < −20 → vila eller max 30 min Z1
- TSB −10 to −20 → distans OK, ersätt tröskel med Z2
- TSB > −10 → kör enligt plan

### Cron delivery style
- Kort, direkt, svenska
- Ingen "hur känns det?" — bara leverera
- Max 4 rader
- Ingen rutt om inte atleten bett om det

## 6. Route Building (when athlete asks)

Use the maps skill (`maps_client.py` at `~/.hermes/skills/maps/scripts/`):
- Geocode start address with `search`
- Get cycling distances between key points with `distance --mode cycling`
- Get turn-by-turn with `directions --mode cycling`
- Query Overpass for `surface=gravel|unpaved|dirt` to find gravel roads in area

For gravel-specific routes: OSRM cycling profile doesn't prioritize surface type.
Supplement with local knowledge from the athlete's past activity names and known
gravel networks. Build routes as out-and-back or loop descriptions, not GPX files
(OSRM doesn't produce GPX).

## 7. Pushing Plan to intervals.icu Calendar (Garmin Sync)

After the plan is written to the markdown file, the athlete will often ask:
"Kan jag skicka till min Garmin Edge?" Answer: yes — create all planned events
on intervals.icu and they auto-sync to Garmin Connect → Garmin Edge.

### Bulk creation workflow

The `create_planned_event` tool creates one event per call. For a full program
(~25-30 events), batch them in groups of 3-4 per turn. Never use general-purpose
tools (curl, execute_code) — `create_planned_event` is the only supported path.

**Per-event parameters:**
- `name`: Short, descriptive (e.g. "Distans Z2", "Tröskel 2×12'")
- `date_iso`: YYYY-MM-DD
- `duration_min`: Minutes
- `description`: Pulse zone + interval structure + nutrition notes
- `planned_load`: Estimated TSS (see formula below)
- `planned_intensity`: Estimated IF (decimal, e.g. 0.65)
- `category`: "WORKOUT"
- `event_type`: "Ride" (default), "Walk" for recovery walks

### TL (Training Load) estimation

When precise TL isn't available (plan is programmatic, not from actual data),
estimate based on the sport.

**For cycling:** use the standard TSS formula:
```
TSS = duration_hours × IF² × 100
```

**Typical IF values by cycling workout type:**
| Workout | IF | Example: 90 min → TSS |
|---------|-----|----------------------|
| Z2 distans | 0.65 | 1.5 × 42.25 × 100 ≈ 63 |
| Z2 lätt (recovery week) | 0.60 | 0.83 × 36 × 100 ≈ 30 |
| Tröskelintervaller | 0.80 | 1.0 × 64 × 100 ≈ 64 |
| Långpass Z2 | 0.65 | 3.0 × 42.25 × 100 ≈ 126 |
| Lopp/tävling | 0.70 | 4.5 × 49 × 100 ≈ 220 |
| Öppningspass (pre-race) | 0.55-0.65 | 0.67 × 30.25 × 100 ≈ 20 |
| Promenad återhämtning | 0.30 | 0.5 × 9 × 100 ≈ 5 |

**For running:** use recent comparable workouts as a baseline — don't apply the
cycling TSS formula. intervals.icu uses HR-based TRIMP for running, which doesn't
map cleanly to IF². Instead:

| Run type | TL range (from recent data) |
|----------|---------------------------|
| Löpning lätt 35-40 min | 24–28 |
| Löpning lätt 30 min (recovery) | 20 |
| Tröskel 3×10 min (~62 min) | 66–68 |
| Tröskel 4×8 min (~60 min) | 66 |
| Tröskel 4×10 min (~68 min) | 74 |
| Tröskel 5×6 min (~60 min) | 68 |
| Långpass 75 min progressivt | 58 |
| Långpass 85–90 min progressivt | 65–68 |
| Långpass 60 min lugnt (recovery) | 40 |
| Styrka 40 min | 12 |
| Styrka lätt 30 min (recovery) | 8 |

**For running strength sessions:** use `event_type: "WeightTraining"` with low
TL (8–12). The TL is deliberately low because strength work contributes to
musculoskeletal development but shouldn't inflate the running CTL model.

### Present plan for approval FIRST (mandatory)

**Never bulk-create events before the athlete has reviewed the plan.** Present
the full weekly overview as a markdown table, explain the structure (build vs
recovery weeks, progression logic), and wait for explicit confirmation. If the
athlete wants changes, iterating on a table is trivial — deleting and recreating
30+ events is not. Only proceed to creation after the athlete says yes.

### Batch execution pattern

Create events week-by-week. Include the week header as a comment in your
response so the athlete can follow progress. Up to 8 parallel calls per turn
works reliably. Example flow:

```
Vecka 31 → 8 create_planned_event calls (parallel)
Vecka 32 → 8 calls
...
```

After all events are created, call `get_planned_events(days_ahead=90)` to
verify the full calendar. Confirm the count and highlight key sessions
(first threshold, longest ride, race day). **This verification step is mandatory
— do not skip it.**

### What NOT to push

- **Pure rest days** — leave the calendar empty. intervals.icu doesn't need
  "Vila" events.
- **Route suggestions** — the athlete builds their own unless asked.
- **Events for dates already past** — only create future events.

## Pitfalls

- **Don't trust intervals.icu's max HR.** Athlete-reported max HR overrides the configured value. A 3 bpm error shifts all HR zones.
- **Verify race surface via the official website.** Athletes describe events generically ("motionslopp"). Klarälvsloppet is asphalt on an old railway embankment — not gravel. Look up the race site before finalizing the plan. Surface determines expected speed, tire choice, and training terrain.
- **VO2max provides context, not a program constraint.** When an athlete shares VO2max (e.g. 38.5 at age 66), interpret it as a percentile rank, not a limiter. "Excellent" for age group confirms the Z2-heavy approach is correct but doesn't change workout prescriptions.
- **FTP gap is the first thing to report.** Before ANY zone analysis or workout prescription, flag the configured-FTP vs eFTP difference.
- **Start conservatively if the athlete reports ≤ 6/10 feel.** Don't prescribe intensity in the first week.
- **The cron agent must NEVER ask "hur känns det?".** The athlete isn't there to answer — it's a push notification, not a conversation. Deliver the workout or flag the TSB warning.
- **Don't prescribe routes unless asked.** Some athletes prefer to build their own.
- **Masters athletes (60+) need a completely different periodization.** If `get_athlete_profile` returns `date_of_birth` indicating ≥60, or the athlete tells you their age, switch to the masters template immediately. A standard 4-week block (3 build + 1 recovery) with 2 threshold sessions/week WILL cause overtraining in a 66-year-old. See `references/masters-training.md`.
