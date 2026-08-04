"""Strength Coach — strength training tools for Hermes Coach.

Provides tools for strength training assessment, exercise lookup,
workout generation, and program design.  All knowledge is sourced
from coach-brain YAML files — no external API dependency.

Tools registered:
  - assess_strength_level     → returns structured assessment questionnaire
  - exercise_lookup           → detailed exercise info, form cues, progressions
  - generate_strength_workout → generates a single workout session
  - design_strength_program   → generates a multi-week training program
"""

from __future__ import annotations

import json
import logging
from typing import Any

from ._brain import _load_all

logger = logging.getLogger(__name__)


# ── Tool: assess_strength_level ────────────────────────────────────────────

def assess_strength_level(**_: Any) -> str:
    """Return the structured strength assessment questionnaire.

    No user data required — returns the questions and benchmarks the agent
    should use to classify the athlete's training level, goals, equipment,
    and injury history.
    """
    brain = _load_all()
    standards = brain.get("strength_standards", {})
    assessment = standards.get("assessment_questions", {})
    levels = standards.get("classification_levels", {})
    benchmarks = {
        "bench_by_level": standards.get("bench_by_level", {}),
        "squat_by_level": standards.get("squat_by_level", {}),
        "deadlift_by_level": standards.get("deadlift_by_level", {}),
        "ohp_by_level": standards.get("ohp_by_level", {}),
        "pullup_by_level": standards.get("pullup_by_level", {}),
    }

    classification = {}
    for key, val in levels.items():
        classification[key] = val

    return json.dumps({
        "tool": "assess_strength_level",
        "description": (
            "Use these questions to classify the athlete's strength training level. "
            "Ask questions conversationally — don't dump the entire questionnaire. "
            "Start with training history, then goals, then equipment/time constraints. "
            "Only ask injury questions last."
        ),
        "questions": assessment,
        "classification_levels": classification,
        "strength_benchmarks": benchmarks,
        "usage_guide": {
            "step_1": (
                "Ask Q1 (training duration) and Q2 (comfort with main lifts). "
                "These establish the baseline training level."
            ),
            "step_2": (
                "Ask Q5 (goal) — this determines program type "
                "(strength vs hypertrophy vs health)."
            ),
            "step_3": (
                "Ask Q6-Q8 (equipment, frequency, session duration) — "
                "these determine the split and exercise selection."
            ),
            "step_4": (
                "Ask Q4 (strength self-report) to calibrate the level assessment. "
                "Ask Q9 (injuries) only if relevant to program design."
            ),
        },
    })


# ── Tool: exercise_lookup ──────────────────────────────────────────────────

def exercise_lookup(name: str, **_: Any) -> str:
    """Look up detailed information about a strength exercise.

    Returns form cues, common errors, progressions, regressions, muscle targets,
    and set/rep guidelines.  Searches the exercise-database in coach-brain.

    Args:
        name: Exercise name, e.g. 'barbell back squat', 'deadlift', 'pull up',
              'overhead press', 'bulgarian split squat'.
    """
    brain = _load_all()
    exercises = brain.get("exercise_database", {})

    name_lower = name.lower().strip().replace("-", " ")

    # Direct key match first
    for key, ex in exercises.items():
        key_lower = key.replace("_", " ")
        if name_lower == key_lower:
            return json.dumps({"matched": True, "exercise": ex})

    # Fuzzy: check if name appears in the exercise name field
    matches = []
    for key, ex in exercises.items():
        ex_name = ex.get("name", "").lower()
        if name_lower in ex_name or name_lower in key.replace("_", " "):
            matches.append({"key": key, "name": ex.get("name", key)})

    if len(matches) == 1:
        ex = exercises[matches[0]["key"]]
        return json.dumps({"matched": True, "exercise": ex})
    elif len(matches) > 1:
        return json.dumps({
            "matched": False,
            "reason": "Multiple matches found — please be more specific",
            "matches": matches,
            "hint": (
                "Pick the exact exercise name from the matches list above. "
                "For example: 'conventional deadlift' or 'romanian deadlift' "
                "instead of just 'deadlift'."
            ),
        })

    # No match — list available exercises
    available = [
        {"key": k, "name": v.get("name", k)}
        for k, v in sorted(exercises.items())
    ]
    return json.dumps({
        "matched": False,
        "reason": f"No exercise matching '{name}' found",
        "available_exercises": available,
    })


