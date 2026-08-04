"""intervals.icu HTTP transport and cache layer.

Extracted from intervals_icu.py (Candidate 2: split at the HTTP seam).

Interface:
    _API_BASE           — base URL
    _TTL_*              — cache TTL constants
    _cache_dir(id)      — Path to cache directory
    _cache_key(endpoint, params) -> str
    _cache_get(discord_id, key, ttl) -> Optional[Any]
    _cache_set(discord_id, key, data)
    _auth_header(api_key) -> str
    _request(athlete_id, api_key, path, params?, timeout?) -> Any
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
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Optional

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
        raise RuntimeError(
            f"intervals.icu API error {exc.code}: {exc.reason}"
        ) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(
            f"Could not reach intervals.icu: {exc.reason}"
        ) from exc


def _today_iso() -> str:
    return date.today().isoformat()


def _n_days_ago_iso(n: int) -> str:
    return (date.today() - timedelta(days=n)).isoformat()
