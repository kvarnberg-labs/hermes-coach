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
import logging
import os
import re
import struct
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

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
    """Build a FIT workout file from step definitions.

    Uses fit-tool if available, otherwise a minimal template-based builder.
    """
    try:
        import fit_tool  # noqa: F401
        return _build_fit_with_fittool(sport, steps, max_hr, ftp)
    except ImportError:
        pass
    try:
        import fit_tool  # noqa: F401  # second attempt after path setup
    except ImportError:
        pass
    # Fall back to template-based builder
    return _build_fit_template(sport, steps, max_hr, ftp)


def _build_fit_with_fittool(sport, steps, max_hr, ftp):
    """Build FIT using the fit-tool library."""
    from fit_tool.fit_file_builder import FitFileBuilder
    from fit_tool.profile.messages.workout_message import WorkoutMessage
    from fit_tool.profile.messages.workout_step_message import WorkoutStepMessage
    from fit_tool.profile.messages.file_id_message import FileIdMessage
    from fit_tool.profile.profile_type import (
        Sport, Intensity, WorkoutStepDuration, WorkoutStepTarget, FileType,
    )

    sport_map = {"Run": Sport.RUNNING, "Ride": Sport.CYCLING, "VirtualRide": Sport.CYCLING}
    intensity_map = {"WARMUP": Intensity.WARMUP, "ACTIVE": Intensity.ACTIVE,
                     "REST": Intensity.REST, "COOLDOWN": Intensity.COOLDOWN}

    builder = FitFileBuilder(auto_define=True)

    fid = FileIdMessage()
    fid.type = FileType.WORKOUT
    builder.add(fid)

    w = WorkoutMessage()
    w.sport = sport_map.get(sport, Sport.CYCLING)
    w.workout_name = ""
    w.num_valid_steps = len(steps)
    builder.add(w)

    for s in steps:
        dur = float(s.get("duration_sec", 0))
        stype = str(s.get("type", "ACTIVE")).upper()
        target = str(s.get("target", "")).upper()
        name = str(s.get("name", ""))[:16]

        # Auto-detect target from provided fields
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
            if max_hr > 0:  # convert BPM → %max HR
                lo = max(1, min(100, round(lo / max_hr * 100)))
                hi = max(1, min(100, round(hi / max_hr * 100)))
            msg.target_type = WorkoutStepTarget.HEART_RATE
            msg.custom_target_heart_rate_low = lo
            msg.custom_target_heart_rate_high = hi
        elif target == "POWER":
            lo = pw_low or s.get("min", 0)
            hi = pw_high or s.get("max", 0)
            if isinstance(lo, (int, float)) and float(lo) > 20 and ftp > 0:
                lo = round(float(lo) / ftp * 100)
            if isinstance(hi, (int, float)) and float(hi) > 20 and ftp > 0:
                hi = round(float(hi) / ftp * 100)
            msg.target_type = WorkoutStepTarget.POWER
            msg.custom_target_power_low = int(lo) if lo else 0
            msg.custom_target_power_high = int(hi) if hi else 0
        elif target == "PACE":
            lo = _parse_pace_to_ms(pc_low or s.get("min", 0))
            hi = _parse_pace_to_ms(pc_high or s.get("max", 0))
            msg.target_type = WorkoutStepTarget.SPEED
            msg.custom_target_speed_low = float(lo)
            msg.custom_target_speed_high = float(hi)
        else:
            msg.duration_type = WorkoutStepDuration.TIME
            msg.duration_time = dur

        builder.add(msg)

    fit_file = builder.build()
    return fit_file.to_bytes()


