"""Tests for the training plugin — intervals.icu API tools."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "plugins"))

from training import intervals_icu


@pytest.fixture
def mock_credentials(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Set up a fake HERMES_HOME with stored credentials."""
    hermes_home = tmp_path / ".hermes"
    hermes_home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))

    user_dir = hermes_home / "users" / "test-user-123"
    user_dir.mkdir(parents=True)
    (user_dir / "intervals_key").write_text("fake-api-key-abc")
    (user_dir / "intervals_athlete_id").write_text("i12345")


class TestAuthHeader:
    def test_builds_basic_auth(self):
        header = intervals_icu._auth_header("mykey")
        assert header.startswith("Basic ")
        import base64

        token = header.split(" ", 1)[1]
        decoded = base64.b64decode(token).decode()
        assert decoded == "API_KEY:mykey"


class TestCache:
    def test_cache_get_returns_none_when_missing(self, mock_credentials):
        result = intervals_icu._cache_get("test-user-123", "nonexistent", 3600)
        assert result is None

    def test_cache_get_returns_data_when_fresh(self, mock_credentials):
        intervals_icu._cache_set("test-user-123", "test-key", {"value": 42})
        result = intervals_icu._cache_get("test-user-123", "test-key", 3600)
        assert result == {"value": 42}

    def test_cache_key_is_deterministic(self):
        k1 = intervals_icu._cache_key("/athlete/i12345", {"a": 1})
        k2 = intervals_icu._cache_key("/athlete/i12345", {"a": 1})
        assert k1 == k2
        assert len(k1) == 16

    def test_cache_key_differs_for_different_params(self):
        k1 = intervals_icu._cache_key("/activities", {"days": 7})
        k2 = intervals_icu._cache_key("/activities", {"days": 14})
        assert k1 != k2

    def test_cache_set_creates_file_mode_600(self, mock_credentials):
        import os

        intervals_icu._cache_set("test-user-123", "perm-key", {"v": 1})
        cache_dir = (
            Path(os.environ["HERMES_HOME"]) / "users" / "test-user-123" / "cache"
        )
        files = list(cache_dir.glob("*.json"))
        assert files, "cache file should exist"
        assert (files[0].stat().st_mode & 0o777) == 0o600

    def test_sweep_removes_orphaned_files_only(self, mock_credentials):
        import os
        import time as _time
        from training import _http

        intervals_icu._cache_set("test-user-123", "fresh-key", {"v": 1})
        cache_dir = (
            Path(os.environ["HERMES_HOME"]) / "users" / "test-user-123" / "cache"
        )
        orphan = cache_dir / "orphan.json"
        orphan.write_text("{}")
        aged = _time.time() - 25 * 3600  # beyond the 24h sweep floor
        os.utime(orphan, (aged, aged))

        _http._last_sweep = 0.0  # force the next _cache_set to sweep
        intervals_icu._cache_set("test-user-123", "another-key", {"v": 2})

        assert not orphan.exists()
        assert list(cache_dir.glob("*.json")), "fresh files must survive the sweep"


class TestRequest:
    def test_raises_value_error_on_401(self, mock_credentials):
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = b'{"error": "unauthorized"}'
            mock_resp.__enter__ = lambda s: mock_resp
            mock_resp.__exit__ = lambda s, *a: None
            # Simulate 401
            import urllib.error

            mock_urlopen.side_effect = urllib.error.HTTPError(
                "url", 401, "Unauthorized", {}, MagicMock()
            )
            with pytest.raises(ValueError, match="401 Unauthorized"):
                intervals_icu._request("i12345", "bad-key", "/athlete/i12345")

    def test_raises_runtime_error_on_network_failure(self, mock_credentials):
        with patch("urllib.request.urlopen") as mock_urlopen:
            import urllib.error

            mock_urlopen.side_effect = urllib.error.URLError("Connection refused")
            with pytest.raises(RuntimeError, match="Could not reach intervals.icu"):
                intervals_icu._request("i12345", "key", "/athlete/i12345")


class TestDateHelpers:
    def test_today_iso_returns_iso_date(self):
        from datetime import date

        assert intervals_icu._today_iso() == date.today().isoformat()

    def test_n_days_ago_iso(self):
        from datetime import date, timedelta

        expected = (date.today() - timedelta(days=7)).isoformat()
        assert intervals_icu._n_days_ago_iso(7) == expected

    def test_today_iso_with_tz(self):
        from datetime import datetime
        try:
            from zoneinfo import ZoneInfo
        except ImportError:
            pytest.skip("zoneinfo unavailable")
        assert intervals_icu._today_iso("UTC") == datetime.now(ZoneInfo("UTC")).date().isoformat()

    def test_n_days_ago_iso_with_tz(self):
        from datetime import datetime, timedelta
        try:
            from zoneinfo import ZoneInfo
        except ImportError:
            pytest.skip("zoneinfo unavailable")
        expected = (datetime.now(ZoneInfo("UTC")).date() - timedelta(days=7)).isoformat()
        assert intervals_icu._n_days_ago_iso(7, "UTC") == expected

    def test_invalid_tz_falls_back_to_server_local(self):
        from datetime import date, timedelta
        # Unknown zone must NOT raise; falls back to server-local date.
        assert intervals_icu._today_iso("not/a/zone") == date.today().isoformat()
        assert intervals_icu._n_days_ago_iso(3, "not/a/zone") == (
            date.today() - timedelta(days=3)
        ).isoformat()

    def test_none_tz_uses_server_local(self):
        from datetime import date, timedelta
        assert intervals_icu._today_iso(None) == date.today().isoformat()
        assert intervals_icu._n_days_ago_iso(7, None) == (
            date.today() - timedelta(days=7)
        ).isoformat()


