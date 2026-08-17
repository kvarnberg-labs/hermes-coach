"""Create planned events on intervals.icu calendar.

Uses the intervals.icu REST API to POST new events to the athlete's calendar.
The event appears on intervals.icu and syncs to Garmin automatically.

Structured workout steps (for Garmin step-by-step guidance) are uploaded as
FIT files via file_contents_base64.  FIT generation requires the fit-tool
package (installed in the runtime image).

Authentication uses the same credential files as other intervals.icu tools:
  $HERMES_HOME/users/<discord_id>/intervals_key
  $HERMES_HOME/users/<discord_id>/intervals_athlete_id
"""

from __future__ import annotations

import base64
import json
from datetime import date
from typing import Any

from ._credentials import _load_credentials, _require_user_id
from ._http import _delete_json, _post_json, _request

# ── Sport metadata ──────────────────────────────────────────────────────────
# Single source of truth mapping intervals.icu event_type -> (FIT Sport enum
# name, event-level target). Both the FIT `sport` field and the calendar
# event target derive from this, so they can never diverge (the old bug: runs
# whose event target said PACE were written into the FIT as CYCLING).
# The Sport name is resolved with getattr(..., GENERIC) so an unknown/typo'd
# name degrades to a generic workout instead of raising.
_SPORT_META: dict[str, tuple[str, str | None]] = {
    "Run":              ("RUNNING", "PACE"),
    "TrailRun":         ("RUNNING", "PACE"),
    "VirtualRun":       ("RUNNING", "PACE"),
    "Ride":             ("CYCLING", "POWER"),
    "VirtualRide":      ("CYCLING", "POWER"),
    "GravelRide":       ("CYCLING", "POWER"),
    "MountainBikeRide": ("CYCLING", "POWER"),
    "Swim":             ("SWIMMING", None),
    "OpenWaterSwim":    ("SWIMMING", None),
    "Walk":             ("WALKING", None),
    "Hike":             ("HIKING", None),
    "Rowing":           ("ROWING", None),
}


def _sport_target(event_type: str) -> str | None:
    """Event-level target for a sport, or None if the sport has no default."""
    return _SPORT_META.get(event_type, (None, None))[1]


# intervals.icu sport-settings are keyed by base activity type (Run, Ride,
# Swim, ...). Variant event types (TrailRun, VirtualRide, GravelRide) share
# their base type's FTP/max_hr — the athlete configures "Run", not "TrailRun"
# — so fetch settings for the canonical base type. Querying the variant
# directly can 404 (no settings entry with that id), leaving max_hr/ftp=0.
_FIT_TO_ICU_SPORT = {
    "RUNNING": "Run", "CYCLING": "Ride", "SWIMMING": "Swim",
    "WALKING": "Walk", "HIKING": "Hike", "ROWING": "Rowing",
}


def _settings_sport(event_type: str) -> str:
    """Canonical intervals.icu sport for the sport-settings URL."""
    fit_name = _SPORT_META.get(event_type, ("GENERIC", None))[0]
    return _FIT_TO_ICU_SPORT.get(fit_name, event_type)


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


def _validate_fit_targets(steps: list[dict], max_hr: int, ftp: int) -> None:
    """Refuse inputs FIT would silently misread as dangerous targets.

    Garmin/Intervals interpret FIT power targets as %FTP and HR targets as
    %maxHR. Writing raw watts with no FTP, or raw BPM with no max_hr, would be
    read as a percentage (e.g. 200W -> 200% FTP). The call site (create_event)
    guards the user-facing path; this puts the invariant next to the
    conversion so the builder is safe to call directly.
    """
    for s in steps:
        is_pct = bool(s.get("power_pct_min") or s.get("power_pct_max"))
        # Treat 0 as absent — tool schemas serialize omitted numeric fields as 0.
        has_watts = s.get("power_min") not in (None, 0) or s.get("power_max") not in (None, 0)
        if has_watts and not is_pct and ftp <= 0:
            # Any watt value with no FTP would be read as %FTP by Garmin
            # (e.g. 10W -> 10%). Require FTP for watts; use power_pct_* for %.
            # Matches the call-site guard in create_event (no <=20 guess).
            raise ValueError(
                "watt-based power target cannot be safely converted to %FTP "
                "without the athlete's FTP. Specify power_pct_min/power_pct_max."
            )
        # Same 0-as-absent treatment for HR.
        has_hr = s.get("hr_min") not in (None, 0) or s.get("hr_max") not in (None, 0)
        if has_hr and max_hr <= 0:
            raise ValueError(
                "HR target cannot be safely converted to %maxHR without the "
                "athlete's max_hr."
            )


