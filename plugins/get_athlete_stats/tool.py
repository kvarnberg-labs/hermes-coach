
"""get_athlete_stats - Aggregate training statistics over a date range.

Fetches all activities from the intervals.icu API for the given date range and
returns totals grouped by sport type (Ride, Run, VirtualRide, Hike, etc.) plus
overall aggregates: activity count, total distance, duration, calories, and
training load.

Authentication uses the same credential files as other intervals.icu tools:
  $HERMES_HOME/users/<discord_id>/intervals_key
  $HERMES_HOME/users/<discord_id>/intervals_athlete_id
"""

from __future__ import annotations

import base64
import json
import logging
import os
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_API_BASE = "https://intervals.icu/api/v1"
_DISCORD_ID_RE = re.compile(r"^[1-9]\d{16,19}$")

# ── credential helpers ──

def _require_user_id(kw: dict) -> str:
    uid = str(kw.get("user_id", ""))
    if not _DISCORD_ID_RE.match(uid):
        raise ValueError(
            "User identity not available — the Discord gateway did not "
            "provide a valid user ID."
        )
    return uid


def _user_dir(discord_id: str) -> Path:
    hermes_home = os.environ.get("HERMES_HOME", "/opt/data")
    d = Path(hermes_home) / "users" / str(discord_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _load_credentials(discord_id: str) -> tuple[str, str]:
    key_file = _user_dir(discord_id) / "intervals_key"
    id_file = _user_dir(discord_id) / "intervals_athlete_id"
    if not key_file.exists() or not id_file.exists():
        raise ValueError(
            "No intervals.icu credentials found. Please run /start first."
        )
    api_key = key_file.read_text(encoding="utf-8").strip()
    athlete_id = id_file.read_text(encoding="utf-8").strip()
    if not api_key or not athlete_id:
        raise ValueError("Credentials are empty. Please run /start again.")
    return athlete_id, api_key


def _auth_header(api_key: str) -> str:
    token = base64.b64encode(f"API_KEY:{api_key}".encode()).decode()
    return f"Basic {token}"


# ── API helper ──

def _get_json(athlete_id: str, api_key: str, path: str, timeout: int = 30) -> Any:
    url = f"{_API_BASE}{path}"
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
        body = ""
        try:
            body = exc.read().decode("utf-8")[:500]
        except Exception:
            pass
        if exc.code == 401:
            raise ValueError(
                "intervals.icu returned 401 Unauthorized. "
                "Your API key may have expired - please run /start to reconnect."
            ) from exc
        raise RuntimeError(
            f"intervals.icu API error {exc.code}: {exc.reason}"
        ) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Could not reach intervals.icu: {exc.reason}") from exc


# ── main tool ──

def get_athlete_stats(discord_id: str, **kw: Any) -> str:
    """Aggregate training statistics over a date range.

    Args:
        start_date: Start date YYYY-MM-DD (defaults to Jan 1 of current year).
        end_date: End date YYYY-MM-DD (defaults to today).

    Returns a JSON string with:
        source, start_date, end_date, total_activities, total_distance_km,
        total_duration_hours, total_calories, total_training_load, sports
        (dict keyed by sport type with per-sport totals: count, distance_km,
        duration_hours, calories, training_load).
    """
    import datetime as dt

    start_date = str(kw.get("start_date", "")).strip()
    end_date = str(kw.get("end_date", "")).strip()

    today = dt.date.today()
    if not start_date:
        start_date = f"{today.year}-01-01"
    if not end_date:
        end_date = today.isoformat()

    try:
        _ = dt.date.fromisoformat(start_date)
        _ = dt.date.fromisoformat(end_date)
    except ValueError:
        return json.dumps(
            {"error": "Invalid date format. Use YYYY-MM-DD."}
        )

    try:
        athlete_id, api_key = _load_credentials(discord_id)
    except ValueError as exc:
        return json.dumps({"error": str(exc)})

    path = (
        f"/athlete/{athlete_id}/activities"
        f"?oldest={start_date}&newest={end_date}"
    )

    try:
        data = _get_json(athlete_id, api_key, path)
    except (ValueError, RuntimeError) as exc:
        return json.dumps({"error": str(exc)})

    if not isinstance(data, list):
        return json.dumps({"error": f"Unexpected response: {type(data).__name__}"})

    sports: dict[str, dict[str, float]] = {}
    totals = {
        "count": 0,
        "distance_km": 0.0,
        "duration_hours": 0.0,
        "calories": 0,
        "training_load": 0,
    }

    for act in data:
        if not isinstance(act, dict):
            continue
        sport = act.get("type") or "Unknown"
        if sport not in sports:
            sports[sport] = {
                "count": 0,
                "distance_km": 0.0,
                "duration_hours": 0.0,
                "calories": 0,
                "training_load": 0,
            }

        dist_m = act.get("distance") or 0.0
        moving_secs = act.get("moving_time") or 0
        cal = act.get("calories") or 0
        load = act.get("icu_training_load") or 0

        dist_km = (dist_m or 0) / 1000.0
        hours = (moving_secs or 0) / 3600.0
        cal_int = int(cal or 0)
        load_int = int(load or 0)

        sports[sport]["count"] = int(sports[sport]["count"]) + 1
        sports[sport]["distance_km"] = round(sports[sport]["distance_km"] + dist_km, 2)
        sports[sport]["duration_hours"] = round(sports[sport]["duration_hours"] + hours, 2)
        sports[sport]["calories"] = int(sports[sport]["calories"]) + cal_int
        sports[sport]["training_load"] = int(sports[sport]["training_load"]) + load_int

        totals["count"] += 1
        totals["distance_km"] = round(totals["distance_km"] + dist_km, 2)
        totals["duration_hours"] = round(totals["duration_hours"] + hours, 2)
        totals["calories"] += cal_int
        totals["training_load"] += load_int

    return json.dumps(
        {
            "source": "intervals.icu",
            "start_date": start_date,
            "end_date": end_date,
            "total_activities": totals["count"],
            "total_distance_km": totals["distance_km"],
            "total_duration_hours": totals["duration_hours"],
            "total_calories": totals["calories"],
            "total_training_load": totals["training_load"],
            "sports": sports,
        }
    )


# ── registration ──

def register_tools(ctx) -> None:
    def _tool(name, description, properties, required, fn):
        model_props = {k: v for k, v in properties.items() if k != "discord_id"}
        model_req = [r for r in required if r != "discord_id"]
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
            handler=lambda args, **kw: fn(
                discord_id=_require_user_id(kw),
                **args,
            ),
        )

    _D = {"discord_id": {"type": "string", "description": "Discord user ID."}}

    _tool(
        name="get_athlete_stats",
        description=(
            "Fetch aggregated training statistics over a date range from "
            "intervals.icu. Returns total activities, distance (km), duration "
            "(hours), calories, training load, and a per-sport breakdown "
            "(Ride, Run, VirtualRide, Hike, etc.). Use this when an athlete "
            "asks for year-to-date totals, calories burned, total hours, or "
            "total distance. The start_date and end_date parameters accept "
            "YYYY-MM-DD format. Defaults to current calendar year if omitted."
        ),
        properties={
            **_D,
            "start_date": {
                "type": "string",
                "description": "Start date YYYY-MM-DD. Defaults to Jan 1 of current year.",
            },
            "end_date": {
                "type": "string",
                "description": "End date YYYY-MM-DD. Defaults to today.",
            },
        },
        required=["discord_id"],
        fn=get_athlete_stats,
    )
