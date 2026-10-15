"""Routing contract for get_coaching_knowledge against the real coach-brain.

The tool description enumerates the topics the model is told it can ask for.
If a YAML key is renamed or a topic is added to the description without a
matching section, retrieval silently degrades to `matched: false`. Topics are
parsed from the registered description itself, so the two cannot drift apart.

Omnibus sections (ADR 0001) must not leak into endurance queries: before
2026-10-15 any topic containing "training" pulled `strength_training`, so the
endurance SKILL.md's own documented calls ("injury return to training",
"nutrition during training") returned strength content.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "plugins"))

from training.coaching import _OMNIBUS_SECTIONS, get_coaching_knowledge, register_tools

REPO_BRAIN = Path(__file__).parent.parent / "coach-brain"

# Description topic -> the section a correct lookup must return.
EXPECTED_KEY = {
    "altitude": "altitude_acclimatization",
    "cold weather": "cold_weather_training",
    "coaching safety": "coaching_safety",
    "cycling hand numbness": "cycling_hand_numbness",
    "exercise database": "exercise_database",
    "female physiology": "female_athlete_physiology",
    "goal continuity": "goal_continuity_adaptive_planning",
    "headless coaching failures": "headless_coaching_failures",
    "heat": "heat_acclimatization",
    "injury": "injury_return_to_training",
    "nutrition": "nutrition",
    "persistent performance decline": "persistent_performance_decline",
    "post-workout feedback": "post_workout_feedback",
    "power zones": "coggan_power_7_zone",
    "race course verification": "race_course_verification",
    "recovery": "recovery_heuristics",
    "sleep": "sleep_optimization",
    "strength principles": "strength_principles",
    "strength programming": "strength_programming",
    "strength standards": "strength_standards",
    "strength training": "strength_training",
    "tapering": "tapering",
    "temporal load validation": "temporal_load_validation",
    "training philosophies": "training_philosophies",
    "vo2max": "vo2max",
    "workout library": "workout_library",
}

# Endurance topics, including calls documented in skills/coaching/, that must
# never pull an omnibus section.
ENDURANCE_TOPICS = [
    "training philosophies",
    "training periodization",
    "polarized training",
    "cross training",
    "injury return to training",
    "recovery heuristics",
    "threshold intervals",
    "tapering",
    "half marathon",
]


def _description_topics() -> list[str]:
    captured = {}

    class _Ctx:
        def register_tool(self, **kwargs):
            captured.update(kwargs)

    register_tools(_Ctx())
    description = captured["schema"]["description"]
    listed = description.split("Topics include:")[1].strip().rstrip(".")
    return [t.strip() for t in listed.split(",")]


@pytest.fixture(autouse=True)
def _real_brain(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("training._brain._brain_dir", lambda: REPO_BRAIN)


def _keys(topic: str) -> set[str]:
    result = json.loads(get_coaching_knowledge(topic))
    assert result.get("matched") is True, f"{topic!r} did not match: {result}"
    return set(result["knowledge"])


def test_every_description_topic_has_an_expectation():
    assert sorted(_description_topics()) == sorted(EXPECTED_KEY)


@pytest.mark.parametrize("topic", sorted(EXPECTED_KEY))
def test_description_topic_routes_to_its_section(topic: str):
    assert EXPECTED_KEY[topic] in _keys(topic)


@pytest.mark.parametrize("topic", ENDURANCE_TOPICS)
def test_endurance_topic_pulls_no_omnibus_section(topic: str):
    assert not _keys(topic) & _OMNIBUS_SECTIONS


def test_nutrition_query_pulls_only_nutrition_omnibus():
    assert _keys("nutrition during training") & _OMNIBUS_SECTIONS == {"nutrition"}


def test_strength_skill_keeps_explicit_access():
    assert {"strength_principles", "strength_standards"} <= _keys("strength")