def _step_message(s: dict, max_hr: int, ftp: int, primary: str | None = None):
    """Build one WorkoutStepMessage from a step dict.

    Owns target auto-detection, the watts->%FTP and BPM->%maxHR conversions,
    and pace parsing. FIT encodes one target per step, so only one detected
    target is written. When the sport has a primary target (`primary`, e.g.
    PACE for runs, POWER for rides) and the step supplies it, that wins so the
    step matches the event target; otherwise fall back to HR > POWER > PACE.
    """
    from fit_tool.profile.messages.workout_step_message import WorkoutStepMessage
    from fit_tool.profile.profile_type import (
        Intensity, WorkoutStepDuration, WorkoutStepTarget,
    )

    intensity_map = {"WARMUP": Intensity.WARMUP, "ACTIVE": Intensity.ACTIVE,
                     "REST": Intensity.REST, "COOLDOWN": Intensity.COOLDOWN}

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
        has_hr = hr_low is not None or hr_high is not None
        has_pw = pw_low is not None or pw_high is not None
        has_pc = pc_low is not None or pc_high is not None
        if primary == "PACE" and has_pc:
            target = "PACE"
        elif primary == "POWER" and has_pw:
            target = "POWER"
        elif has_hr:
            target = "HR"
        elif has_pw:
            target = "POWER"
        elif has_pc:
            target = "PACE"

    msg = WorkoutStepMessage()
    msg.workout_step_name = name
    desc = s.get("description")
    if isinstance(desc, str) and desc.strip():
        msg.notes = desc.strip()[:255]  # cap notes; no FIT spec max, defensive
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
        # Pace is inverse to speed; normalize converted bounds for FIT.
        pace_a = _parse_pace_to_ms(pc_low or s.get("min", 0))
        pace_b = _parse_pace_to_ms(pc_high or s.get("max", 0))
        lo, hi = sorted((pace_a, pace_b))
        msg.target_type = WorkoutStepTarget.SPEED
        msg.custom_target_speed_low = float(lo)
        msg.custom_target_speed_high = float(hi)

    return msg


