# Credential Path Mismatch — Wrong Athlete Data

## Status: Largely Resolved

The original credential mismatch bug (wrong athlete's data silently returned)
is now addressed by three layered fixes:

1. **Hermes core update** — `handle_function_call` in `model_tools.py` now
   accepts a `user_id` parameter and threads it to `registry.dispatch()`, so
   the Discord adapter's `source.user_id` (the athlete's snowflake) reaches
   plugin tool handlers via `kw["user_id"]`.

2. **PR #15 — `verify_athlete_identity` tool** — stores the athlete's Discord
   display name during onboarding and verifies credentials against the API
   at the start of each session. Returns `verified: false` with specific
   `mismatched_fields` when something is wrong.

3. **PR #18 — `_user_dir` hardening** — removed the `Path.home()` fallback
   that created a second, independent credential directory. `_user_dir` now
   raises `RuntimeError` if `HERMES_HOME` is unset rather than silently
   switching paths.

## Historical Context (for diagnosing legacy issues)

### Original root cause

The plugin's `_user_dir()` function resolved credentials from:

```python
Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes")) / "users" / discord_id
```

With `HERMES_HOME=/opt/data`, the plugin read from `/opt/data/users/discord_dm/`.
But `Path.home()` resolved to `/opt/data/home` (not `/opt/data`), so the fallback
path was `/opt/data/home/.hermes/users/discord_dm/` — a completely different
directory. Both directories lived on the same PVC and persisted across restarts.

### Why the paths diverged

If `HERMES_HOME` was ever unset (cron session, plugin reload race, non-gateway
invocation), the plugin silently switched to the home-based path and read a
different athlete's credentials.

### Multi-user credential sharing (pre-fix)

The Discord platform adapter did NOT propagate `source.user_id` to tool dispatch.
`handle_function_call` only passed `task_id`, `session_id`, and `user_task` —
never `user_id`. Therefore `_require_user_id(kw)` always hit the `discord_dm`
fallback, and **all users shared the same credential slot**.

## Current architecture (post-fix)

See `references/credential-isolation.md` for the full per-user credential
isolation design.

## Diagnosis (if wrong-athlete data recurs)

1. Call `verify_athlete_identity` — check `verified`, `mismatched_fields`.
2. If `verified: false`, call `get_athlete_profile` — check `name` and `athlete_id`.
3. Check which credential directory is in use:
   ```bash
   echo "HERMES_HOME=$HERMES_HOME"
   ls /opt/data/users/<snowflake>/  # the athlete's own credential directory (never enumerate other users')
   cat /opt/data/users/<snowflake>/intervals_athlete_id
   ```
4. If old `discord_dm` directory still exists with stale credentials, that means
   the athlete hasn't re-onboarded since the per-user isolation update.

## Credential recovery

The sanctioned fix for stale or wrong credentials is re-onboarding via `/start`
(coach_onboard), which writes all three per-user files and verifies against
the API in one step. Manual per-snowflake credential writes are a break-glass
operation — documented only in the repo's `docs/OPS-BREAKGLASS.md` (not
shipped to athlete sessions).

## Prevention

- **Call `verify_athlete_identity` at the start of every coaching session.**
  This tool detects stale/wrong credentials before any training data is pulled.
- After verification passes, call `get_athlete_profile` as secondary confirmation.
- If the athlete says "you're looking at the wrong person" or questions the data,
  check identity immediately — do not argue or defend the data.

---

## Moved from SKILL.md (2026-09-14)

- **Credential path mismatch causes wrong-athlete data.** The plugin resolves credentials from `Path(HERMES_HOME) / "users" / discord_id`. With `HERMES_HOME=/opt/data`, it reads from `/opt/data/users/discord_dm/`. If wrong credentials are in that path, ALL tools silently return the wrong athlete's data. **Prevention:** `verify_athlete_identity` catches this — it returns `verified: false` when credentials lack a stored name (manually placed) or the API profile mismatches. The permanent fix (PR #15) adds identity verification. **Live fix:** copy correct credential files AND write `intervals_athlete_name` (Discord username), then call `verify_athlete_identity`. This reverts on pod restart. See `references/identity-verification.md`.
