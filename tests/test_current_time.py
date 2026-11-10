"""Tests for get_current_time — the coach's clock without a shell.

The Discord toolset has no terminal, so `terminal date` (the previous way to
satisfy coach-brain/temporal-load-validation.yaml's clock rule) is gone. The
tool must resolve "now" from the clock and the *cached* profile timezone only:
no API call, and no invented timezone.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "plugins"))

from training import current_time, intervals_icu
from training._http import _TTL_PROFILE, _cache_set
from training.intervals_icu import _profile_cache_key

USER = "123456789012345678"
ATHLETE = "i12345"
# Europe/Stockholm: CEST (UTC+2) until 2026-10-25 01:00Z, CET (UTC+1) after.
STOCKHOLM = "Europe/Stockholm"


@pytest.fixture
def hermes_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    user_dir = home / "users" / USER
    user_dir.mkdir(parents=True)
    (user_dir / "intervals_key").write_text("fake-api-key", encoding="utf-8")
    (user_dir / "intervals_athlete_id").write_text(ATHLETE, encoding="utf-8")
    return home


def _freeze(monkeypatch: pytest.MonkeyPatch, instant: str) -> None:
    frozen = datetime.strptime(instant, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    monkeypatch.setattr(current_time, "_now", lambda: frozen)


def _cache_profile(timezone_name: str | None) -> None:
    """Write the payload get_athlete_profile caches, through the same key."""
    _cache_set(USER, _profile_cache_key(ATHLETE), {
        "source": "intervals.icu", "athlete_id": ATHLETE, "name": None,
        "athlete_name": None, "timezone": timezone_name,
    })


def _call(**kwargs) -> dict:
    return json.loads(current_time.get_current_time(discord_id=USER, **kwargs))


def test_utc_only_shape_with_no_cached_profile(hermes_home, monkeypatch):
    _freeze(monkeypatch, "2026-11-10T11:03:00Z")
    result = _call()
    assert result == {
        "utc": "2026-11-10T11:03:00Z",
        "iso_date": "2026-11-10",
        "iso_weekday": "Tuesday",
        "timezone": None,
        "utc_offset_minutes": None,
        "local_time": None,
        "local_date": None,
    }


def test_no_api_call_when_the_profile_is_not_cached(hermes_home, monkeypatch):
    """Absent cache means UTC only — never a fetch, never a guess."""
    _freeze(monkeypatch, "2026-11-10T11:03:00Z")
    monkeypatch.setattr(intervals_icu, "_request",
                        lambda *_a, **_kw: pytest.fail("the clock must not call the API"))
    assert _call()["timezone"] is None


def test_cached_timezone_applies_local_time_and_offset(hermes_home, monkeypatch):
    _cache_profile(STOCKHOLM)
    # The 2026-10-19 session: 08:17 UTC was 10:17 CEST, still a Monday.
    _freeze(monkeypatch, "2026-10-19T08:17:00Z")
    result = _call()
    assert result["utc"] == "2026-10-19T08:17:00Z"
    assert result["iso_weekday"] == "Monday"
    assert result["timezone"] == STOCKHOLM
    assert result["utc_offset_minutes"] == 120
    assert result["local_time"] == "2026-10-19T10:17:00"
    assert result["local_date"] == "2026-10-19"


@pytest.mark.parametrize("instant,weekday,offset,local_time", [
    ("2026-07-01T10:39:00Z", "Wednesday", 120, "2026-07-01T12:39:00"),  # CEST
    ("2026-10-25T00:30:00Z", "Sunday", 120, "2026-10-25T02:30:00"),  # still CEST
    ("2026-10-25T01:30:00Z", "Sunday", 60, "2026-10-25T02:30:00"),  # CET after the switch
    ("2026-11-10T11:03:00Z", "Tuesday", 60, "2026-11-10T12:03:00"),  # CET
], ids=["summer-cest", "dst-last-hour", "dst-first-winter-hour", "winter-cet"])
def test_offset_and_weekday_across_the_dst_boundary(
    hermes_home, monkeypatch, instant, weekday, offset, local_time
):
    _cache_profile(STOCKHOLM)
    _freeze(monkeypatch, instant)
    result = _call()
    assert result["iso_weekday"] == weekday
    assert result["utc_offset_minutes"] == offset
    assert result["local_time"] == local_time


def test_local_date_rolls_over_before_utc_midnight(hermes_home, monkeypatch):
    """23:30 UTC is already tomorrow in Stockholm: the dates must differ."""
    _cache_profile(STOCKHOLM)
    _freeze(monkeypatch, "2026-11-10T23:30:00Z")
    result = _call()
    assert result["iso_date"] == "2026-11-10"
    assert result["iso_weekday"] == "Tuesday"
    assert result["local_date"] == "2026-11-11"
    assert result["local_time"] == "2026-11-11T00:30:00"
    assert result["utc_offset_minutes"] == 60


def test_unknown_cached_zone_falls_back_to_utc(hermes_home, monkeypatch):
    _cache_profile("Mars/Olympus_Mons")
    _freeze(monkeypatch, "2026-11-10T11:03:00Z")
    result = _call()
    assert result["utc"] == "2026-11-10T11:03:00Z"
    assert result["local_time"] is None and result["utc_offset_minutes"] is None


def test_no_credentials_is_not_an_error(hermes_home, monkeypatch):
    """A clock is not athlete data: a user without /start still gets a time."""
    _freeze(monkeypatch, "2026-11-10T11:03:00Z")
    assert json.loads(current_time.get_current_time(discord_id="987654321098765432"))[
        "iso_date"] == "2026-11-10"


def test_output_stays_small(hermes_home, monkeypatch):
    _cache_profile(STOCKHOLM)
    _freeze(monkeypatch, "2026-11-10T11:03:00Z")
    assert len(current_time.get_current_time(discord_id=USER)) < 300


class TestRegistration:
    def test_registered_name_toolset_and_handler_without_identity(self):
        registered = {}

        class FakeCtx:
            def register_tool(self, name, toolset, schema, handler):
                registered[name] = (toolset, schema, handler)

        current_time.register_tools(FakeCtx())
        assert list(registered) == ["get_current_time"]
        toolset, schema, handler = registered["get_current_time"]
        assert toolset == "training"
        assert schema["name"] == "get_current_time"
        assert schema["parameters"] == {"type": "object", "properties": {}, "required": []}
        # Identity comes from the gateway only; a missing one is an error JSON,
        # never a raise and never a model-supplied id.
        result = json.loads(handler({}, user_id="not-a-snowflake"))
        assert "error" in result
        assert "user ID" in result["error"]

    def test_handler_passes_the_gateway_identity(self, hermes_home, monkeypatch):
        registered = {}

        class FakeCtx:
            def register_tool(self, name, toolset, schema, handler):
                registered[name] = handler

        current_time.register_tools(FakeCtx())
        _freeze(monkeypatch, "2026-11-10T11:03:00Z")
        _cache_profile(STOCKHOLM)
        assert json.loads(registered["get_current_time"]({}, user_id=USER))["timezone"] == STOCKHOLM
