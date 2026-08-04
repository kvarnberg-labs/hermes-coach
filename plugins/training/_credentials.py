"""Credential storage for intervals.icu athletes.

Extracted from intervals_icu.py (Candidate 2: split at the HTTP seam).

Interface functions — all take a Discord snowflake and operate on files:
    _require_user_id(kw: dict) -> str
    _user_dir(discord_id: str) -> Path
    _key_path(discord_id: str) -> Path
    _athlete_id_path(discord_id: str) -> Path
    _athlete_name_path(discord_id: str) -> Path
    store_user_credentials(discord_id, athlete_id, api_key, athlete_name="")
    _load_credentials(discord_id: str) -> (athlete_id, api_key)
    _load_verified_name(discord_id: str) -> Optional[str]

Imports from here instead of intervals_icu let onboarding.py avoid
tight-coupling to the entire 1,327-line module.
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Discord snowflake IDs are 17–20 decimal digits, never all-zeros.
_DISCORD_ID_RE = re.compile(r"^[1-9]\d{16,19}$")


def _require_user_id(kw: dict) -> str:
    """Return the Discord snowflake from the gateway, or raise ValueError."""
    uid = str(kw.get("user_id", ""))
    if _DISCORD_ID_RE.match(uid):
        return uid
    raise ValueError(
        "User identity not available — the Discord gateway did not provide "
        "a valid user ID.  Your training data cannot be loaded without "
        "a known identity.  Please reconnect or try again."
    )


def _user_dir(discord_id: str) -> Path:
    """Return the credential directory for a Discord user.

    Raises RuntimeError if HERMES_HOME is not set.
    """
    hermes_home_raw = os.environ.get("HERMES_HOME")
    if not hermes_home_raw:
        raise RuntimeError(
            "HERMES_HOME is not set — cannot resolve credential directory. "
            "The gateway must export HERMES_HOME before loading plugins."
        )
    hermes_home = Path(hermes_home_raw)
    d = hermes_home / "users" / str(discord_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _key_path(discord_id: str) -> Path:
    return _user_dir(discord_id) / "intervals_key"


def _athlete_id_path(discord_id: str) -> Path:
    return _user_dir(discord_id) / "intervals_athlete_id"


def _athlete_name_path(discord_id: str) -> Path:
    return _user_dir(discord_id) / "intervals_athlete_name"


def store_user_credentials(
    discord_id: str, athlete_id: str, api_key: str, athlete_name: str = ""
) -> None:
    """Persist an athlete's intervals.icu credentials."""
    key_file = _key_path(discord_id)
    key_file.write_text(api_key, encoding="utf-8")
    key_file.chmod(0o600)

    id_file = _athlete_id_path(discord_id)
    id_file.write_text(athlete_id.strip(), encoding="utf-8")
    id_file.chmod(0o600)
    logger.info("Stored intervals.icu credentials for discord_id=%s", discord_id)

    if athlete_name:
        name_file = _athlete_name_path(discord_id)
        name_file.write_text(athlete_name.strip(), encoding="utf-8")
        name_file.chmod(0o600)
        logger.info(
            "Stored athlete display name '%s' for discord_id=%s",
            athlete_name, discord_id,
        )


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


def _load_verified_name(discord_id: str) -> Optional[str]:
    """Return the athlete's Discord display name stored during onboarding."""
    name_file = _athlete_name_path(discord_id)
    if not name_file.exists():
        return None
    try:
        raw = name_file.read_text(encoding="utf-8").strip()
        return raw or None
    except Exception:
        return None
