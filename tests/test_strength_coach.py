"""Tests for the strength_coach training tools.

Covers the four registered tools (assess_strength_level, exercise_lookup,
generate_strength_workout, design_strength_program) and the two helpers
(_select_exercises_for_session, _build_phase_structure).

Uses a SYNTHETIC coach-brain dir so the tests do not couple to the real YAML
corpus (which the self-improvement loop edits daily). The synthetic data
models the real shape: exercise_database entries have category/equipment/
primary_muscles; strength_programming holds goal_parameters, split templates,
deload_templates and progression methods.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent / "plugins"))

from training import _brain, strength_coach


def _write_brain(d: Path, name: str, data: dict) -> None:
    (d / name).write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


@pytest.fixture
def strength_brain(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Build a minimal but shape-accurate coach-brain dir for the strength tools."""
    d = tmp_path / "coach-brain"
    d.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setattr("training._brain._brain_dir", lambda: d)

    _write_brain(d, "exercise-database.yaml", {"exercise_database": {
        "barbell_back_squat": {"name": "Barbell Back Squat", "category": "Squat",
            "primary_muscles": ["Quadriceps"], "equipment": ["Barbell", "Squat Rack"],
            "set_rep_guidelines": {"strength": "5x5"}},
        "conventional_deadlift": {"name": "Conventional Deadlift", "category": "Hinge",
            "primary_muscles": ["Hamstrings"], "equipment": ["Barbell"],
            "set_rep_guidelines": {"strength": "5x3"}},
        "barbell_bench_press": {"name": "Barbell Bench Press", "category": "Horizontal Push",
            "primary_muscles": ["Chest"], "equipment": ["Barbell", "Bench"]},
        "barbell_row": {"name": "Barbell Row", "category": "Horizontal Pull",
            "primary_muscles": ["Back"], "equipment": ["Barbell"]},
        "overhead_press": {"name": "Overhead Press", "category": "Vertical Push",
            "primary_muscles": ["Shoulders"], "equipment": ["Barbell"]},
        "pull_up": {"name": "Pull Up", "category": "Vertical Pull",
            "primary_muscles": ["Lats"], "equipment": ["Bodyweight"]},
        "bulgarian_split_squat": {"name": "Bulgarian Split Squat", "category": "Unilateral Lower",
            "primary_muscles": ["Quadriceps"], "equipment": ["Dumbbell"]},
        "plank": {"name": "Plank", "category": "Core",
            "primary_muscles": ["Core"], "equipment": ["Bodyweight"]},
        "bicep_curl": {"name": "Bicep Curl", "category": "Accessory",
            "primary_muscles": ["Biceps"], "equipment": ["Dumbbell"]},
    }})

    _write_brain(d, "strength-standards.yaml", {"strength_standards": {
        "assessment_questions": {"q1": "How long have you trained?",
            "q2": "Comfortable with main lifts?"},
        "classification_levels": {"novice": {"description": "0-6 months"},
            "intermediate": {"description": "1-2 years"}},
        "bench_by_level": {"novice": 60, "intermediate": 100},
        "squat_by_level": {"novice": 80, "intermediate": 140},
        "deadlift_by_level": {"novice": 100, "intermediate": 180},
        "ohp_by_level": {"novice": 35, "intermediate": 60},
        "pullup_by_level": {"novice": 0, "intermediate": 5},
    }})

    _write_brain(d, "strength-programming.yaml", {"strength_programming": {
        "goal_parameters": {
            "general_strength": {"rep_range": "4-6", "intensity_range": "80-90% 1RM",
                "sets_per_exercise": "4-5", "rest": "3-5 min"},
            "health_longevity": {"rep_range": "8-12", "intensity_range": "65-75% 1RM",
                "sets_per_exercise": "3", "rest": "60-90 sec"},
        },
        "full_body_3x": {"name": "Full Body 3x", "description": "3 full-body sessions"},
        "two_day_minimal": {"name": "Two Day Minimal", "description": "2 sessions"},
        "upper_lower_4x": {"name": "Upper/Lower 4x", "description": "4 sessions"},
        "strength_focused_4x": {"name": "Strength Focused 4x", "description": "4 strength"},
        "hypertrophy_focused_4x": {"name": "Hypertrophy Focused 4x", "description": "4 hypertrophy"},
        "push_pull_legs_6x": {"name": "Push/Pull/Legs 6x", "description": "6 sessions"},
        "dumbbell_only": {"name": "Dumbbell Only", "description": "dumbbells"},
        "bodyweight_only": {"name": "Bodyweight Only", "description": "bodyweight"},
        "deload_templates": {"standard_deload": {"volume": "reduce 40-50%"}},
        "linear_progression": {"description": "add weight each session"},
        "double_progression": {"description": "add reps then weight"},
        "rpe_autoregulation": {"description": "RPE-based"},
    }})
    return d


class TestAssessStrengthLevel:
    def test_returns_questionnaire_and_benchmarks(self, strength_brain):
        r = json.loads(strength_coach.assess_strength_level())
        assert r["tool"] == "assess_strength_level"
        assert r["questions"] == {"q1": "How long have you trained?",
                                  "q2": "Comfortable with main lifts?"}
        assert r["classification_levels"]["novice"]["description"] == "0-6 months"
        assert set(r["strength_benchmarks"]) == {
            "bench_by_level", "squat_by_level", "deadlift_by_level",
            "ohp_by_level", "pullup_by_level",
        }
        assert "usage_guide" in r


