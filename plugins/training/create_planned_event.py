"""Create planned events on intervals.icu calendar.

Uses the intervals.icu REST API to POST new events to the athlete's calendar.
The event appears on intervals.icu and syncs to Garmin automatically.

Structured workout steps (for Garmin step-by-step guidance) are uploaded as
FIT files via file_contents_base64.  FIT generation uses fit-tool if available,
or falls back to a template-based builder using only the standard library.

Authentication uses the same credential files as other intervals.icu tools:
  $HERMES_HOME/users/<discord_id>/intervals_key
  $HERMES_HOME/users/<discord_id>/intervals_athlete_id
"""

from __future__ import annotations

import base64
import json
import os
import re
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path
from typing import Any, Optional


_API_BASE = "https://intervals.icu/api/v1"
_DISCORD_ID_RE = re.compile(r"^[1-9]\d{16,19}$")

# ── Pace conversion ─────────────────────────────────────────────────────────


def _parse_pace_to_ms(pace_str) -> float:
    """Convert '5:40' (min:sec/km) → m/s."""
    if isinstance(pace_str, (int, float)):
        return float(pace_str)
    pace_str = str(pace_str).strip()
    if ":" in pace_str:
        parts = pace_str.split(":")
        if len(parts) == 2:
            total_sec = int(parts[0]) * 60 + int(parts[1])
            if total_sec > 0:
                return round(1000.0 / total_sec, 2)
    try:
        return float(pace_str)
    except (ValueError, TypeError):
        return 0.0


# ── FIT generation ──────────────────────────────────────────────────────────


