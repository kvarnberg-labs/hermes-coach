---
name: strength-coaching
description: Evidence-based strength training coaching — assessments, exercise guidance, workout generation, and program design.
version: 1.0.0
author: kvarnberg-labs
metadata:
  hermes:
    tags:
      - training
      - coaching
      - strength
      - resistance-training
    category: training
---

# Strength Coaching Skill

Provides structured, evidence-based strength training guidance. Uses coach-brain
YAML knowledge files and dedicated strength coaching tools. No intervals.icu
dependency — works for any athlete, endurance or not.

For **endurance coaching** (cycling, running, triathlon), use the sibling skill
`coaching` — it provides intervals.icu integration, workout analysis, and
sport-specific training guidance. When an athlete trains both endurance and
strength, load both skills. (Where strength sessions sit inside a runner's
week is the `coaching` skill's `strength-for-runners` reference; what goes in
the session is this skill.)

**Assess first.** If you do not know this athlete's strength level, goal and
equipment, call `assess_strength_level` before any advice or workout — also for
experienced endurance athletes. An advanced programme given to a novice is
dangerous. Before lower-body work, ask about current pain, swelling, injury
return or post-illness symptoms (`coach-brain/coaching-safety.yaml →
strength_boundary`); red flags mean referral, not a workout.

## When to Use

- Athlete asks about strength training for the first time (assessment needed)
- Athlete wants a workout for today's gym session
- Athlete asks for a multi-week training program or plan
- Athlete asks about exercise form, technique, or alternatives
- Athlete asks about strength standards or benchmarks
- **Athlete asks specifically about endurance/cycling/running → load `coaching` skill instead** (this skill covers strength only)

## Available Tools

| Tool | When | Returns |
|------|------|---------|
| `assess_strength_level` | First contact — new athlete, no training profile known | Assessment questions + classification benchmarks |
| `exercise_lookup` | Athlete asks about an exercise, or you're prescribing a new movement | Form cues, common errors, progressions, regressions, muscle targets |
| `generate_strength_workout` | Athlete asks "what should I do today" | Single session: exercise selection, set/rep/intensity, warm-up |
| `design_strength_program` | Athlete asks for a multi-week plan | Structured program: phases, split, progression, deloads |

## Procedure

### Step 1: Assess

`assess_strength_level` returns:

- **Interview questions** — ask these CONVERSATIONALLY, not as a dump:
  1. Training history (how long, what type)
  2. Comfort with main lifts (squat, deadlift, press)
  3. Strength self-assessment (bodyweight ratios)
  4. Training goal (strength, hypertrophy, health, power, fat loss, endurance)
  5. Equipment access (full gym, basic gym, dumbbells, bodyweight)
  6. Available frequency and session duration
  7. Injury history (ask last)
- **Classification levels** — use the benchmarks to classify the athlete as
  untrained, novice, early_intermediate, intermediate, or advanced
- **Usage guide** — follow the recommended question order in the guide

### Step 2: Prescribe

Based on the assessment classification:

**Single workout** → `generate_strength_workout(goal, level, equipment, days, session_duration_min, focus)`
- Returns full session with exercise selections, parameters, warm-up, and notes
- Omitting `focus` always gives a **full-body** session. For a split, pass
  `focus` explicitly: `upper`, `lower`, `push`, `pull` or `legs`.

**Multi-week program** → `design_strength_program(goal, level, equipment, weeks, days_per_week)`
- Returns phased program with split templates, progression methods, and deload schedule

### Step 3: Track prescribed vs completed

At the next contact, compare what was prescribed (sets × reps × load) with what
the athlete completed. Progress only when all reps were clean; three sessions
in a row of missed reps at the same load → follow `stall_protocol`
(`get_coaching_knowledge("strength programming")` → `linear_progression.stall_protocol`:
deload 10–15 % and rebuild).

### Step 4: Explain

For any new exercise prescribed, call `exercise_lookup(name)` to get:
- Setup and execution cues
- Breathing pattern
- Common errors to avoid
- Progressions (harder) and regressions (easier)
- Muscle targets

## Knowledge Retrieval

Prefer the four tools — they already read the YAML. `get_coaching_knowledge`
matches top-level section names and returns up to ~15 KB, so ask for one
section by name and only when the tools do not answer the question:

| Need | Call |
|---|---|
| Principles (overload, specificity, recovery, deloads) | `get_coaching_knowledge("strength principles")` |
| Programming methods, progression, stall protocol | `get_coaching_knowledge("strength programming")` |
| Classification benchmarks | `assess_strength_level` (or `get_coaching_knowledge("strength standards")`) |
| One exercise | `exercise_lookup(name)` — never the whole exercise database |
| Endurance-athlete and masters specifics | `get_coaching_knowledge("strength training")` |

## Key Principles

1. **Form over load.** When prescribing a new exercise, ALWAYS call `exercise_lookup`
   to provide proper form instructions. Mention at least the top 2 common errors.

2. **Progressive overload is the foundation.** Every program must specify how the
   athlete progresses — session-to-session for novices, weekly for intermediates,
   mesocycle-based for advanced.

3. **Concurrent training rules.** For endurance athletes who strength train:
   - ≥6 hours separation between hard bike/run sessions and heavy leg days
   - Avoid heavy lower-body work the day before threshold/VO2max sessions
   - In-season: 1–2×/week maintenance, off-season: 2–3×/week building

4. **Recovery and deload.** Every program beyond 4 weeks includes planned
   deloads (`strength-general.yaml → deload_guidelines`): novice every 8–12
   weeks, intermediate every 4–6, advanced every 3–5; deload by cutting sets
   40–50 % (keep intensity) or load to 60–70 % (keep volume).
   `design_strength_program` returns the cadence for the athlete's level.

## Pitfalls

- **Don't prescribe Olympic lifts without coaching.** The exercise database covers
  squats, deadlifts, presses, rows, and accessories — not snatch/clean & jerk.
  Refer to a qualified coach for technical lifts.
- **Don't prescribe 1RM testing for novices.** Use the benchmarks in
  `assess_strength_level` for classification, not max-effort testing.
- **Equipment matters.** A program designed for full_gym won't work with
  dumbbell_only. Always confirm equipment before prescribing.
- **Masters athletes (50+)** (`strength-training.yaml → masters_athletes_50_plus`):
  2×/week year-round (never below 1), 8–12 reps at moderate load, avoid ≥ 90 %
  1RM, move submaximal loads fast, longer warm-ups.

## Quick Reference

| Athlete says | Do this |
|-------------|---------|
| "I want to start strength training" | `assess_strength_level` → classify → prescribe |
| "What should I do in the gym today?" | `generate_strength_workout` (assess first if unknown) |
| "Give me a 12-week program" | `design_strength_program` |
| "How do I squat properly?" | `exercise_lookup("barbell back squat")` |
| "Is my deadlift good for my weight?" | `assess_strength_level` → check benchmarks |
| "I'm a cyclist, should I lift?" | Load both `coaching` + `strength-coaching`, follow concurrent training rules |
