"""intervals.icu API integration for Hermes Coach.

Provides 12 tools for fetching athlete training data:

  get_athlete_profile    — profile, weight, height, sex, DOB, training availability
  get_sport_settings     — FTP, zones, LTHR, W', threshold pace, load order
  get_recent_activities  — last N days of completed workouts
  get_wellness           — CTL, ATL, TSB, daily load, HRV, sleep, readiness
  get_planned_events     — calendar workouts and races (forward and back)
  get_best_effort_curve  — best effort curve for a sport (power/pace/HR)
  get_power_curve        — deprecated alias for get_best_effort_curve(sport='Ride')
  get_activity_detail    — full detail for a single activity
  get_activity_intervals — the athlete's own detected intervals for one activity
  verify_athlete_identity — validate stored credentials match expected athlete
  get_activity_streams   — per-stream data summaries and peak power
  get_fitness_chart      — full CTL/ATL/TSB history (up to 365 days)

Authentication:
  intervals.icu uses HTTP Basic Auth.
  Username is the literal string "API_KEY".
  Password is the user's personal API key.
  The athlete self-reference in URL paths is the string "i".

User keys are stored per-Discord-user in:
  $HERMES_HOME/users/<discord_id>/intervals_key   (plaintext, chmod 0600, PVC-local)

Cache:
  Raw API responses are cached under:
  $HERMES_HOME/users/<discord_id>/cache/<endpoint_hash>.json
  with a configurable TTL (default 15 minutes for activities/wellness,
  6 hours for profile/sport-settings).
"""

from __future__ import annotations

import json
import logging
from datetime import date
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

# Bump when the *projected shape* of a cached endpoint changes (fields added
# to or removed from the response). The cache key includes this version, so a
# projection change cannot serve the previous shape from a warm PVC cache until
# the TTL expires. Live-verified 2026-09-18: after adding `height` /
# `training_availability` to the profile projection, a pre-existing cache entry
# kept returning the old shape (`height=None`) for up to 6 h.
_PROJECTION_VERSION = 2

# ---------------------------------------------------------------------------
# Wellness fields the coach-brain corpus coaches against.
#
# Passed as the API `fields` param, which also omits null values — so a field
# the athlete does not log costs nothing in context. Live-verified 2026-09-18:
# the extended set costs ~2 KB more at 42 days (7.3-11.1 KB vs 5.3-9.1 KB), and
# ctlLoad/atlLoad populate 43/43 while the health fields are null for all
# athletes tested.
# ---------------------------------------------------------------------------
_WELLNESS_FIELDS = (
    # `id` is the ISO date and is the record's date key — it must be in the
    # projection, because `fields` excludes every field it does not list.
    "id,ctl,atl,rampRate,ctlLoad,atlLoad,"
    "hrv,hrvSDNN,restingHR,avgSleepingHR,"
    "sleepSecs,sleepScore,sleepQuality,readiness,"
    "weight,bodyFat,vo2max,respiration,spO2,"
    "menstrualPhase,menstrualPhasePredicted,injury,"
    "soreness,fatigue,stress,mood,motivation,"
    "hydration,hydrationVolume,kcalConsumed,"
    "carbohydrates,protein,fatTotal,comments,"
    "systolic,diastolic,bloodGlucose,lactate,baevskySI,steps,sportInfo"
)

# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------


