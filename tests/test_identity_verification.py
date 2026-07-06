"""Tests for credential identity verification.

Verifies that:
  1. store_user_credentials stores the athlete_name file when a name is given
  2. _load_verified_name reads the stored name correctly
  3. verify_athlete_identity detects missing name (no onboarding)
  4. verify_athlete_identity returns verified=True when credentials match
  5. get_athlete_profile includes athlete_name in the response
"""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "plugins"))
from training.intervals_icu import (
    store_user_credentials,
    _load_verified_name,
    verify_athlete_identity,
    get_athlete_profile,
)


def _temp_user_dir():
    """Create a temporary user directory for isolated tests."""
    return Path(tempfile.mkdtemp())


def test_store_and_load_athlete_name():
    """store_user_credentials saves the athlete_name file when given."""
    user_dir = _temp_user_dir()

    with patch("training.intervals_icu._user_dir", return_value=user_dir):
        store_user_credentials(
            "test_user", "i12345", "dummy_key", athlete_name="Joey"
        )

    name_file = user_dir / "intervals_athlete_name"
    assert name_file.exists(), "athlete_name file should be created"
    assert name_file.read_text().strip() == "Joey"

    # Clean up
    for f in user_dir.glob("*"):
        f.unlink()
    user_dir.rmdir()


def test_load_verified_name_returns_none_when_missing():
    """_load_verified_name returns None when no name file exists."""
    user_dir = _temp_user_dir()

    with patch("training.intervals_icu._user_dir", return_value=user_dir):
        result = _load_verified_name("no_name_user")

    assert result is None
    user_dir.rmdir()


def test_load_verified_name_returns_none_for_empty_file():
    """_load_verified_name returns None when name file is empty."""
    user_dir = _temp_user_dir()
    name_file = user_dir / "intervals_athlete_name"
    name_file.write_text("   \n")

    with patch("training.intervals_icu._user_dir", return_value=user_dir):
        result = _load_verified_name("empty_name_user")

    assert result is None
    name_file.unlink()
    user_dir.rmdir()


def test_verify_athlete_identity_no_stored_name():
    """verify_athlete_identity returns verified=False when no name was stored."""
    user_dir = _temp_user_dir()

    with patch("training.intervals_icu._user_dir", return_value=user_dir):
        # Store credentials without a name (simulates manual placement)
        store_user_credentials("discord_dm", "i494629", "test_key", athlete_name="")

        mock_profile = {"id": "i494629", "name": "Millberg", "timezone": "Europe/Berlin"}

        with patch("training.intervals_icu._request", return_value=mock_profile):
            result = json.loads(verify_athlete_identity("discord_dm"))

    assert result["verified"] is False
    assert "no_stored_name" in result.get("mismatched_fields", [])
    assert "Credentials were not written through the onboarding flow" in result.get("error", "")

    # Clean up
    for f in user_dir.glob("*"):
        f.unlink()
    user_dir.rmdir()


def test_verify_athlete_identity_with_stored_name():
    """verify_athlete_identity returns verified=True when name is stored."""
    user_dir = _temp_user_dir()

    with patch("training.intervals_icu._user_dir", return_value=user_dir):
        # Simulate onboarding: store credentials WITH a name
        store_user_credentials(
            "discord_dm", "i494629", "test_key", athlete_name="Millberg"
        )

        mock_profile = {"id": "i494629", "name": "Millberg", "timezone": "Europe/Berlin"}

        with patch("training.intervals_icu._request", return_value=mock_profile):
            result = json.loads(verify_athlete_identity("discord_dm"))

    assert result["verified"] is True, f"Expected verified=True, got: {result}"
    assert result["stored_name"] == "Millberg"
    assert result["api_name"] == "Millberg"
    assert result["has_stored_name"] is True
    assert "error" not in result

    # Clean up
    for f in user_dir.glob("*"):
        f.unlink()
    user_dir.rmdir()


def test_get_athlete_profile_includes_athlete_name():
    """get_athlete_profile returns athlete_name from the stored name file."""
    user_dir = _temp_user_dir()

    with patch("training.intervals_icu._user_dir", return_value=user_dir):
        store_user_credentials(
            "discord_dm", "i344591", "test_key", athlete_name="Joey"
        )

        mock_profile = {
            "id": "i344591",
            "name": "JohanM",
            "timezone": "Europe/Stockholm",
            "icu_weight": 78.4,
            "icu_resting_hr": 55,
            "sex": "M",
            "icu_date_of_birth": "1998-05-04",
        }

        with patch("training.intervals_icu._cache_get", return_value=None):
            with patch("training.intervals_icu._cache_set"):
                with patch("training.intervals_icu._request", return_value=mock_profile):
                    result = json.loads(get_athlete_profile("discord_dm"))

    assert result["name"] == "JohanM"
    assert result["athlete_name"] == "Joey"
    assert result["athlete_id"] == "i344591"

    # Clean up
    for f in user_dir.glob("*"):
        f.unlink()
    user_dir.rmdir()


def test_get_athlete_profile_athlete_name_none_when_missing():
    """get_athlete_profile returns athlete_name=None when name file absent."""
    user_dir = _temp_user_dir()

    with patch("training.intervals_icu._user_dir", return_value=user_dir):
        store_user_credentials(
            "discord_dm", "i344591", "test_key", athlete_name=""
        )

        mock_profile = {
            "id": "i344591",
            "name": "JohanM",
            "timezone": "Europe/Stockholm",
            "icu_weight": 78.4,
            "icu_resting_hr": 55,
            "sex": "M",
            "icu_date_of_birth": "1998-05-04",
        }

        with patch("training.intervals_icu._cache_get", return_value=None):
            with patch("training.intervals_icu._cache_set"):
                with patch("training.intervals_icu._request", return_value=mock_profile):
                    result = json.loads(get_athlete_profile("discord_dm"))

    assert result["athlete_name"] is None

    # Clean up
    for f in user_dir.glob("*"):
        f.unlink()
    user_dir.rmdir()


def test_verify_onboarded_credentials_remain_verified():
    """After onboarding, verify_athlete_identity stays verified on re-check."""
    user_dir = _temp_user_dir()

    with patch("training.intervals_icu._user_dir", return_value=user_dir):
        # First: onboard
        store_user_credentials(
            "discord_dm", "i344591", "test_key", athlete_name="Joey"
        )

        mock_profile = {"id": "i344591", "name": "JohanM", "timezone": "Europe/Stockholm"}

        with patch("training.intervals_icu._request", return_value=mock_profile):
            result1 = json.loads(verify_athlete_identity("discord_dm"))

        assert result1["verified"] is True

        # Second: verify again (simulates next session)
        with patch("training.intervals_icu._request", return_value=mock_profile):
            result2 = json.loads(verify_athlete_identity("discord_dm"))

        assert result2["verified"] is True, f"Re-verification should also pass: {result2}"

    # Clean up
    for f in user_dir.glob("*"):
        f.unlink()
    user_dir.rmdir()