def _build_fit_file(
    sport: str,
    steps: list[dict],
    max_hr: int,
    ftp: int,
) -> bytes:
    """Build a FIT workout file from step definitions using fit-tool."""
    _validate_fit_targets(steps, max_hr, ftp)

    from fit_tool.fit_file_builder import FitFileBuilder
    from fit_tool.profile.messages.workout_message import WorkoutMessage
    from fit_tool.profile.messages.file_id_message import FileIdMessage
    from fit_tool.profile.profile_type import Sport, FileType

    sport_name = _SPORT_META.get(sport, ("GENERIC", None))[0]
    primary = _sport_target(sport)

    builder = FitFileBuilder(auto_define=True)

    fid = FileIdMessage()
    fid.type = FileType.WORKOUT
    builder.add(fid)

    w = WorkoutMessage()
    w.sport = getattr(Sport, sport_name, Sport.GENERIC)
    w.num_valid_steps = len(steps)
    builder.add(w)

    for s in steps:
        builder.add(_step_message(s, max_hr, ftp, primary))

    return builder.build().to_bytes()


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

    # Refuse any step without a positive duration. The FIT builder always
    # writes duration_type=TIME, so a step missing duration_sec encodes a
    # 0-second block that intervals.icu accepts as a broken workout (the model
    # then loops create→delete). This is per-step, not list-wide: one junk step
    # ([{}], [{"target":"PACE"}] with no bounds, or a good step + a trailing {})
    # is enough to reject, so a single empty step can't ride along on a
    # partially-valid list.
    if step_list:
        empty = [i for i, s in enumerate(step_list) if not s.get("duration_sec")]
        if empty:
            return json.dumps({"error": (
                f"steps {empty} are empty — no duration_sec. Every step needs a "
                "positive duration_sec, plus a target: pace_min/pace_max "
                "(running), hr_min/hr_max (BPM), power_min/power_max (watts) or "
                "power_pct_min/power_pct_max (% FTP)."
            )})

    # Set event-level target and generate FIT file for structured steps
    if step_list:
        target = _sport_target(event_type)
        if target:
            payload["target"] = target

        # Both FTP and max_hr come from the per-sport settings endpoint. The
        # profile endpoint does NOT return max_hr (verified against the
        # intervals.icu OpenAPI spec: max_hr is on SportSettings, not Athlete),
        # so the old separate profile fetch always read max_hr=0. One call, one
        # try: a guessed max_hr/FTP would convert real targets against the
        # wrong reference, so default to 0 and let the guards below refuse.
        ftp = 0
        max_hr = 0
        try:
            settings = _request(
                athlete_id, api_key,
                f"/athlete/{athlete_id}/sport-settings/{_settings_sport(event_type)}",
                timeout=10,
            )
            ftp = settings.get("ftp") or 0
            if indoor:
                # Zwift/trainer events use a separate FTP; fall back to outdoor
                # ftp if indoor_ftp isn't set. max_hr is physiological (same
                # indoors and out).
                ftp = settings.get("indoor_ftp") or ftp
            max_hr = settings.get("max_hr") or 0
        except Exception:
            pass

        # Safety: FIT power targets are interpreted by Garmin as %FTP. If we
        # could not fetch the athlete's FTP, watt-based targets would be
        # written verbatim and read as %FTP (e.g. 200W -> 200% FTP = a
        # dangerous target). Refuse rather than prescribe a dangerous workout.
        # %FTP steps (power_pct_*) are safe — they don't need the athlete's FTP.
        # Not scoped to cycling: watt targets are dangerous for any sport.
        if ftp <= 0:
            needs_ftp = any(
                # Tool schemas may serialize omitted numeric fields as 0;
                # zero is not a real watt target.
                (s.get("power_min") not in (None, 0) or s.get("power_max") not in (None, 0))
                and not (s.get("power_pct_min") or s.get("power_pct_max"))
                for s in step_list
            )
            if needs_ftp:
                return json.dumps({
                    "error": (
                        "Could not retrieve the athlete's FTP from intervals.icu, "
                        "so watt-based power targets cannot be safely converted to "
                        "%FTP for the FIT file. Retry, or specify targets as "
                        "power_pct_min/power_pct_max (% FTP) directly."
                    ),
                })

        # Same safety stance for HR: FIT HR targets are read as %maxHR, so a
        # BPM target with no known max_hr would be misread. Refuse instead of
        # converting against a guess (mirrors the FTP guard above).
        if max_hr <= 0:
            needs_hr = any(
                s.get("hr_min") is not None or s.get("hr_max") is not None
                for s in step_list
            )
            if needs_hr:
                return json.dumps({
                    "error": (
                        "Could not retrieve the athlete's max_hr from "
                        "intervals.icu, so HR targets (BPM) cannot be safely "
                        "converted to %maxHR for the FIT file. Retry, or specify "
                        "targets as pace or power_pct instead."
                    ),
                })

        try:
            fit_bytes = _build_fit_file(event_type, step_list, max_hr, ftp)
        except ValueError as exc:
            return json.dumps({"error": str(exc)})
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
                    "Structured workout steps for Garmin live guidance. Each step "
                    "needs duration_sec and exactly one target: pace_min/pace_max "
                    "(running, '5:40' = 5min40sec/km), hr_min/hr_max (BPM), "
                    "power_min/power_max (watts, needs athlete FTP) or "
                    "power_pct_min/power_pct_max (% FTP). target is auto-detected "
                    "from which fields you fill."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Short step label, e.g. 'Interval'."},
                        "duration_sec": {"type": "integer", "description": "Step duration in seconds."},
                        "type": {"type": "string", "enum": ["WARMUP", "ACTIVE", "REST", "COOLDOWN"], "description": "Step intensity."},
                        "target": {"type": "string", "description": "Explicit target HR/POWER/PACE; auto-detected if omitted."},
                        "description": {"type": "string", "description": "Optional step notes."},
                        "hr_min": {"type": "integer", "description": "HR target low (BPM)."},
                        "hr_max": {"type": "integer", "description": "HR target high (BPM)."},
                        "power_min": {"type": "integer", "description": "Power target low (watts). Needs athlete FTP."},
                        "power_max": {"type": "integer", "description": "Power target high (watts). Needs athlete FTP."},
                        "power_pct_min": {"type": "integer", "description": "Power target low (% FTP)."},
                        "power_pct_max": {"type": "integer", "description": "Power target high (% FTP)."},
                        "pace_min": {"type": "string", "description": "Pace fast bound, e.g. '5:30' (min:sec/km)."},
                        "pace_max": {"type": "string", "description": "Pace slow bound, e.g. '6:00' (min:sec/km)."},
                    },
                },
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
