"""Tests for get_activity_detail field mapping fix.

Verifies that get_activity_detail uses the correct intervals.icu API field names
(icu_hr_zones, icu_hr_zone_times, icu_power_zones, icu_zone_times) instead of the
old incorrect names (heartrate_zones, heartrate_zone_times, etc.).
"""

import json
import sys
from unittest.mock import patch, MagicMock

sys.path.insert(0, "/opt/hermes/plugins")
from training.intervals_icu import get_activity_detail


def test_activity_detail_returns_hr_zone_data():
    """HR zones and zone times should be populated from the API."""
    mock_response = {
        "id": "i123456",
        "name": "Test Ride",
        "start_date_local": "2026-07-04T10:00:00",
        "type": "Ride",
        "moving_time": 3600,
        "distance": 40000,
        "icu_training_load": 100,
        "icu_intensity": 65.0,
        "avg_heartrate": 130,
        "max_heartrate": 155,
        "lthr": 164,
        "pace": 8.0,
        "max_speed": 15.0,
        "total_elevation_gain": 200,
        "avg_cadence": 80,
        "icu_weighted_avg_watts": 170,
        "icu_average_watts": 160,
        "icu_ftp": 265,
        "icu_rpe": 2,
        "calories": 800,
        "carbs_used": 200,
        "coasting_time": 120,
        "decoupling": 2.5,
        "icu_variability_index": 1.1,
        "icu_efficiency_factor": 1.4,
        "icu_power_hr": 1.3,
        "icu_power_hr_z2_mins": 15,
        "icu_sweet_spot_min": 84,
        "icu_sweet_spot_max": 97,
        "icu_joules_above_ftp": 5000,
        "icu_warmup_time": 600,
        "icu_cooldown_time": 300,
        "icu_cadence_z2": 85,
        "icu_hr_zones": [131, 146, 153, 163, 167, 172, 181],
        "icu_hr_zone_times": [2400, 900, 200, 100, 0, 0, 0],
        "icu_power_zones": [55, 75, 90, 105, 120, 150, 999],
        "icu_zone_times": [
            {"id": "Z1", "secs": 1200},
            {"id": "Z2", "secs": 1800},
            {"id": "Z3", "secs": 400},
            {"id": "Z4", "secs": 100},
            {"id": "Z5", "secs": 50},
            {"id": "Z6", "secs": 50},
            {"id": "Z7", "secs": 0},
        ],
        "interval_summary": ["1x 300s 250w", "1x 60s 400w"],
        "laps": [{"index": 1, "name": "Warmup"}],
    }

    with patch("training.intervals_icu._load_credentials", return_value=("i494629", "test_key")):
        with patch("training.intervals_icu._cache_get", return_value=None):
            with patch("training.intervals_icu._cache_set"):
                with patch("training.intervals_icu._request", return_value=mock_response):
                    result = json.loads(get_activity_detail("discord_dm", activity_id="i123456"))

    # HR zones should be populated (old code returned None — this was the bug)
    assert result["hr_zones"] == [131, 146, 153, 163, 167, 172, 181]
    assert result["hr_zone_times"] == [2400, 900, 200, 100, 0, 0, 0]

    # Power zones should be populated
    assert result["power_zones"] == [55, 75, 90, 105, 120, 150, 999]
    assert result["power_zone_times"] is not None
    assert len(result["power_zone_times"]) == 7

    # New fields should be present
    assert result["avg_power_w"] == 160
    assert result["calories"] == 800
    assert result["carbs_used_g"] == 200
    assert result["coasting_time_s"] == 120
    assert result["decoupling_pct"] == 2.5
    assert result["variability_index"] == 1.1
    assert result["efficiency_factor"] == 1.4
    assert result["interval_summary"] == ["1x 300s 250w", "1x 60s 400w"]
    assert result["lthr"] == 164
    assert result["rpe"] == 2


def test_activity_detail_old_field_names_not_used():
    """The old field names (heartrate_zones etc.) should not appear in the result."""
    mock_response = {
        "id": "i123",
        "name": "Test",
        "start_date_local": "2026-07-04T10:00:00",
        "type": "Ride",
        "moving_time": 3600,
        "distance": 40000,
        "icu_training_load": 50,
        "icu_intensity": 60,
        "heartrate_zones": [131, 146, 153],
        "heartrate_zone_times": [1000, 500, 100],
        "power_zones": [55, 75, 90],
        "power_zone_times": [{"id": "Z1", "secs": 1000}],
        "icu_hr_zones": [131, 146, 153, 163],
        "icu_hr_zone_times": [2000, 1000, 200, 100],
        "icu_power_zones": [55, 75, 90, 105],
        "icu_zone_times": [{"id": "Z1", "secs": 2000}],
        "icu_weighted_avg_watts": 160,
        "icu_ftp": 265,
    }

    with patch("training.intervals_icu._load_credentials", return_value=("i494629", "test_key")):
        with patch("training.intervals_icu._cache_get", return_value=None):
            with patch("training.intervals_icu._cache_set"):
                with patch("training.intervals_icu._request", return_value=mock_response):
                    result = json.loads(get_activity_detail("discord_dm", activity_id="i123"))

    # Should use icu_* fields, not the old field names
    assert result["hr_zones"] == [131, 146, 153, 163]  # 4 zones from icu_hr_zones
    assert result["hr_zone_times"] == [2000, 1000, 200, 100]
    assert result["power_zones"] == [55, 75, 90, 105]
    # Should NOT be the old-format data
    assert result["hr_zones"] != [131, 146, 153]  # Would be 3 if using old field
