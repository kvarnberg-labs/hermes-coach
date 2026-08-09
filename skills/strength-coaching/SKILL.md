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
strength, load both skills.

## When to Use

- Athlete asks about strength training for the first time (assessment needed)
- Athlete wants a workout for today's gym session
- Athlete asks for a multi-week training program or plan
- Athlete asks about exercise form, technique, or alternatives
- Athlete asks about strength standards or benchmarks
- **Athlete asks specifically about endurance/cycling/running → load `coaching` skill instead** (this skill covers strength only)

## Prerequisites

- `coach-brain/` directory populated with strength YAML knowledge files:
  `exercise-database.yaml`, `strength-general.yaml`, `strength-programming.yaml`,
  `strength-standards.yaml`, `strength-training.yaml`
- Tools registered via `strength_coach.py`:
  `assess_strength_level`, `exercise_lookup`, `generate_strength_workout`,
  `design_strength_program`

## Available Tools

| Tool | When | Returns |
|------|------|---------|
| `assess_strength_level` | First contact — new athlete, no training profile known | Assessment questions + classification benchmarks |
| `exercise_lookup` | Athlete asks about an exercise, or you're prescribing a new movement | Form cues, common errors, progressions, regressions, muscle targets |
| `generate_strength_workout` | Athlete asks "what should I do today" | Single session: exercise selection, set/rep/intensity, warm-up |
| `design_strength_program` | Athlete asks for a multi-week plan | Structured program: phases, split, progression, deloads |

## Procedure

### Step 1: Assess (always first)

If you don't know the athlete's strength training background, call
`assess_strength_level` before giving ANY advice. This returns:

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
- The `focus` parameter auto-selects upper/lower/full_body based on days/week

**Multi-week program** → `design_strength_program(goal, level, equipment, weeks, days_per_week)`
- Returns phased program with split templates, progression methods, and deload schedule

### Step 3: Explain

For any new exercise prescribed, call `exercise_lookup(name)` to get:
- Setup and execution cues
- Breathing pattern
- Common errors to avoid
- Progressions (harder) and regressions (easier)
- Muscle targets

## Knowledge Retrieval

All strength knowledge lives in coach-brain YAML files. Use `get_coaching_knowledge`
for deeper dives:

| Topic | Tool Call | Content |
|-------|-----------|---------|
| Strength principles | `get_coaching_knowledge("strength principles")` | Progressive overload, specificity, recovery, periodization |
| Exercise database | `get_coaching_knowledge("exercise database")` or use `exercise_lookup` | Complete exercise library |
| Programming methods | `get_coaching_knowledge("strength programming")` | Goal parameters, periodization models, progression methods |
| Strength standards | `get_coaching_knowledge("strength standards")` | Classification benchmarks, assessment questions |

## Key Principles

1. **Assess before prescribing.** Never give a workout without knowing the athlete's
   level, goal, and equipment. An advanced powerlifting program given to a novice
   is dangerous.

2. **Form over load.** When prescribing a new exercise, ALWAYS call `exercise_lookup`
   to provide proper form instructions. Mention at least the top 2 common errors.

3. **Progressive overload is the foundation.** Every program must specify how the
   athlete progresses — session-to-session for novices, weekly for intermediates,
   mesocycle-based for advanced.

4. **Concurrent training rules.** For endurance athletes who strength train:
   - ≥6 hours separation between hard bike/run sessions and heavy leg days
   - Avoid heavy lower-body work the day before threshold/VO2max sessions
   - In-season: 1–2×/week maintenance, off-season: 2–3×/week building

5. **Recovery and deload.** Every program beyond 4 weeks must include deload weeks
   (every 4th week for intermediates, every 4–8 weeks for advanced).

## Pitfalls

- **Don't skip the assessment for returning athletes.** If you haven't classified
  this athlete's strength level, call `assess_strength_level` first — even if
  they're an experienced endurance athlete.
- **Don't prescribe Olympic lifts without coaching.** The exercise database covers
  squats, deadlifts, presses, rows, and accessories — not snatch/clean & jerk.
  Refer to a qualified coach for technical lifts.
- **Don't prescribe 1RM testing for novices.** Use the benchmarks in
  `assess_strength_level` for classification, not max-effort testing.
- **Equipment matters.** A program designed for full_gym won't work with
  dumbbell_only. Always confirm equipment before prescribing.
- **Masters athletes (50+) need modifications:** lower volume, longer warm-ups,
  emphasis on power (RPE 6–8) over maximal strength, 2×/week frequency preferred.

## Quick Reference

| Athlete says | Do this |
|-------------|---------|
| "I want to start strength training" | `assess_strength_level` → classify → prescribe |
| "What should I do in the gym today?" | `generate_strength_workout` (assess first if unknown) |
| "Give me a 12-week program" | `design_strength_program` |
| "How do I squat properly?" | `exercise_lookup("barbell back squat")` |
| "Is my deadlift good for my weight?" | `assess_strength_level` → check benchmarks |
| "I'm a cyclist, should I lift?" | Load both `coaching` + `strength-coaching`, follow concurrent training rules |
