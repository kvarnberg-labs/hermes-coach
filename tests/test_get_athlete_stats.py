"""Tests for get_athlete_stats training tool.

Covers date validation, credential handling, and aggregation of the
intervals.icu /activities response into per-sport and overall totals.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "plugins"))

from training import get_athlete_stats


@pytest.fixture
def mock_credentials(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Set up a fake HERMES_HOME with stored credentials for test-user-123."""
    hermes_home = tmp_path / ".hermes"
    hermes_home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))

    user_dir = hermes_home / "users" / "test-user-123"
    user_dir.mkdir(parents=True)
    (user_dir / "intervals_key").write_text("fake-api-key-abc")
    (user_dir / "intervals_athlete_id").write_text("i12345")


class TestDateValidation:
    def test_valid_date(self):
        assert get_athlete_stats._validate_date("2026-08-20", "start_date") == "2026-08-20"

    def test_invalid_date_raises(self):
        with pytest.raises(ValueError, match="start_date"):
            get_athlete_stats._validate_date("20-08-2026", "start_date")

    def test_non_string_raises(self):
        with pytest.raises(ValueError):
            get_athlete_stats._validate_date(None, "end_date")


class TestGetAthleteStats:
    def test_invalid_start_date_returns_error(self, mock_credentials):
        r = json.loads(get_athlete_stats.get_athlete_stats(
            "test-user-123", start_date="bad", end_date="2026-08-20"))
        assert "error" in r
        assert "start_date" in r["error"]

    def test_invalid_end_date_returns_error(self, mock_credentials):
        r = json.loads(get_athlete_stats.get_athlete_stats(
            "test-user-123", start_date="2026-08-20", end_date="2026-13-01"))
        assert "error" in r

    def test_no_credentials_returns_error(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        r = json.loads(get_athlete_stats.get_athlete_stats(
            "ghost-user", start_date="2026-08-01", end_date="2026-08-20"))
        assert "error" in r

    def test_api_error_propagated(self, mock_credentials):
        with patch.object(get_athlete_stats, "_request") as mock_req:
            mock_req.side_effect = ValueError("401 Unauthorized")
            r = json.loads(get_athlete_stats.get_athlete_stats(
                "test-user-123", start_date="2026-08-01", end_date="2026-08-20"))
        assert r["error"] == "401 Unauthorized"

    def test_non_list_response_returns_error(self, mock_credentials):
        with patch.object(get_athlete_stats, "_request", return_value={"not": "a list"}):
            r = json.loads(get_athlete_stats.get_athlete_stats(
                "test-user-123", start_date="2026-08-01", end_date="2026-08-20"))
        assert "error" in r

    def test_empty_activities(self, mock_credentials):
        with patch.object(get_athlete_stats, "_request", return_value=[]):
            r = json.loads(get_athlete_stats.get_athlete_stats(
                "test-user-123", start_date="2026-08-01", end_date="2026-08-20"))
        assert r["total_activities"] == 0
        assert r["total_distance_km"] == 0.0
        assert r["sports"] == {}
        assert r["source"] == "intervals.icu"

    def test_aggregation_and_sport_breakdown(self, mock_credentials):
        activities = [
            {"type": "Ride", "distance": 40000, "moving_time": 5400,
             "calories": 600, "icu_training_load": 80},
            {"type": "Ride", "distance": 20000, "moving_time": 2700,
             "calories": 300, "icu_training_load": 40},
            {"type": "Run", "distance": 10000, "moving_time": 3000,
             "calories": 400, "icu_training_load": 50},
            {"type": "VirtualRide", "distance": None, "moving_time": None,
             "calories": None, "icu_training_load": None},  # nulls → zero
            "not-a-dict",  # ignored
        ]
        with patch.object(get_athlete_stats, "_request", return_value=activities):
            r = json.loads(get_athlete_stats.get_athlete_stats(
                "test-user-123", start_date="2026-08-01", end_date="2026-08-31"))
        assert r["total_activities"] == 4  # 3 dicts with data + 1 with nulls
        # 40000 + 20000 + 10000 + 0 = 70000 m = 70 km
        assert r["total_distance_km"] == 70.0
        # (5400 + 2700 + 3000 + 0) / 3600 = 3.0833 → 3.08
        assert r["total_duration_hours"] == round(11100 / 3600, 2)
        assert r["total_calories"] == 1300
        assert r["total_training_load"] == 170

        rides = r["sports"]["Ride"]
        assert rides["activities"] == 2
        assert rides["distance_km"] == 60.0
        assert rides["training_load"] == 120

        runs = r["sports"]["Run"]
        assert runs["activities"] == 1
        assert runs["distance_km"] == 10.0

        # VirtualRide with all-null fields still counted as an activity
        assert r["sports"]["VirtualRide"]["activities"] == 1
        assert r["sports"]["VirtualRide"]["distance_km"] == 0.0

    def test_request_uses_date_params(self, mock_credentials):
        with patch.object(get_athlete_stats, "_request", return_value=[]) as mock_req:
            get_athlete_stats.get_athlete_stats(
                "test-user-123", start_date="2026-08-01", end_date="2026-08-31")
        params = mock_req.call_args.kwargs.get("params") or mock_req.call_args[1].get("params")
        assert params == {"oldest": "2026-08-01", "newest": "2026-08-31"}


class TestHelpers:
    def test_float_or_zero(self):
        assert get_athlete_stats._float_or_zero(3.5) == 3.5
        assert get_athlete_stats._float_or_zero(None) == 0.0

    def test_int_or_zero(self):
        assert get_athlete_stats._int_or_zero(5) == 5
        assert get_athlete_stats._int_or_zero(None) == 0
        assert get_athlete_stats._int_or_zero("abc") == 0
