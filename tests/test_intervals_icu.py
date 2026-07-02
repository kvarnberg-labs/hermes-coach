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
        # Too short to be a Discord snowflake (< 17 digits)
        with pytest.raises(ValueError, match="User identity check failed"):
            intervals_icu._require_user_id({"user_id": "1234"})


class TestTSBCalculation:
    def _parse_wellness(self, data_list):
        """Helper: run get_wellness parse logic against synthetic data."""
        # We replicate the parse loop from get_wellness to test it directly.
        import json
        records = []
        for w in data_list:
            ctl = w.get("ctl")
            atl = w.get("atl")
            tsb = round((ctl or 0.0) - (atl or 0.0), 1) if ctl is not None or atl is not None else None
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
        # Athlete with no training history — both 0.0 is valid, TSB should be 0.0
        rows = self._parse_wellness([{"ctl": 0.0, "atl": 0.0}])
        assert rows[0]["tsb"] == 0.0, "TSB must be 0.0 when CTL=ATL=0, not None"

    def test_tsb_none_when_both_missing(self):
        rows = self._parse_wellness([{}])
        assert rows[0]["tsb"] is None

    def test_ctl_zero_produces_non_null(self):
        rows = self._parse_wellness([{"ctl": 0.0, "atl": 10.0}])
        assert rows[0]["ctl"] == 0.0
        assert rows[0]["tsb"] == -10.0