# ── Tool: generate_strength_workout ────────────────────────────────────────

def generate_strength_workout(
    goal: str = "general_strength",
    level: str = "novice",
    equipment: str = "full_gym",
    days: int = 3,
    session_duration_min: int = 60,
    focus: Optional[str] = None,
    **_: Any,
) -> str:
    """Generate a single strength training session.

    Pulls from coach-brain programming templates and adapts based on goal,
    level, equipment availability, and time constraints.

    Args:
        goal: 'general_strength', 'hypertrophy', 'power', 'endurance', 'health',
              or 'fat_loss'
        level: 'untrained', 'novice', 'early_intermediate', 'intermediate',
               'advanced'
        equipment: 'full_gym', 'basic_gym', 'dumbbell_only', 'bodyweight_only'
        days: Training days per week (2–6), used to determine session density
        session_duration_min: How long the athlete has per session
        focus: Optional specific focus like 'upper', 'lower', 'full_body', 'push',
               'pull', or 'legs' (used for split programs)
    """
    brain = _load_all()
    exercises_db = brain.get("exercise_database", {})
    programming = brain.get("strength_programming", {})
    # Map tool goal names to YAML keys
    goal_key_map = {
        "health": "health_longevity",
        "fat_loss": "fat_loss_preserve_muscle",
    }
    yaml_goal = goal_key_map.get(goal, goal)
    goal_params = programming.get("goal_parameters", {}).get(yaml_goal, {})

    if not goal_params:
        return json.dumps({
            "error": f"Unknown goal '{goal}'. Choose from: general_strength, "
                     f"hypertrophy, power, endurance, health, fat_loss",
        })

    # Determine volume parameters
    rep_range = goal_params.get("rep_range", "6–12")
    intensity = goal_params.get("intensity_range", "65–80% 1RM")
    sets = goal_params.get("sets_per_exercise", "3–4")

    # Build session based on focus and equipment
    if focus == "full_body" or (not focus and days <= 3):
        session_type = "full_body"
    elif focus in ("upper", "lower", "push", "pull", "legs"):
        session_type = focus
    else:
        session_type = "full_body"

    # Generate exercise selections based on equipment and session type
    exercises = _select_exercises_for_session(
        exercises_db, session_type, equipment, session_duration_min
    )

    result = {
        "workout_type": session_type,
        "goal": goal,
        "level": level,
        "equipment": equipment,
        "estimated_duration_min": session_duration_min,
        "parameters": {
            "rep_range": rep_range,
            "intensity": intensity,
            "sets": sets,
            "rpe_target": "7–9 (1–3 RIR)" if goal in ("general_strength", "hypertrophy") else "6–8 (avoid failure)",
            "rest_between_sets": "2–5 min (compounds) / 60–90 sec (isolation)"
            if goal == "general_strength" else "60–90 sec",
        },
        "exercises": exercises,
        "warm_up": {
            "general": "5 min light cardio (bike, row, or jog)",
            "dynamic": "Leg swings, arm circles, hip circles, cat-cow, bodyweight squat ×10, push-up ×5",
            "specific": "2–3 ramp-up sets on the first main lift starting at 50% working weight",
        },
        "notes": [
            "Record all sets, reps, and weight. Progressive overload requires tracking.",
            "If you can't complete all prescribed reps with good form, stay at that weight next session.",
            f"As a {level}, expect to progress {'session to session' if level in ('untrained', 'novice') else 'weekly' if level == 'early_intermediate' else 'every 2–4 weeks'}.",
        ],
    }

    return json.dumps(result)


