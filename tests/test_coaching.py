"""Tests for the training plugin — coach-brain YAML loading and search."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "plugins"))

from training.coaching import _brain_dir, _load_all, get_coaching_knowledge


@pytest.fixture
def coach_brain_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create a temporary coach-brain directory and patch HERMES_HOME."""
    d = tmp_path / "coach-brain"
    d.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setattr("training.coaching._brain_dir", lambda: d)
    return d


class TestBrainDir:
    def test_returns_hermes_home_coach_brain(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        assert _brain_dir() == tmp_path / "coach-brain"

    def test_falls_back_to_home_dot_hermes(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv("HERMES_HOME", raising=False)
        monkeypatch.setattr("pathlib.Path.home", lambda: Path("/fake/home"))
        assert _brain_dir() == Path("/fake/home/.hermes/coach-brain")


class TestLoadAll:
    def test_loads_single_yaml(self, coach_brain_dir: Path):
        (coach_brain_dir / "test.yaml").write_text(
            "training_philosophies:\n  polarized:\n    summary: 80/20 distribution\n"
        )
        result = _load_all()
        assert result["training_philosophies"]["polarized"]["summary"] == "80/20 distribution"

    def test_loads_multiple_yaml_files(self, coach_brain_dir: Path):
        (coach_brain_dir / "a.yaml").write_text("nutrition:\n  carbs: 3-5g/kg\n")
        (coach_brain_dir / "b.yaml").write_text("recovery_heuristics:\n  tsb: CTL minus ATL\n")
        result = _load_all()
        assert "nutrition" in result
        assert "recovery_heuristics" in result
        assert result["nutrition"]["carbs"] == "3-5g/kg"
        assert result["recovery_heuristics"]["tsb"] == "CTL minus ATL"

    def test_ignores_invalid_yaml(self, coach_brain_dir: Path):
        (coach_brain_dir / "good.yaml").write_text("valid: confirmed\n")
        (coach_brain_dir / "bad.yaml").write_text("{{invalid yaml content\n")
        result = _load_all()
        assert result["valid"] == "confirmed"

    def test_ignores_non_dict_yaml(self, coach_brain_dir: Path):
        (coach_brain_dir / "list.yaml").write_text("- item1\n- item2\n")
        result = _load_all()
        assert result == {}

    def test_returns_empty_when_directory_missing(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        monkeypatch.setattr("training.coaching._brain_dir", lambda: tmp_path / "nonexistent")
        result = _load_all()
        assert result == {}


class TestGetCoachingKnowledge:
    """get_coaching_knowledge returns matched TOP-LEVEL keys from the merged brain dict.
    Each YAML file contributes its top-level key(s), so the knowledge dict mirrors
    the merged brain structure: {top_level_key: {...nested...}}."""

    def test_matches_exact_topic(self, coach_brain_dir: Path):
        (coach_brain_dir / "workouts.yaml").write_text(
            "workout_library:\n  threshold_intervals:\n    intensity: 95-105% FTP\n"
        )
        result = json.loads(get_coaching_knowledge("threshold intervals"))
        assert result["matched"] is True
        # Top-level key matched
        assert "workout_library" in result["knowledge"]
        # Nested key present inside the matched section
        assert "threshold_intervals" in result["knowledge"]["workout_library"]

    def test_matches_partial_keyword(self, coach_brain_dir: Path):
        (coach_brain_dir / "recovery.yaml").write_text(
            "recovery_heuristics:\n  hrv_interpretation:\n    well_recovered: above baseline\n"
        )
        result = json.loads(get_coaching_knowledge("hrv"))
        assert result["matched"] is True
        assert "recovery_heuristics" in result["knowledge"]
        assert "hrv_interpretation" in result["knowledge"]["recovery_heuristics"]

    def test_returns_available_topics_on_no_match(self, coach_brain_dir: Path):
        (coach_brain_dir / "nutrition.yaml").write_text("nutrition:\n  protein: 1.6g/kg\n")
        result = json.loads(get_coaching_knowledge("quantum physics"))
        assert result["matched"] is False
        assert "nutrition" in result["available_topics"]

    def test_returns_error_when_brain_empty(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        monkeypatch.setattr("training.coaching._brain_dir", lambda: tmp_path / "missing")
        result = json.loads(get_coaching_knowledge("anything"))
        assert "error" in result

    def test_searches_nested_content(self, coach_brain_dir: Path):
        (coach_brain_dir / "injury.yaml").write_text(
            "injury_return:\n  knee_pain:\n    patellofemoral:\n      description: anterior knee pain\n"
        )
        result = json.loads(get_coaching_knowledge("knee pain"))
        assert result["matched"] is True
        # Top-level key matched; nested content is inside it
        assert "injury_return" in result["knowledge"]
        assert "knee_pain" in result["knowledge"]["injury_return"]

    def test_hyphenated_topic_matches_underscore_key(self, coach_brain_dir: Path):
        (coach_brain_dir / "periodization.yaml").write_text(
            "periodization:\n  block_training:\n    summary: concentrated loading\n"
        )
        result = json.loads(get_coaching_knowledge("block-training"))
        assert result["matched"] is True
