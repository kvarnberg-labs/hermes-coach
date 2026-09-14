"""Tests for the training plugin — weather tool."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "plugins"))

from training.weather import get_weather, _coaching_notes, _WMO_CODES


@pytest.fixture(autouse=True)
def _reset_weather_cache():
    """The module-level TTL cache must not leak between tests."""
    from training import weather as _weather

    _weather._weather_cache.clear()
    yield
    _weather._weather_cache.clear()


class TestWmoCodes:
    def test_covers_all_standard_codes(self):
        expected = {0, 1, 2, 3, 45, 48, 51, 53, 55, 61, 63, 65,
                    71, 73, 75, 77, 80, 81, 82, 85, 86, 95, 96, 99}
        assert expected.issubset(set(_WMO_CODES.keys()))

    def test_clear_sky(self):
        assert _WMO_CODES[0] == "Clear sky"

    def test_thunderstorm(self):
        assert "Thunderstorm" in _WMO_CODES[95]


class TestCoachingNotes:
    def test_no_notes_for_normal_conditions(self):
        current = {
            "temperature_2m": 20,
            "apparent_temperature": 19,
            "wind_speed_10m": 15,
            "uv_index": 3,
            "weathercode": 1,
        }
        notes = _coaching_notes(current, [])
        assert notes == []

    def test_heat_risk_note(self):
        current = {
            "temperature_2m": 38,
            "apparent_temperature": 42,
            "wind_speed_10m": 10,
            "uv_index": 2,
            "weathercode": 0,
        }
        notes = _coaching_notes(current, [])
        assert any("Heat risk" in n for n in notes)

    def test_cold_risk_note(self):
        current = {
            "temperature_2m": -15,
            "apparent_temperature": -20,
            "wind_speed_10m": 5,
            "uv_index": 0,
            "weathercode": 75,
        }
        notes = _coaching_notes(current, [])
        assert any("Cold risk" in n for n in notes)

    def test_strong_wind_note(self):
        current = {
            "temperature_2m": 15,
            "apparent_temperature": 12,
            "wind_speed_10m": 60,
            "uv_index": 2,
            "weathercode": 2,
        }
        notes = _coaching_notes(current, [])
        assert any("Strong wind" in n for n in notes)

    def test_uv_note(self):
        current = {
            "temperature_2m": 25,
            "apparent_temperature": 25,
            "wind_speed_10m": 10,
            "uv_index": 9,
            "weathercode": 0,
        }
        notes = _coaching_notes(current, [])
        assert any("UV index" in n for n in notes)

    def test_rain_note(self):
        current = {
            "temperature_2m": 15,
            "apparent_temperature": 14,
            "wind_speed_10m": 10,
            "uv_index": 1,
            "weathercode": 61,
        }
        forecast = [
            {"precip_prob_pct": 80, "precip_mm": 3},
            {"precip_prob_pct": 20, "precip_mm": 0},
        ]
        notes = _coaching_notes(current, forecast)
        assert any("Rain likely" in n for n in notes)

    def test_thunderstorm_note(self):
        current = {
            "temperature_2m": 25,
            "apparent_temperature": 28,
            "wind_speed_10m": 20,
            "uv_index": 2,
            "weathercode": 95,
        }
        notes = _coaching_notes(current, [])
        assert any("Thunderstorm" in n for n in notes)


class TestGetWeather:
    def test_returns_error_on_network_failure(self):
        with patch("urllib.request.urlopen") as mock_urlopen:
            import urllib.error
            mock_urlopen.side_effect = urllib.error.URLError("DNS failure")
            result = json.loads(get_weather(60.17, 24.94))
            assert "error" in result
            assert "Open-Meteo" in result["error"]

    def test_returns_current_and_forecast_on_success(self):
        mock_data = {
            "current": {
                "temperature_2m": 22,
                "apparent_temperature": 20,
                "relative_humidity_2m": 65,
                "precipitation": 0,
                "wind_speed_10m": 12,
                "wind_direction_10m": 180,
                "weathercode": 2,
                "uv_index": 4,
                "is_day": 1,
            },
            "hourly": {
                "time": [f"2025-07-01T{h:02d}:00" for h in range(48)],
                "temperature_2m": [20 + h % 5 for _ in range(48) for h in range(1)][0:48],
                "apparent_temperature": [19 + h % 5 for _ in range(48) for h in range(1)][0:48],
                "precipitation_probability": [0] * 48,
                "precipitation": [0] * 48,
                "wind_speed_10m": [10] * 48,
                "weathercode": [2] * 48,
                "uv_index": [3] * 48,
            },
            "timezone": "Europe/Helsinki",
        }
        # Fix the list comprehensions above
        mock_data["hourly"]["temperature_2m"] = [20 + (h % 5) for h in range(48)]
        mock_data["hourly"]["apparent_temperature"] = [19 + (h % 5) for h in range(48)]

        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(mock_data).encode()
        mock_resp.__enter__ = lambda s: mock_resp
        mock_resp.__exit__ = lambda s, *a: None

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = json.loads(get_weather(60.17, 24.94, "Helsinki"))

        assert result["location"] == "Helsinki"
        assert result["current"]["temp_c"] == 22
        assert result["current"]["conditions"] == "Partly cloudy"
        assert len(result["forecast_48h"]) == 16  # 48 hours / 3-hour buckets


class TestWeatherCache:
    """TTL payload cache: hits skip the Open-Meteo round-trip; display
    fields are always rebuilt from the current call's arguments."""

    PAYLOAD = {"current": {}, "hourly": {"time": []}, "timezone": "UTC"}

    def _patched_urlopen(self):
        m = MagicMock()
        m.__enter__.return_value.read.return_value = json.dumps(self.PAYLOAD).encode()
        return m

    def test_second_call_within_ttl_skips_fetch(self):
        with patch(
            "urllib.request.urlopen", return_value=self._patched_urlopen()
        ) as mock_urlopen:
            get_weather(60.17, 24.94)
            get_weather(60.17, 24.94)
            assert mock_urlopen.call_count == 1

    def test_nearby_coordinates_share_cache_entry(self):
        with patch(
            "urllib.request.urlopen", return_value=self._patched_urlopen()
        ) as mock_urlopen:
            get_weather(60.17, 24.94)
            get_weather(60.174, 24.941)  # rounds to the same ~1.1 km cell
            assert mock_urlopen.call_count == 1

    def test_expired_entry_refetches(self):
        import time as _time

        from training import weather as _weather

        with patch(
            "urllib.request.urlopen", return_value=self._patched_urlopen()
        ) as mock_urlopen:
            get_weather(60.17, 24.94)
            ts, payload = _weather._weather_cache[(60.17, 24.94)]
            _weather._weather_cache[(60.17, 24.94)] = (_time.time() - 601, payload)
            get_weather(60.17, 24.94)
            assert mock_urlopen.call_count == 2

    def test_display_fields_rebuilt_per_call(self):
        with patch("urllib.request.urlopen", return_value=self._patched_urlopen()):
            get_weather(60.17, 24.94, location_name="First")
            second = json.loads(get_weather(60.17, 24.94, location_name="Second"))
        # A cache hit must not echo the first caller's location label.
        assert second["location"] == "Second"
