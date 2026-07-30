"""get_athlete_stats — aggregated activity statistics for a date range from intervals.icu.

Fetches activities within [start_date, end_date] from the intervals.icu API
(GET /api/v1/athlete/{athlete_id}/activities?oldest=...&newest=...) and
returns totals (distance, duration, calories, training load, activity count)
plus a per-sport breakdown.

Credential loading follows the exact same pattern as the intervals_icu.py
plugin: _require_user_id, _user_dir, _load_credentials, _auth_header.
discord_id is injected by the gateway via kw["user_id"]; register_tools
strips it from the model-visible schema so the model cannot spoof identity.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

_API_BASE = "https://intervals.icu/api/v1"

# Discord snowflake IDs: 17-19 decimal digits, never starting with 0.
_DISCORD_ID_RE = re.compile(r"^[1-9]\d{16,19}$")

# YYYY-MM-DD
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


# ---------------------------------------------------------------------------
# Identity & credential loading (same pattern as intervals_icu.py)
# ---------------------------------------------------------------------------


def _require_user_id(kw: dict) -> str:
    """Return the Discord snowflake from the gateway, or raise ValueError.

    Raises ValueError when the gateway has not injected a valid Discord
    snowflake into kw["user_id"]. No fallback — prevents mixed-user
    credential directory access.
    """
    uid = str(kw.get("user_id", ""))
    if _DISCORD_ID_RE.match(uid):
        return uid
    raise ValueError(
        "User identity not available — the Discord gateway did not provide "
        "a valid user ID."
    )


def _user_dir(discord_id: str) -> Path:
    """Return the credential directory for a Discord user."""
    hermes_home_raw = os.environ.get("HERMES_HOME")
    if not hermes_home_raw:
        raise RuntimeError(
            "HERMES_HOME is not set — cannot resolve credential directory."
        )
    d = Path(hermes_home_raw) / "users" / str(discord_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _key_path(discord_id: str) -> Path:
    return _user_dir(discord_id) / "intervals_key"


def _athlete_id_path(discord_id: str) -> Path:
    return _user_dir(discord_id) / "intervals_athlete_id"


def _load_credentials(discord_id: str) -> tuple[str, str]:
    """Return (athlete_id, api_key) or raise ValueError if not configured."""
    key_file = _key_path(discord_id)
    id_file = _athlete_id_path(discord_id)

    if not key_file.exists() or not id_file.exists():
        raise ValueError(
            f"No intervals.icu credentials found for Discord user {discord_id}. "
            "Please run /start to connect your intervals.icu account."
        )
    api_key = key_file.read_text(encoding="utf-8").strip()
    athlete_id = id_file.read_text(encoding="utf-8").strip()
    if not api_key or not athlete_id:
        raise ValueError(
            "intervals.icu credentials are empty. Please run /start again."
        )
    return athlete_id, api_key


def _auth_header(api_key: str) -> str:
    """Build the Basic Auth header value for intervals.icu."""
    token = base64.b64encode(f"API_KEY:{api_key}".encode()).decode()
    return f"Basic {token}"


# ---------------------------------------------------------------------------
# HTTP client
# ---------------------------------------------------------------------------


def _request(
    athlete_id: str,
    api_key: str,
    path: str,
    params: Optional[dict] = None,
    timeout: int = 20,
) -> Any:
    """Make an authenticated GET request to intervals.icu and return parsed JSON."""
    url = f"{_API_BASE}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(
            {k: v for k, v in params.items() if v is not None}
        )

    req = urllib.request.Request(
        url,
        headers={
            "Authorization": _auth_header(api_key),
            "Accept": "application/json",
            "User-Agent": "hermes-coach/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            raise ValueError(
                "intervals.icu returned 401 Unauthorized. "
                "Your API key may have expired — please run /start to reconnect."
            ) from exc
        raise RuntimeError(
            f"intervals.icu API error {exc.code}: {exc.reason}"
        ) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Could not reach intervals.icu: {exc.reason}") from exc


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _validate_date(date_str: Any, field: str) -> str:
    """Validate a YYYY-MM-DD date string; raise ValueError on bad format."""
    if not isinstance(date_str, str) or not _DATE_RE.match(date_str):
        raise ValueError(
            f"Invalid {field}: {date_str!r}. Expected YYYY-MM-DD."
        )
    return date_str


def _float_or_zero(v: Any) -> float:
    return float(v) if v is not None else 0.0


def _int_or_zero(v: Any) -> int:
    try:
        return int(v) if v is not None else 0
    except (TypeError, ValueError):
        return 0


# ---------------------------------------------------------------------------
# Tool implementation
# ---------------------------------------------------------------------------


def get_athlete_stats(
    discord_id: str,
    start_date: str,
    end_date: str,
    **_: Any,
) -> str:
    """Fetch aggregated activity statistics for a date range from intervals.icu.

    Args:
        discord_id: Discord user ID (injected by gateway; not model-visible).
        start_date: Start of date range (YYYY-MM-DD, inclusive).
        end_date: End of date range (YYYY-MM-DD, inclusive).

    Returns a JSON string with:
        source, start_date, end_date, total_activities, total_distance_km,
        total_duration_hours, total_calories, total_training_load, sports.

    The `sports` field is a dict keyed by sport type (Ride, Run, VirtualRide, ...)
    with per-sport totals: activities, distance_km, duration_hours, calories,
    training_load. Null fields in activities are treated as zero.
    """
    try:
        _validate_date(start_date, "start_date")
        _validate_date(end_date, "end_date")
    except ValueError as exc:
        return json.dumps({"error": str(exc)})

    try:
        athlete_id, api_key = _load_credentials(discord_id)
    except ValueError as exc:
        return json.dumps({"error": str(exc)})

    try:
        activities = _request(
            athlete_id,
            api_key,
            f"/athlete/{athlete_id}/activities",
            params={"oldest": start_date, "newest": end_date},
        )
    except (ValueError, RuntimeError) as exc:
        return json.dumps({"error": str(exc)})

    if not isinstance(activities, list):
        return json.dumps(
            {"error": "intervals.icu returned an unexpected response (not a list)."}
        )

    sports: dict[str, dict[str, Any]] = {}
    total_distance_m = 0.0
    total_duration_s = 0.0
    total_calories = 0
    total_training_load = 0
    total_activities = 0

    for act in activities:
        if not isinstance(act, dict):
            continue
        sport = act.get("type") or "Unknown"
        distance_m = _float_or_zero(act.get("distance"))
        moving_time_s = _float_or_zero(act.get("moving_time"))
        calories = _int_or_zero(act.get("calories"))
        training_load = _int_or_zero(act.get("icu_training_load"))

        total_activities += 1
        total_distance_m += distance_m
        total_duration_s += moving_time_s
        total_calories += calories
        total_training_load += training_load

        if sport not in sports:
            sports[sport] = {
                "activities": 0,
                "distance_km": 0.0,
                "duration_hours": 0.0,
                "calories": 0,
                "training_load": 0,
            }
        s = sports[sport]
        s["activities"] += 1
        s["distance_km"] += distance_m / 1000.0
        s["duration_hours"] += moving_time_s / 3600.0
        s["calories"] += calories
        s["training_load"] += training_load

    # Round sport totals
    for s in sports.values():
        s["distance_km"] = round(s["distance_km"], 2)
        s["duration_hours"] = round(s["duration_hours"], 2)

    result = {
        "source": "intervals.icu",
        "start_date": start_date,
        "end_date": end_date,
        "total_activities": total_activities,
        "total_distance_km": round(total_distance_m / 1000.0, 2),
        "total_duration_hours": round(total_duration_s / 3600.0, 2),
        "total_calories": total_calories,
        "total_training_load": total_training_load,
        "sports": sports,
    }
    return json.dumps(result)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def register_tools(ctx) -> None:
    """Register get_athlete_stats with the Hermes plugin context."""

    def _tool(name: str, description: str, properties: dict, required: list, fn):
        # Strip discord_id from model-visible schema — identity comes
        # exclusively from the gateway (kw["user_id"]), never from
        # model-supplied arguments.
        model_props = {k: v for k, v in properties.items() if k != "discord_id"}
        model_req = [r for r in required if r != "discord_id"]

        def _handler(args, **kw):
            try:
                uid = _require_user_id(kw)
            except ValueError as exc:
                return json.dumps({"error": str(exc)})
            return fn(discord_id=uid, **args)

        ctx.register_tool(
            name=name,
            toolset="training",
            schema={
                "name": name,
                "description": description,
                "parameters": {
                    "type": "object",
                    "properties": model_props,
                    "required": model_req,
                },
            },
            handler=_handler,
        )

    _DISCORD_ID_PROP = {
        "discord_id": {
            "type": "string",
            "description": "Discord user ID of the athlete to look up.",
        }
    }

    _tool(
        name="get_athlete_stats",
        description=(
            "Fetch aggregated activity statistics for a date range from "
            "intervals.icu. Returns total distance, total duration, total "
            "calories, total training load, activity count, and a per-sport "
            "breakdown. Use this to summarise training volume over a period."
        ),
        properties={
            **_DISCORD_ID_PROP,
            "start_date": {
                "type": "string",
                "description": "Start of date range in YYYY-MM-DD (inclusive).",
            },
            "end_date": {
                "type": "string",
                "description": "End of date range in YYYY-MM-DD (inclusive).",
            },
        },
        required=["discord_id", "start_date", "end_date"],
        fn=get_athlete_stats,
    )