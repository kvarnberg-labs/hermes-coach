"""Live model driver for `scripts/eval_decisions.py --live`.

Contract (`scripts/eval_decisions.py:drive_live`): one case JSON on stdin, one
transcript JSON on stdout, nothing else.

The case is replayed, not re-run: a tool call returns the frozen payload the live
session produced instead of hitting intervals.icu, so the score depends on the
model's decisions and not on today's API. Tool *schemas* are the real ones,
imported from `plugins/training`: a driver with invented schemas measures the
prompt author's imagination, not the coach.

Model config from env only, never argv (argv is visible in `ps`):
  HERMES_DRIVER_API_KEY    required; a missing key exits 3, the key is never echoed
  HERMES_DRIVER_BASE_URL   default https://opencode.ai/zen/go/v1
  HERMES_DRIVER_MODEL      default deepseek-v4.1-flash
  HERMES_DRIVER_MAX_STEPS  default 8 tool-call rounds per case

    PYTHONPATH=plugins python scripts/eval_decisions.py --live \
        --driver 'PYTHONPATH=plugins python scripts/live_driver.py'
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_BASE_URL = "https://opencode.ai/zen/go/v1"
DEFAULT_MODEL = "deepseek-v4.1-flash"
FIXTURES_DIR = (Path(__file__).resolve().parent.parent
                / "tests" / "golden" / "decisions" / "fixtures")

# Fixture filename prefix -> the tool that produced the payload
# (tests/golden/decisions/fixtures/, one file per tool call in the real session).
FIXTURE_TOOLS = {
    "wellness-": "get_wellness",
    "activities-": "get_recent_activities",
    "planned-events-": "get_planned_events",
    "athlete-profile-": "get_athlete_profile",
    "sport-settings-": "get_sport_settings",
    "identity-": "verify_athlete_identity",
}

SYSTEM_MESSAGE = (
    "This is a replay of a real athlete conversation. Tools return data recorded "
    "from that session, not live data; call them as you normally would."
)


def _message(role: str, content: str, tool: str | None = None,
             args: dict | None = None, ok: bool | None = None) -> dict:
    """One transcript message, in the shape decision_predicates reads."""
    return {"role": role, "tool": tool, "args": args, "content": content, "ok": ok}


def model_config() -> dict:
    """Env only. A missing key exits 3 before anything else is attempted."""
    key = os.environ.get("HERMES_DRIVER_API_KEY", "")
    if not key:
        print("set HERMES_DRIVER_API_KEY (env only; it is never echoed)", file=sys.stderr)
        raise SystemExit(3)
    try:
        max_steps = int(os.environ.get("HERMES_DRIVER_MAX_STEPS", "8"))
    except ValueError:
        raise SystemExit("HERMES_DRIVER_MAX_STEPS must be an integer") from None
    return {
        "key": key,
        "base_url": os.environ.get("HERMES_DRIVER_BASE_URL", DEFAULT_BASE_URL).rstrip("/"),
        "model": os.environ.get("HERMES_DRIVER_MODEL", DEFAULT_MODEL),
        "max_steps": max_steps,
    }


def load_fixtures(case: dict) -> dict[str, str]:
    """fixture filename -> payload as JSON text.

    `eval_decisions.py` ships parsed payloads under `_fixtures`; a bare `fixtures`
    name list is resolved against the committed case fixtures. Neither present is
    a driver with no data, which would grade a model that never got any.
    """
    shipped = case.get("_fixtures") or {}
    names = list(shipped) or list(case.get("fixtures") or [])
    if not names:
        raise SystemExit(f"case {case.get('id')} has no fixture payloads; "
                         "a driver with no data grades nothing")
    payloads = {}
    for name in names:
        path = FIXTURES_DIR / name
        if name in shipped:
            payloads[name] = json.dumps(shipped[name])
        elif path.is_file():
            payloads[name] = path.read_text(encoding="utf-8")
        else:
            raise SystemExit(f"case {case.get('id')}: no payload for fixture {name} "
                             f"(not in _fixtures, no {path})")
    return payloads


def fixture_tools(payloads: dict[str, str]) -> dict[str, str]:
    """tool -> fixture filename.

    An unmapped fixture exits: silently skipping it grades a model that never got
    the data the case was built around.
    """
    table: dict[str, str] = {}
    for name in payloads:
        matches = [tool for prefix, tool in FIXTURE_TOOLS.items() if name.startswith(prefix)]
        if len(matches) != 1:
            raise SystemExit(f"fixture {name} maps to {len(matches)} tools, expected exactly one; "
                             f"known prefixes: {', '.join(FIXTURE_TOOLS)}")
        table[matches[0]] = name
    return table


class _Recorder:
    """The plugin ctx, recording schemas: the driver reads schemas, never handlers."""

    def __init__(self) -> None:
        self.schemas: list[dict] = []

    def register_tool(self, **kwargs) -> None:
        self.schemas.append(kwargs["schema"])

    def register_hook(self, *args, **kwargs) -> None:
        pass

    def register_command(self, *args, **kwargs) -> None:
        pass


def training_schemas() -> list[dict]:
    """Every schema the coaching plugin registers — the tool surface the model sees
    in production."""
    try:
        import training

        recorder = _Recorder()
        training.register(recorder)
    except Exception as exc:  # noqa: BLE001 - any failure here means no schemas
        raise SystemExit(
            f"cannot load the training plugin's tool schemas ({exc!r}): run the driver "
            "with PYTHONPATH=plugins so it measures the real tools"
        ) from None
    return recorder.schemas


def _post(config: dict, payload: dict) -> dict:
    """One OpenAI-compatible chat completion."""
    request = urllib.request.Request(
        f"{config['base_url']}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {config['key']}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        # Body only: the request headers carry the key.
        body = exc.read().decode("utf-8", "replace")[:200]
        raise SystemExit(f"model call failed: HTTP {exc.code}: {body}") from None
    except urllib.error.URLError as exc:
        raise SystemExit(f"model call failed: {exc.reason}") from None


def _tool_args(call: dict) -> dict:
    """Echoed args, minus identifiers a transcript must never carry."""
    try:
        args = json.loads(call["function"].get("arguments") or "{}")
    except json.JSONDecodeError:
        return {}
    if not isinstance(args, dict):
        return {}
    return {key: value for key, value in args.items() if key != "discord_id"}


def _tool_content(fixtures: dict[str, str], name: str) -> tuple[str, bool]:
    """Replayed payload for a tool call, or an error the model can read.

    A tool with no fixture is reported and the loop continues: the case measures
    what the coach does with what it has, not whether the fixture set is complete.
    """
    if name in fixtures:
        return fixtures[name], True
    return json.dumps({"error": f"no fixture for {name} in this case"}), False


def drive(case: dict, schemas: list[dict], fixtures: dict[str, str], config: dict) -> dict:
    """One model run. Tool calls replay fixtures until the model answers or
    `max_steps` runs out."""
    tool_specs = [{"type": "function", "function": schema} for schema in schemas]
    athlete_message = case["athlete_message"]
    messages = [_message("user", athlete_message)]
    api_messages = [{"role": "system", "content": SYSTEM_MESSAGE},
                    {"role": "user", "content": athlete_message}]
    truncated = True
    for _step in range(config["max_steps"]):
        reply = _post(config, {"model": config["model"], "temperature": 0,
                               "messages": api_messages, "tools": tool_specs})
        reply_message = reply["choices"][0]["message"]
        calls = reply_message.get("tool_calls") or []
        if not calls:
            messages.append(_message("assistant", reply_message.get("content") or ""))
            truncated = False
            break
        api_messages.append({"role": "assistant", "tool_calls": calls,
                             "content": reply_message.get("content") or ""})
        for call in calls:
            name = call["function"]["name"]
            content, ok = _tool_content(fixtures, name)
            # `result` mirrors `content`: decision_predicates reads tool payloads
            # from `result` to see a verify_athlete_identity that returned a 401.
            messages.append({**_message("tool", content, tool=name,
                                        args=_tool_args(call), ok=ok), "result": content})
            api_messages.append({"role": "tool", "tool_call_id": call.get("id") or name,
                                 "content": content})
    transcript = {"case_id": case["id"], "chat_type": case.get("chat_type"),
                  "messages": messages}
    if truncated:
        transcript["truncated"] = True
    return transcript


def main() -> int:
    config = model_config()
    case = json.load(sys.stdin)
    payloads = load_fixtures(case)
    fixtures = {tool: payloads[name] for tool, name in fixture_tools(payloads).items()}
    transcript = drive(case, training_schemas(), fixtures, config)
    print(json.dumps(transcript, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