def _profile_cache_key(athlete_id: str) -> str:
    """Single source for the athlete-profile cache key (shared by the profile
    fetch and the best-effort timezone lookup)."""
    return _cache_key(f"/athlete/{athlete_id}", {"v": _PROJECTION_VERSION})


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
        "height_m": data.get("height"),
        # The athlete's own declared weekly availability (day of week,
        # max_training_time, can_train_sports). Often unset — live-verified
        # null for 3 of 4 athletes, [] for the fourth. When present it is the
        # athlete's own constraint and overrides the agent's assumption.
        "training_availability": data.get("training_availability"),
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

    ck = _cache_key(
        f"/athlete/{athlete_id}/sport-settings/{sport}",
        {"v": _PROJECTION_VERSION},
    )
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
        # Running anchor (the running analog of FTP) — required to
        # calibrate pace zones and race-pace targets.
        "threshold_pace_mps": data.get("threshold_pace"),
        "p_max": data.get("p_max"),
        "w_prime": data.get("w_prime"),
        "sweet_spot_min_pct": data.get("sweet_spot_min"),
        "sweet_spot_max_pct": data.get("sweet_spot_max"),
        "power_spike_threshold_pct": data.get("power_spike_threshold"),
        "lthr": data.get("lthr"),
        "max_hr": data.get("max_hr"),
        "power_zones": data.get("power_zones"),
        "hr_zones": data.get("hr_zones"),
        "pace_zones": data.get("pace_zones"),
        # Zone names as the athlete sees them in the UI, so the coach's
        # zone references match the athlete's labels.
        "power_zone_names": data.get("power_zone_names"),
        "hr_zone_names": data.get("hr_zone_names"),
        "pace_zone_names": data.get("pace_zone_names"),
        # Which stream drives load and time-in-zone. Without this the
        # agent cannot tell how to read every IF and zone time.
        "load_order": data.get("load_order"),
        "tiz_order": data.get("tiz_order"),
        "hr_load_type": data.get("hr_load_type"),
        "pace_load_type": data.get("pace_load_type"),
        "gap_model": data.get("gap_model"),
        "use_gap_zone_times": data.get("use_gap_zone_times"),
        "best_effort_distances_m": data.get("best_effort_distances"),
        "pace_curve_start": data.get("pace_curve_start"),
        "default_workout_time": data.get("default_workout_time"),
        "types": data.get("types"),
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
        # NOTE: field names must be the published model names (average_heartrate,
        # average_cadence, pace). The Strava-style aliases (avg_heartrate,
        # avg_cadence, avg_pace) are NOT accepted by the API and are silently
        # dropped, so the projection would always read None. Live-verified
        # 2026-09-18: average_* populated 30/30, avg_* 0/30.
        "fields": (
            "id,name,start_date_local,type,moving_time,distance,"
            "icu_training_load,icu_ctl,icu_atl,icu_intensity,"
            "icu_weighted_avg_watts,icu_ftp,trimp,hr_load,power_load,"
            "icu_rpe,feel,session_rpe,"
            "pace,average_heartrate,max_heartrate,max_speed,"
            "total_elevation_gain,average_cadence,"
            "paired_event_id"
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
                "pace_mps": act.get("pace"),
                "avg_hr": act.get("average_heartrate"),
                "max_hr": act.get("max_heartrate"),
                "max_speed_mps": act.get("max_speed"),
                "elevation_gain_m": act.get("total_elevation_gain"),
                "avg_cadence": act.get("average_cadence"),
                "paired_event_id": act.get("paired_event_id"),
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
    """Fetch full detail for a single activity.

    Returns zone distributions (HR/power/pace), decoupling, efficiency,
    variability, compliance, training-load model data, and the paired planned
    event.  Interval objects are NOT here — use get_activity_intervals for
    interval-by-interval analysis.

    Args:
        activity_id: The intervals.icu activity ID (e.g. "i161875412").
                     Obtain this from get_recent_activities output.
    """
    try:
        athlete_id, api_key = _load_credentials(discord_id)
    except ValueError as exc:
        return json.dumps({"error": str(exc)})

    params = {
        # Field names must be the published model names. The `fields` param
        # silently drops unknown names, so a Strava-style alias yields no key at
        # all. NOTE: `icu_intervals`, `icu_groups` and `laps` are JS-script-only
        # fields — they are absent from the REST response even with no `fields`
        # filter. Structured intervals come from GET /activity/{id}/intervals
        # (get_activity_intervals). Live-verified 2026-09-18.
        "fields": (
            "id,name,start_date_local,type,moving_time,distance,"
            "icu_training_load,icu_intensity,"
            "average_heartrate,max_heartrate,lthr,"
            "pace,max_speed,"
            "pace_zones,pace_zone_times,threshold_pace,"
            "total_elevation_gain,average_cadence,"
            "icu_lap_count,interval_summary,"
            "icu_hr_zones,icu_hr_zone_times,"
            "icu_power_zones,icu_zone_times,"
            "icu_weighted_avg_watts,icu_average_watts,icu_ftp,"
            "icu_rpe,feel,session_rpe,"
            "calories,carbs_used,coasting_time,"
            "decoupling,icu_variability_index,icu_efficiency_factor,"
            "icu_power_hr,icu_power_hr_z2,icu_power_hr_z2_mins,"
            "icu_sweet_spot_min,icu_sweet_spot_max,"
            "icu_joules_above_ftp,"
            "icu_warmup_time,icu_cooldown_time,icu_cadence_z2,"
            "icu_rolling_ftp,icu_rolling_ftp_delta,"
            "icu_pm_ftp,icu_pm_w_prime,icu_pm_cp,"
            "icu_max_wbal_depletion,"
            "polarization_index,strain_score,gap,gap_zone_times,"
            "icu_hrr,icu_achievements,icu_ignore_hr,"
            "icu_training_load_data,compliance,coach_tick,"
            "paired_event_id"
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
        "avg_hr": act.get("average_heartrate"),
        "max_hr": act.get("max_heartrate"),
        "lthr": act.get("lthr"),
        "pace_mps": act.get("pace"),
        "pace_zones": act.get("pace_zones"),
        "pace_zone_times": act.get("pace_zone_times"),
        "threshold_pace_mps": act.get("threshold_pace"),
        "max_speed_mps": act.get("max_speed"),
        "elevation_gain_m": act.get("total_elevation_gain"),
        "avg_cadence": act.get("average_cadence"),
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
        "rolling_ftp_w": act.get("icu_rolling_ftp"),
        "rolling_ftp_delta_w": act.get("icu_rolling_ftp_delta"),
        "pm_ftp_w": act.get("icu_pm_ftp"),
        "pm_w_prime_j": act.get("icu_pm_w_prime"),
        "pm_cp_w": act.get("icu_pm_cp"),
        "max_wbal_depletion_j": act.get("icu_max_wbal_depletion"),
        "polarization_index": act.get("polarization_index"),
        "strain_score": act.get("strain_score"),
        "gap_mps": act.get("gap"),
        "gap_zone_times": act.get("gap_zone_times"),
        "hr_recovery": act.get("icu_hrr"),
        "achievements": act.get("icu_achievements"),
        "ignore_hr": act.get("icu_ignore_hr"),
        "training_load_data": act.get("icu_training_load_data"),
        "compliance": act.get("compliance"),
        "coach_tick": act.get("coach_tick"),
        "paired_event_id": act.get("paired_event_id"),
        "power_hr_z2": act.get("icu_power_hr_z2"),
    }
    _cache_set(discord_id, ck, result)
    return json.dumps(result)


def get_activity_intervals(
    discord_id: str,
    activity_id: str,
    **_: Any,
) -> str:
    """Fetch the athlete's own detected intervals for one activity.

    Uses GET /api/v1/activity/{id}/intervals, which returns the structured
    interval objects the intervals.icu UI shows: per-interval power, heart rate,
    cadence, intensity (% FTP), zone, duration, training load and W' balance,
    plus grouped aggregates for repeated intervals.

    These fields (`icu_intervals`, `icu_groups`) are JS-script-only — they are
    NOT returned by the activity detail endpoint, so `fields=icu_intervals` there
    silently yields nothing. Live-verified 2026-09-18: 6-11 intervals per ride.

    Use this for interval-by-interval analysis (interval splits, work/recovery
    structure, zone distribution, pacing) instead of fetching raw streams.

    Args:
        activity_id: The intervals.icu activity ID (e.g. 'i161875412').
                     Obtain this from get_recent_activities output.
    """
    try:
        athlete_id, api_key = _load_credentials(discord_id)
    except ValueError as exc:
        return json.dumps({"error": str(exc)})

    ck = _cache_key(f"/activity/{activity_id}/intervals", {})
    cached = _cache_get(discord_id, ck, _TTL_ACTIVITIES)
    if cached is not None:
        return json.dumps(cached)

    try:
        data = _request(
            athlete_id, api_key,
            f"/activity/{activity_id}/intervals",
            timeout=30,
        )
    except (ValueError, RuntimeError) as exc:
        return json.dumps({"error": str(exc)})

    act = data if isinstance(data, dict) else {}

    intervals = []
    for iv in act.get("icu_intervals") or []:
        if not isinstance(iv, dict):
            continue
        intervals.append({
            "index": iv.get("id"),
            "label": iv.get("label"),
            "type": iv.get("type"),
            "zone": iv.get("zone"),
            "intensity_pct": iv.get("intensity"),
            "moving_time_s": iv.get("moving_time"),
            "distance_m": iv.get("distance"),
            "average_watts": iv.get("average_watts"),
            "weighted_avg_watts": iv.get("weighted_average_watts"),
            "average_hr": iv.get("average_heartrate"),
            "max_hr": iv.get("max_heartrate"),
            "average_cadence": iv.get("average_cadence"),
            "training_load": iv.get("training_load"),
            "decoupling_pct": iv.get("decoupling"),
            "wbal_start_j": iv.get("wbal_start"),
            "wbal_end_j": iv.get("wbal_end"),
            "joules_above_ftp": iv.get("joules_above_ftp"),
            "start_index": iv.get("start_index"),
            "end_index": iv.get("end_index"),
        })

    groups = []
    for g in act.get("icu_groups") or []:
        if not isinstance(g, dict):
            continue
        groups.append({
            "zone": g.get("zone"),
            "count": g.get("count"),
            "moving_time_s": g.get("moving_time"),
            "distance_m": g.get("distance"),
            "average_watts": g.get("average_watts"),
            "average_hr": g.get("average_heartrate"),
            "average_cadence": g.get("average_cadence"),
            "intensity_pct": g.get("intensity"),
        })

    result = {
        "source": "intervals.icu",
        "activity_id": activity_id,
        "analyzed": act.get("analyzed"),
        "interval_count": len(intervals),
        "group_count": len(groups),
        "intervals": intervals,
        "groups": groups,
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

    Includes CTL (fitness), ATL (fatigue), TSB (form), ramp rate, daily load
    (ctlLoad/atlLoad), HRV, HRV SDNN, sleeping HR, sleep hours, sleep quality,
    sleep score, resting HR, readiness, weight, body fat, VO2max, respiration,
    SpO2, menstrual phase (and predicted), injury, fatigue, soreness, stress,
    mood, motivation, hydration, nutrition intake, blood pressure, glucose and
    lactate, steps, comments, and per-sport info (eFTP, W', Pmax).

    Fields the athlete has not logged are omitted from the response (the API's
    `fields` param excludes null values), so the payload only grows by the fields
    actually recorded.

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
        "fields": _WELLNESS_FIELDS,
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
                "ctl_load": w.get("ctlLoad"),
                "atl_load": w.get("atlLoad"),
                "hrv": w.get("hrv"),
                "hrv_sdnn": w.get("hrvSDNN"),
                "resting_hr": w.get("restingHR"),
                "avg_sleeping_hr": w.get("avgSleepingHR"),
                "sleep_hours": round((w.get("sleepSecs") or 0) / 3600, 1) or None,
                "sleep_quality": w.get("sleepQuality"),
                "sleep_score": w.get("sleepScore"),
                "readiness": w.get("readiness"),
                "weight_kg": w.get("weight"),
                "body_fat_pct": w.get("bodyFat"),
                "vo2max": w.get("vo2max"),
                "respiration": w.get("respiration"),
                "sp_o2": w.get("spO2"),
                "menstrual_phase": w.get("menstrualPhase"),
                "menstrual_phase_predicted": w.get("menstrualPhasePredicted"),
                "injury": w.get("injury"),
                "fatigue": w.get("fatigue"),
                "soreness": w.get("soreness"),
                "stress": w.get("stress"),
                "mood": w.get("mood"),
                "motivation": w.get("motivation"),
                "hydration": w.get("hydration"),
                "hydration_volume_l": w.get("hydrationVolume"),
                "kcal_consumed": w.get("kcalConsumed"),
                "carbohydrates_g": w.get("carbohydrates"),
                "protein_g": w.get("protein"),
                "fat_total_g": w.get("fatTotal"),
                "systolic": w.get("systolic"),
                "diastolic": w.get("diastolic"),
                "blood_glucose": w.get("bloodGlucose"),
                "lactate": w.get("lactate"),
                "baevsky_si": w.get("baevskySI"),
                "steps": w.get("steps"),
                "comments": w.get("comments"),
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
    days_back: int = 0,
    **_: Any,
) -> str:
    """Fetch planned workouts and races from the intervals.icu calendar.

    Returns per event: id, date, category, type, name, description,
    planned training load, planned intensity, projected CTL/ATL,
    time target, and distance target.  Provides TSB trajectory
    projections for taper planning.

    Set days_back > 0 to also return past events — use this to compare
    planned vs completed sessions (match event `id` against an activity's
    `paired_event_id`) for plan-adherence review.

    Args:
        days_ahead: How many days forward to look (default 14, max 90).
        days_back:  How many days back to look (default 0, max 90).
    """
    days_ahead = min(int(days_ahead), 90)
    days_back = min(max(int(days_back), 0), 90)
    try:
        athlete_id, api_key = _load_credentials(discord_id)
    except ValueError as exc:
        return json.dumps({"error": str(exc)})

    tz = _athlete_tz(discord_id, athlete_id)
    params = {
        "oldest": _n_days_ago_iso(days_back, tz),
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
        "days_back": days_back,
        "count": len(events),
        "events": events,
    }
    _cache_set(discord_id, ck, result)
    return json.dumps(result)


# Standard best-effort targets per curve type. Power and HR curves are indexed by
# duration (seconds); the pace curve is indexed by distance (metres).
_CURVE_DURATIONS = ((5, "5s"), (60, "1min"), (300, "5min"), (1200, "20min"), (3600, "60min"))
_CURVE_DISTANCES = (
    (1000, "1km"), (1609.34, "1mi"), (5000, "5km"),
    (10000, "10km"), (21097.5, "half_marathon"),
)

# Sports whose best-effort curve lives on the power endpoint. Everything not
# listed here and not in _PACE_SPORTS falls back to the HR curve. The sport names
# are the published ActivityType values.
_POWER_SPORTS = frozenset({
    "Ride", "VirtualRide", "GravelRide", "MountainBikeRide", "EBikeRide",
    "EMountainBikeRide", "Cyclocross", "TrackRide", "Handcycle", "Velomobile",
    "BMX", "TrackRide",
})
_PACE_SPORTS = frozenset({"Run", "TrailRun", "VirtualRun"})


def _curve_endpoint(sport: str) -> tuple[str, str, str]:
    """Map a sport to (endpoint, curve_type, axis_key).

    The published API exposes three curve endpoints: power-curves (secs/watts),
    pace-curves (distance/values, values = seconds to cover the distance) and
    hr-curves (secs/values, values = bpm).
    """
    if sport in _POWER_SPORTS:
        return "power-curves", "power", "secs"
    if sport in _PACE_SPORTS:
        return "pace-curves", "pace", "distance"
    return "hr-curves", "hr", "secs"


def _nearest_curve_value(axis: list, values: list, target: float) -> Optional[float]:
    """Return the value at the axis point closest to target.

    intervals.icu returns the curve as two parallel arrays sampled at its own
    points, so a standard duration/distance is looked up as the nearest sample.
    Returns None when the closest sample is more than 15% away from the target
    (the curve does not cover that duration).

    # ponytail: 15% nearest-sample tolerance; replace with interpolation if
    # the agent ever needs exact standard-duration values.
    """
    if not axis or not values or len(axis) != len(values):
        return None
    i = min(range(len(axis)), key=lambda j: abs(float(axis[j]) - target))
    if abs(float(axis[i]) - target) > 0.15 * target:
        return None
    return values[i]


def get_best_effort_curve(
    discord_id: str,
    sport: str = "Ride",
    days: int = 42,
    **_: Any,
) -> str:
    """Fetch the athlete's best-effort curve for a sport over a date range.

    One interface for all three published curve endpoints:
      - Ride / VirtualRide / GravelRide etc -> power-curves
      - Run / TrailRun / VirtualRun        -> pace-curves
      - anything else                       -> hr-curves

    Returns the best effort at standard targets for that curve type:
      - power: watts at 5s, 1min, 5min, 20min, 60min
      - pace:  seconds to cover 1km, 1mi, 5km, 10km, half marathon
      - hr:    bpm at 1min, 5min, 20min, 60min

    `curve_type` tells you how to read `best_effort`; `axis` names the axis the
    curve is indexed by. Use this for strengths/weaknesses, race-pace
    benchmarking and season trends — for running athletes the data is on the pace
    endpoint, not the power endpoint.

    Args:
        sport: Sport type (default "Ride").
        days:  How many days to look back (default 42, max 365).
    """
    days = min(int(days), 365)
    try:
        athlete_id, api_key = _load_credentials(discord_id)
    except ValueError as exc:
        return json.dumps({"error": str(exc)})

    endpoint, curve_type, axis_key = _curve_endpoint(sport)
    tz = _athlete_tz(discord_id, athlete_id)
    params = {
        "type": sport,
        "oldest": _n_days_ago_iso(days, tz),
        "newest": _today_iso(tz),
    }

    ck = _cache_key(f"/athlete/{athlete_id}/{endpoint}", params)
    cached = _cache_get(discord_id, ck, _TTL_POWER_CURVE)
    if cached is not None:
        return json.dumps(cached)

    try:
        data = _request(
            athlete_id, api_key, f"/athlete/{athlete_id}/{endpoint}", params
        )
    except (ValueError, RuntimeError) as exc:
        return json.dumps({"error": str(exc)})

    # Response shape: {"list": [{"label", "days", axis_key: [...],
    # "values"/"watts": [...]}], "activities": {...}}. `secs`/`watts` for
    # power, `distance`/`values` for pace, `secs`/`values` for HR.
    value_key = "watts" if curve_type == "power" else "values"
    curves = (data.get("list") or []) if isinstance(data, dict) else []
    curve = curves[0] if curves else {}
    axis = curve.get(axis_key) or []
    values = curve.get(value_key) or []

    targets = _CURVE_DISTANCES if curve_type == "pace" else _CURVE_DURATIONS
    best = {}
    for target, label in targets:
        best[label] = _nearest_curve_value(axis, values, target)

    result = {
        "source": "intervals.icu",
        "sport": sport,
        "days": days,
        "curve_type": curve_type,
        "axis": axis_key,
        "curve_label": curve.get("label"),
        "best_effort": best,
        "curve_points": len(axis),
    }
    _cache_set(discord_id, ck, result)
    return json.dumps(result)


def get_power_curve(
    discord_id: str,
    sport: str = "Ride",
    days: int = 42,
    **_: Any,
) -> str:
    """Deprecated alias for get_best_effort_curve (sport='Ride').

    Kept for scheduled jobs whose stored prompts call this name. Returns the
    legacy peak-power shape. Prefer get_best_effort_curve.

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

    # The response is {"list": [{"secs": [...], "watts": [...]}]}, NOT a
    # flat list of {secs, watts} points. The old parser expected a list and so
    # returned None for every duration. Live-verified 2026-09-18.
    curves = (data.get("list") or []) if isinstance(data, dict) else []
    curve = curves[0] if curves else {}
    secs = curve.get("secs") or []
    watts = curve.get("watts") or []

    peaks = {
        label: _nearest_curve_value(secs, watts, target)
        for target, label in _CURVE_DURATIONS
    }

    result = {
        "source": "intervals.icu",
        "sport": sport,
        "days": days,
        "peak_power": peaks,
        "full_curve_points": len(secs),
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
    and track eFTP trends over time. Daily resolution for days <= 60;
    weekly (last daily record per ISO week) for longer ranges, so season
    queries stay compact in model context.

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
        "fields": _WELLNESS_FIELDS,
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
                "ctl_load": w.get("ctlLoad"),
                "atl_load": w.get("atlLoad"),
                "vo2max": w.get("vo2max"),
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

    # Season-range queries downsample to weekly (last daily record per ISO
    # week) so ~365-day responses stay compact in model context. CTL/ATL/TSB
    # are level metrics — the weekly close is representative, no averaging.
    resolution = "daily"
    if days > 60:
        resolution = "weekly"
        # Sort by date first so "last record of the week" is well-defined
        # regardless of the API's response order.
        dated: list[tuple[date, dict]] = []
        undated: list[dict] = []
        for rec in records:
            try:
                dated.append((date.fromisoformat(str(rec.get("date") or "")), rec))
            except ValueError:
                undated.append(rec)
        dated.sort(key=lambda pair: pair[0])
        by_week: dict[tuple[int, int], dict] = {}
        for rec_date, rec in dated:
            by_week[rec_date.isocalendar()[:2]] = rec
        records = list(by_week.values()) + undated

    result = {
        "source": "intervals.icu",
        "days": days,
        "resolution": resolution,
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
            "name, weight, height, timezone, resting HR, sex, date of birth, "
            "Discord display name, and declared weekly training availability "
            "(day, max training time, allowed sports). "
            "Use this to determine athlete sex (for female-physiology coaching), "
            "age (for age-appropriate training recommendations), and the "
            "athlete's own weekly time constraints before planning."
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
            "Fetch completed workouts from intervals.icu: per-activity summaries "
            "with training load, CTL/ATL, intensity, power/HR/pace aggregates, and RPE. "
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
            "TSB (form), ramp rate, daily load (ctlLoad/atlLoad), HRV, HRV SDNN, "
            "sleep, resting HR, readiness, weight, VO2max, steps, mood and "
            "motivation, plus per-sport eFTP/W'/Pmax. Fields the athlete has not "
            "logged are omitted. Always call this when evaluating readiness or recovery."
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
            "Fetch planned workouts and races from the intervals.icu calendar: "
            "per-event date, category, name, planned load/intensity, projected CTL/ATL, "
            "and time/distance targets. Use for A-races, recovery weeks, and taper planning. "
            "Set days_back>0 to also return past events and compare planned vs "
            "completed sessions (event id matches the activity's paired_event_id)."
        ),
        properties={
            **_DISCORD_ID_PROP,
            "days_ahead": {
                "type": "integer",
                "description": "How many days forward to look (default 14, max 90).",
                "default": 14,
            },
            "days_back": {
                "type": "integer",
                "description": (
                    "How many days back to look (default 0, max 90). "
                    "Use >0 to review plan adherence against completed sessions."
                ),
                "default": 0,
            },
        },
        required=["discord_id"],
        fn=get_planned_events,
    )

    _tool(
        name="get_best_effort_curve",
        description=(
            "Fetch the athlete's best-effort curve for a sport: power "
            "(Ride-family), pace (Run-family) or heart rate (other sports). "
            "Returns best effort at standard targets — watts at 5s/1min/5min/20min/60min, "
            "or seconds to cover 1km/1mi/5km/10km/half marathon, or bpm at "
            "1min/5min/20min/60min. `curve_type` says how to read `best_effort`. "
            "Use for strengths/weaknesses, race-pace benchmarking and season trends. "
            "For running athletes the data is on the pace curve, not the power curve."
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
        fn=get_best_effort_curve,
    )

    _tool(
        name="get_power_curve",
        description=(
            "DEPRECATED alias for get_best_effort_curve(sport='Ride'); kept for "
            "existing scheduled jobs. Fetch best power at 5s, 1min, 5min, 20min, "
            "60min over a date range."
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
            "Fetch full detail for a single activity from intervals.icu: HR/power/pace "
            "zone distributions, decoupling, efficiency, variability, compliance, "
            "training-load model data, and paired_event_id (the planned event this "
            "activity completed, if any). "
            "For interval-by-interval splits use get_activity_intervals instead — the "
            "interval objects are NOT returned by this endpoint. "
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
        name="get_activity_intervals",
        description=(
            "Fetch the athlete's own detected intervals for one activity from "
            "intervals.icu: per-interval power, heart rate, cadence, intensity "
            "(% FTP), zone, duration, training load, W' balance, and grouped "
            "aggregates for repeated intervals. These fields are JS-script-only "
            "and are NOT returned by get_activity_detail. "
            "Use this for interval-by-interval analysis (interval splits, "
            "work/recovery structure, zone distribution, pacing) instead of "
            "fetching raw streams. "
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
        fn=get_activity_intervals,
    )

    _tool(
        name="get_activity_streams",
        description=(
            "Fetch raw second-by-second stream data for a single activity. "
            "Returns compact per-stream summaries (first/last samples) plus computed "
            "peak power at 5s/1min/5min/20min/60min and an eFTP estimate — not the "
            "raw arrays. Use to validate FTP against raw data, analyze pacing, or "
            "detect intervals from the actual power trace. "
            "The activity_id comes from the 'id' field in get_recent_activities output. "
            "CAUTION: processes large arrays server-side — use only when raw-data "
            "metrics are genuinely needed."
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
            "(up to 365 days). Daily resolution for days <= 60; weekly "
            "(last day per ISO week) for longer ranges, so season queries stay "
            "compact. Use for 'how has my fitness evolved' questions: CTL "
            "trajectory, eFTP progression, peak fitness periods. "
            "For 'how recovered am I today' use get_wellness instead."
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
