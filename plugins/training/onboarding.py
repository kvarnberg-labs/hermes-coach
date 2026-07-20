"""Onboarding tool — /start command for connecting intervals.icu.

Registers a `coach_onboard` tool that Hermes calls when a user runs /start
or when their credentials are missing.  The tool drives the DM conversation:
  1. Ask for athlete ID (the iXXXXX ID visible in their intervals.icu URL)
  2. Ask for API key (from intervals.icu Settings → Developer → API Key)
  3. Validate against GET /api/v1/athlete/{id}
  4. Store credentials and confirm with athlete summary

This is a tool rather than a slash command so Hermes can invoke it
mid-conversation whenever credentials are missing (graceful re-onboarding).
"""

from __future__ import annotations

import json
import logging
from typing import Any

from .intervals_icu import _require_user_id

logger = logging.getLogger(__name__)


def coach_onboard(
    discord_id: str,
    athlete_id: str,
    api_key: str,
    athlete_name: str = "",
    **_: Any,
) -> str:
    """Store and validate an athlete's intervals.icu credentials.

    Call this after collecting the athlete_id and api_key from the user.
    Returns a success summary or an error message.

    Args:
        discord_id:    Discord user ID (injected by Hermes gateway).
        athlete_id:    intervals.icu athlete ID, e.g. "i12345".
        api_key:       intervals.icu API key from Settings → Developer.
        athlete_name:  The athlete's Discord display name.  Stored alongside
                       credentials so the verify_athlete_identity tool can
                       detect wrong-athlete credential files later.
    """
    from .intervals_icu import _request, store_user_credentials

    # Normalise athlete ID — users sometimes include the full URL
    athlete_id = athlete_id.strip().rstrip("/").split("/")[-1]
    if not athlete_id.startswith("i"):
        athlete_id = f"i{athlete_id}"

    api_key = api_key.strip()
    if not api_key:
        return json.dumps({"success": False, "error": "API key cannot be empty."})

    # Validate credentials by fetching the athlete profile
    try:
        data = _request(athlete_id, api_key, f"/athlete/{athlete_id}")
    except ValueError as exc:
        # 401 — bad credentials
        return json.dumps({
            "success": False,
            "error": str(exc),
            "hint": (
                "Double-check your athlete ID (it looks like i12345 in your "
                "intervals.icu URL) and your API key from "
                "Settings → Developer → API Key."
            ),
        })
    except RuntimeError as exc:
        return json.dumps({"success": False, "error": str(exc)})

    # Credentials valid — store them along with the display name
    store_user_credentials(discord_id, athlete_id, api_key, athlete_name)

    name = data.get("name") or "Athlete"
    ftp_hint = ""
    # Try to surface FTP from sport settings if present in the profile
    sport_settings = data.get("sportSettings") or []
    for ss in sport_settings:
        if ss.get("type") == "Ride" and ss.get("ftp"):
            ftp_hint = f"Cycling FTP: {ss['ftp']} W. "
            break

    return json.dumps({
        "success": True,
        "message": (
            f"Connected! Welcome, {name}. "
            f"{ftp_hint}"
            "Your intervals.icu account is now linked. "
            "You can ask me training questions and I'll use your real data."
        ),
        "athlete_id": athlete_id,
        "name": name,
        "security_note": (
            "For your security: please delete the Discord message where you shared "
            "your API key. You can edit or delete messages by right-clicking on them."
        ),
    })


def register_tools(ctx) -> None:
    def _coach_onboard_handler(args, **kw):
        try:
            uid = _require_user_id(kw)
        except ValueError as exc:
            return json.dumps({"error": str(exc)})
        return coach_onboard(
            discord_id=uid,
            athlete_id=args["athlete_id"],
            api_key=args["api_key"],
            athlete_name=args.get("athlete_name", ""),
        )

    ctx.register_tool(
        name="coach_onboard",
        toolset="training",
        schema={
            "name": "coach_onboard",
            "description": (
                "Store and validate an athlete's intervals.icu credentials. "
                "Call this after the user has provided their athlete ID and API key "
                "during the /start onboarding flow, or when their credentials are missing. "
                "Returns a success confirmation or an actionable error."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "athlete_id": {
                        "type": "string",
                        "description": (
                            "intervals.icu athlete ID, e.g. 'i12345'. "
                            "Found in the URL: intervals.icu/athlete/i12345"
                        ),
                    },
                    "api_key": {
                        "type": "string",
                        "description": (
                            "intervals.icu API key from Settings → Developer → API Key."
                        ),
                    },
                    "athlete_name": {
                        "type": "string",
                        "description": (
                            "The athlete's Discord display name. "
                            "Stored for identity verification so subsequent "
                            "sessions can detect wrong-athlete credential files."
                        ),
                    },
                },
                "required": ["athlete_id", "api_key"],
            },
        },
        handler=_coach_onboard_handler,
    )
