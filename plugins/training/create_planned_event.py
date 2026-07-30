
"""Create planned events on intervals.icu calendar.

Uses the intervals.icu REST API to POST new events to the athlete's calendar.
The event appears on intervals.icu and syncs to Garmin automatically.

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
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

_API_BASE = "https://intervals.icu/api/v1"
_DISCORD_ID_RE = re.compile(r"^[1-9]\d{16,19}$")


def _require_user_id(kw: dict) -> str:
    uid = str(kw.get("user_id", ""))
    if not _DISCORD_ID_RE.match(uid):
        raise ValueError(
            "User identity not available — the Discord gateway did not provide a valid user ID."
        )
    return uid


def _user_dir(discord_id: str) -> Path:
    hermes_home = os.environ.get("HERMES_HOME")
    if not hermes_home:
        raise RuntimeError(
            "HERMES_HOME is not set — cannot resolve credential directory."
        )
    d = Path(hermes_home) / "users" / str(discord_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _load_credentials(discord_id: str) -> tuple[str, str]:
    key_file = _user_dir(discord_id) / "intervals_key"
    id_file = _user_dir(discord_id) / "intervals_athlete_id"
    if not key_file.exists() or not id_file.exists():
        raise ValueError(
            f"No intervals.icu credentials found. Please run /start first."
        )
    api_key = key_file.read_text(encoding="utf-8").strip()
    athlete_id = id_file.read_text(encoding="utf-8").strip()
    if not api_key or not athlete_id:
        raise ValueError("Credentials are empty. Please run /start again.")
    return athlete_id, api_key


def _auth_header(api_key: str) -> str:
    token = base64.b64encode(f"API_KEY:{api_key}".encode()).decode()
    return f"Basic {token}"


def _post_json(
    athlete_id: str,
    api_key: str,
    path: str,
    payload: dict,
    timeout: int = 20,
) -> Any:
    """Make an authenticated POST request to intervals.icu."""
    url = f"{_API_BASE}{path}"
    data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": _auth_header(api_key),
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "hermes-coach/1.0",
        },
        method="POST",
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
            f"intervals.icu API error {exc.code}: {exc.reason}. Body: {body}"
        ) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Could not reach intervals.icu: {exc.reason}") from exc


def _delete_json(
    athlete_id: str,
    api_key: str,
    path: str,
    timeout: int = 20,
) -> bool:
    """Make an authenticated DELETE request to intervals.icu."""
    url = f"{_API_BASE}{path}"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": _auth_header(api_key),
            "Accept": "application/json",
            "User-Agent": "hermes-coach/1.0",
        },
        method="DELETE",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status in (200, 204)
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8")[:300]
        except Exception:
            pass
        raise RuntimeError(
            f"intervals.icu DELETE error {exc.code}: {exc.reason}. Body: {body}"
        ) from exc


def create_event(discord_id: str, **kw: Any) -> str:
    """Create a new planned event on the athlete's intervals.icu calendar.

    Args:
        name: Event name (e.g. "Threshold 3x12min").
        date_iso: Date in YYYY-MM-DD format (e.g. "2026-07-13").
        event_type: Sport type, default "Ride".
        description: Optional longer description with watt targets, RPE, etc.
        planned_load: Optional planned training load (TSS equivalent).
        planned_intensity: Optional planned intensity factor (0-100 scale).
        duration_min: Optional planned duration in minutes.
        indoor: Set True for Zwift/indoor trainer sessions.
        category: Event category, default "WORKOUT".
        start_time: Optional ISO datetime like "2026-07-13T08:00:00".

    Returns a JSON object with the created event's id and details, or an error.
    """
    name = str(kw.get("name", "")).strip()
    date_iso = str(kw.get("date_iso", "")).strip()
    event_type = str(kw.get("event_type", "Ride")).strip()
    description = str(kw.get("description", "")).strip()
    planned_load = kw.get("planned_load")
    planned_intensity = kw.get("planned_intensity")
    duration_min = kw.get("duration_min")
    indoor = kw.get("indoor", False)
    category = str(kw.get("category", "WORKOUT")).strip()
    start_time = str(kw.get("start_time", "")).strip()

    if not name:
        return json.dumps({"error": "name is required"})
    if not date_iso:
        return json.dumps({"error": "date_iso is required (YYYY-MM-DD format)"})

    try:
        parsed_date = date.fromisoformat(date_iso)
    except ValueError:
        return json.dumps({"error": f"Invalid date: {date_iso}. Use YYYY-MM-DD format."})

    try:
        athlete_id, api_key = _load_credentials(discord_id)
    except ValueError as exc:
        return json.dumps({"error": str(exc)})

    if not start_time:
        start_time = f"{date_iso}T09:00:00"

    payload: dict[str, Any] = {
        "name": name,
        "type": event_type,
        "category": category,
        "start_date_local": start_time,
    }

    if description:
        payload["description"] = description
    if planned_load is not None:
        payload["icu_training_load"] = int(planned_load)
    if planned_intensity is not None:
        payload["icu_intensity"] = float(planned_intensity)
    if duration_min is not None:
        payload["moving_time"] = int(float(duration_min) * 60)
    if indoor:
        payload["indoor"] = True

    try:
        result = _post_json(
            athlete_id, api_key,
            f"/athlete/{athlete_id}/events",
            payload,
        )
    except (ValueError, RuntimeError) as exc:
        return json.dumps({"error": str(exc)})

    return json.dumps({
        "created": True,
        "event_id": result.get("id"),
        "name": result.get("name"),
        "date": (result.get("start_date_local") or "")[:10],
        "type": result.get("type"),
        "category": result.get("category"),
        "planned_load": result.get("icu_training_load"),
    })


def delete_event(discord_id: str, **kw: Any) -> str:
    """Delete a planned event from the athlete's intervals.icu calendar.

    Args:
        event_id: The numeric event ID to delete (e.g. 120111989).

    Returns a JSON object confirming deletion or an error.
    """
    event_id = kw.get("event_id")
    if event_id is None:
        return json.dumps({"error": "event_id is required"})

    try:
        athlete_id, api_key = _load_credentials(discord_id)
    except ValueError as exc:
        return json.dumps({"error": str(exc)})

    try:
        success = _delete_json(
            athlete_id, api_key,
            f"/athlete/{athlete_id}/events/{int(event_id)}",
        )
        return json.dumps({"deleted": success, "event_id": int(event_id)})
    except (ValueError, RuntimeError) as exc:
        return json.dumps({"error": str(exc)})


def register_tools(ctx) -> None:
    """Register create_event and delete_event as Hermes tools."""

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
        name="create_planned_event",
        description=(
            "Create a new planned workout on the intervals.icu calendar "
            "(syncs to Garmin). Provide name, date_iso (YYYY-MM-DD), and "
            "optionally description, planned_load, planned_intensity, "
            "duration_min, indoor, and start_time."
        ),
        properties={
            **_D,
            "name": {"type": "string", "description": "Event name."},
            "date_iso": {"type": "string", "description": "Date YYYY-MM-DD."},
            "event_type": {"type": "string", "description": "Sport type, default Ride."},
            "description": {"type": "string", "description": "Optional description."},
            "planned_load": {"type": "integer", "description": "Planned TSS/load."},
            "planned_intensity": {"type": "number", "description": "Planned IF %."},
            "duration_min": {"type": "integer", "description": "Planned duration minutes."},
            "indoor": {"type": "boolean", "description": "True for Zwift/indoor."},
            "category": {"type": "string", "description": "Category, default WORKOUT."},
            "start_time": {"type": "string", "description": "ISO datetime override."},
        },
        required=["discord_id", "name", "date_iso"],
        fn=create_event,
    )

    _tool(
        name="delete_planned_event",
        description=(
            "Delete a planned event from intervals.icu calendar by numeric event_id."
        ),
        properties={
            **_D,
            "event_id": {"type": "integer", "description": "Numeric event ID to delete."},
        },
        required=["discord_id", "event_id"],
        fn=delete_event,
    )