def _build_fit_template(sport, steps, max_hr, ftp):
    """Minimal FIT builder using a known-good template pattern.

    Constructs a simple single-definition FIT file with file_id,
    workout, and workout_step messages.  Avoids external dependencies.
    """
    buf = bytearray()

    # ── Header (12 bytes) ──────────────────────────────────────────
    buf.append(0x0E)            # header size (14)
    buf.append(0x10)            # protocol version
    buf.append(0x00)            # profile version low
    buf.append(0x00)            # profile version high
    buf.extend(b"\x00\x00\x00\x00")  # data size (placeholder)
    buf.extend(b".FIT")          # data type

    # ── Helpers ─────────────────────────────────────────────────────
    def emit_define(local_num, global_num, fields):
        """fields: list of (field_num, size, base_type)."""
        buf.append(0x40 | local_num)
        buf.append(0x00)  # reserved
        buf.append(0x01)  # little-endian
        buf.extend(struct.pack("<H", global_num))
        buf.append(len(fields))
        for fn, fs, ft in fields:
            buf.extend([fn, fs, ft])
        buf.append(local_num)
        return buf

    def u8(v): return struct.pack("<B", v & 0xFF)
    def u16(v): return struct.pack("<H", v & 0xFFFF)
    def u32(v): return struct.pack("<I", v & 0xFFFFFFFF)
    def f32(v): return struct.pack("<f", float(v))

    # ── File ID message (global 0) ─────────────────────────────────
    # fields: type(0,1,enum), manufacturer(1,2,uint16), product(2,2,uint16),
    #         serial(3,4,uint32z), time_created(4,4,uint32)
    emit_define(0, 0, [
        (0, 1, 0x00), (1, 2, 0x84), (2, 2, 0x84),
        (3, 4, 0x8C), (4, 4, 0x86),
    ])
    buf.append(0x06)  # type = workout
    buf.extend(u16(1))  # manufacturer = garmin
    buf.extend(u16(0))  # product
    buf.extend(u32(0))  # serial
    buf.extend(u32(0))  # time_created (0 = not set)

    # ── Workout message (global 26) ─────────────────────────────────
    # fields: sport(4,1,enum), sub_sport(5,2,uint16), num_valid_steps(8,4,uint32)
    sport_enum = {"Run": 1, "Ride": 2, "VirtualRide": 2}.get(sport, 2)
    emit_define(1, 26, [
        (4, 1, 0x00), (11, 2, 0x84), (14, 4, 0x86),
    ])
    buf.append(sport_enum)
    buf.extend(u16(0))  # sub_sport
    buf.extend(u32(len(steps)))

    # ── Workout Step messages (global 27) ───────────────────────────
    for si, s in enumerate(steps):
        dur = int(s.get("duration_sec", 0))
        stype = str(s.get("type", "ACTIVE")).upper()
        target = str(s.get("target", "")).upper()
        name = str(s.get("name", ""))[:16]

        hr_low = s.get("hr_min") or s.get("min")
        hr_high = s.get("hr_max") or s.get("max")
        pw_low = s.get("power_pct_min") or s.get("power_min") or s.get("min")
        pw_high = s.get("power_pct_max") or s.get("power_max") or s.get("max")
        pc_low = s.get("pace_min") or s.get("min")
        pc_high = s.get("pace_max") or s.get("max")

        if not target:
            if hr_low is not None:
                target = "HR"
            elif pw_low is not None:
                target = "POWER"
            elif pc_low is not None:
                target = "PACE"

        intensity = {"WARMUP": 1, "ACTIVE": 0, "REST": 3, "COOLDOWN": 2}.get(stype, 0)
        ttype = {"HR": 1, "POWER": 2, "PACE": 0}.get(target, 0)

        emit_define(2 + si, 27, [
            (1, 1, 0x00),   # duration_type
            (2, 4, 0x86),   # duration_value
            (3, 1, 0x00),   # target_type
            (5, 4, 0x86),   # custom_target_value_low
            (6, 4, 0x86),   # custom_target_value_high
            (7, 1, 0x00),   # intensity
            (8, 16, 0x07),  # name (string)
        ])

        buf.append(0x00)  # duration_type = time
        buf.extend(u32(dur))

        buf.append(ttype)

        if target == "HR":
            lo = int(hr_low or 0)
            hi = int(hr_high or 0)
            if max_hr > 0:
                lo = max(1, min(100, round(lo / max_hr * 100)))
                hi = max(1, min(100, round(hi / max_hr * 100)))
            buf.extend(u32(lo))
            buf.extend(u32(hi))
        elif target == "POWER":
            lo_val = float(pw_low or 0)
            hi_val = float(pw_high or 0)
            if lo_val > 20 and ftp > 0:
                lo_val = round(lo_val / ftp * 100)
            if hi_val > 20 and ftp > 0:
                hi_val = round(hi_val / ftp * 100)
            buf.extend(u32(int(lo_val)))
            buf.extend(u32(int(hi_val)))
        elif target == "PACE":
            lo = _parse_pace_to_ms(pc_low)
            hi = _parse_pace_to_ms(pc_high)
            # Speed in m/s stored as float in uint32 field
            buf.extend(f32(lo))
            buf.extend(f32(hi))
        else:
            buf.extend(u32(0))
            buf.extend(u32(0))

        buf.append(intensity)
        buf.extend(name.encode("utf-8")[:16].ljust(16, b"\x00"))

    # ── CRC ──────────────────────────────────────────────────────────
    data_size = len(buf) - 14
    struct.pack_into("<I", buf, 4, data_size)

    # CRC16-CCITT
    crc = 0
    for byte in bytes(buf):
        crc = ((crc >> 4) & 0x0FFF) ^ [
            0x0000, 0xCC01, 0xD801, 0x1400, 0xF001, 0x3C00, 0x2800, 0xE401,
            0xA001, 0x6C00, 0x7800, 0xB401, 0x5000, 0x9C01, 0x8801, 0x4400,
        ][(crc ^ byte) & 0xF]
        crc = ((crc >> 4) & 0x0FFF) ^ [
            0x0000, 0xCC01, 0xD801, 0x1400, 0xF001, 0x3C00, 0x2800, 0xE401,
            0xA001, 0x6C00, 0x7800, 0xB401, 0x5000, 0x9C01, 0x8801, 0x4400,
        ][(crc ^ (byte >> 4)) & 0xF]
    buf.extend(struct.pack("<H", crc & 0xFFFF))

    return bytes(buf)


# ── Credential helpers ─────────────────────────────────────────────────────


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
