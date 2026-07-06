"""Tests for the training plugin — onboarding flow."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "plugins"))

from training.onboarding import coach_onboard


class TestCoachOnboard:
    """_request and store_user_credentials are imported inside coach_onboard(),
    so we patch them on the modules where they LIVE (intervals_icu), not on
    the onboarding module's namespace."""

    def test_returns_error_on_empty_api_key(self):
        result = json.loads(coach_onboard("user123", "i12345", ""))
        assert not result["success"]
        assert "empty" in result["error"]

    def test_normalizes_athlete_id_from_url(self):
        mock_profile = {"name": "Test Athlete", "sportSettings": []}
        with patch("training.intervals_icu._request", return_value=mock_profile):
            with patch("training.intervals_icu.store_user_credentials") as mock_store:
                result = json.loads(
                    coach_onboard("user123", "https://intervals.icu/athlete/i99999", "mykey")
                )
                assert result["success"]
                mock_store.assert_called_once_with("user123", "i99999", "mykey", "")

    def test_normalizes_athlete_id_without_i_prefix(self):
        mock_profile = {"name": "Test Athlete", "sportSettings": []}
        with patch("training.intervals_icu._request", return_value=mock_profile):
            with patch("training.intervals_icu.store_user_credentials") as mock_store:
                result = json.loads(
                    coach_onboard("user123", "99999", "mykey")
                )
                assert result["success"]
                mock_store.assert_called_once_with("user123", "i99999", "mykey", "")

    def test_returns_error_on_401(self):
        with patch("training.intervals_icu._request", side_effect=ValueError("401 Unauthorized")):
            result = json.loads(coach_onboard("user123", "i12345", "bad-key"))
            assert not result["success"]
            assert "hint" in result

    def test_returns_error_on_network_failure(self):
        with patch("training.intervals_icu._request", side_effect=RuntimeError("Connection refused")):
            result = json.loads(coach_onboard("user123", "i12345", "mykey"))
            assert not result["success"]

    def test_includes_ftp_in_success_message(self):
        mock_profile = {
            "name": "Pro Cyclist",
            "sportSettings": [{"type": "Ride", "ftp": 320}],
        }
        with patch("training.intervals_icu._request", return_value=mock_profile):
            with patch("training.intervals_icu.store_user_credentials"):
                result = json.loads(coach_onboard("user123", "i12345", "mykey"))
                assert result["success"]
                assert "320" in result["message"]
                assert "Cycling FTP" in result["message"]

    def test_handles_missing_name(self):
        mock_profile = {"sportSettings": []}
        with patch("training.intervals_icu._request", return_value=mock_profile):
            with patch("training.intervals_icu.store_user_credentials"):
                result = json.loads(coach_onboard("user123", "i12345", "mykey"))
                assert result["success"]
                assert "Athlete" in result["message"]
