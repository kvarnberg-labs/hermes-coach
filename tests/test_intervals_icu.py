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


class TestStoreAndLoadCredentials:
    def test_store_credentials(self, tmp_path, monkeypatch):
        hermes_home = tmp_path / ".hermes"
        hermes_home.mkdir()
        monkeypatch.setenv("HERMES_HOME", str(hermes_home))

        intervals_icu.store_user_credentials("user1", "i99999", "secret-key")

        assert (hermes_home / "users" / "user1" / "intervals_key").read_text() == "secret-key"
        assert (hermes_home / "users" / "user1" / "intervals_athlete_id").read_text() == "i99999"

    def test_load_credentials_raises_when_missing(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        with pytest.raises(ValueError, match="No intervals.icu credentials found"):
            intervals_icu._load_credentials("nonexistent-user")


class TestRequireUserId:
    def test_valid_snowflake_returns_id(self):
        uid = intervals_icu._require_user_id({"user_id": "123456789012345678"})
        assert uid == "123456789012345678"

    def test_missing_raises(self):
        with pytest.raises(ValueError, match="User identity check failed"):
            intervals_icu._require_user_id({})

    def test_empty_string_raises(self):
        with pytest.raises(ValueError, match="User identity check failed"):
            intervals_icu._require_user_id({"user_id": ""})

    def test_non_numeric_raises(self):
        with pytest.raises(ValueError, match="User identity check failed"):
            intervals_icu._require_user_id({"user_id": "attacker_id"})

    def test_short_id_raises(self):
        with pytest.raises(ValueError, match="User identity check failed"):
            intervals_icu._require_user_id({"user_id": "1234"})

    def test_all_zero_snowflake_raises(self):
        # All-zero IDs are not valid Discord snowflakes (epoch would be 0, pre-Discord)
        with pytest.raises(ValueError, match="User identity check failed"):
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
            records.append({
                "ctl": round(ctl, 1) if ctl is not None else None,
                "atl": round(atl, 1) if atl is not None else None,
                "tsb": tsb,
            })
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
            records.append({"date": d, "ctl": 50.0 + i, "atl": 55.0 - i, "tsb": -5.0 + 2 * i})
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
        result = json.loads(render_wellness_chart(json.dumps({"records": [{"date": "2025-01-01", "ctl": 50.0}]})))
        assert result["success"] is False

    def test_power_curve_chart_returns_path(self, tmp_path, monkeypatch):
        import json
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        pytest.importorskip("matplotlib")
        from training.render_chart import render_power_curve_chart
        payload = json.dumps({"peak_power": {"5s": 800, "1min": 450, "5min": 320, "20min": 270, "60min": 240}, "sport": "Ride", "days": 90})
        result = json.loads(render_power_curve_chart(payload))
        assert result["success"] is True
        from pathlib import Path
        assert Path(result["chart_path"]).exists()

    def test_zone_chart_returns_path(self, tmp_path, monkeypatch):
        import json
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        pytest.importorskip("matplotlib")
        from training.render_chart import render_zone_distribution_chart
        payload = json.dumps({"zones": [
            {"name": "Z1 Recovery", "percent": 15},
            {"name": "Z2 Endurance", "percent": 42},
            {"name": "Z3 Tempo", "percent": 18},
            {"name": "Z4 Threshold", "percent": 15},
            {"name": "Z5 VO2max", "percent": 7},
            {"name": "Z6+ Anaerobic", "percent": 3},
        ], "total_hours": 12, "days": 28})
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
        payload = json.dumps({"zones": [{"percent": 40}, {"name": "Z2", "percent": 60}]})
        result = json.loads(render_zone_distribution_chart(payload))
        assert result["success"] is True

    def test_wellness_chart_invalid_date(self, tmp_path, monkeypatch):
        import json
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        pytest.importorskip("matplotlib")
        from training.render_chart import render_wellness_chart
        payload = json.dumps({"records": [
            {"date": "not-a-date", "ctl": 50.0, "atl": 55.0, "tsb": -5.0},
            {"date": "2025-01-02", "ctl": 51.0, "atl": 54.0, "tsb": -3.0},
        ]})
        result = json.loads(render_wellness_chart(payload))
        assert result["success"] is False

    def test_power_curve_with_ftp(self, tmp_path, monkeypatch):
        import json
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        pytest.importorskip("matplotlib")
        from training.render_chart import render_power_curve_chart
        payload = json.dumps({"peak_power": {"5s": 900, "5min": 350, "20min": 280, "60min": 250}, "sport": "Ride", "days": 90})
        result = json.loads(render_power_curve_chart(payload, ftp_w=270))
        assert result["success"] is True
        from pathlib import Path
        assert Path(result["chart_path"]).exists()
