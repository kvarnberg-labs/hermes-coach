# Norwegian Singles (Running)

Moved verbatim from skills/coaching/SKILL.md (2026-09 restructure). The
threshold format library and progression warnings here have no counterpart
in coach-brain/training-philosophies.yaml — this file is their only home.

### Norwegian Singles (Running)

A threshold-focused training approach popularized by Norwegian endurance athletes,
adapted for single-sport-day amateurs (the "singles" variant, as opposed to the elite
"double threshold" model).

**Core principles:**
- 2 threshold sessions per week, separated by at least one easy day
- Threshold intervals are **controlled** — at or just below lactate threshold,
  never all-out. Athlete should finish feeling they could do one more rep.
- Short recoveries between intervals (typically 60 seconds)
- Easy days are **truly easy** — conversational pace, no grey zone

**Threshold format library** (pick format based on athlete's fitness, fatigue, and preference):

| Format | Total Work | Character | Best when... |
|---|---|---|---|
| 5×6 min | 30 min | Short, snappy. Less mental grind per rep. Good for maintaining form at pace. | Athlete wants variety from longer intervals; fresher feel |
| 4×8 min | 32 min | Balanced. More reps than 3×10, slightly more total work. | Smooth progression from 3×10 |
| 3×10 min | 30 min | Classic Norwegian format. Proven balance of stimulus and sustainability. | Default starting point; well-tested |
| 3×12 min | 36 min | Longer blocks, volume bump. Builds endurance at threshold. | Athlete ready for volume increase from 3×10 |
| 2×15 min | 30 min | Long sustained blocks. Tests concentration and pacing discipline. | Athlete wants fewer, longer intervals |
| 6×5 min | 30 min | Very short reps, high density. Sharpens form at target pace. | Peaking or when freshness is high |

**Progressive overload path:** 3×6 min → 5×6 min → 3×8 min → 4×8 min → 3×10 min → 4×10 min → 3×12 min
Start conservatively and extend only when the athlete consistently finishes sessions
feeling they had one more rep left.

**⚠️ Never skip progression steps.** Each step increases one variable at a time (total work, rep length, or rep count). Jumping from 3×6 directly to 3×8 skips 5×6 and increases both rep length (+33%) and total work (+20%) simultaneously — the athlete may be forced to pause mid-interval as HR drifts above threshold. When an athlete tolerates their current level, the temptation is to jump ahead — resist it. Move one step at a time. If an athlete fails a step (pauses, HR drifts above zone, RPE exceeds target), drop back to the previous step and rebuild.

**Pace source priority:**
1. **Lactate testing data first** — if the athlete has lactrace or lab lactate test results
   with actual mmol/L paces, those are authoritative. Ask before giving generic estimates.
2. intervals.icu running FTP from `get_sport_settings(sport="Run")`
3. Recent threshold session data from `get_recent_activities(sport="Run")`

**Pace zones** (derived from threshold pace, ~60-min race pace):

| Zone | Offset from threshold | Use |
|---|---|---|
| Easy/Recovery | +60–90 sec/km | Most days. Conversational. |
| Moderate | +30–45 sec/km | Optional bridge, use sparingly |
| Threshold | ±0 | Quality sessions (3-5×6-10 min, 60s rest) |
| 10K pace | −15–20 sec/km | Rare progression test |

**Weekly template (with strength):**
```
Mon: Easy run 35-40 min + 💪 Styrka A (ben) 25 min     → ~60 min total
Tue: Threshold session #1 (e.g. 4×8 min)                → ~60 min
Wed: Easy run 35-40 min                                  → ~40 min
Thu: 🛌 Rest / optional easy run 0-25 min
Fri: 💪 Styrka B (överkropp+bål+spänst) 25 min          → ~25 min
Sat: Threshold session #2 (e.g. 5×6 min)                → ~60 min
Sun: Long run 60-90 min progressive                      → 60-90 min
```

**Strength variety rules:**
- Styrka A = lower body focus (split squats, deadlifts, hip thrusts, lunges — rotate exercises weekly)
- Styrka B = upper body + core + plyometrics (rows, presses, anti-rotation, box jumps — rotate weekly)
- No single weekday session exceeds 60 min total
- Rest day (Thursday) is explicitly labeled in the calendar, never left as an empty slot

**Template without strength** (athlete prefers 0-1 strength sessions):
```
Mon: Easy run 35-45 min
Tue: Threshold session #1
Wed: Easy run 40 min or rest
Thu: Rest or easy run 30-40 min
Fri: Easy run 35-45 min
Sat: Threshold session #2
Sun: Long run 60-90 min progressive
```

**Common mistake:** Running easy days too fast, turning them into "grey zone" junk mileage
that adds fatigue without stimulus. Easy days must stay easy.

See `references/norwegian-singles-paces.md` for pace calculation methodology.
