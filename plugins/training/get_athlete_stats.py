"""get_athlete_stats — aggregated activity statistics for a date range from intervals.icu.

Fetches activities within [start_date, end_date] from the intervals.icu API
(GET /api/v1/athlete/{athlete_id}/activities?oldest=...&newest=...) and
returns totals (distance, duration, calories, training load, activity count)
plus a per-sport breakdown.

Credential loading and HTTP transport use the shared ``_credentials`` and
``_http`` modules (same source of truth as intervals_icu.py / onboarding.py),
so identity validation and auth can never drift between plugins. discord_id is
injected by the gateway via kw["user_id"]; register_tools strips it from the
model-visible schema so the model cannot spoof identity.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from ._credentials import _load_credentials, _require_user_id
from ._http import _request

logger = logging.getLogger(__name__)

# YYYY-MM-DD
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


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
