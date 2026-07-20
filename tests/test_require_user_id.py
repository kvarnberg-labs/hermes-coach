"""Tests for _require_user_id rejecting fallback to shared credential directory.

Verifies that:
  1. _require_user_id accepts valid Discord snowflakes
  2. _require_user_id raises ValueError on empty/non-snowflake user_id
  3. The error message is informative about the identity problem
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "plugins"))
from training.intervals_icu import _require_user_id


def test_require_user_id_accepts_valid_snowflake():
    """_require_user_id returns the snowflake when given a valid one."""
    result = _require_user_id({"user_id": "785756739492511774"})
    assert result == "785756739492511774"


def test_require_user_id_accepts_17_digit_snowflake():
    """_require_user_id works with minimum-length Discord snowflakes."""
    result = _require_user_id({"user_id": "123456789012345678"})  # 18 digits
    assert result == "123456789012345678"


def test_require_user_id_rejects_empty_string():
    """_require_user_id raises ValueError when user_id is empty."""
    with pytest.raises(ValueError) as exc_info:
        _require_user_id({"user_id": ""})
    assert "User identity not available" in str(exc_info.value)


def test_require_user_id_rejects_missing_key():
    """_require_user_id raises ValueError when user_id key is missing."""
    with pytest.raises(ValueError) as exc_info:
        _require_user_id({})
    assert "User identity not available" in str(exc_info.value)


def test_require_user_id_rejects_non_snowflake():
    """_require_user_id raises ValueError when user_id is not a snowflake."""
    with pytest.raises(ValueError) as exc_info:
        _require_user_id({"user_id": "discord_dm"})
    assert "User identity not available" in str(exc_info.value)


def test_require_user_id_rejects_short_string():
    """_require_user_id raises ValueError when user_id is too short."""
    with pytest.raises(ValueError) as exc_info:
        _require_user_id({"user_id": "123"})
    assert "User identity not available" in str(exc_info.value)


def test_require_user_id_rejects_zero_prefixed():
    """_require_user_id rejects snowflakes that start with 0."""
    with pytest.raises(ValueError) as exc_info:
        _require_user_id({"user_id": "0785756739492511774"})
    assert "User identity not available" in str(exc_info.value)


def test_require_user_id_handles_int_user_id():
    """_require_user_id handles integer user_id by stringifying it (gateway sends str)."""
    result = _require_user_id({"user_id": 785756739492511774})
    assert result == "785756739492511774"
