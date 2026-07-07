"""Tests for get_activity_streams and get_fitness_chart tools."""

import json
import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "plugins"))
from training.intervals_icu import get_activity_streams, get_fitness_chart


# ---------------------------------------------------------------------------
# get_activity_streams
# ---------------------------------------------------------------------------

def test_activity_streams_returns_stream_data():
    """Should return per-second arrays for each available stream type."""

    mock_response = [
        {
            "type": "time",
            "name": None,
            "data": [0, 1, 2, 3, 4],
            "valueType": "double",
        },
        {
            "type": "watts",
            "name": None,
            "data": [0, 100, 200, 150, 0],
            "valueType": "int",
        },
        {
            "type": "heartrate",
            "name": None,
            "data": [120, 130, 140, 135, 125],
            "valueType": "int",
        },
    ]

    with patch("training.intervals_icu._load_credentials", return_value=("i494629", "test_key")):
        with patch("training.intervals_icu._cache_get", return_value=None):
            with patch("training.intervals_icu._cache_set"):
                with patch("training.intervals_icu._request", return_value=mock_response):
                    result = json.loads(
                        get_activity_streams("discord_dm", activity_id="i123456")
                    )

    assert result["source"] == "intervals.icu"
    assert result["activity_id"] == "i123456"
    assert result["stream_count"] == 3

    # Each stream should have type, name, data, value_type
    types = {s["type"] for s in result["streams"]}
    assert types == {"time", "watts", "heartrate"}

    watts_stream = [s for s in result["streams"] if s["type"] == "watts"][0]
    assert watts_stream["data"] == [0, 100, 200, 150, 0]
    assert watts_stream["value_type"] == "int"


def test_activity_streams_empty_response():
    """Should handle an empty response gracefully."""

    with patch("training.intervals_icu._load_credentials", return_value=("i494629", "test_key")):
        with patch("training.intervals_icu._cache_get", return_value=None):
            with patch("training.intervals_icu._cache_set"):
                with patch("training.intervals_icu._request", return_value=[]):
                    result = json.loads(
                        get_activity_streams("discord_dm", activity_id="i123456")
                    )

    assert result["stream_count"] == 0
    assert result["streams"] == []


def test_activity_streams_missing_credentials():
    """Should return error when credentials are absent."""

    with patch("training.intervals_icu._load_credentials",
               side_effect=ValueError("No credentials")):
        result = json.loads(
            get_activity_streams("discord_dm", activity_id="i123456")
        )

    assert "error" in result
    assert "No credentials" in result["error"]


# ---------------------------------------------------------------------------
# get_fitness_chart
# ---------------------------------------------------------------------------

def test_fitness_chart_returns_long_range_data():
    """Should return daily CTL/ATL/TSB records with sport-specific eFTP."""

    mock_response = [
        {"id": "2026-01-01", "ctl": 30.0, "atl": 20.0, "rampRate": 1.5,
         "sportInfo": [{"type": "Ride", "eftp": 250.0}]},
        {"id": "2026-01-02", "ctl": 31.0, "atl": 22.0, "rampRate": 2.0,
         "sportInfo": [{"type": "Ride", "eftp": 251.0}]},
        {"id": "2026-01-03", "ctl": 32.0, "atl": 24.0, "rampRate": 2.5,
         "sportInfo": [{"type": "Ride", "eftp": 252.0}]},
    ]

    with patch("training.intervals_icu._load_credentials", return_value=("i494629", "test_key")):
        with patch("training.intervals_icu._cache_get", return_value=None):
            with patch("training.intervals_icu._cache_set"):
                with patch("training.intervals_icu._request", return_value=mock_response):
                    result = json.loads(
                        get_fitness_chart("discord_dm", days=365)
                    )

    assert result["source"] == "intervals.icu"
    assert result["record_count"] == 3
    assert len(result["records"]) == 3

    # TSB should be computed: CTL - ATL
    assert result["records"][0]["tsb"] == 10.0  # 30 - 20
    assert result["records"][1]["tsb"] == 9.0   # 31 - 22
    assert result["records"][2]["tsb"] == 8.0   # 32 - 24

    # eFTP should be present
    assert result["records"][0]["sport_info"][0]["sport"] == "Ride"
    assert result["records"][0]["sport_info"][0]["eftp"] == 250.0


def test_fitness_chart_days_clamped():
    """Should clamp days parameter to 365 max."""

    mock_response = []

    with patch("training.intervals_icu._load_credentials", return_value=("i494629", "test_key")):
        with patch("training.intervals_icu._cache_get", return_value=None):
            with patch("training.intervals_icu._cache_set"):
                with patch("training.intervals_icu._request", return_value=mock_response):
                    # Request 500 days — should be clamped to 365
                    result = json.loads(
                        get_fitness_chart("discord_dm", days=500)
                    )

    # The cache key should reflect the clamped value
    # and the request should go through (empty response is fine)
    assert result["days"] == 365


def test_fitness_chart_missing_credentials():
    """Should return error when credentials are absent."""

    with patch("training.intervals_icu._load_credentials",
               side_effect=ValueError("No credentials")):
        result = json.loads(
            get_fitness_chart("discord_dm", days=30)
        )

    assert "error" in result
    assert "No credentials" in result["error"]


def test_fitness_chart_handles_none_values():
    """Should compute TSB only when both CTL and ATL are present."""

    mock_response = [
        {"id": "2026-01-01", "ctl": 30.0, "atl": None, "rampRate": 1.0,
         "sportInfo": []},
        {"id": "2026-01-02", "ctl": None, "atl": 20.0, "rampRate": 1.0,
         "sportInfo": []},
        {"id": "2026-01-03", "ctl": 35.0, "atl": 25.0, "rampRate": 2.0,
         "sportInfo": []},
    ]

    with patch("training.intervals_icu._load_credentials", return_value=("i494629", "test_key")):
        with patch("training.intervals_icu._cache_get", return_value=None):
            with patch("training.intervals_icu._cache_set"):
                with patch("training.intervals_icu._request", return_value=mock_response):
                    result = json.loads(
                        get_fitness_chart("discord_dm", days=30)
                    )

    # TSB should be None when either CTL or ATL is None
    assert result["records"][0]["tsb"] is None  # ATL is None
    assert result["records"][1]["tsb"] is None  # CTL is None
    assert result["records"][2]["tsb"] == 10.0  # both present