def _build_fit_file(
    sport: str,
    steps: list[dict],
    max_hr: int,
    ftp: int,
) -> bytes:
    """Build a FIT workout file from step definitions using fit-tool."""
    from fit_tool.fit_file_builder import FitFileBuilder
    from fit_tool.profile.messages.workout_message import WorkoutMessage
    from fit_tool.profile.messages.workout_step_message import WorkoutStepMessage
    from fit_tool.profile.messages.file_id_message import FileIdMessage
    from fit_tool.profile.profile_type import (
        Sport, Intensity, WorkoutStepDuration, WorkoutStepTarget, FileType,
    )

    sport_map = {"Run": Sport.RUNNING, "Ride": Sport.CYCLING,
                 "VirtualRide": Sport.CYCLING, "GravelRide": Sport.CYCLING,
                 "MountainBikeRide": Sport.CYCLING}
    intensity_map = {"WARMUP": Intensity.WARMUP, "ACTIVE": Intensity.ACTIVE,
                     "REST": Intensity.REST, "COOLDOWN": Intensity.COOLDOWN}

    builder = FitFileBuilder(auto_define=True)

    fid = FileIdMessage()
    fid.type = FileType.WORKOUT
    builder.add(fid)

    w = WorkoutMessage()
    w.sport = sport_map.get(sport, Sport.CYCLING)
    w.num_valid_steps = len(steps)
    builder.add(w)

    for s in steps:
        dur = float(s.get("duration_sec", 0))
        stype = str(s.get("type", "ACTIVE")).upper()
        target = str(s.get("target", "")).upper()
        name = str(s.get("name", ""))[:16]

        hr_low = s.get("hr_min")
        hr_high = s.get("hr_max")
        pw_low = s.get("power_pct_min") or s.get("power_min")
        pw_high = s.get("power_pct_max") or s.get("power_max")
        pc_low = s.get("pace_min")
        pc_high = s.get("pace_max")

        if not target:
            if hr_low is not None or hr_high is not None:
                target = "HR"
            elif pw_low is not None or pw_high is not None:
                target = "POWER"
            elif pc_low is not None or pc_high is not None:
                target = "PACE"

        msg = WorkoutStepMessage()
        msg.workout_step_name = name
        msg.intensity = intensity_map.get(stype, Intensity.ACTIVE)
        msg.duration_type = WorkoutStepDuration.TIME
        msg.duration_time = dur

        if target == "HR":
            lo = int(hr_low or s.get("min", 0))
            hi = int(hr_high or s.get("max", 0))
            if max_hr > 0:
                lo = max(1, min(100, round(lo / max_hr * 100)))
                hi = max(1, min(100, round(hi / max_hr * 100)))
            msg.target_type = WorkoutStepTarget.HEART_RATE
            msg.custom_target_heart_rate_low = lo
            msg.custom_target_heart_rate_high = hi
        elif target == "POWER":
            lo = int(pw_low or s.get("min", 0))
            hi = int(pw_high or s.get("max", 0))
            # FIT sends power targets as absolute values — intervals.icu/Garmin
            # interpret them as %FTP regardless. If values look like watts (>20
            # and power_pct_* not explicitly set), convert to %FTP.
            is_pct = bool(s.get("power_pct_min") or s.get("power_pct_max"))
            if not is_pct and isinstance(lo, (int, float)) and float(lo) > 20 and ftp > 0:
                lo = round(float(lo) / ftp * 100)
                hi = round(float(hi) / ftp * 100)
            msg.target_type = WorkoutStepTarget.POWER
            msg.custom_target_power_low = int(lo)
            msg.custom_target_power_high = int(hi)
        elif target == "PACE":
            lo = _parse_pace_to_ms(pc_low or s.get("min", 0))
            hi = _parse_pace_to_ms(pc_high or s.get("max", 0))
            msg.target_type = WorkoutStepTarget.SPEED
            msg.custom_target_speed_low = float(lo)
            msg.custom_target_speed_high = float(hi)

        builder.add(msg)

    return builder.build().to_bytes()



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
        raise RuntimeError("HERMES_HOME is not set")
    d = Path(hermes_home) / "users" / str(discord_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _load_credentials(discord_id: str) -> tuple[str, str]:
    key_file = _user_dir(discord_id) / "intervals_key"
    id_file = _user_dir(discord_id) / "intervals_athlete_id"
    if not key_file.exists() or not id_file.exists():
        raise ValueError("No intervals.icu credentials found. Please run /start first.")
    api_key = key_file.read_text(encoding="utf-8").strip()
    athlete_id = id_file.read_text(encoding="utf-8").strip()
    if not api_key or not athlete_id:
        raise ValueError("Credentials are empty. Please run /start again.")
    return athlete_id, api_key


def _auth_header(api_key: str) -> str:
    token = base64.b64encode(f"API_KEY:{api_key}".encode()).decode()
    return f"Basic {token}"


def _post_json(athlete_id: str, api_key: str, path: str, payload: dict, timeout: int = 20) -> Any:
    url = f"{_API_BASE}{path}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data,
        headers={"Authorization": _auth_header(api_key), "Accept": "application/json",
                 "Content-Type": "application/json", "User-Agent": "hermes-coach/1.0"},
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
            raise ValueError("intervals.icu 401. API key may have expired — run /start.") from exc
        raise RuntimeError(f"intervals.icu error {exc.code}: {exc.reason}. Body: {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Could not reach intervals.icu: {exc.reason}") from exc


def _delete_json(athlete_id: str, api_key: str, path: str, timeout: int = 20) -> bool:
    url = f"{_API_BASE}{path}"
    req = urllib.request.Request(
        url,
        headers={"Authorization": _auth_header(api_key), "Accept": "application/json",
                 "User-Agent": "hermes-coach/1.0"},
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
        raise RuntimeError(f"intervals.icu DELETE error {exc.code}. Body: {body}") from exc


# ── Tool implementations ────────────────────────────────────────────────────


def create_event(discord_id: str, **kw: Any) -> str:
    """Create a new planned event on the athlete's intervals.icu calendar.

    Args:
        name: Event name.
        date_iso: Date YYYY-MM-DD.
        event_type: Sport type, default "Ride".
        description: Optional description.
        planned_load: Optional planned TSS/load.
        planned_intensity: Optional planned IF %.
        duration_min: Optional planned duration in minutes.
        indoor: True for Zwift/indoor.
        category: Event category, default "WORKOUT".
        start_time: ISO datetime override.
        steps: Optional list of structured workout steps for Garmin sync.
               Each step: {name, duration_sec, type (WARMUP|ACTIVE|REST|COOLDOWN),
               hr_min/hr_max (BPM), power_min/power_max (watts),
               power_pct_min/power_pct_max (% FTP), pace_min/pace_max ('5:40' or m/s)}.

    Returns JSON with created event_id or error.
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
    step_list: list[dict] = kw.get("steps") or []

    if not name:
        return json.dumps({"error": "name is required"})
    if not date_iso:
        return json.dumps({"error": "date_iso is required (YYYY-MM-DD format)"})

    try:
        date.fromisoformat(date_iso)
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
    if indoor:
        payload["indoor"] = True

    # Auto-compute moving_time from steps if not provided
    if step_list and duration_min is None:
        total_sec = sum(int(s.get("duration_sec", 0)) for s in step_list)
        if total_sec > 0:
            duration_min = round(total_sec / 60)

    if duration_min is not None:
        payload["moving_time"] = int(float(duration_min) * 60)

    # Set event-level target and generate FIT file for structured steps
    if step_list:
        if event_type in ("Run", "TrailRun", "VirtualRun"):
            payload["target"] = "PACE"
        elif event_type in ("Ride", "VirtualRide", "GravelRide", "MountainBikeRide"):
            payload["target"] = "POWER"

        max_hr = 193
        ftp = 0
        try:
            hdrs = {
                "Authorization": _auth_header(api_key),
                "Accept": "application/json",
                "User-Agent": "hermes-coach/1.0",
            }
            req = urllib.request.Request(f"{_API_BASE}/athlete/{athlete_id}", headers=hdrs)
            with urllib.request.urlopen(req, timeout=10) as resp:
                max_hr = json.loads(resp.read()).get("max_hr") or max_hr
            req2 = urllib.request.Request(
                f"{_API_BASE}/athlete/{athlete_id}/sport-settings/{event_type}", headers=hdrs)
            with urllib.request.urlopen(req2, timeout=10) as resp2:
                ftp = json.loads(resp2.read()).get("ftp") or 0
        except Exception:
            pass

        fit_bytes = _build_fit_file(event_type, step_list, max_hr, ftp)
        payload["file_contents_base64"] = base64.b64encode(fit_bytes).decode()
        payload["filename"] = "workout.fit"

    try:
        result = _post_json(athlete_id, api_key, f"/athlete/{athlete_id}/events", payload)
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
        "has_steps": len(step_list) > 0,
    })


def delete_event(discord_id: str, **kw: Any) -> str:
    """Delete a planned event from intervals.icu calendar by numeric event_id."""
    event_id = kw.get("event_id")
    if event_id is None:
        return json.dumps({"error": "event_id is required"})
    try:
        athlete_id, api_key = _load_credentials(discord_id)
    except ValueError as exc:
        return json.dumps({"error": str(exc)})
    try:
        success = _delete_json(athlete_id, api_key,
                               f"/athlete/{athlete_id}/events/{int(event_id)}")
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
            handler=lambda args, **kw: fn(discord_id=_require_user_id(kw), **args),
        )

    _D = {"discord_id": {"type": "string", "description": "Discord user ID."}}

    _tool(
        name="create_planned_event",
        description=(
            "Create a new planned workout on the intervals.icu calendar "
            "(syncs to Garmin). Provide name, date_iso (YYYY-MM-DD), and "
            "optionally description, planned_load, planned_intensity, "
            "duration_min, indoor, start_time, and steps for structured "
            "Garmin guidance."
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
            "steps": {
                "type": "array",
                "description": (
                    "Structured workout steps for Garmin live guidance. "
                    "Each step: {name, duration_sec, type (WARMUP|ACTIVE|REST|COOLDOWN), "
                    "description?, target? (auto-detected). "
                    "Use hr_min/hr_max for HR (BPM), power_min/power_max for watts, "
                    "power_pct_min/power_pct_max for % FTP, "
                    "pace_min/pace_max for pace ('5:40' min:sec/km or m/s)."
                ),
                "items": {"type": "object"},
            },
        },
        required=["discord_id", "name", "date_iso"],
        fn=create_event,
    )

    _tool(
        name="delete_planned_event",
        description="Delete a planned event from intervals.icu calendar by numeric event_id.",
        properties={**_D, "event_id": {"type": "integer", "description": "Numeric event ID to delete."}},
        required=["discord_id", "event_id"],
        fn=delete_event,
    )