class TestExerciseLookup:
    def test_direct_key_match(self, strength_brain):
        r = json.loads(strength_coach.exercise_lookup(name="barbell back squat"))
        assert r["matched"] is True
        assert r["exercise"]["name"] == "Barbell Back Squat"

    def test_fuzzy_single_match(self, strength_brain):
        # "pull up" matches the pull_up key exactly (direct path) -> single hit
        r = json.loads(strength_coach.exercise_lookup(name="pull up"))
        assert r["matched"] is True
        assert r["exercise"]["name"] == "Pull Up"

    def test_multiple_matches(self, strength_brain):
        # "squat" appears in Barbell Back Squat and Bulgarian Split Squat
        r = json.loads(strength_coach.exercise_lookup(name="squat"))
        assert r["matched"] is False
        assert "Multiple matches" in r["reason"]
        assert len(r["matches"]) == 2

    def test_no_match_lists_available(self, strength_brain):
        r = json.loads(strength_coach.exercise_lookup(name="quantum curl"))
        assert r["matched"] is False
        assert "No exercise matching" in r["reason"]
        assert len(r["available_exercises"]) == 9


class TestGenerateStrengthWorkout:
    def test_unknown_goal_returns_error(self, strength_brain):
        r = json.loads(strength_coach.generate_strength_workout(goal="powerlifting"))
        assert "error" in r
        assert "powerlifting" in r["error"]

    def test_valid_goal_returns_session(self, strength_brain):
        r = json.loads(strength_coach.generate_strength_workout(
            goal="general_strength", level="novice", equipment="full_gym", days=3))
        assert r["workout_type"] == "full_body"
        assert r["goal"] == "general_strength"
        assert r["parameters"]["rep_range"] == "4-6"
        assert len(r["exercises"]) >= 1
        assert "warm_up" in r and "notes" in r

    def test_focus_override(self, strength_brain):
        r = json.loads(strength_coach.generate_strength_workout(
            goal="general_strength", level="novice", equipment="full_gym", focus="upper"))
        assert r["workout_type"] == "upper"

    def test_equipment_filter_excludes_barbell(self, strength_brain):
        r = json.loads(strength_coach.generate_strength_workout(
            goal="general_strength", level="novice", equipment="bodyweight_only", days=3))
        names = [e["name"] for e in r["exercises"]]
        assert "Barbell Back Squat" not in names
        assert all("Barbell" not in n for n in names)


class TestDesignStrengthProgram:
    def test_returns_program_structure(self, strength_brain):
        r = json.loads(strength_coach.design_strength_program(
            goal="general_strength", level="novice", equipment="full_gym",
            weeks=12, days_per_week=3))
        assert r["goal"] == "general_strength"
        assert r["split"] == "full_body_3x"
        assert r["duration_weeks"] == 12
        for key in ("parameters", "deload", "phase_structure", "rules", "template"):
            assert key in r
        assert r["parameters"]["progression_method"] == "linear_progression"

    def test_split_by_days(self, strength_brain):
        def split(days, goal="general_strength"):
            return json.loads(strength_coach.design_strength_program(
                goal=goal, level="novice", equipment="full_gym", days_per_week=days))["split"]
        assert split(2) == "two_day_minimal"
        assert split(3) == "full_body_3x"
        assert split(4) == "strength_focused_4x"
        assert split(4, goal="hypertrophy") == "hypertrophy_focused_4x"
        assert split(5) == "push_pull_legs_6x"

    def test_equipment_overrides_split(self, strength_brain):
        def split(eq):
            return json.loads(strength_coach.design_strength_program(
                goal="general_strength", level="novice", equipment=eq, days_per_week=3))["split"]
        assert split("dumbbell_only") == "dumbbell_only"
        assert split("bodyweight_only") == "bodyweight_only"

    def test_level_drives_progression_method(self, strength_brain):
        r = json.loads(strength_coach.design_strength_program(
            goal="general_strength", level="intermediate", equipment="full_gym",
            weeks=12, days_per_week=3))
        assert r["parameters"]["progression_method"] == "double_progression"


class TestBuildPhaseStructure:
    def test_short_program_single_block(self):
        phases = strength_coach._build_phase_structure(4, "novice", "general_strength")
        assert len(phases) == 1
        assert phases[0]["phase"] == "Single Block"

    def test_novice_two_phases(self):
        phases = strength_coach._build_phase_structure(12, "novice", "general_strength")
        assert len(phases) == 2
        assert phases[0]["name"] == "Accumulation / Technique"
        assert phases[1]["name"] == "Intensification"

    def test_intermediate_block_periodization(self):
        phases = strength_coach._build_phase_structure(12, "intermediate", "general_strength")
        assert len(phases) == 3
        assert phases[2]["name"] == "Realization / Peak"


class TestSelectExercisesForSession:
    def _db(self, strength_brain):
        return _brain._load_all()["exercise_database"]

    def test_full_body_selects_one_per_pattern(self, strength_brain):
        sel = strength_coach._select_exercises_for_session(
            self._db(strength_brain), "full_body", "full_gym", 60)
        names = [e["name"] for e in sel]
        # one exercise per pattern: squat, hinge, horizontal_push, horizontal_pull, core
        assert "Barbell Back Squat" in names
        assert "Plank" in names
        assert len(sel) == 5

    def test_time_cap_limits_exercises(self, strength_brain):
        # 16 min -> max(3, 16//8=2)=3 -> at most 3 exercises even with 5 patterns
        sel = strength_coach._select_exercises_for_session(
            self._db(strength_brain), "full_body", "full_gym", 16)
        assert len(sel) == 3

    def test_equipment_filter_bodyweight(self, strength_brain):
        sel = strength_coach._select_exercises_for_session(
            self._db(strength_brain), "full_body", "bodyweight_only", 60)
        # only bodyweight-compatible exercises; barbell exercises excluded
        assert len(sel) == 1  # only Plank (core) qualifies among full_body patterns
        assert all("Barbell" not in e["name"] for e in sel)
