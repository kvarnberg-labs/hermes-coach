"""get_current_time — resolve the current instant without a shell.

coach-brain/temporal-load-validation.yaml opens with clock discipline ("resolve
the current instant before any day-relative statement"). Until 2026-11-10 the
only way to satisfy that was `terminal date`; the Discord toolset no longer
carries a shell (7 tools, no terminal), so the coach had no clock at all.

No network and no subprocess: the athlete's timezone comes from the
already-cached get_athlete_profile payload and is null when that cache is
empty, so a reply is never blocked on the intervals.icu API and no timezone is
ever invented.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional
from zoneinfo import ZoneInfo

from ._credentials import _load_credentials, _require_user_id
from .intervals_icu import _athlete_tz

# English weekday names indexed by datetime.weekday(); strftime("%A") follows
# the pod's locale, and the coach quotes these names verbatim in its reply.
_WEEKDAYS = (
    "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday",
)


def _now() -> datetime:
    """The clock. A module function so tests can freeze the instant."""
    return datetime.now(timezone.utc)


def _cached_timezone(discord_id: str) -> Optional[str]:
    """The athlete's tz from the profile cache, or None when nothing is cached."""
    try:
        athlete_id, _api_key = _load_credentials(discord_id)
    except (ValueError, RuntimeError):
        return None  # not onboarded / no HERMES_HOME -> UTC only
    return _athlete_tz(discord_id, athlete_id)


def get_current_time(discord_id: str, **_: Any) -> str:
    """Current UTC date, time and weekday, plus the athlete's local time."""
    now = _now()
    tz_name = _cached_timezone(discord_id)
    local = None
    if tz_name:
        try:
            local = now.astimezone(ZoneInfo(tz_name))
        except Exception:
            pass  # unknown zone in a stale profile -> report UTC only
    result = {
        "utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "iso_date": now.date().isoformat(),
        "iso_weekday": _WEEKDAYS[now.weekday()],
        "timezone": tz_name,
        "utc_offset_minutes": None,
        "local_time": None,
        "local_date": None,
    }
    if local is not None:
        result.update(
            utc_offset_minutes=int(local.utcoffset().total_seconds() // 60),
            local_time=local.strftime("%Y-%m-%dT%H:%M:%S"),
            local_date=local.date().isoformat(),
        )
    return json.dumps(result)


def register_tools(ctx) -> None:
    """Register get_current_time with the Hermes plugin context."""

    def _handler(args, **kw):
        try:
            uid = _require_user_id(kw)
        except ValueError as exc:
            return json.dumps({"error": str(exc)})
        return get_current_time(discord_id=uid, **args)

    ctx.register_tool(
        name="get_current_time",
        toolset="training",
        schema={
            "name": "get_current_time",
            "description": (
                "Current UTC date, time and weekday, plus the athlete's local time and "
                "UTC offset when their timezone is already cached — no network call; "
                "use it to resolve 'today' before any day-relative statement."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
        handler=_handler,
    )
