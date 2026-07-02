"""intervals.icu API integration for Hermes Coach.

Provides 6 tools for fetching athlete training data:

  get_athlete_profile   — basic profile, weight, timezone
  get_sport_settings    — FTP, zones, LTHR, W' for a given sport
  get_recent_activities — last N days of completed workouts
  get_wellness          — CTL, ATL, TSB, HRV, sleep, weight over a date range
  get_planned_events    — upcoming calendar workouts and races
  get_power_curve       — peak power curve for a sport over a date range

Authentication:
  intervals.icu uses HTTP Basic Auth.
  Username is the literal string "API_KEY".
  Password is the user's personal API key.
  The athlete self-reference in URL paths is the string "i".

User keys are stored per-Discord-user in:
  $HERMES_HOME/users/<discord_id>/intervals_key   (age-encrypted)

Cache:
  Raw API responses are cached under:
  $HERMES_HOME/users/<discord_id>/cache/<endpoint_hash>.json
  with a configurable TTL (default 15 minutes for activities/wellness,
  6 hours for profile/sport-settings).
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Discord snowflake IDs are 17–20 decimal digits, never all-zeros.
_DISCORD_ID_RE = re.compile(r"^[1-9]\d{16,19}$")


_FALLBACK_USER_ID = "discord_dm"


def _require_user_id(kw: dict) -> str:
    """Return the Discord snowflake from the gateway, or 'discord_dm' as fallback.

    Fallback is used when the gateway doesn't inject user_id (cron sessions,
    non-Discord contexts). Real Discord sessions always get the snowflake path.
    """
    uid = str(kw.get("user_id", ""))
    return uid if _DISCORD_ID_RE.match(uid) else _FALLBACK_USER_ID


_API_BASE = "https://intervals.icu/api/v1"

# Cache TTLs in seconds
_TTL_PROFILE = 6 * 3600  # athlete profile changes rarely
_TTL_SPORT_SETTINGS = 6 * 3600
_TTL_ACTIVITIES = 15 * 60  # workouts update after syncing a ride
_TTL_WELLNESS = 15 * 60
_TTL_EVENTS = 15 * 60
_TTL_POWER_CURVE = 30 * 60


# ---------------------------------------------------------------------------
# Key storage
# ---------------------------------------------------------------------------


def _user_dir(discord_id: str) -> Path:
    hermes_home = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
    d = hermes_home / "users" / str(discord_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _key_path(discord_id: str) -> Path:
    return _user_dir(discord_id) / "intervals_key"


def _athlete_id_path(discord_id: str) -> Path:
    return _user_dir(discord_id) / "intervals_athlete_id"


def store_user_credentials(discord_id: str, athlete_id: str, api_key: str) -> None:
    """Persist an athlete's intervals.icu credentials.

    In production the key file should be encrypted with age.  For v1 we
    write plaintext with mode 0600 — the PVC is not world-readable, and
    the file is only accessible inside the container.  A TODO to add age
    encryption is tracked in the issue tracker.
    """
    key_file = _key_path(discord_id)
    key_file.write_text(api_key, encoding="utf-8")
    key_file.chmod(0o600)

    id_file = _athlete_id_path(discord_id)
    id_file.write_text(athlete_id.strip(), encoding="utf-8")
    id_file.chmod(0o600)
    logger.info("Stored intervals.icu credentials for discord_id=%s", discord_id)


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


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------


def _cache_dir(discord_id: str) -> Path:
    d = _user_dir(discord_id) / "cache"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _cache_key(endpoint: str, params: dict) -> str:
    raw = endpoint + json.dumps(params, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _cache_get(discord_id: str, cache_key: str, ttl: int) -> Optional[Any]:
    path = _cache_dir(discord_id) / f"{cache_key}.json"
    if not path.exists():
        return None
    age = time.time() - path.stat().st_mtime
    if age > ttl:
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _cache_set(discord_id: str, cache_key: str, data: Any) -> None:
    path = _cache_dir(discord_id) / f"{cache_key}.json"
    path.write_text(json.dumps(data), encoding="utf-8")


# ---------------------------------------------------------------------------
# HTTP client
# ---------------------------------------------------------------------------


def _auth_header(api_key: str) -> str:
    """Build the Basic Auth header value for intervals.icu."""
    token = base64.b64encode(f"API_KEY:{api_key}".encode()).decode()
    return f"Basic {token}"


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
        raise RuntimeError(f"intervals.icu API error {exc.code}: {exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Could not reach intervals.icu: {exc.reason}") from exc


def _today_iso() -> str:
    return date.today().isoformat()


def _n_days_ago_iso(n: int) -> str:
    return (date.today() - timedelta(days=n)).isoformat()


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------


def get_athlete_profile(discord_id: str, **_: Any) -> str:
    """Fetch the athlete's basic profile from intervals.icu.

    Returns name, weight, timezone, VO2max estimate, and resting HR.
    """
    try:
        athlete_id, api_key = _load_credentials(discord_id)
    except ValueError as exc:
        return json.dumps({"error": str(exc)})

    ck = _cache_key(f"/athlete/{athlete_id}", {})
    cached = _cache_get(discord_id, ck, _TTL_PROFILE)
    if cached is not None:
        return json.dumps(cached)

    try:
        data = _request(athlete_id, api_key, f"/athlete/{athlete_id}")
    except (ValueError, RuntimeError) as exc:
        return json.dumps({"error": str(exc)})

    result = {
        "source": "intervals.icu",
        "athlete_id": athlete_id,
        "name": data.get("name"),
        "timezone": data.get("timezone"),
        "weight_kg": data.get("icu_weight"),
        "resting_hr": data.get("icu_resting_hr"),
        "sex": data.get("sex"),
        "date_of_birth": data.get("icu_date_of_birth"),
    }
    _cache_set(discord_id, ck, result)
    return json.dumps(result)


def get_sport_settings(discord_id: str, sport: str = "Ride", **_: Any) -> str:
    """Fetch FTP, power zones, and LTHR for a given sport.

    Args:
        sport: intervals.icu sport type e.g. "Ride", "Run", "Swim".
               Defaults to "Ride".
    """
    try:
        athlete_id, api_key = _load_credentials(discord_id)
    except ValueError as exc:
        return json.dumps({"error": str(exc)})

    ck = _cache_key(f"/athlete/{athlete_id}/sport-settings/{sport}", {})
    cached = _cache_get(discord_id, ck, _TTL_SPORT_SETTINGS)
    if cached is not None:
        return json.dumps(cached)

    try:
        data = _request(
            athlete_id, api_key, f"/athlete/{athlete_id}/sport-settings/{sport}"
        )
    except (ValueError, RuntimeError) as exc:
        return json.dumps({"error": str(exc)})

    result = {
        "source": "intervals.icu",
        "sport": sport,
        "ftp": data.get("ftp"),
        "indoor_ftp": data.get("indoor_ftp"),
        "lthr": data.get("lthr"),
        "max_hr": data.get("max_hr"),
        "w_prime": data.get("w_prime"),
        "power_zones": data.get("power_zones"),
        "hr_zones": data.get("hr_zones"),
        "pace_zones": data.get("pace_zones"),
    }
    _cache_set(discord_id, ck, result)
    return json.dumps(result)


def get_recent_activities(
    discord_id: str,
    days: int = 14,
    sport: Optional[str] = None,
    **_: Any,
) -> str:
    """Fetch completed workouts over the past N days.

    Args:
        days:  How many days back to look (default 14, max 90).
        sport: Filter by sport type e.g. "Ride", "Run". None means all sports.

    Returns key fields per activity: date, type, duration, distance,
    training load (ATL/CTL impulse), normalized power, intensity factor, RPE.
    """
    days = min(int(days), 90)
    try:
        athlete_id, api_key = _load_credentials(discord_id)
    except ValueError as exc:
        return json.dumps({"error": str(exc)})

    params: dict = {
        "oldest": _n_days_ago_iso(days),
        "newest": _today_iso(),
        # Request only the fields we need to keep the payload small
        "fields": (
            "id,name,start_date_local,type,moving_time,distance,"
            "icu_training_load,icu_ctl,icu_atl,icu_intensity,"
            "icu_weighted_avg_watts,icu_ftp,trimp,hr_load,power_load,"
            "icu_rpe,feel,session_rpe"
        ),
    }
    if sport:
        params["type"] = sport

    ck = _cache_key(f"/athlete/{athlete_id}/activities", params)
    cached = _cache_get(discord_id, ck, _TTL_ACTIVITIES)
    if cached is not None:
        return json.dumps(cached)

    try:
        data = _request(
            athlete_id, api_key, f"/athlete/{athlete_id}/activities", params
        )
    except (ValueError, RuntimeError) as exc:
        return json.dumps({"error": str(exc)})

    activities = []
    for act in data if isinstance(data, list) else [data]:
        activities.append(
            {
                "id": act.get("id"),
                "name": act.get("name"),
                "date": act.get("start_date_local", "")[:10],
                "type": act.get("type"),
                "duration_min": round((act.get("moving_time") or 0) / 60, 1),
                "distance_km": round((act.get("distance") or 0) / 1000, 2),
                "training_load": act.get("icu_training_load"),
                "ctl_after": act.get("icu_ctl"),
                "atl_after": act.get("icu_atl"),
                "intensity_factor": act.get("icu_intensity"),
                "normalized_power_w": act.get("icu_weighted_avg_watts"),
                "ftp_used_w": act.get("icu_ftp"),
                "trimp": act.get("trimp"),
                "rpe": act.get("icu_rpe") or act.get("session_rpe") or act.get("feel"),
            }
        )

    result = {
        "source": "intervals.icu",
        "days": days,
        "count": len(activities),
        "activities": activities,
    }
    _cache_set(discord_id, ck, result)
    return json.dumps(result)


def get_wellness(
    discord_id: str,
    days: int = 7,
    **_: Any,
) -> str:
    """Fetch wellness records over the past N days.

    Includes CTL (fitness), ATL (fatigue), TSB (form), HRV, sleep,
    resting HR, weight, and subjective feel scores.

    Args:
        days: How many days back (default 7, max 42).
    """
    days = min(int(days), 42)
    try:
        athlete_id, api_key = _load_credentials(discord_id)
    except ValueError as exc:
        return json.dumps({"error": str(exc)})

    params = {
        "oldest": _n_days_ago_iso(days),
        "newest": _today_iso(),
    }

    ck = _cache_key(f"/athlete/{athlete_id}/wellness", params)
    cached = _cache_get(discord_id, ck, _TTL_WELLNESS)
    if cached is not None:
        return json.dumps(cached)

    try:
        data = _request(athlete_id, api_key, f"/athlete/{athlete_id}/wellness", params)
    except (ValueError, RuntimeError) as exc:
        return json.dumps({"error": str(exc)})

    records = []
    for w in data if isinstance(data, list) else [data]:
        ctl = w.get("ctl")
        atl = w.get("atl")
        # Require both to be present: TSB is meaningless if one side is unknown.
        # Using `and` (not `or`) avoids treating a missing ATL as zero and returning
        # a spurious positive TSB. The old `if ctl and atl` additionally broke on 0.0.
        tsb = round(ctl - atl, 1) if ctl is not None and atl is not None else None
        records.append(
            {
                "date": w.get("id"),  # wellness id is the ISO date string
                "ctl": round(ctl, 1) if ctl is not None else None,
                "atl": round(atl, 1) if atl is not None else None,
                "tsb": tsb,
                "ramp_rate": w.get("rampRate"),
                "hrv": w.get("hrv"),
                "hrv_sdnn": w.get("hrvSDNN"),
                "resting_hr": w.get("restingHR"),
                "sleep_hours": round((w.get("sleepSecs") or 0) / 3600, 1) or None,
                "sleep_quality": w.get("sleepQuality"),
                "sleep_score": w.get("sleepScore"),
                "readiness": w.get("readiness"),
                "weight_kg": w.get("weight"),
                "fatigue": w.get("fatigue"),
                "soreness": w.get("soreness"),
                "motivation": w.get("motivation"),
                "mood": w.get("mood"),
            }
        )

    result = {
        "source": "intervals.icu",
        "days": days,
        "records": records,
        # Convenience: today's values at top level for quick access
        "today": records[-1] if records else None,
    }
    _cache_set(discord_id, ck, result)
    return json.dumps(result)


def get_planned_events(
    discord_id: str,
    days_ahead: int = 14,
    **_: Any,
) -> str:
    """Fetch upcoming planned workouts and races from the athlete's calendar.

    Args:
        days_ahead: How many days forward to look (default 14, max 90).
    """
    days_ahead = min(int(days_ahead), 90)
    try:
        athlete_id, api_key = _load_credentials(discord_id)
    except ValueError as exc:
        return json.dumps({"error": str(exc)})

    today = _today_iso()
    params = {
        "oldest": today,
        "newest": (date.today() + timedelta(days=days_ahead)).isoformat(),
    }

    ck = _cache_key(f"/athlete/{athlete_id}/events", params)
    cached = _cache_get(discord_id, ck, _TTL_EVENTS)
    if cached is not None:
        return json.dumps(cached)

    try:
        data = _request(athlete_id, api_key, f"/athlete/{athlete_id}/events", params)
    except (ValueError, RuntimeError) as exc:
        return json.dumps({"error": str(exc)})

    events = []
    for ev in data if isinstance(data, list) else [data]:
        events.append(
            {
                "id": ev.get("id"),
                "date": (ev.get("start_date_local") or "")[:10],
                "category": ev.get("category"),
                "type": ev.get("type"),
                "name": ev.get("name"),
                "description": ev.get("description"),
                "planned_load": ev.get("icu_training_load"),
                "planned_intensity": ev.get("icu_intensity"),
                "projected_ctl": ev.get("icu_ctl"),
                "projected_atl": ev.get("icu_atl"),
                "time_target_min": round((ev.get("time_target") or 0) / 60, 1) or None,
                "distance_target_km": round((ev.get("distance_target") or 0) / 1000, 2)
                or None,
            }
        )

    result = {
        "source": "intervals.icu",
        "days_ahead": days_ahead,
        "count": len(events),
        "events": events,
    }
    _cache_set(discord_id, ck, result)
    return json.dumps(result)


def get_power_curve(
    discord_id: str,
    sport: str = "Ride",
    days: int = 42,
    **_: Any,
) -> str:
    """Fetch the athlete's peak power curve over a date range.

    Returns best power at standard durations (5s, 1min, 5min, 20min, 60min).

    Args:
        sport: Sport type (default "Ride").
        days:  How many days to look back (default 42, max 365).
    """
    days = min(int(days), 365)
    try:
        athlete_id, api_key = _load_credentials(discord_id)
    except ValueError as exc:
        return json.dumps({"error": str(exc)})

    params = {
        "type": sport,
        "oldest": _n_days_ago_iso(days),
        "newest": _today_iso(),
    }

    ck = _cache_key(f"/athlete/{athlete_id}/power-curves", params)
    cached = _cache_get(discord_id, ck, _TTL_POWER_CURVE)
    if cached is not None:
        return json.dumps(cached)

    try:
        data = _request(
            athlete_id, api_key, f"/athlete/{athlete_id}/power-curves", params
        )
    except (ValueError, RuntimeError) as exc:
        return json.dumps({"error": str(exc)})

    # data is a list of {secs, watts} points; extract standard durations
    _DURATIONS = {5: "5s", 60: "1min", 300: "5min", 1200: "20min", 3600: "60min"}
    curve_map: dict[int, float] = {}
    raw_curves = data if isinstance(data, list) else []
    for point in raw_curves:
        secs = point.get("secs") or point.get("t")
        watts = point.get("watts") or point.get("w")
        if secs is not None and watts is not None:
            curve_map[int(secs)] = round(float(watts), 1)

    peaks = {label: curve_map.get(secs) for secs, label in _DURATIONS.items()}

    result = {
        "source": "intervals.icu",
        "sport": sport,
        "days": days,
        "peak_power": peaks,
        "full_curve_points": len(curve_map),
    }
    _cache_set(discord_id, ck, result)
    return json.dumps(result)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def register_tools(ctx) -> None:
    """Register all intervals.icu tools with the Hermes plugin context."""

    def _tool(name: str, description: str, properties: dict, required: list, fn):
        # Strip discord_id from model-visible schema — identity comes exclusively
        # from the gateway (kw["user_id"]), never from model-supplied arguments (M1).
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

    # discord_id is kept as a sentinel in properties dicts so the filtering above
    # can strip it; it is never sent to the model.
    _DISCORD_ID_PROP = {
        "discord_id": {
            "type": "string",
            "description": "Discord user ID of the athlete to look up.",
        }
    }

    _tool(
        name="get_athlete_profile",
        description=(
            "Fetch the athlete's basic profile from intervals.icu: "
            "name, weight, timezone, resting HR."
        ),
        properties=_DISCORD_ID_PROP,
        required=["discord_id"],
        fn=get_athlete_profile,
    )

    _tool(
        name="get_sport_settings",
        description=(
            "Fetch FTP, power zones, LTHR, and W' for the athlete's chosen sport. "
            "Use sport='Ride' for cycling (default), 'Run' for running."
        ),
        properties={
            **_DISCORD_ID_PROP,
            "sport": {
                "type": "string",
                "description": "Sport type: 'Ride', 'Run', 'Swim', etc. Defaults to 'Ride'.",
                "default": "Ride",
            },
        },
        required=["discord_id"],
        fn=get_sport_settings,
    )

    _tool(
        name="get_recent_activities",
        description=(
            "Fetch completed workouts from intervals.icu. "
            "Returns training load, intensity, normalized power, and RPE per activity. "
            "Use this to assess recent training stress before making a recommendation."
        ),
        properties={
            **_DISCORD_ID_PROP,
            "days": {
                "type": "integer",
                "description": "How many days back to fetch (default 14, max 90).",
                "default": 14,
            },
            "sport": {
                "type": "string",
                "description": "Filter by sport type. Leave empty for all sports.",
            },
        },
        required=["discord_id"],
        fn=get_recent_activities,
    )

    _tool(
        name="get_wellness",
        description=(
            "Fetch wellness data from intervals.icu: CTL (fitness), ATL (fatigue), "
            "TSB (form = CTL - ATL), HRV, sleep hours, resting HR, and subjective scores. "
            "Always call this when evaluating readiness or recovery."
        ),
        properties={
            **_DISCORD_ID_PROP,
            "days": {
                "type": "integer",
                "description": "How many days of wellness to fetch (default 7, max 42).",
                "default": 7,
            },
        },
        required=["discord_id"],
        fn=get_wellness,
    )

    _tool(
        name="get_planned_events",
        description=(
            "Fetch the athlete's upcoming planned workouts and races from the intervals.icu calendar. "
            "Use this when checking for A-races, recovery weeks, or planned intensity sessions."
        ),
        properties={
            **_DISCORD_ID_PROP,
            "days_ahead": {
                "type": "integer",
                "description": "How many days forward to look (default 14, max 90).",
                "default": 14,
            },
        },
        required=["discord_id"],
        fn=get_planned_events,
    )

    _tool(
        name="get_power_curve",
        description=(
            "Fetch the athlete's peak power curve from intervals.icu: "
            "best power at 5s, 1min, 5min, 20min, 60min over a date range. "
            "Useful for assessing strengths, weaknesses, and fitness trends."
        ),
        properties={
            **_DISCORD_ID_PROP,
            "sport": {
                "type": "string",
                "description": "Sport type (default 'Ride').",
                "default": "Ride",
            },
            "days": {
                "type": "integer",
                "description": "Days to look back (default 42, max 365).",
                "default": 42,
            },
        },
        required=["discord_id"],
        fn=get_power_curve,
    )