def _select_exercises_for_session(
    exercises_db: dict,
    session_type: str,
    equipment: str,
    duration_min: int,
) -> list[dict]:
    """Select appropriate exercises for a session based on type and equipment."""
    # Map session types to movement patterns needed
    patterns = {
        "full_body": ["squat", "hinge", "horizontal_push", "horizontal_pull", "core"],
        "upper": ["horizontal_push", "horizontal_pull", "vertical_push", "vertical_pull", "accessory"],
        "lower": ["squat", "hinge", "unilateral_lower", "core"],
        "push": ["horizontal_push", "vertical_push", "accessory"],
        "pull": ["horizontal_pull", "vertical_pull", "hinge"],
        "legs": ["squat", "hinge", "unilateral_lower", "core"],
    }

    # Equipment-specific available equipment (used for substring matching)
    equipment_map = {
        "full_gym": ["barbell", "dumbbell", "cable", "bench", "rack"],
        "basic_gym": ["barbell", "dumbbell", "bench", "rack"],
        "dumbbell_only": ["dumbbell"],
        "bodyweight_only": ["bodyweight"],
    }

    needed_patterns = patterns.get(session_type, patterns["full_body"])
    allowed_eq = equipment_map.get(equipment, equipment_map["full_gym"])

    def _equipment_compatible(ex_equipment: list, allowed: list) -> bool:
        """Check if exercise equipment is compatible with available equipment.

        Uses case-insensitive substring matching so 'Dumbbell' matches
        'dumbbell' and 'Dumbbells or Barbell' also matches 'dumbbell'.
        'Bodyweight' exercises are always compatible.
        """
        ex_eq_lower = " ".join(ex_equipment).lower()
        if "bodyweight" in ex_eq_lower:
            return True
        return any(ae in ex_eq_lower for ae in allowed)

    selected = []
    for pattern in needed_patterns:
        for key, ex in exercises_db.items():
            if not isinstance(ex, dict):
                continue
            ex_patterns = ex.get("category", "").lower().replace(" ", "_")
            # Check pattern match
            if pattern == "squat" and "squat" in ex_patterns:
                pass
            elif pattern == "hinge" and ("hinge" in ex_patterns or "deadlift" in key):
                pass
            elif pattern == "horizontal_push" and "horizontal_push" in ex_patterns:
                pass
            elif pattern == "horizontal_pull" and "horizontal_pull" in ex_patterns:
                pass
            elif pattern == "vertical_push" and "vertical_push" in ex_patterns:
                pass
            elif pattern == "vertical_pull" and "vertical_pull" in ex_patterns:
                pass
            elif pattern == "unilateral_lower" and "unilateral" in ex_patterns:
                pass
            elif pattern == "core" and "core" in ex_patterns:
                pass
            elif pattern == "accessory" and "accessory" in ex_patterns:
                pass
            else:
                continue

            # Check equipment compatibility
            ex_equipment = ex.get("equipment", [])
            if _equipment_compatible(ex_equipment, allowed_eq):
                selected.append({
                    "name": ex.get("name", key),
                    "category": ex.get("category", pattern),
                    "primary_muscles": ex.get("primary_muscles", []),
                    "set_rep_guidelines": ex.get("set_rep_guidelines", {}),
                })
                break  # One exercise per pattern

    # Limit based on time: ~5 min per exercise (including rest)
    max_exercises = max(3, duration_min // 8)
    return selected[:max_exercises]


# ── Tool: design_strength_program ──────────────────────────────────────────

def design_strength_program(
    goal: str = "general_strength",
    level: str = "novice",
    equipment: str = "full_gym",
    weeks: int = 12,
    days_per_week: int = 3,
    **_: Any,
) -> str:
    """Design a multi-week strength training program.

    Pulls from coach-brain programming templates and adapts for the athlete's
    goal, level, equipment, and time horizon.

    Args:
        goal: 'general_strength', 'hypertrophy', 'power', 'endurance', 'health',
              or 'fat_loss'
        level: 'untrained', 'novice', 'early_intermediate', 'intermediate',
               'advanced'
        equipment: 'full_gym', 'basic_gym', 'dumbbell_only', 'bodyweight_only'
        weeks: Program duration in weeks (4–16)
        days_per_week: Training days per week (2–6)
    """
    brain = _load_all()
    programming = brain.get("strength_programming", {})
    principles = brain.get("strength_principles", {})
    standards = brain.get("strength_standards", {})

    # Select split
    if days_per_week == 2:
        split_name = "two_day_minimal"
    elif days_per_week == 3:
        split_name = "full_body_3x"
    elif days_per_week == 4:
        split_name = "upper_lower_4x"
        if goal == "hypertrophy":
            split_name = "hypertrophy_focused_4x"
        elif goal == "general_strength":
            split_name = "strength_focused_4x"
    elif days_per_week >= 5:
        split_name = "push_pull_legs_6x"
    else:
        split_name = "full_body_3x"

    # Equipment overrides
    if equipment == "dumbbell_only":
        split_name = "dumbbell_only"
    elif equipment == "bodyweight_only":
        split_name = "bodyweight_only"

    split_template = programming.get(split_name, programming.get("full_body_3x", {}))
    goal_key_map = {"health": "health_longevity", "fat_loss": "fat_loss_preserve_muscle"}
    yaml_goal = goal_key_map.get(goal, goal)
    goal_params = programming.get("goal_parameters", {}).get(yaml_goal, {})
    deload_templates = programming.get("deload_templates", {})
    progression_methods = {
        "untrained": "linear_progression",
        "novice": "linear_progression",
        "early_intermediate": "double_progression",
        "intermediate": "double_progression",
        "advanced": "rpe_autoregulation",
    }
    prog_method = progression_methods.get(level, "linear_progression")
    prog_detail = programming.get(prog_method, {})

    # Deload cadence
    deload_cadence = {
        "untrained": "Every 8–12 weeks",
        "novice": "Every 8–10 weeks",
        "early_intermediate": "Every 6–8 weeks",
        "intermediate": "Every 4–6 weeks",
        "advanced": "Every 4–5 weeks",
    }

    # Classification detail
    class_detail = standards.get("classification_levels", {}).get(level, {})

    program = {
        "program_name": split_template.get("name", f"{level.title()} {goal.replace('_', ' ').title()} Program"),
        "goal": goal,
        "level": level,
        "level_description": class_detail.get("description", ""),
        "equipment": equipment,
        "duration_weeks": weeks,
        "days_per_week": days_per_week,
        "split": split_name,
        "split_description": split_template.get("description", ""),
        "template": split_template,
        "parameters": {
            "rep_range": goal_params.get("rep_range", "6–12"),
            "intensity_range": goal_params.get("intensity_range", "65–85% 1RM"),
            "sets_per_exercise": goal_params.get("sets_per_exercise", "3–4"),
            "rest": goal_params.get("rest", "2–5 min for compounds, 60–90 sec for isolation"),
            "rpe_target": "8–9 (1–2 RIR)" if goal in ("general_strength", "hypertrophy") else "6–8",
            "progression_method": prog_method,
            "progression_detail": prog_detail.get("description", ""),
        },
        "deload": {
            "cadence": deload_cadence.get(level, "Every 4–6 weeks"),
            "method": "Reduce volume (sets) by 40–50%. Keep intensity at ~85%.",
            "deload_template": deload_templates.get("standard_deload", {}),
        },
        "phase_structure": _build_phase_structure(weeks, level, goal),
        "rules": [
            "Always warm up: 5 min general + 2–3 ramp-up sets on first lift.",
            "Record every set: weight × reps. You cannot progress what you don't track.",
            "If you miss a session, continue with the next scheduled day. Do not try to 'make up' missed sessions.",
            "If joint pain (not muscle soreness) occurs, stop the exercise and substitute.",
            "Sleep and nutrition drive adaptation. Training is the stimulus, not the result.",
        ],
    }

    return json.dumps(program)


def _build_phase_structure(weeks: int, level: str, goal: str) -> list[dict]:
    """Build a phase structure for a program."""
    phases = []

    if weeks <= 4:
        phases.append({
            "phase": "Single Block",
            "weeks": f"1–{weeks}",
            "focus": "Build momentum and establish consistency",
            "progression": "Add weight or reps each session/week",
        })
        return phases

    if level in ("untrained", "novice"):
        # Simple accumulation → intensification
        mid = weeks // 2
        phases.append({
            "phase": 1,
            "name": "Accumulation / Technique",
            "weeks": f"1–{mid}",
            "focus": "Movement quality, building work capacity, establishing baseline loads",
            "progression": "Add 2.5–5 kg to main lifts each session",
            "rpe": "7–8 (leave 2–3 reps in reserve)",
        })
        phases.append({
            "phase": 2,
            "name": "Intensification",
            "weeks": f"{mid + 1}–{weeks}",
            "focus": "Increase load, push toward rep PR territory",
            "progression": "Add 1.25–2.5 kg each session. RPE approaches 8–9.",
            "rpe": "8–9 (leave 1–2 reps in reserve)",
        })
    else:
        # Block periodization for intermediates+
        block_len = max(3, weeks // 3)
        phases.append({
            "phase": 1,
            "name": "Accumulation",
            "weeks": f"1–{block_len}",
            "focus": "Higher volume, moderate intensity. Build work capacity.",
            "rpe": "7–8",
            "progression": "Add reps within the range, then add sets",
        })
        phases.append({
            "phase": 2,
            "name": "Intensification",
            "weeks": f"{block_len + 1}–{min(2 * block_len, weeks)}",
            "focus": "Moderate volume, higher intensity. Convert capacity to strength.",
            "rpe": "8–9",
            "progression": "Add load weekly. Reps stay at the lower end of the range.",
        })
        remaining = weeks - 2 * block_len
        if remaining >= 2:
            phases.append({
                "phase": 3,
                "name": "Realization / Peak",
                "weeks": f"{2 * block_len + 1}–{weeks}",
                "focus": "Low volume, high intensity. Express strength. Test maxes in final week if desired.",
                "rpe": "8–9.5",
                "progression": "Work up to heavy singles or AMRAP sets in the final week.",
            })

    return phases


# ── Plugin registration ────────────────────────────────────────────────────

def register_tools(ctx) -> None:
    ctx.register_tool(
        name="assess_strength_level",
        toolset="training",
        schema={
            "name": "assess_strength_level",
            "description": (
                "Return the structured strength training assessment questionnaire. "
                "Use this when a new athlete asks about strength training — before "
                "giving any advice, use this to determine their training level, goals, "
                "equipment, and constraints. Returns questions the agent should ask "
                "conversationally (don't dump the full questionnaire at once), plus "
                "benchmarks for classifying the athlete's level."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
        handler=lambda args, **kw: assess_strength_level(**kw),
    )

    ctx.register_tool(
        name="exercise_lookup",
        toolset="training",
        schema={
            "name": "exercise_lookup",
            "description": (
                "Look up detailed information about a strength training exercise. "
                "Returns form cues (setup, execution, breathing), common errors, "
                "progressions, regressions, muscle targets, variants, and set/rep "
                "guidelines. Use this when an athlete asks about how to perform an "
                "exercise, or when you're prescribing exercises and need to provide "
                "proper form instructions."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": (
                            "Exercise name, e.g. 'barbell back squat', 'conventional deadlift', "
                            "'pull up', 'overhead press', 'romanian deadlift', 'bulgarian split squat', "
                            "'hip thrust', 'face pull'."
                        ),
                    },
                },
                "required": ["name"],
            },
        },
        handler=lambda args, **kw: exercise_lookup(name=args["name"], **kw),
    )

    ctx.register_tool(
        name="generate_strength_workout",
        toolset="training",
        schema={
            "name": "generate_strength_workout",
            "description": (
                "Generate a single strength training workout session based on the "
                "athlete's goal, training level, available equipment, and time constraints. "
                "Returns exercise selections, set/rep/intensity parameters, warm-up "
                "instructions, and progression notes. Use this when an athlete asks for "
                "'a workout for today' or 'what should I do in the gym today'. Call "
                "assess_strength_level first if you don't know their training profile."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "goal": {
                        "type": "string",
                        "description": (
                            "Training goal: 'general_strength', 'hypertrophy', 'power', "
                            "'endurance', 'health', or 'fat_loss'."
                        ),
                    },
                    "level": {
                        "type": "string",
                        "description": (
                            "Training level from assessment: 'untrained', 'novice', "
                            "'early_intermediate', 'intermediate', or 'advanced'."
                        ),
                    },
                    "equipment": {
                        "type": "string",
                        "description": (
                            "Equipment access: 'full_gym' (barbell, rack, dumbbells, cables, machines), "
                            "'basic_gym' (barbell, rack, dumbbells), 'dumbbell_only', or 'bodyweight_only'."
                        ),
                    },
                    "days": {
                        "type": "integer",
                        "description": "Training days per week (2–6). Default 3.",
                    },
                    "session_duration_min": {
                        "type": "integer",
                        "description": "Available time per session in minutes (default 60).",
                    },
                    "focus": {
                        "type": "string",
                        "description": (
                            "Optional focus: 'full_body', 'upper', 'lower', 'push', 'pull', "
                            "or 'legs'. Omit for auto-selection based on days/week."
                        ),
                    },
                },
                "required": ["goal", "level", "equipment"],
            },
        },
        handler=lambda args, **kw: generate_strength_workout(
            goal=args.get("goal", "general_strength"),
            level=args.get("level", "novice"),
            equipment=args.get("equipment", "full_gym"),
            days=args.get("days", 3),
            session_duration_min=args.get("session_duration_min", 60),
            focus=args.get("focus"),
            **kw,
        ),
    )

    ctx.register_tool(
        name="design_strength_program",
        toolset="training",
        schema={
            "name": "design_strength_program",
            "description": (
                "Design a multi-week strength training program based on the athlete's "
                "goal, training level, equipment, and time horizon. Returns a structured "
                "program with phase breakdown, split template, progression method, deload "
                "schedule, and exercise selections per day. Use this when an athlete asks "
                "for a training plan, program, or 'what should I do for the next N weeks'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "goal": {
                        "type": "string",
                        "description": (
                            "Training goal: 'general_strength', 'hypertrophy', 'power', "
                            "'endurance', 'health', or 'fat_loss'."
                        ),
                    },
                    "level": {
                        "type": "string",
                        "description": (
                            "Training level from assessment: 'untrained', 'novice', "
                            "'early_intermediate', 'intermediate', or 'advanced'."
                        ),
                    },
                    "equipment": {
                        "type": "string",
                        "description": (
                            "Equipment: 'full_gym', 'basic_gym', 'dumbbell_only', or 'bodyweight_only'."
                        ),
                    },
                    "weeks": {
                        "type": "integer",
                        "description": "Program duration in weeks (4–16, default 12).",
                    },
                    "days_per_week": {
                        "type": "integer",
                        "description": "Training days per week (2–6, default 3).",
                    },
                },
                "required": ["goal", "level", "equipment"],
            },
        },
        handler=lambda args, **kw: design_strength_program(
            goal=args.get("goal", "general_strength"),
            level=args.get("level", "novice"),
            equipment=args.get("equipment", "full_gym"),
            weeks=args.get("weeks", 12),
            days_per_week=args.get("days_per_week", 3),
            **kw,
        ),
    )
