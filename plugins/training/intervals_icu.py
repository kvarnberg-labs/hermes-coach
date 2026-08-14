"""intervals.icu API integration for Hermes Coach.

Provides 10 tools for fetching athlete training data:

  get_athlete_profile    — basic profile, weight, timezone, sex, DOB
  get_sport_settings     — FTP, zones, LTHR, W', FTP W/kg for a sport
  get_recent_activities  — last N days of completed workouts
  get_wellness           — CTL, ATL, TSB, HRV, sleep, readiness
  get_planned_events     — upcoming calendar workouts and races
  get_power_curve        — peak power curve for a sport over a date range
  get_activity_detail    — full detail for a single activity
  verify_athlete_identity — validate stored credentials match expected athlete
  get_activity_streams   — per-stream data summaries and peak power
  get_fitness_chart      — full CTL/ATL/TSB history (up to 365 days)

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

import json
import logging
from typing import Any, Optional

from ._credentials import (
    _load_credentials,
    _load_verified_name,
    _require_user_id,
    store_user_credentials,  # noqa: F401  (re-exported for tests)
)
from ._http import (
    _TTL_ACTIVITIES,
    _TTL_EVENTS,
    _TTL_POWER_CURVE,
    _TTL_PROFILE,
    _TTL_SPORT_SETTINGS,
    _TTL_WELLNESS,
    _auth_header,  # noqa: F401  (re-exported for tests)
    _cache_get,
    _cache_key,
    _cache_set,
    _n_days_ago_iso,
    _request,
    _today_iso,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------


def _profile_cache_key(athlete_id: str) -> str:
    """Single source for the athlete-profile cache key (shared by the profile
    fetch and the best-effort timezone lookup)."""
    return _cache_key(f"/athlete/{athlete_id}", {})


def _profile_result(discord_id: str, athlete_id: str, api_key: str) -> dict:
    """Fetch + project + cache the athlete profile.

    Single owner of the profile cache entry: both get_athlete_profile and
    get_sport_settings go through here, so the cache always holds the SAME
    projected shape (no raw-vs-projected poisoning) and the cache key is
    constructed in one place. Raises ValueError/RuntimeError on API errors.
    """
    ck = _profile_cache_key(athlete_id)
    cached = _cache_get(discord_id, ck, _TTL_PROFILE)
    if cached is not None:
        return cached
    data = _request(athlete_id, api_key, f"/athlete/{athlete_id}")
    result = {
        "source": "intervals.icu",
        "athlete_id": athlete_id,
        "name": data.get("name"),
        "athlete_name": _load_verified_name(discord_id),
        "timezone": data.get("timezone"),
        "weight_kg": data.get("icu_weight"),
        "resting_hr": data.get("icu_resting_hr"),
        "sex": data.get("sex"),
        "date_of_birth": data.get("icu_date_of_birth"),
    }
    _cache_set(discord_id, ck, result)
    return result


def _athlete_tz(discord_id: str, athlete_id: str) -> Optional[str]:
    """Best-effort athlete timezone from the profile cache (no extra API call).

    Returns None when the profile isn't already cached, so date helpers fall
    back to server-local time. In a coaching session the profile is normally
    fetched early, so the timezone flows to later date-bounded calls for free.
    """
    profile = _cache_get(discord_id, _profile_cache_key(athlete_id), _TTL_PROFILE)
    if isinstance(profile, dict):
        return profile.get("timezone")
    return None


def verify_athlete_identity(discord_id: str, **_: Any) -> str:
    """Verify that stored credentials belong to the expected athlete."""
    try:
        athlete_id, api_key = _load_credentials(discord_id)
    except ValueError as exc:
        return json.dumps({
            "verified": False,
            "error": str(exc),
            "mismatched_fields": ["credentials"],
        })

    stored_name = _load_verified_name(discord_id)

    try:
        data = _request(athlete_id, api_key, f"/athlete/{athlete_id}")
    except (ValueError, RuntimeError) as exc:
        return json.dumps({
            "verified": False,
            "error": str(exc),
            "mismatched_fields": ["api_request"],
        })

    api_name = (data.get("name") or "").strip()
    api_athlete_id = str(data.get("id") or "").strip()

    mismatched = []
    # Actually compare the API-returned id against the stored one. Previously
    # api_athlete_id was set to the stored value, so this check was a tautology
    # and a wrong/stale athlete_id file could never be detected.
    if api_athlete_id and api_athlete_id != athlete_id:
        mismatched.append("athlete_id")
    if stored_name is None:
        mismatched.append("no_stored_name")
    if not api_name:
        mismatched.append("no_api_name")

    result: dict[str, Any] = {
        "verified": len(mismatched) == 0,
        "stored_athlete_id": athlete_id,
        "stored_name": stored_name,
        "api_athlete_id": api_athlete_id or athlete_id,
        "api_name": api_name,
        "has_stored_name": stored_name is not None,
    }
    if mismatched:
        result["mismatched_fields"] = mismatched
        if "athlete_id" in mismatched:
            result["error"] = (
                f"Stored athlete_id {athlete_id!r} does not match the id "
                f"({api_athlete_id!r}) returned by the intervals.icu API. "
                "Re-run /start to re-onboard."
            )
        elif "no_stored_name" in mismatched:
            result["error"] = (
                "Credentials were not written through the onboarding flow "
                "(no stored display name).  Run /start to re-onboard."
            )
        else:
            result["error"] = (
                f"Credential verification failed: {', '.join(mismatched)}. "
                "Re-run /start to re-onboard."
            )
    return json.dumps(result)


def get_athlete_profile(discord_id: str, **_: Any) -> str:
    """Fetch the athlete's basic profile from intervals.icu.

    Returns name, weight, timezone, resting HR, sex, date of birth,
    and Discord display name.
    """
    try:
        athlete_id, api_key = _load_credentials(discord_id)
    except ValueError as exc:
        return json.dumps({"error": str(exc)})
    try:
        result = _profile_result(discord_id, athlete_id, api_key)
    except (ValueError, RuntimeError) as exc:
        return json.dumps({"error": str(exc)})
    return json.dumps(result)


def get_sport_settings(discord_id: str, sport: str = "Ride", **_: Any) -> str:
    """Fetch FTP, indoor FTP, power zones, HR zones, pace zones, LTHR, max HR, W', and FTP W/kg for a given sport.

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

    # Compute W/kg: sport-settings API doesn't return weight, so reuse the
    # projected profile cache (shared with get_athlete_profile via
    # _profile_result) — same shape, no raw-vs-projected cache poisoning.
    ftp = data.get("ftp")
    ftp_w_kg = None
    if ftp:
        try:
            weight_kg = _profile_result(discord_id, athlete_id, api_key).get("weight_kg")
            if weight_kg:
                ftp_w_kg = round(ftp / weight_kg, 2)
        except (ValueError, RuntimeError):
            pass  # weight unavailable — leave ftp_w_kg as None

    result = {
        "source": "intervals.icu",
        "sport": sport,
        "ftp": ftp,
        "indoor_ftp": data.get("indoor_ftp"),
        "ftp_w_kg": ftp_w_kg,
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

    Returns per-activity fields: id, name, date, type, duration, distance,
    training load, CTL/ATL after, intensity factor, normalized power,
    FTP used, trimp, hr_load, power_load, RPE, pace, avg/max HR,
    max speed, elevation gain, and cadence.
    """
    days = min(int(days), 90)
    try:
        athlete_id, api_key = _load_credentials(discord_id)
    except ValueError as exc:
        return json.dumps({"error": str(exc)})

    tz = _athlete_tz(discord_id, athlete_id)
    params: dict = {
        "oldest": _n_days_ago_iso(days, tz),
        "newest": _today_iso(tz),
        # Request all fields needed for both cycling and running coaching.
        "fields": (
            "id,name,start_date_local,type,moving_time,distance,"
            "icu_training_load,icu_ctl,icu_atl,icu_intensity,"
            "icu_weighted_avg_watts,icu_ftp,trimp,hr_load,power_load,"
            "icu_rpe,feel,session_rpe,"
            "pace,avg_pace,avg_heartrate,max_heartrate,max_speed,"
            "total_elevation_gain,avg_cadence"
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
                "hr_load": act.get("hr_load"),
                "power_load": act.get("power_load"),
                "rpe": act.get("icu_rpe") or act.get("session_rpe") or act.get("feel"),
                "pace_mps": act.get("pace") or act.get("avg_pace"),
                "avg_hr": act.get("avg_heartrate"),
                "max_hr": act.get("max_heartrate"),
                "max_speed_mps": act.get("max_speed"),
                "elevation_gain_m": act.get("total_elevation_gain"),
                "avg_cadence": act.get("avg_cadence"),
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


def get_activity_detail(
    discord_id: str,
    activity_id: str,
    **_: Any,
) -> str:
    """Fetch full detail for a single activity including laps, interval summary,
    and HR/power zone data.

    Use this after get_recent_activities when you need to analyze a specific
    workout in depth — interval splits, zone distribution, pacing, and
    lap-by-lap data that the summary endpoint omits.

    Args:
        activity_id: The intervals.icu activity ID (e.g. "i161875412").
                     Obtain this from get_recent_activities output.
    """
    try:
        athlete_id, api_key = _load_credentials(discord_id)
    except ValueError as exc:
        return json.dumps({"error": str(exc)})

    params = {
        "fields": (
            "id,name,start_date_local,type,moving_time,distance,"
            "icu_training_load,icu_intensity,"
            "avg_heartrate,max_heartrate,lthr,"
            "pace,avg_pace,max_speed,"
            "total_elevation_gain,avg_cadence,"
            "icu_lap_count,laps,interval_summary,"
            "icu_hr_zones,icu_hr_zone_times,"
            "icu_power_zones,icu_zone_times,"
            "icu_weighted_avg_watts,icu_average_watts,icu_ftp,"
            "icu_rpe,feel,session_rpe,"
            "calories,carbs_used,coasting_time,"
            "decoupling,icu_variability_index,icu_efficiency_factor,"
            "icu_power_hr,icu_power_hr_z2_mins,"
            "icu_sweet_spot_min,icu_sweet_spot_max,"
            "icu_joules_above_ftp,"
            "icu_warmup_time,icu_cooldown_time,icu_cadence_z2"
        ),
    }

    ck = _cache_key(f"/athlete/{athlete_id}/activities/{activity_id}", params)
    cached = _cache_get(discord_id, ck, _TTL_ACTIVITIES)
    if cached is not None:
        return json.dumps(cached)

    try:
        data = _request(
            athlete_id, api_key,
            f"/athlete/{athlete_id}/activities/{activity_id}",
            params,
        )
    except (ValueError, RuntimeError) as exc:
        return json.dumps({"error": str(exc)})

    # The detail endpoint returns a single object, not a list
    act = data if isinstance(data, dict) else (data[0] if isinstance(data, list) and data else {})

    result = {
        "source": "intervals.icu",
        "activity_id": activity_id,
        "name": act.get("name"),
        "date": (act.get("start_date_local") or "")[:10],
        "type": act.get("type"),
        "duration_min": round((act.get("moving_time") or 0) / 60, 1),
        "distance_km": round((act.get("distance") or 0) / 1000, 2),
        "training_load": act.get("icu_training_load"),
        "intensity_factor": act.get("icu_intensity"),
        "avg_hr": act.get("avg_heartrate"),
        "max_hr": act.get("max_heartrate"),
        "lthr": act.get("lthr"),
        "pace_mps": act.get("pace") or act.get("avg_pace"),
        "max_speed_mps": act.get("max_speed"),
        "elevation_gain_m": act.get("total_elevation_gain"),
        "avg_cadence": act.get("avg_cadence"),
        "normalized_power_w": act.get("icu_weighted_avg_watts"),
        "avg_power_w": act.get("icu_average_watts"),
        "ftp_w": act.get("icu_ftp"),
        "rpe": act.get("icu_rpe") or act.get("feel") or act.get("session_rpe"),
        "calories": act.get("calories"),
        "carbs_used_g": act.get("carbs_used"),
        "coasting_time_s": act.get("coasting_time"),
        "decoupling_pct": act.get("decoupling"),
        "variability_index": act.get("icu_variability_index"),
        "efficiency_factor": act.get("icu_efficiency_factor"),
        "power_hr_ratio": act.get("icu_power_hr"),
        "power_hr_z2_mins": act.get("icu_power_hr_z2_mins"),
        "sweet_spot_min_pct": act.get("icu_sweet_spot_min"),
        "sweet_spot_max_pct": act.get("icu_sweet_spot_max"),
        "joules_above_ftp": act.get("icu_joules_above_ftp"),
        "warmup_time_s": act.get("icu_warmup_time"),
        "cooldown_time_s": act.get("icu_cooldown_time"),
        "cadence_z2_rpm": act.get("icu_cadence_z2"),
        "hr_zones": act.get("icu_hr_zones"),
        "hr_zone_times": act.get("icu_hr_zone_times"),
        "power_zones": act.get("icu_power_zones"),
        "power_zone_times": act.get("icu_zone_times"),
        "lap_count": act.get("icu_lap_count"),
        "interval_summary": act.get("interval_summary"),
        "laps": act.get("laps"),
    }
    _cache_set(discord_id, ck, result)
    return json.dumps(result)


def get_activity_streams(
    discord_id: str,
    activity_id: str,
    **_: Any,
) -> str:
    """Fetch raw second-by-second stream data for a single activity.

    Returns per-stream data summaries (first and last 5 data points per
    stream type) and computed peak power at standard durations (5s, 1min,
    5min, 20min, 60min) plus an eFTP estimate (95% of best 20-min power).
    The full per-second arrays (power, heart rate, cadence, speed,
    elevation, temperature) are processed server-side — only summary
    metrics and sample points are returned, not the raw 10K+ data arrays.

    Use this after get_activity_detail when you need the raw-data story
    behind the summary stats: FTP validation, interval timing, or pacing
    analysis.

    Args:
        activity_id: The intervals.icu activity ID (e.g. 'i161875412').
                     Obtain this from get_recent_activities output.
    """
    try:
        athlete_id, api_key = _load_credentials(discord_id)
    except ValueError as exc:
        return json.dumps({"error": str(exc)})

    ck = _cache_key(f"/activity/{activity_id}/streams", {})
    cached = _cache_get(discord_id, ck, _TTL_ACTIVITIES)
    if cached is not None:
        return json.dumps(cached)

    try:
        data = _request(
            athlete_id, api_key,
            f"/activity/{activity_id}/streams",
            timeout=30,
        )
    except (ValueError, RuntimeError) as exc:
        return json.dumps({"error": str(exc)})

    # Extract stream data
    stream_map: dict[str, list] = {}
    stream_types: list[str] = []
    for s in data if isinstance(data, list) else []:
        stype = s.get("type", "")
        sdata = s.get("data") or []
        stream_types.append(stype)
        stream_map[stype] = sdata

    # Build compact per-stream summary: type, count, samples
    streams_summary = []
    for stype in stream_types:
        sdata = stream_map.get(stype, [])
        streams_summary.append({
            "type": stype,
            "count": len(sdata),
            "first": sdata[:5] if len(sdata) >= 5 else sdata,
            "last": sdata[-5:] if len(sdata) >= 5 else sdata,
        })

    # Compute peak power metrics from watts + time streams
    peaks = _compute_power_peaks(stream_map)

    result = {
        "source": "intervals.icu",
        "activity_id": activity_id,
        "stream_count": len(stream_types),
        "stream_types": stream_types,
        "streams_summary": streams_summary,
        "peak_power": peaks,
    }
    _cache_set(discord_id, ck, result)
    return json.dumps(result)


def _compute_power_peaks(stream_map: dict) -> dict:
    """Compute peak power at standard durations from raw stream data.

    Uses a sliding-window max over the watts stream aligned with
    the time stream to find best average power at 5s, 1min, 5min,
    20min, and 60min.
    """
    watts = stream_map.get("watts", [])
    time_secs = stream_map.get("time", [])

    if not watts or not time_secs or len(watts) != len(time_secs):
        return {}

    # Work out the typical sample interval (usually 1s for cycling)
    intervals = [time_secs[i] - time_secs[i - 1] for i in range(1, min(100, len(time_secs)))]
    sample_interval = max(1, round(sum(intervals) / max(1, len(intervals))))

    durations = {"5s": 5, "1min": 60, "5min": 300, "20min": 1200, "60min": 3600}

    peaks = {}
    for label, target_dur in durations.items():
        window_points = target_dur // sample_interval
        if window_points < 2 or window_points > len(watts):
            peaks[label] = None
            continue

        best_avg = 0.0
        # Sliding window: average power over each window of window_points
        window_sum = sum(watts[:window_points])
        best_avg = window_sum / window_points

        for i in range(window_points, len(watts)):
            window_sum += watts[i] - watts[i - window_points]
            avg = window_sum / window_points
            if avg > best_avg:
                best_avg = avg

        peaks[label] = round(best_avg, 1) if best_avg > 0 else None

    # eFTP estimate: 95% of best 20-min power
    if peaks.get("20min"):
        peaks["eftp_estimate"] = round(peaks["20min"] * 0.95, 1)

    return peaks


def get_wellness(
    discord_id: str,
    days: int = 7,
    **_: Any,
) -> str:
    """Fetch wellness records over the past N days.

    Includes CTL (fitness), ATL (fatigue), TSB (form), ramp rate,
    HRV, HRV SDNN, sleep hours, sleep quality, sleep score, resting HR,
    readiness, weight, fatigue, soreness, motivation, mood,
    and per-sport info (eFTP, W', Pmax).

    Args:
        days: How many days back (default 7, max 42).
    """
    days = min(int(days), 42)
    try:
        athlete_id, api_key = _load_credentials(discord_id)
    except ValueError as exc:
        return json.dumps({"error": str(exc)})

    tz = _athlete_tz(discord_id, athlete_id)
    params = {
        "oldest": _n_days_ago_iso(days, tz),
        "newest": _today_iso(tz),
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
                "sport_info": [
                    {
                        "sport": si.get("type"),
                        "eftp": si.get("eftp"),
                        "w_prime": si.get("wPrime"),
                        "p_max": si.get("pMax"),
                    }
                    for si in (w.get("sportInfo") or [])
                ],
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
    """Fetch upcoming planned workouts and races from the intervals.icu calendar.

    Returns per event: id, date, category, type, name, description,
    planned training load, planned intensity, projected CTL/ATL,
    time target, and distance target.  Provides TSB trajectory
    projections for taper planning.

    Args:
        days_ahead: How many days forward to look (default 14, max 90).
    """
    days_ahead = min(int(days_ahead), 90)
    try:
        athlete_id, api_key = _load_credentials(discord_id)
    except ValueError as exc:
        return json.dumps({"error": str(exc)})

    tz = _athlete_tz(discord_id, athlete_id)
    params = {
        "oldest": _today_iso(tz),
        "newest": _n_days_ago_iso(-days_ahead, tz),
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

    tz = _athlete_tz(discord_id, athlete_id)
    params = {
        "type": sport,
        "oldest": _n_days_ago_iso(days, tz),
        "newest": _today_iso(tz),
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


def get_fitness_chart(
    discord_id: str,
    days: int = 365,
    **_: Any,
) -> str:
    """Fetch the full CTL/ATL/TSB fitness history from intervals.icu.

    Like get_wellness but designed for long-range trend analysis (up to
    365 days vs wellness's 42-day cap).  Returns daily CTL (fitness),
    ATL (fatigue), TSB (form), ramp rate, and per-sport eFTP, W', Pmax
    so you can see season-long progression, identify peak fitness periods,
    and track eFTP trends over time.

    Use this when you need to answer "how has my fitness evolved"
    questions — CTL trajectory, eFTP history, training load over months.

    Args:
        days: How many days to look back (default 365, max 365).
    """
    days = min(int(days), 365)
    try:
        athlete_id, api_key = _load_credentials(discord_id)
    except ValueError as exc:
        return json.dumps({"error": str(exc)})

    tz = _athlete_tz(discord_id, athlete_id)
    params = {
        "oldest": _n_days_ago_iso(days, tz),
        "newest": _today_iso(tz),
    }

    ck = _cache_key(f"/athlete/{athlete_id}/wellness-fitness-{days}", params)
    cached = _cache_get(discord_id, ck, _TTL_POWER_CURVE)
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
        tsb = round(ctl - atl, 1) if ctl is not None and atl is not None else None
        records.append(
            {
                "date": w.get("id"),
                "ctl": round(ctl, 1) if ctl is not None else None,
                "atl": round(atl, 1) if atl is not None else None,
                "tsb": tsb,
                "ramp_rate": w.get("rampRate"),
                "sport_info": [
                    {
                        "sport": si.get("type"),
                        "eftp": si.get("eftp"),
                        "w_prime": si.get("wPrime"),
                        "p_max": si.get("pMax"),
                    }
                    for si in (w.get("sportInfo") or [])
                ],
            }
        )

    result = {
        "source": "intervals.icu",
        "days": days,
        "record_count": len(records),
        "records": records,
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
            "name, weight, timezone, resting HR, sex, date of birth, "
            "and Discord display name. "
            "Use this to determine athlete sex (for female-physiology coaching) "
            "and age (for age-appropriate training recommendations)."
        ),
        properties=_DISCORD_ID_PROP,
        required=["discord_id"],
        fn=get_athlete_profile,
    )

    _tool(
        name="get_sport_settings",
        description=(
            "Fetch FTP, indoor FTP, power zones, HR zones, pace zones, LTHR, "
            "max HR, W', and FTP W/kg for the athlete's chosen sport. "
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
            "Returns per activity: id, name, date, type, duration, distance, training load, "
            "CTL/ATL after, intensity factor, normalized power, FTP used, trimp, "
            "hr_load, power_load, RPE, pace, avg/max HR, max speed, "
            "elevation gain, and cadence. "
            "Use this to assess recent training stress before making a recommendation. "
            "The 'id' field can be passed to get_activity_detail for deeper workout analysis."
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
            "TSB (form = CTL - ATL), ramp rate, HRV, HRV SDNN, sleep hours, "
            "sleep quality, sleep score, resting HR, readiness, weight, "
            "fatigue, soreness, motivation, mood, and per-sport info "
            "(eFTP, W', Pmax). Always call this when evaluating readiness or recovery."
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
            "Returns per event: id, date, category, type, name, description, planned training load, "
            "planned intensity, projected CTL/ATL, time target, and distance target. "
            "Use this when checking for A-races, recovery weeks, or planned intensity sessions. "
            "Provides TSB trajectory projections for taper planning."
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

    _tool(
        name="get_activity_detail",
        description=(
            "Fetch full detail for a single activity from intervals.icu: "
            "name, date, type, duration, distance, training load, intensity "
            "factor, average and max HR, LTHR, pace, max speed, elevation gain, "
            "cadence, normalized and average power, FTP used, RPE, calories, "
            "carbs used, coasting time, decoupling, variability index, "
            "efficiency factor, power-HR ratio, power-HR Z2 minutes, sweet spot "
            "range (min/max), joules above FTP, warmup and cooldown time, "
            "cadence Z2, HR zones with zone times, power zones with zone times, "
            "lap count, interval summary, and laps. "
            "Use this after get_recent_activities when you need to analyze "
            "a specific workout in depth (e.g. interval splits, zone distribution, "
            "aerobic decoupling, fueling, pacing). "
            "The activity_id comes from the 'id' field in get_recent_activities output."
        ),
        properties={
            **_DISCORD_ID_PROP,
            "activity_id": {
                "type": "string",
                "description": (
                    "The intervals.icu activity ID (e.g. 'i161875412'). "
                    "Obtain this from get_recent_activities output."
                ),
            },
        },
        required=["discord_id", "activity_id"],
        fn=get_activity_detail,
    )

    _tool(
        name="verify_athlete_identity",
        description=(
            "Verify that stored intervals.icu credentials belong to the expected "
            "athlete. Fetches the athlete profile and checks that the stored "
            "athlete_id matches the API response, and that a Discord display name "
            "was recorded during onboarding (missing means credentials were manually "
            "placed). Call this at the start of every coaching session to catch "
            "stale or swapped credential files before pulling training data."
        ),
        properties=_DISCORD_ID_PROP,
        required=["discord_id"],
        fn=verify_athlete_identity,
    )

    _tool(
        name="get_activity_streams",
        description=(
            "Fetch raw second-by-second stream data for a single activity "
            "from intervals.icu. "
            "Returns per-stream data summaries (sample counts, first/last 5 data points) "
            "for power (watts), heart rate (bpm), cadence (rpm), speed (m/s), "
            "elevation (m), temperature (°C), and any other available channels. "
            "Also returns computed peak power at standard durations "
            "(5s, 1min, 5min, 20min, 60min) plus an eFTP estimate. "
            "Use this when you need to validate FTP against raw data, "
            "analyze pacing, or detect intervals from the actual power trace "
            "rather than Garmin's auto-detection. "
            "The activity_id comes from the 'id' field in get_recent_activities output. "
            "CAUTION: processes large arrays (10K+ data points per stream) server-side. "
            "Use only when you genuinely need raw-data-derived metrics for computation."
        ),
        properties={
            **_DISCORD_ID_PROP,
            "activity_id": {
                "type": "string",
                "description": (
                    "The intervals.icu activity ID (e.g. 'i161875412'). "
                    "Obtain this from get_recent_activities output."
                ),
            },
        },
        required=["discord_id", "activity_id"],
        fn=get_activity_streams,
    )

    _tool(
        name="get_fitness_chart",
        description=(
            "Fetch the full CTL/ATL/TSB fitness history from intervals.icu "
            "(up to 365 days). "
            "Returns daily CTL (fitness), ATL (fatigue), TSB (form), ramp rate, "
            "and per-sport eFTP, W', Pmax for season-long trend analysis. "
            "Like get_wellness but for long-range questions: CTL trajectory, "
            "eFTP progression, peak fitness periods, training load over months. "
            "Use this when you need to answer 'how has my fitness evolved' "
            "rather than 'how recovered am I today'."
        ),
        properties={
            **_DISCORD_ID_PROP,
            "days": {
                "type": "integer",
                "description": "How many days back (default 365, max 365).",
                "default": 365,
            },
        },
        required=["discord_id"],
        fn=get_fitness_chart,
    )
