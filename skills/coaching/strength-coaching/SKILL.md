---
name: strength-coaching
description: Evidence-based strength training coaching — assessments, exercise guidance, workout generation, and program design. No intervals.icu dependency.
version: 1.0.0
author: kvarnberg-labs
metadata:
  hermes:
    tags:
      - strength
      - coaching
      - resistance-training
      - hypertrophy
    category: coaching
---

# Strength Coaching Skill

Provides structured, evidence-based coaching for strength training, bodybuilding,
powerlifting, and general resistance training. **No intervals.icu dependency** —
works with any athlete regardless of whether they have endurance training data.

All knowledge is sourced from coach-brain YAML files (`strength-general.yaml`,
`exercise-database.yaml`, `strength-programming.yaml`, `strength-standards.yaml`).

## When to Use

- Athlete asks about strength training, lifting, or getting stronger
- Athlete wants a workout program or training plan
- Athlete asks how to perform a specific exercise
- Athlete wants to build muscle (hypertrophy)
- Athlete wants to combine strength and endurance training
- Athlete has no intervals.icu data and wants coaching (strength is the entry point)

## Tools

| Tool | Purpose |
|------|---------|
| `assess_strength_level` | Returns structured assessment questionnaire + benchmarks |
| `exercise_lookup(name)` | Detailed exercise info: form cues, muscles, progressions, errors |
| `generate_strength_workout(goal, level, equipment, ...)` | Single workout session |
| `design_strength_program(goal, level, equipment, weeks, ...)` | Multi-week program |
| `get_coaching_knowledge(topic)` | Pulls strength-general, exercise-database, or strength-programming sections |

## Workflow

### 1. New Athlete (No Assessment)

When an athlete asks about strength training for the first time:

1. Call `assess_strength_level` to get the questionnaire and benchmarks.
2. **Do NOT dump the full questionnaire at once.** Ask conversationally:
   - **First:** "How long have you been strength training consistently?" (training history)
   - **Then:** "What's your main goal — get stronger, build muscle, general health, or fat loss?"
   - **Then:** "What equipment do you have access to?"
   - **Then:** "How many days per week and how long per session?"
   - **Finally (only if relevant):** "Any injuries or movement limitations?"
3. Classify the athlete using the `classification_levels` and `strength_benchmarks`.
4. Verify: "So you'd say you're at a [novice/intermediate/advanced] level — does that sound right?"

### 2. Athlete Wants a Workout

1. Confirm goal, level, equipment, and time from assessment (or ask if unknown).
2. Call `generate_strength_workout(goal, level, equipment, days, session_duration_min, focus)`.
3. For each exercise in the output, call `exercise_lookup(name)` for form cues.
4. Present the workout with exercise names, set×rep schemes, and brief form notes.
5. Add warm-up instructions and progression guidance.

### 3. Athlete Asks About an Exercise

1. Call `exercise_lookup(name)`.
2. If `matched: false` with matches listed, ask the athlete to clarify which variant.
3. Present: name, primary muscles, setup cues, execution cues, common errors, progressions.

### 4. Athlete Wants a Program

1. Confirm goal, level, equipment, weeks, and days/week.
2. Call `design_strength_program(goal, level, equipment, weeks, days_per_week)`.
3. Present the program structure: split name, phase breakdown, progression method, deload schedule.
4. **Present the plan for approval before elaborating on every detail.** Let the athlete confirm the split and structure.
5. After approval, present the day-by-day template with exercise selections.

### 5. Athlete Asks a General Question

1. Call `get_coaching_knowledge(topic)` with relevant keywords.
   - "progressive overload" → strength_principles
   - "how often should I train" → training_frequency
   - "deload" → deload_guidelines
   - "nutrition for muscle" → nutrition_for_strength
   - "soreness after lifting" → recovery_and_adaptation
   - "warm up before lifting" → warm_up_protocol
   - "program for older adult" → special_populations
2. Synthesize from the returned knowledge. Always cite the principles, not generic model knowledge.

## Combining Strength + Endurance

For athletes who do both:

1. **Assess each sport independently.** Don't blend strength and endurance into one analysis.
2. For endurance data, follow the `coaching` skill workflow (verify identity, pull intervals.icu data).
3. For strength, follow this skill's workflow.
4. When programming both concurrently, reference `get_coaching_knowledge("concurrent training")` from the existing `strength-training.yaml` (cycling-specific) and `get_coaching_knowledge("recovery")` for managing total training stress.
5. Strength sessions should be scheduled away from hard endurance sessions (separate by ≥6 hours or on different days).

## Evidence Base

All guidance is drawn from:
- **ACSM Position Stand** on Resistance Training (2009, 2011)
- **NSCA Essentials of Strength Training and Conditioning** (4th ed.)
- **Schoenfeld et al.** (2016–2021) — hypertrophy, frequency, volume
- **Helms et al.** Muscle & Strength Pyramids — RPE, nutrition, programming
- **Nuckols, G.** The Art and Science of Lifting — programming models
- **Rippetoe, M.** Starting Strength — barbell technique
- **Prilepin's Chart** — set/rep/load optimization
- **Israetel, M. / Renaissance Periodization** — volume landmarks, MRV

## Pitfalls

- **Do NOT prescribe near-maximal loads (≥90% 1RM) to untrained or novice athletes.** They need movement quality first. Max testing is for intermediates+.
- **Do NOT prescribe exercises that load an injured area** without medical clearance. If the athlete mentions pain, ask for specifics and work around it.
- **"No pain, no gain" is wrong.** Joint pain is a stop signal. Muscle soreness (DOMS) is normal for the first 1–2 weeks of a new program.
- **Progressive overload must be tracked.** Tell the athlete to log every set — weight × reps. Without tracking, there is no progression.
- **Rest is training.** The adaptation happens during recovery. If the athlete reports poor sleep, high stress, or persistent fatigue, recommend a deload.
- **More is not better.** A novice doing 3 quality full-body sessions per week will progress faster than one doing 6 sloppy sessions. Quality and consistency beat volume.
- **Form over weight.** When an athlete asks "how much should I lift," the answer is "the weight you can move with perfect form for the prescribed reps." Starting too heavy is the #1 beginner mistake.
- **Don't assume bodyweight exercises are easy.** A proper set of push-ups or inverted rows to near-failure is effective for hypertrophy and strength in novices. Progress by changing leverage, not just adding external load.
- **Women are not "small men" for programming.** The relative strength standards differ (~65–75% of male benchmarks). Menstrual cycle phase can affect performance and recovery. Programming advice should be the same (same principles apply), but benchmark expectations differ.
- **Older adults (55+) need different programming.** Higher reps (8–15), lower absolute intensity, power training emphasis, longer warm-ups. See `get_coaching_knowledge("older adults")` or `get_coaching_knowledge("special populations")`.
- **Don't create a program without knowing equipment.** A program with barbell squats and cable crossovers is useless to someone with only dumbbells. Always confirm equipment first.

## Verification

After giving strength coaching advice, verify:
1. The athlete's level, goal, and equipment were confirmed (not assumed).
2. Exercise prescriptions include form cues (not just "do 3×5 squats").
3. Progression method is appropriate for their level (linear for novices, weekly for intermediates).
4. Warm-up and safety guidance is included.
5. The program is realistic for their time constraints.
