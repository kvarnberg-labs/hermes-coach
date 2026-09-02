# Cross-Training (HIIT Cycling) as a Weekly Complement for Runners

Guidance for integrating high-intensity cross-training — typically Les Mills Sprint,
Zwift racing, or studio cycling classes — into a runner's weekly plan without
compromising run-specific adaptations.

## When It's Appropriate

| Scenario | Verdict |
|---|---|
| One-time substitution (life-driven schedule change) | ✅ Always fine — don't overthink it |
| Weekly complement replacing an *easy* run day | ✅ Good — preserves run volume via the remaining sessions |
| Weekly complement *added on top* of existing plan (extra quality day) | ⚠️ Risk — creates 3 quality days/week, likely too much for sub-35 CTL runners |
| During injury recovery or extreme leg fatigue | ✅ Excellent — maintains cardiovascular fitness without impact |
| Final 6–8 weeks before goal race | ❌ No — running must dominate entirely |

## Benefits

1. **VO2max stimulus without impact load** — HIIT cycling pushes HR toward
   threshold/VO2max zones without the tendon/joint/periosteal stress of running.
   Valuable for athletes already running 3–4×/week.

2. **Active recovery for running legs** — cycling uses musculature differently
   (more quadriceps, less eccentric loading on calves/hamstrings). Light cycling
   the day after a hard run can promote blood flow and speed recovery.

3. **Mental variety** — prevents training monotony in a 5–6 day/week program.
   Sustainable training requires psychological engagement, not just physiological
   stimulus.

4. **Body composition support** — high calorie burn in short time, supports
   athletes who want to stay lean while preserving running volume.

## Constraints

- **Does NOT replace run-specific training.** Cycling improves general
  cardiovascular fitness but transfer to running pace is partial (~50–70%).
  Running economy, stride mechanics, and run-specific endurance require
  actual running. As race approaches, running must dominate.

- **HIIT = high recovery cost.** A 30-min Sprint class at IF ~0.77, RPE 7,
  load ~29 is not a huge load, but the *intensity* competes with recovery
  for the next threshold session. Two threshold sessions (Norwegian Singles)
  + one HIIT cycling session = three quality days/week — the maximum for
  most sub-35 CTL athletes.

- **Time budget is finite.** Weekday sessions are capped at ~60 min. If a
  cross-training session fills that slot, something else must move. Never
  silently displace a strength session — identify the conflict and present
  the trade-off explicitly.

- **Back-to-back hard days.** Friday HIIT + Saturday threshold is within
  the 2-consecutive-hard-day limit, but the athlete should be warned to
  report fatigue. If Sprint leaves legs heavy, Saturday threshold should
  be adjusted (reduce volume, e.g. 3×6 instead of 4×8) or the Sprint
  replaced with easy cycling.

## Schedule Integration Patterns

### Pattern 1: Strength + HIIT on the same day (preferred for 60-min budget)

```
Fri: 💪 Styrka B (25 min) + 🚴 Les Mills Sprint (30 min) = 55 min
```

- Strength first (upper body/core/plyo — no leg conflict), HIIT second.
- Preserves the separate strength session without exceeding time budget.
- The non-leg strength won't compromise the cycling effort.

### Pattern 2: Jog before HIIT (preserves run volume)

```
Fri: 🏃 Easy jog 30 min (Z1) + 🚴 Les Mills Sprint 30 min = 60 min
```

- Maintains run frequency/volume but loses the strength session.
- Only viable if strength can move to another day without exceeding 60 min.

### Pattern 3: HIIT replaces an easy run (simplest)

```
Fri: 🚴 Les Mills Sprint 30 min (replaces easy run)
```

- Clean swap, no time conflict. Reduces weekly run volume by one session.
- Best when the athlete has enough run volume from other days.

## Analyzing a Cross-Training Session (VirtualRide) for a Runner

When a runner completes a cycling HIIT session and asks for analysis:

### Data to pull

1. `get_recent_activities(days=2, sport="Ride")` — find the VirtualRide
2. `get_activity_detail(activity_id)` — HR zones, zone times, IF, load, calories
3. `get_activity_streams(activity_id)` — may only return HR + time (gym bikes
   often lack power data). Don't expect power zones or NP.

### Key analysis points

- **Cycling HR vs running HR:** Cycling HR runs ~5–10 bpm lower than running
  HR at the same relative intensity. A max HR of 186 on the bike may
  correspond to ~191–196 while running. Account for this when classifying
  intensity — "reached 186 bpm" on a bike is approximately threshold, not
  VO2max, for an athlete with LTHR 191 running.

- **HR zone distribution:** Use the athlete's *cycling* HR zones if available
  (from `get_sport_settings(sport="Ride")`). If only running zones exist,
  note the HR offset and interpret cautiously. A session with 12% time in
  Z4 (cycling) is a controlled HIIT session — not an all-out effort.

- **No power data is common:** Gym bikes (Les Mills, Echelon, spinning
  studios) typically don't record power. IF and load are HR-based and less
  precise. State this limitation explicitly rather than presenting HR-derived
  IF as equivalent to power-derived IF.

- **Load comparison:** Compare the actual load to what the displaced running
  session would have produced. A Sprint session at load 29 replacing a 60-min
  easy run at load 40 is less total stress but higher intensity — different
  stimulus, not directly comparable.

- **Recovery check:** Post-session HR recovery (last 2 min of stream data)
  indicates cardiovascular recovery. A drop from 186 → 149 bpm in the
  cooldown suggests good recovery capacity.

### What to tell the athlete

1. HR zone distribution table (zones, times, percentages)
2. Intensity characterization (controlled HIIT vs all-out)
3. Load and comparison to the displaced session
4. Whether the session counts as a "quality day" for recovery purposes
5. Next-session guidance — especially if tomorrow is another quality session

## Pitfalls

- **Don't present HIIT cycling as equivalent to threshold running.** The
  physiological stimulus overlaps but is not identical. Running threshold
  works running-specific motor units, running economy, and lactate clearance
  at running cadence. Cycling HIIT builds general VO2max and lactate
  tolerance. Both are valuable; they are not interchangeable.

- **Don't let HIIT become a third weekly quality session without checking
  total load.** Norwegian Singles already has 2 threshold sessions. Adding
  HIIT cycling on top means 3 hard days — monitor RPE, HRV, and TSB closely.
  If the athlete shows fatigue signs, reduce HIIT frequency or replace with
  easy cycling.

- **Don't forget the strength session.** When HIIT cycling takes a weekday
  slot, the strength session that was there must go somewhere. The athlete
  values strength for both performance and body composition. Present the
  displacement explicitly and let the athlete choose the arrangement.

- **Cycling HR zones ≠ running HR zones.** If the athlete's intervals.icu
  cycling HR zones are unset or default, HR zone distribution from a
  VirtualRide may be misleading. Always check `get_sport_settings(sport="Ride")`
  for cycling-specific zones. If unavailable, note the limitation.
