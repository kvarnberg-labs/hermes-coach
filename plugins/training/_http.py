"""intervals.icu HTTP transport and cache layer.

Extracted from intervals_icu.py (Candidate 2: split at the HTTP seam).

Interface:
    _API_BASE           — base URL
    _TTL_*              — cache TTL constants
    _cache_dir(id)      — Path to cache directory
    _cache_key(endpoint, params) -> str
    _cache_get(discord_id, key, ttl) -> Optional[Any]   (also cleans stale files)
    _cache_set(discord_id, key, data)
    _auth_header(api_key) -> str
    _request(athlete_id, api_key, path, params?, timeout?) -> Any   (GET; retries 429/503)
    _post_json(athlete_id, api_key, path, payload, timeout?) -> Any
    _delete_json(athlete_id, api_key, path, timeout?) -> bool
    _today_iso() -> str
    _n_days_ago_iso(n: int) -> str
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Optional

try:
    from zoneinfo import ZoneInfo
except ImportError:  # Python < 3.9 (not expected; defensive)
    ZoneInfo = None  # type: ignore[assignment]

from ._credentials import _user_dir

logger = logging.getLogger(__name__)

_API_BASE = "https://intervals.icu/api/v1"

# Cache TTLs in seconds
_TTL_PROFILE = 6 * 3600  # athlete profile changes rarely
_TTL_SPORT_SETTINGS = 6 * 3600
_TTL_ACTIVITIES = 15 * 60  # workouts update after syncing a ride
_TTL_WELLNESS = 15 * 60
_TTL_EVENTS = 15 * 60
_TTL_POWER_CURVE = 30 * 60

# Transient-failure retry: a single retry on 429 (rate limit) / 503 (service
# unavailable) only. 401/404/422 and network URLErrors are not retried — they
# are not transient in a way a retry fixes, and retrying URLError would add
# latency to every real outage. 429/503 are the cases where a multi-athlete
# bot benefits from a transparent retry.
_MAX_RETRIES = 1
_BACKOFF_BASE = 0.5  # seconds


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
        # Stale entry — remove it so the cache directory doesn't grow unbounded
        # over months of use (each user accumulates one file per unique
        # endpoint+params call). Best-effort; ignore concurrent removal.
        try:
            path.unlink()
        except OSError:
            pass
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _cache_set(discord_id: str, cache_key: str, data: Any) -> None:
    path = _cache_dir(discord_id) / f"{cache_key}.json"
    path.write_text(json.dumps(data), encoding="utf-8")


def _auth_header(api_key: str) -> str:
    """Build the Basic Auth header value for intervals.icu."""
    token = base64.b64encode(f"API_KEY:{api_key}".encode()).decode()
    return f"Basic {token}"


def _retry_after_seconds(exc: urllib.error.HTTPError) -> float:
    """Parse the Retry-After header (seconds) from a 429, or 0.0 if absent."""
    try:
        return float(exc.headers.get("Retry-After", "0") or 0)
    except (TypeError, ValueError):
        return 0.0


def _request(
    athlete_id: str,
    api_key: str,
    path: str,
    params: Optional[dict] = None,
    timeout: int = 20,
) -> Any:
    """Make an authenticated GET request to intervals.icu and return parsed JSON.

    Retries once on 429/503 (honouring Retry-After) with backoff. 401 raises
    ValueError (re-onboard); other HTTP errors and network failures raise
    RuntimeError.
    """
    url = f"{_API_BASE}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(
            {k: v for k, v in params.items() if v is not None}
        )
    headers = {
        "Authorization": _auth_header(api_key),
        "Accept": "application/json",
        "User-Agent": "hermes-coach/1.0",
    }

    for attempt in range(_MAX_RETRIES + 1):
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code == 401:
                raise ValueError(
                    "intervals.icu returned 401 Unauthorized. "
                    "Your API key may have expired — please run /start to reconnect."
                ) from exc
            if exc.code in (429, 503) and attempt < _MAX_RETRIES:
                wait = _retry_after_seconds(exc) or (_BACKOFF_BASE * (2 ** attempt))
                time.sleep(wait)
                continue
            raise RuntimeError(
                f"intervals.icu API error {exc.code}: {exc.reason}"
            ) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(
                f"Could not reach intervals.icu: {exc.reason}"
            ) from exc
    # Unreachable: the loop either returns or raises on every path.
    raise RuntimeError("intervals.icu request failed after retries")


def _post_json(
    athlete_id: str,
    api_key: str,
    path: str,
    payload: dict,
    timeout: int = 20,
) -> Any:
    """POST JSON to intervals.icu and return the parsed response."""
    del athlete_id  # path already contains the athlete_id; kept for call symmetry
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
            raise ValueError(
                "intervals.icu 401. API key may have expired — run /start."
            ) from exc
        raise RuntimeError(
            f"intervals.icu error {exc.code}: {exc.reason}. Body: {body}"
        ) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Could not reach intervals.icu: {exc.reason}") from exc


def _delete_json(
    athlete_id: str,
    api_key: str,
    path: str,
    timeout: int = 20,
) -> bool:
    """DELETE an intervals.icu resource; return True on 200/204."""
    del athlete_id  # path already contains the athlete_id; kept for call symmetry
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


def _today_date(tz: Optional[str] = None) -> date:
    """Current date in the athlete's timezone (best-effort).

    Falls back to server-local time when tz is None, unknown, or zoneinfo is
    unavailable, so callers can always pass an optional tz safely.
    """
    if tz and ZoneInfo is not None:
        try:
            return datetime.now(ZoneInfo(tz)).date()
        except Exception:
            pass  # unknown zone -> server-local fallback
    return date.today()


def _today_iso(tz: Optional[str] = None) -> str:
    return _today_date(tz).isoformat()


def _n_days_ago_iso(n: int, tz: Optional[str] = None) -> str:
    return (_today_date(tz) - timedelta(days=n)).isoformat()