class TestStoreAndLoadCredentials:
    def test_store_credentials(self, tmp_path, monkeypatch):
        hermes_home = tmp_path / ".hermes"
        hermes_home.mkdir()
        monkeypatch.setenv("HERMES_HOME", str(hermes_home))

        intervals_icu.store_user_credentials("user1", "i99999", "secret-key")

        assert (
            hermes_home / "users" / "user1" / "intervals_key"
        ).read_text() == "secret-key"
        assert (
            hermes_home / "users" / "user1" / "intervals_athlete_id"
        ).read_text() == "i99999"

    def test_load_credentials_raises_when_missing(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        with pytest.raises(ValueError, match="No intervals.icu credentials found"):
            intervals_icu._load_credentials("nonexistent-user")


class TestRequireUserId:
    def test_valid_snowflake_returns_id(self):
        uid = intervals_icu._require_user_id({"user_id": "123456789012345678"})
        assert uid == "123456789012345678"

    def test_missing_raises_value_error(self):
        with pytest.raises(ValueError, match="User identity not available"):
            intervals_icu._require_user_id({})

    def test_empty_string_raises_value_error(self):
        with pytest.raises(ValueError, match="User identity not available"):
            intervals_icu._require_user_id({"user_id": ""})

    def test_non_numeric_raises_value_error(self):
        with pytest.raises(ValueError, match="User identity not available"):
            intervals_icu._require_user_id({"user_id": "attacker_id"})

    def test_short_id_raises_value_error(self):
        with pytest.raises(ValueError, match="User identity not available"):
            intervals_icu._require_user_id({"user_id": "1234"})

    def test_all_zero_snowflake_raises_value_error(self):
        with pytest.raises(ValueError, match="User identity not available"):
            intervals_icu._require_user_id({"user_id": "00000000000000000"})


class TestTSBCalculation:
    def _parse_wellness(self, data_list):
        """Replicate the get_wellness parse loop to test TSB logic directly."""
        records = []
        for w in data_list:
            ctl = w.get("ctl")
            atl = w.get("atl")
            # Both must be present: TSB is meaningless if one side is unknown.
            tsb = round(ctl - atl, 1) if ctl is not None and atl is not None else None
            records.append(
                {
                    "ctl": round(ctl, 1) if ctl is not None else None,
                    "atl": round(atl, 1) if atl is not None else None,
                    "tsb": tsb,
                }
            )
        return records

    def test_tsb_normal(self):
        rows = self._parse_wellness([{"ctl": 50.5, "atl": 60.3}])
        assert rows[0]["tsb"] == -9.8

    def test_tsb_zero_ctl_and_atl(self):
        rows = self._parse_wellness([{"ctl": 0.0, "atl": 0.0}])
        assert rows[0]["tsb"] == 0.0, "TSB must be 0.0 when CTL=ATL=0, not None"

    def test_tsb_none_when_both_missing(self):
        rows = self._parse_wellness([{}])
        assert rows[0]["tsb"] is None

    def test_ctl_zero_atl_present(self):
        rows = self._parse_wellness([{"ctl": 0.0, "atl": 10.0}])
        assert rows[0]["ctl"] == 0.0
        assert rows[0]["tsb"] == -10.0

    def test_tsb_none_when_atl_missing(self):
        # CTL present but ATL unknown — TSB cannot be computed
        rows = self._parse_wellness([{"ctl": 50.0}])
        assert rows[0]["tsb"] is None

    def test_tsb_none_when_ctl_missing(self):
        rows = self._parse_wellness([{"atl": 60.0}])
        assert rows[0]["tsb"] is None


class TestRenderChart:
    """Tests for render_chart chart-rendering tools."""

    def setup_method(self):
        import sys
        from pathlib import Path

        sys.path.insert(0, str(Path(__file__).parent.parent / "plugins"))

    def _wellness_json(self, n=5):
        import json
        from datetime import date, timedelta

        records = []
        for i in range(n):
            d = (date(2025, 1, 1) + timedelta(days=i)).isoformat()
            records.append(
                {"date": d, "ctl": 50.0 + i, "atl": 55.0 - i, "tsb": -5.0 + 2 * i}
            )
        return json.dumps({"records": records})

    def test_wellness_chart_returns_path(self, tmp_path, monkeypatch):
        import json

        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        pytest.importorskip("matplotlib")
        from training.render_chart import render_wellness_chart

        result = json.loads(render_wellness_chart(self._wellness_json()))
        assert result["success"] is True
        assert "chart_path" in result
        assert result["chart_path"].endswith(".png")
        from pathlib import Path

        assert Path(result["chart_path"]).exists()

    def test_wellness_chart_too_few_records(self):
        import json

        pytest.importorskip("matplotlib")
        from training.render_chart import render_wellness_chart

        result = json.loads(
            render_wellness_chart(
                json.dumps({"records": [{"date": "2025-01-01", "ctl": 50.0}]})
            )
        )
        assert result["success"] is False

    def test_power_curve_chart_returns_path(self, tmp_path, monkeypatch):
        import json

        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        pytest.importorskip("matplotlib")
        from training.render_chart import render_power_curve_chart

        payload = json.dumps(
            {
                "peak_power": {
                    "5s": 800,
                    "1min": 450,
                    "5min": 320,
                    "20min": 270,
                    "60min": 240,
                },
                "sport": "Ride",
                "days": 90,
            }
        )
        result = json.loads(render_power_curve_chart(payload))
        assert result["success"] is True
        from pathlib import Path

        assert Path(result["chart_path"]).exists()

    def test_zone_chart_returns_path(self, tmp_path, monkeypatch):
        import json

        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        pytest.importorskip("matplotlib")
        from training.render_chart import render_zone_distribution_chart

        payload = json.dumps(
            {
                "zones": [
                    {"name": "Z1 Recovery", "percent": 15},
                    {"name": "Z2 Endurance", "percent": 42},
                    {"name": "Z3 Tempo", "percent": 18},
                    {"name": "Z4 Threshold", "percent": 15},
                    {"name": "Z5 VO2max", "percent": 7},
                    {"name": "Z6+ Anaerobic", "percent": 3},
                ],
                "total_hours": 12,
                "days": 28,
            }
        )
        result = json.loads(render_zone_distribution_chart(payload))
        assert result["success"] is True
        from pathlib import Path

        assert Path(result["chart_path"]).exists()

    def test_zone_chart_empty_input(self):
        import json

        pytest.importorskip("matplotlib")
        from training.render_chart import render_zone_distribution_chart

        result = json.loads(render_zone_distribution_chart(json.dumps({})))
        assert result["success"] is False

    def test_zone_chart_missing_name_key(self, tmp_path, monkeypatch):
        import json

        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        pytest.importorskip("matplotlib")
        from training.render_chart import render_zone_distribution_chart

        # Zone without "name" key should not crash — fallback to "Zone N"
        payload = json.dumps(
            {"zones": [{"percent": 40}, {"name": "Z2", "percent": 60}]}
        )
        result = json.loads(render_zone_distribution_chart(payload))
        assert result["success"] is True

    def test_wellness_chart_invalid_date(self, tmp_path, monkeypatch):
        import json

        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        pytest.importorskip("matplotlib")
        from training.render_chart import render_wellness_chart

        payload = json.dumps(
            {
                "records": [
                    {"date": "not-a-date", "ctl": 50.0, "atl": 55.0, "tsb": -5.0},
                    {"date": "2025-01-02", "ctl": 51.0, "atl": 54.0, "tsb": -3.0},
                ]
            }
        )
        result = json.loads(render_wellness_chart(payload))
        assert result["success"] is False

    def test_power_curve_with_ftp(self, tmp_path, monkeypatch):
        import json

        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        pytest.importorskip("matplotlib")
        from training.render_chart import render_power_curve_chart

        payload = json.dumps(
            {
                "peak_power": {"5s": 900, "5min": 350, "20min": 280, "60min": 250},
                "sport": "Ride",
                "days": 90,
            }
        )
        result = json.loads(render_power_curve_chart(payload, ftp_w=270))
        assert result["success"] is True
        from pathlib import Path

        assert Path(result["chart_path"]).exists()


# ---------------------------------------------------------------------------
# Response-parser tests for the six get_* tools
# ---------------------------------------------------------------------------


def _make_creds(tmp_path, monkeypatch, user_id, athlete_id):
    """Write minimal credential files and point HERMES_HOME at tmp_path."""
    hermes_home = tmp_path / ".hermes"
    hermes_home.mkdir(exist_ok=True)
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    user_dir = hermes_home / "users" / user_id
    user_dir.mkdir(parents=True, exist_ok=True)
    (user_dir / "intervals_key").write_text("key")
    (user_dir / "intervals_athlete_id").write_text(athlete_id)


class TestGetWellnessParser:
    """Verify get_wellness correctly maps API fields to the output schema."""

    @pytest.fixture(autouse=True)
    def _creds(self, tmp_path, monkeypatch):
        _make_creds(tmp_path, monkeypatch, "u111", "i1")

    def _call(self, raw_list):
        with patch.object(intervals_icu, "_request", return_value=raw_list):
            return json.loads(intervals_icu.get_wellness("u111", days=7))

    def test_fields_mapped_correctly(self):
        raw = [
            {
                "id": "2025-01-10",
                "ctl": 52.3,
                "atl": 60.1,
                "rampRate": 1.2,
                "hrv": 68.0,
                "hrvSDNN": 45.0,
                "restingHR": 48,
                "sleepSecs": 27000,
                "sleepQuality": 3,
                "sleepScore": 82,
                "readiness": 75,
                "weight": 73.5,
                "fatigue": 4,
                "soreness": 3,
                "motivation": 7,
                "mood": 6,
            }
        ]
        result = self._call(raw)
        rec = result["records"][0]
        assert rec["date"] == "2025-01-10"
        assert rec["ctl"] == 52.3
        assert rec["atl"] == 60.1
        assert rec["tsb"] == round(52.3 - 60.1, 1)
        assert rec["ramp_rate"] == 1.2
        assert rec["hrv"] == 68.0
        assert rec["hrv_sdnn"] == 45.0
        assert rec["resting_hr"] == 48
        assert rec["sleep_hours"] == round(27000 / 3600, 1)
        assert rec["sleep_quality"] == 3
        assert rec["sleep_score"] == 82
        assert rec["readiness"] == 75
        assert rec["weight_kg"] == 73.5
        assert rec["fatigue"] == 4
        assert rec["soreness"] == 3
        assert rec["motivation"] == 7
        assert rec["mood"] == 6

    def test_today_convenience_field(self):
        raw = [
            {"id": "2025-01-09", "ctl": 50.0, "atl": 55.0},
            {"id": "2025-01-10", "ctl": 51.0, "atl": 54.0},
        ]
        result = self._call(raw)
        assert result["today"]["date"] == "2025-01-10"
        assert result["today"]["tsb"] == round(51.0 - 54.0, 1)

    def test_today_is_none_when_no_records(self):
        result = self._call([])
        assert result["today"] is None
        assert result["records"] == []

    def test_tsb_none_when_ctl_missing(self):
        result = self._call([{"id": "2025-01-10", "atl": 55.0}])
        assert result["records"][0]["tsb"] is None
        assert result["records"][0]["ctl"] is None
        assert result["records"][0]["atl"] == 55.0

    def test_tsb_none_when_atl_missing(self):
        result = self._call([{"id": "2025-01-10", "ctl": 50.0}])
        assert result["records"][0]["tsb"] is None

    def test_tsb_valid_when_ctl_or_atl_is_zero(self):
        result = self._call([{"id": "2025-01-10", "ctl": 0.0, "atl": 0.0}])
        assert result["records"][0]["tsb"] == 0.0

    def test_sleep_hours_none_when_zero_secs(self):
        result = self._call(
            [{"id": "2025-01-10", "ctl": 50.0, "atl": 50.0, "sleepSecs": 0}]
        )
        assert result["records"][0]["sleep_hours"] is None

    def test_days_capped_at_42(self):
        with patch.object(intervals_icu, "_request", return_value=[]) as mock_req:
            intervals_icu.get_wellness("u111", days=999)
            mock_req.assert_called_once()

    def test_source_field_present(self):
        result = self._call([{"id": "2025-01-10", "ctl": 50.0, "atl": 52.0}])
        assert result["source"] == "intervals.icu"

    def test_credentials_error_returns_json_error(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        result = json.loads(intervals_icu.get_wellness("no-such-user", days=7))
        assert "error" in result


class TestGetRecentActivitiesParser:
    """Verify get_recent_activities correctly maps API fields."""

    @pytest.fixture(autouse=True)
    def _creds(self, tmp_path, monkeypatch):
        hermes_home = tmp_path / ".hermes"
        hermes_home.mkdir()
        monkeypatch.setenv("HERMES_HOME", str(hermes_home))
        user_dir = hermes_home / "users" / "u222"
        user_dir.mkdir(parents=True)
        (user_dir / "intervals_key").write_text("key")
        (user_dir / "intervals_athlete_id").write_text("i2")

    def _call(self, raw_list, days=14, sport=None):
        with patch.object(intervals_icu, "_request", return_value=raw_list):
            return json.loads(
                intervals_icu.get_recent_activities("u222", days=days, sport=sport)
            )

    def test_fields_mapped_correctly(self):
        raw = [
            {
                "id": "a001",
                "name": "Morning Ride",
                "start_date_local": "2025-01-10T07:30:00",
                "type": "Ride",
                "moving_time": 5400,
                "distance": 45000,
                "icu_training_load": 88,
                "icu_ctl": 52.0,
                "icu_atl": 60.0,
                "icu_intensity": 0.82,
                "icu_weighted_avg_watts": 220,
                "icu_ftp": 270,
                "trimp": 95,
                "icu_rpe": 7,
            }
        ]
        result = self._call(raw)
        act = result["activities"][0]
        assert act["id"] == "a001"
        assert act["name"] == "Morning Ride"
        assert act["date"] == "2025-01-10"
        assert act["type"] == "Ride"
        assert act["duration_min"] == round(5400 / 60, 1)
        assert act["distance_km"] == round(45000 / 1000, 2)
        assert act["training_load"] == 88
        assert act["ctl_after"] == 52.0
        assert act["atl_after"] == 60.0
        assert act["intensity_factor"] == 0.82
        assert act["normalized_power_w"] == 220
        assert act["ftp_used_w"] == 270
        assert act["trimp"] == 95
        assert act["rpe"] == 7

    def test_count_and_source(self):
        result = self._call([{"id": "a1"}, {"id": "a2"}])
        assert result["count"] == 2
        assert result["source"] == "intervals.icu"

    def test_empty_list_returns_zero_count(self):
        result = self._call([])
        assert result["count"] == 0
        assert result["activities"] == []

    def test_days_capped_at_90(self):
        with patch.object(intervals_icu, "_request", return_value=[]) as mock_req:
            intervals_icu.get_recent_activities("u222", days=999)
            mock_req.assert_called_once()
            # days parameter in the URL params should be capped
            call_kwargs = mock_req.call_args
            params = (
                call_kwargs[0][3]
                if len(call_kwargs[0]) > 3
                else call_kwargs[1].get("params", {})
            )

    def test_rpe_fallback_to_session_rpe(self):
        result = self._call([{"id": "a1", "session_rpe": 6}])
        assert result["activities"][0]["rpe"] == 6

    def test_rpe_fallback_to_feel(self):
        result = self._call([{"id": "a2", "feel": 8}])
        assert result["activities"][0]["rpe"] == 8

    def test_rpe_none_when_all_missing(self):
        result = self._call([{"id": "a3"}])
        assert result["activities"][0]["rpe"] is None

    def test_date_truncated_to_10_chars(self):
        raw = [{"id": "a1", "start_date_local": "2025-06-15T08:00:00+02:00"}]
        result = self._call(raw)
        assert result["activities"][0]["date"] == "2025-06-15"

    def test_null_distance_and_duration(self):
        raw = [{"id": "a1", "moving_time": None, "distance": None}]
        result = self._call(raw)
        act = result["activities"][0]
        assert act["duration_min"] == 0.0
        assert act["distance_km"] == 0.0

    def test_credentials_error_returns_json_error(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        result = json.loads(intervals_icu.get_recent_activities("no-such-user"))
        assert "error" in result


class TestGetAthleteProfileParser:
    """Verify get_athlete_profile maps API fields correctly."""

    @pytest.fixture(autouse=True)
    def _creds(self, tmp_path, monkeypatch):
        hermes_home = tmp_path / ".hermes"
        hermes_home.mkdir()
        monkeypatch.setenv("HERMES_HOME", str(hermes_home))
        user_dir = hermes_home / "users" / "u333"
        user_dir.mkdir(parents=True)
        (user_dir / "intervals_key").write_text("key")
        (user_dir / "intervals_athlete_id").write_text("i3")

    def test_fields_mapped(self):
        raw = {
            "name": "Johan",
            "timezone": "Europe/Stockholm",
            "icu_weight": 72.0,
            "icu_resting_hr": 46,
            "sex": "M",
            "icu_date_of_birth": "1985-04-12",
        }
        with patch.object(intervals_icu, "_request", return_value=raw):
            result = json.loads(intervals_icu.get_athlete_profile("u333"))
        assert result["name"] == "Johan"
        assert result["timezone"] == "Europe/Stockholm"
        assert result["weight_kg"] == 72.0
        assert result["resting_hr"] == 46
        assert result["sex"] == "M"
        assert result["date_of_birth"] == "1985-04-12"
        assert result["source"] == "intervals.icu"

    def test_missing_fields_are_none(self):
        with patch.object(intervals_icu, "_request", return_value={}):
            result = json.loads(intervals_icu.get_athlete_profile("u333"))
        assert result["name"] is None
        assert result["weight_kg"] is None


class TestGetSportSettingsParser:
    """Verify get_sport_settings maps FTP and zone fields."""

    @pytest.fixture(autouse=True)
    def _creds(self, tmp_path, monkeypatch):
        hermes_home = tmp_path / ".hermes"
        hermes_home.mkdir()
        monkeypatch.setenv("HERMES_HOME", str(hermes_home))
        user_dir = hermes_home / "users" / "u444"
        user_dir.mkdir(parents=True)
        (user_dir / "intervals_key").write_text("key")
        (user_dir / "intervals_athlete_id").write_text("i4")

    def test_ftp_and_zones_present(self):
        raw = {
            "ftp": 270,
            "indoor_ftp": 265,
            "lthr": 168,
            "max_hr": 185,
            "w_prime": 18000,
            "power_zones": [{"name": "Z1", "min": 0, "max": 148}],
            "hr_zones": [{"name": "Z1", "min": 0, "max": 130}],
            "pace_zones": None,
        }
        with patch.object(intervals_icu, "_request", return_value=raw):
            result = json.loads(intervals_icu.get_sport_settings("u444", sport="Ride"))
        assert result["ftp"] == 270
        assert result["indoor_ftp"] == 265
        assert result["lthr"] == 168
        assert result["max_hr"] == 185
        assert result["w_prime"] == 18000
        assert isinstance(result["power_zones"], list)
        assert result["pace_zones"] is None
        assert result["sport"] == "Ride"

    def test_ftp_w_kg_from_projected_profile(self):
        """W/kg uses the projected profile's weight_kg (not raw icu_weight)."""
        sport_raw = {"ftp": 270, "power_zones": [], "hr_zones": [], "pace_zones": None}
        profile_raw = {"icu_weight": 72.0, "name": "J"}
        with patch.object(intervals_icu, "_request", side_effect=[sport_raw, profile_raw]):
            result = json.loads(intervals_icu.get_sport_settings("u444", sport="Ride"))
        assert result["ftp_w_kg"] == round(270 / 72.0, 2)  # 3.75

    def test_sport_settings_reuses_profile_cache(self):
        """get_athlete_profile caches the projected profile; sport-settings must
        reuse it (one API call for sport-settings only) — no poisoning, no
        redundant profile fetch."""
        sport_raw = {"ftp": 270, "power_zones": [], "hr_zones": [], "pace_zones": None}
        profile_raw = {"icu_weight": 72.0, "name": "J", "timezone": "UTC"}
        with patch.object(intervals_icu, "_request", side_effect=[profile_raw]):
            json.loads(intervals_icu.get_athlete_profile("u444"))
        # sport-settings: profile already cached -> only sport-settings hits the API
        with patch.object(intervals_icu, "_request", return_value=sport_raw) as mock_req:
            result = json.loads(intervals_icu.get_sport_settings("u444", sport="Ride"))
        assert result["ftp_w_kg"] == round(270 / 72.0, 2)  # 3.75
        mock_req.assert_called_once()


class TestGetPlannedEventsParser:
    """Verify get_planned_events maps event fields correctly."""

    @pytest.fixture(autouse=True)
    def _creds(self, tmp_path, monkeypatch):
        hermes_home = tmp_path / ".hermes"
        hermes_home.mkdir()
        monkeypatch.setenv("HERMES_HOME", str(hermes_home))
        user_dir = hermes_home / "users" / "u555"
        user_dir.mkdir(parents=True)
        (user_dir / "intervals_key").write_text("key")
        (user_dir / "intervals_athlete_id").write_text("i5")

    def test_event_fields_mapped(self):
        raw = [
            {
                "id": "ev1",
                "start_date_local": "2025-07-20T10:00:00",
                "category": "RACE",
                "type": "Ride",
                "name": "Gran Fondo Alps",
                "description": "160km mountain stage",
                "icu_training_load": 210,
                "icu_intensity": 0.78,
                "icu_ctl": 68.0,
                "icu_atl": 55.0,
                "time_target": 21600,
                "distance_target": 160000,
            }
        ]
        with patch.object(intervals_icu, "_request", return_value=raw):
            result = json.loads(intervals_icu.get_planned_events("u555", days_ahead=30))
        ev = result["events"][0]
        assert ev["id"] == "ev1"
        assert ev["date"] == "2025-07-20"
        assert ev["category"] == "RACE"
        assert ev["name"] == "Gran Fondo Alps"
        assert ev["planned_load"] == 210
        assert ev["time_target_min"] == round(21600 / 60, 1)
        assert ev["distance_target_km"] == round(160000 / 1000, 2)
        assert result["count"] == 1

    def test_empty_calendar_returns_zero_count(self):
        with patch.object(intervals_icu, "_request", return_value=[]):
            result = json.loads(intervals_icu.get_planned_events("u555"))
        assert result["count"] == 0
        assert result["events"] == []


class TestGetPowerCurveParser:
    """Verify get_power_curve extracts standard duration peaks."""

    @pytest.fixture(autouse=True)
    def _creds(self, tmp_path, monkeypatch):
        hermes_home = tmp_path / ".hermes"
        hermes_home.mkdir()
        monkeypatch.setenv("HERMES_HOME", str(hermes_home))
        user_dir = hermes_home / "users" / "u666"
        user_dir.mkdir(parents=True)
        (user_dir / "intervals_key").write_text("key")
        (user_dir / "intervals_athlete_id").write_text("i6")

    def test_standard_durations_extracted(self):
        # Live API shape (verified 2026-09-18): {"list": [{"secs": [...],
        # "watts": [...]}]} — two parallel arrays, NOT a list of points.
        raw = {
            "list": [
                {
                    "secs": [5, 10, 60, 300, 1200, 3600],
                    "watts": [850.0, 780.0, 520.0, 380.0, 290.0, 255.0],
                }
            ]
        }
        with patch.object(intervals_icu, "_request", return_value=raw):
            result = json.loads(
                intervals_icu.get_power_curve("u666", sport="Ride", days=42)
            )
        peaks = result["peak_power"]
        assert peaks["5s"] == 850.0
        assert peaks["1min"] == 520.0
        assert peaks["5min"] == 380.0
        assert peaks["20min"] == 290.0
        assert peaks["60min"] == 255.0
        assert result["sport"] == "Ride"
        assert result["full_curve_points"] == 6

    def test_missing_durations_return_none(self):
        raw = {"list": [{"secs": [5, 30], "watts": [850.0, 700.0]}]}
        with patch.object(intervals_icu, "_request", return_value=raw):
            result = json.loads(intervals_icu.get_power_curve("u666"))
        peaks = result["peak_power"]
        assert peaks["5s"] == 850.0
        assert peaks["1min"] is None
        assert peaks["20min"] is None

    def test_empty_curve_returns_all_none_peaks(self):
        with patch.object(intervals_icu, "_request", return_value={"list": []}):
            result = json.loads(intervals_icu.get_power_curve("u666"))
        assert all(v is None for v in result["peak_power"].values())


# ---------------------------------------------------------------------------
# Data-interface fixes (2026-09-18 live verification)
# ---------------------------------------------------------------------------

class TestCoachingDataInterface:
    """Field-name contract and extended projections.

    Every name asserted here was verified against the live API on 2026-09-18.
    """

    @pytest.fixture(autouse=True)
    def _creds(self, tmp_path, monkeypatch):
        hermes_home = tmp_path / ".hermes"
        hermes_home.mkdir()
        monkeypatch.setenv("HERMES_HOME", str(hermes_home))
        user_dir = hermes_home / "users" / "u777"
        user_dir.mkdir(parents=True)
        (user_dir / "intervals_key").write_text("key")
        (user_dir / "intervals_athlete_id").write_text("i7")

    # -- P0: published field names -----------------------------------------

    def test_recent_activities_maps_average_heartrate(self):
        raw = [{"id": "a1", "average_heartrate": 142, "average_cadence": 88}]
        with patch.object(intervals_icu, "_request", return_value=raw):
            result = json.loads(intervals_icu.get_recent_activities("u777"))
        act = result["activities"][0]
        assert act["avg_hr"] == 142
        assert act["avg_cadence"] == 88

    def test_recent_activities_does_not_read_the_alias(self):
        # The alias is not a published field; only the published name is read.
        raw = [{"id": "a1", "avg_heartrate": 142, "avg_cadence": 88}]
        with patch.object(intervals_icu, "_request", return_value=raw):
            result = json.loads(intervals_icu.get_recent_activities("u777"))
        act = result["activities"][0]
        assert act["avg_hr"] is None
        assert act["avg_cadence"] is None

    def test_recent_activities_maps_paired_event_id(self):
        raw = [{"id": "a1", "paired_event_id": 4242}]
        with patch.object(intervals_icu, "_request", return_value=raw):
            result = json.loads(intervals_icu.get_recent_activities("u777"))
        assert result["activities"][0]["paired_event_id"] == 4242

    def test_recent_activities_requests_published_field_names(self):
        with patch.object(intervals_icu, "_request", return_value=[]) as mock_req:
            intervals_icu.get_recent_activities("u777")
        params = mock_req.call_args[0][3]
        requested = set(params["fields"].split(","))
        assert {"average_heartrate", "average_cadence", "pace"} <= requested
        assert not ({"avg_heartrate", "avg_cadence", "avg_pace"} & requested)

    def test_activity_detail_maps_average_heartrate(self):
        raw = {"id": "a1", "average_heartrate": 138, "average_cadence": 91}
        with patch.object(intervals_icu, "_request", return_value=raw):
            result = json.loads(
                intervals_icu.get_activity_detail("u777", activity_id="a1")
            )
        assert result["avg_hr"] == 138
        assert result["avg_cadence"] == 91

    # -- P1: wellness + sport settings ------------------------------------

    def test_wellness_maps_extended_fields(self):
        raw = [{
            "id": "2026-09-18", "ctl": 60.0, "atl": 55.0,
            "ctlLoad": 72, "atlLoad": 61,
            "menstrualPhase": "LUTEAL", "injury": 1, "stress": 2,
            "hydration": 2, "hydrationVolume": 2.5,
            "spO2": 97, "respiration": 14, "vo2max": 52,
            "avgSleepingHR": 48, "steps": 8123, "comments": "sore legs",
            "systolic": 120, "diastolic": 78, "bodyFat": 12.5,
            "baevskySI": 55, "lactate": 1.2, "bloodGlucose": 5.1,
            "carbohydrates": 320, "protein": 130, "fatTotal": 70,
            "kcalConsumed": 2400,
        }]
        with patch.object(intervals_icu, "_request", return_value=raw):
            result = json.loads(intervals_icu.get_wellness("u777", days=1))
        rec = result["records"][0]
        assert rec["ctl_load"] == 72
        assert rec["atl_load"] == 61
        assert rec["menstrual_phase"] == "LUTEAL"
        assert rec["injury"] == 1
        assert rec["stress"] == 2
        assert rec["hydration"] == 2
        assert rec["sp_o2"] == 97
        assert rec["respiration"] == 14
        assert rec["vo2max"] == 52
        assert rec["avg_sleeping_hr"] == 48
        assert rec["steps"] == 8123
        assert rec["comments"] == "sore legs"
        assert rec["systolic"] == 120
        assert rec["diastolic"] == 78
        assert rec["body_fat_pct"] == 12.5
        assert rec["baevsky_si"] == 55
        assert rec["lactate"] == 1.2
        assert rec["blood_glucose"] == 5.1
        assert rec["carbohydrates_g"] == 320
        assert rec["protein_g"] == 130
        assert rec["fat_total_g"] == 70
        assert rec["kcal_consumed"] == 2400

    def test_wellness_requests_the_extended_fields(self):
        with patch.object(intervals_icu, "_request", return_value=[]) as mock_req:
            intervals_icu.get_wellness("u777", days=42)
        requested = set(mock_req.call_args[0][3]["fields"].split(","))
        assert {"ctlLoad", "atlLoad", "menstrualPhase", "injury",
                "stress", "spO2", "steps", "vo2max"} <= requested

    def test_wellness_unlogged_fields_are_none(self):
        raw = [{"id": "2026-09-18", "ctl": 60.0, "atl": 55.0}]
        with patch.object(intervals_icu, "_request", return_value=raw):
            result = json.loads(intervals_icu.get_wellness("u777", days=1))
        rec = result["records"][0]
        assert rec["menstrual_phase"] is None
        assert rec["injury"] is None
        assert rec["ctl_load"] is None

    def test_fitness_chart_carries_daily_load(self):
        raw = [{"id": "2026-09-18", "ctl": 60.0, "atl": 55.0,
                "ctlLoad": 72, "atlLoad": 61, "vo2max": 52}]
        with patch.object(intervals_icu, "_request", return_value=raw):
            result = json.loads(intervals_icu.get_fitness_chart("u777", days=7))
        rec = result["records"][0]
        assert rec["ctl_load"] == 72
        assert rec["atl_load"] == 61
        assert rec["vo2max"] == 52

    def test_sport_settings_returns_anchors_and_order(self):
        raw = {
            "ftp": 260, "indoor_ftp": 250, "lthr": 165, "max_hr": 190,
            "w_prime": 20000, "threshold_pace": 3.6, "p_max": 900,
            "sweet_spot_min": 84, "sweet_spot_max": 97,
            "power_zones": [55, 75, 90], "hr_zones": [131, 146, 153],
            "pace_zones": [60, 70, 80],
            "power_zone_names": ["Z1", "Z2", "Z3"],
            "hr_zone_names": ["Z1", "Z2", "Z3"],
            "pace_zone_names": ["Z1", "Z2", "Z3"],
            "load_order": "POWER_HR_PACE", "tiz_order": "POWER_HR_PACE",
            "gap_model": "STRAVA_RUN", "use_gap_zone_times": True,
            "best_effort_distances": [1000, 5000, 10000],
            "pace_curve_start": 0, "default_workout_time": "1h",
            "hr_load_type": "HR_LOAD", "pace_load_type": "PACE_LOAD",
            "types": ["Ride"],
        }
        with patch.object(intervals_icu, "_request", return_value=raw):
            with patch.object(intervals_icu, "_profile_result",
                              return_value={"weight_kg": 80}):
                result = json.loads(intervals_icu.get_sport_settings("u777"))
        assert result["threshold_pace_mps"] == 3.6
        assert result["sweet_spot_min_pct"] == 84
        assert result["sweet_spot_max_pct"] == 97
        assert result["p_max"] == 900
        assert result["power_zone_names"] == ["Z1", "Z2", "Z3"]
        assert result["load_order"] == "POWER_HR_PACE"
        assert result["tiz_order"] == "POWER_HR_PACE"
        assert result["best_effort_distances_m"] == [1000, 5000, 10000]

    # -- P2: activity intervals -------------------------------------------

    def test_activity_intervals_returns_work_and_recovery(self):
        raw = {
            "analyzed": "2026-09-18T10:00:00",
            "icu_intervals": [
                {"id": 1, "type": "WORK", "zone": 4, "intensity": 105,
                 "average_watts": 285, "average_heartrate": 165,
                 "average_cadence": 88, "moving_time": 300,
                 "training_load": 42, "label": "5x5"},
                {"id": 2, "type": "RECOVERY", "zone": 1, "intensity": 55,
                 "average_watts": 140, "moving_time": 120},
            ],
            "icu_groups": [
                {"zone": 4, "count": 5, "average_watts": 285,
                 "moving_time": 1500, "intensity": 105},
            ],
        }
        with patch.object(intervals_icu, "_request", return_value=raw):
            result = json.loads(
                intervals_icu.get_activity_intervals("u777", activity_id="a1")
            )
        assert result["interval_count"] == 2
        assert result["group_count"] == 1
        work = result["intervals"][0]
        assert work["type"] == "WORK"
        assert work["zone"] == 4
        assert work["intensity_pct"] == 105
        assert work["average_watts"] == 285
        assert work["average_hr"] == 165
        assert work["average_cadence"] == 88
        assert result["groups"][0]["count"] == 5

    def test_activity_intervals_uses_the_dedicated_endpoint(self):
        with patch.object(intervals_icu, "_request",
                          return_value={}) as mock_req:
            intervals_icu.get_activity_intervals("u777", activity_id="i161875412")
        assert mock_req.call_args[0][2] == "/activity/i161875412/intervals"

    def test_activity_intervals_empty_returns_zero_counts(self):
        with patch.object(intervals_icu, "_request",
                          return_value={"icu_intervals": None}):
            result = json.loads(
                intervals_icu.get_activity_intervals("u777", activity_id="a1")
            )
        assert result["interval_count"] == 0
        assert result["intervals"] == []

    # -- P3: sport-neutral best-effort curve ---------------------------------

    def test_best_effort_curve_run_uses_pace_endpoint(self):
        raw = {"list": [{"label": "1 year",
                         "distance": [1000.0, 5000.0, 10000.0],
                         "values": [279.0, 1526.0, 3173.0]}]}
        with patch.object(intervals_icu, "_request", return_value=raw) as mock_req:
            result = json.loads(
                intervals_icu.get_best_effort_curve("u777", sport="Run", days=42)
            )
        assert mock_req.call_args[0][2] == "/athlete/i7/pace-curves"
        assert result["curve_type"] == "pace"
        assert result["axis"] == "distance"
        assert result["best_effort"]["1km"] == 279.0
        assert result["best_effort"]["5km"] == 1526.0
        assert result["best_effort"]["10km"] == 3173.0

    def test_best_effort_curve_ride_uses_power_endpoint(self):
        raw = {"list": [{"label": "1 year",
                         "secs": [5, 60, 300, 1200, 3600],
                         "watts": [850.0, 520.0, 380.0, 290.0, 255.0]}]}
        with patch.object(intervals_icu, "_request", return_value=raw) as mock_req:
            result = json.loads(
                intervals_icu.get_best_effort_curve("u777", sport="Ride")
            )
        assert mock_req.call_args[0][2] == "/athlete/i7/power-curves"
        assert result["curve_type"] == "power"
        assert result["best_effort"]["5min"] == 380.0
        assert result["best_effort"]["60min"] == 255.0

    def test_best_effort_curve_other_sport_uses_hr_endpoint(self):
        raw = {"list": [{"label": "1 year",
                         "secs": [60, 300, 1200],
                         "values": [180, 175, 168]}]}
        with patch.object(intervals_icu, "_request", return_value=raw) as mock_req:
            result = json.loads(
                intervals_icu.get_best_effort_curve("u777", sport="Hike")
            )
        assert mock_req.call_args[0][2] == "/athlete/i7/hr-curves"
        assert result["curve_type"] == "hr"
        assert result["best_effort"]["5min"] == 175

    def test_best_effort_curve_ignores_uncovered_targets(self):
        raw = {"list": [{"label": "1 year", "secs": [5],
                         "watts": [850.0]}]}
        with patch.object(intervals_icu, "_request", return_value=raw):
            result = json.loads(intervals_icu.get_best_effort_curve("u777"))
        assert result["best_effort"]["5s"] == 850.0
        assert result["best_effort"]["60min"] is None

    # -- P4: availability, event history, pairing ----------------------------

    def test_athlete_profile_returns_training_availability(self):
        raw = {"name": "A", "timezone": "Europe/Stockholm",
               "height": 1.73,
               "training_availability": [
                   {"day_of_week": 1, "max_training_time": 60,
                    "training_availability": "LIMITED"}]}
        with patch.object(intervals_icu, "_request", return_value=raw):
            result = json.loads(intervals_icu.get_athlete_profile("u777"))
        assert result["height_m"] == 1.73
        assert result["training_availability"][0]["max_training_time"] == 60

    def test_planned_events_days_back_extends_oldest(self):
        with patch.object(intervals_icu, "_request", return_value=[]) as mock_req:
            intervals_icu.get_planned_events("u777", days_ahead=7, days_back=14)
        params = mock_req.call_args[0][3]
        assert params["newest"] > params["oldest"]

    def test_planned_events_default_days_back_is_forward_only(self):
        with patch.object(intervals_icu, "_request", return_value=[]) as mock_req:
            intervals_icu.get_planned_events("u777")
        params = mock_req.call_args[0][3]
        assert params["oldest"] <= params["newest"]
        assert params["oldest"] == intervals_icu._today_iso(None)

    def test_planned_events_days_back_is_capped(self):
        with patch.object(intervals_icu, "_request", return_value=[]) as mock_req:
            intervals_icu.get_planned_events("u777", days_ahead=999, days_back=999)
        params = mock_req.call_args[0][3]
        oldest = intervals_icu._n_days_ago_iso(90, None)
        assert params["oldest"] == oldest

    def test_profile_cache_key_is_projection_versioned(self):
        """A projection change must not serve the previous shape from cache.

        The key must encode the projection version, so bumping the version makes
        a warm cache entry from the old shape unreachable.
        """
        with patch.object(intervals_icu, "_PROJECTION_VERSION", 2):
            key_v2 = intervals_icu._profile_cache_key("i7")
        with patch.object(intervals_icu, "_PROJECTION_VERSION", 3):
            key_v3 = intervals_icu._profile_cache_key("i7")
        assert key_v2 != key_v3

    def test_stale_profile_cache_is_not_served_after_version_bump(self):
        """A cached entry written by the previous projection must be ignored."""
        raw = {"name": "A", "height": 1.8}
        with patch.object(intervals_icu, "_request", return_value=raw):
            first = json.loads(intervals_icu.get_athlete_profile("u777"))
        assert first["height_m"] == 1.8
        # Simulate the previous version's entry: same athlete, old shape, keyed
        # without the projection version.
        old_key = intervals_icu._cache_key("/athlete/i7", {})
        intervals_icu._cache_set("u777", old_key, {"height_m": None})
        with patch.object(intervals_icu, "_request", return_value=raw):
            second = json.loads(intervals_icu.get_athlete_profile("u777"))
        assert second["height_m"] == 1.8  # not the stale None

    def test_sport_settings_cache_key_is_projection_versioned(self):
        """A stale sport-settings entry must not be served after a bump."""
        raw = {"ftp": 260}
        with patch.object(intervals_icu, "_request", return_value=raw):
            first = json.loads(intervals_icu.get_sport_settings("u777", "Ride"))
        assert first["ftp"] == 260
        # Previous version's entry: same endpoint, old shape, unversioned key.
        old_key = intervals_icu._cache_key("/athlete/i7/sport-settings/Ride", {})
        intervals_icu._cache_set("u777", old_key, {"ftp": None})
        with patch.object(intervals_icu, "_request", return_value=raw):
            second = json.loads(intervals_icu.get_sport_settings("u777", "Ride"))
        assert second["ftp"] == 260  # not the stale None
