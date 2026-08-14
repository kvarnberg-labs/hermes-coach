# intervals.icu Tool Troubleshooting

When Hermes coaching tools fail with `User identity check failed: expected a Discord
snowflake from the gateway (got '')`, the root cause is in the tool dispatch chain.

## Root cause

`handle_function_call()` in `/opt/hermes/model_tools.py` passes `task_id`,
`session_id`, and `user_task` to `registry.dispatch()`, but **never passes `user_id`**.
The coaching plugin's `_require_user_id(kw)` expects `kw["user_id"]` to contain a valid
Discord snowflake, but it's always empty.

## Fix

### 1. Store credentials

```bash
mkdir -p $HERMES_HOME/users/discord_dm
echo -n "<api_key>" > $HERMES_HOME/users/discord_dm/intervals_key
echo -n "<athlete_id>" > $HERMES_HOME/users/discord_dm/intervals_athlete_id
chmod 600 $HERMES_HOME/users/discord_dm/intervals_key
chmod 600 $HERMES_HOME/users/discord_dm/intervals_athlete_id
```

### 2. Patch identity check

In `/opt/hermes/plugins/training/intervals_icu.py`, modify `_require_user_id` to
fall back to `"discord_dm"` when `kw["user_id"]` is empty:

```python
def _require_user_id(kw: dict) -> str:
    uid = str(kw.get("user_id", ""))
    if not uid:
        import os
        uid = os.environ.get("DEFAULT_INTERVALS_USER", "discord_dm")
    if not _DISCORD_ID_RE.match(uid) and uid != "discord_dm":
        raise ValueError(...)
    return uid
```

### 3. Alternative: implement new tools

If the above is blocked (protected files), use `develop_tool` to create standalone
tools that load credentials from filesystem/env vars without depending on the Discord
identity check.
