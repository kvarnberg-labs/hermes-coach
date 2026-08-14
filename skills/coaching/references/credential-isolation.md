# Per-User Credential Isolation

How intervals.icu credentials are isolated per Discord user, preventing
wrong-athlete data leaks.

## Architecture

### Credential directory resolution

```
Discord adapter → source.user_id (snowflake, e.g. "117694354092457986")
  → handle_function_call(..., user_id=source.user_id)
    → registry.dispatch(..., user_id="117694354092457986")
      → _require_user_id(kw) reads kw["user_id"]
        → returns "117694354092457986" (matches snowflake regex)
          → _user_dir("117694354092457986")
            → /opt/data/users/117694354092457986/
```

Each athlete gets their own directory under `$HERMES_HOME/users/<snowflake>/`
containing:

| File | Purpose |
|------|---------|
| `intervals_key` | intervals.icu API key (mode 0600) |
| `intervals_athlete_id` | intervals.icu athlete ID, e.g. `i344591` |
| `intervals_athlete_name` | Discord display name, written during onboarding |
| `cache/*.json` | Cached API responses (per-user, 15min–6h TTL) |

### Fallback behavior (historical: removed via PR #32, 2026-07-20)

Previously, when `kw["user_id"]` didn't match the Discord snowflake regex,
`_require_user_id` fell back to the literal string `discord_dm` — a shared
directory for all non-Discord contexts (cron, CLI). This was removed because
it caused cross-athlete data leaks: any session that lost the `user_id`
injection would load the shared credentials, showing one athlete's data to
another.

**Current behavior:** `_require_user_id` raises `ValueError` when `user_id`
is not a valid Discord snowflake. The tool registration wrappers catch this
and return a clear JSON error: *"User identity not available — the Discord
gateway did not provide a valid user ID."* No shared fallback directory exists.

The `_FALLBACK_USER_ID` constant was removed. Every coaching tool call
requires a valid Discord snowflake or gets an explicit error.

### `_user_dir` hardening (PR #18)

The function no longer falls back to `Path.home() / ".hermes"` when
`HERMES_HOME` is unset. Instead it raises `RuntimeError`. This eliminates
the split-brain credential state where two directories on the same PVC
held different athletes' data:

- `/opt/data/users/discord_dm/` (HERMES_HOME path)
- `/opt/data/home/.hermes/users/discord_dm/` (Path.home() fallback)

## Onboarding flow

When an athlete runs `/start` in Discord:

1. `coach_onboard` receives `discord_id` = the athlete's snowflake (via
   `_require_user_id(kw)`)
2. Validates credentials against the intervals.icu API
3. Calls `store_user_credentials(discord_id, athlete_id, api_key, athlete_name)`
   - `athlete_name` = the athlete's Discord display name
4. Credentials are written to `/opt/data/users/<snowflake>/`
5. The name file proves onboarding ran — `verify_athlete_identity` checks
   for its presence

## Verification flow

At the start of every coaching session:

1. Call `verify_athlete_identity` — fetches the API profile using stored
   credentials and checks:
   - Credential files exist (key + athlete_id)
   - `intervals_athlete_name` file exists (proves onboarding ran)
   - API returns a valid profile for the stored athlete_id
2. If `verified: false`, stop — see `references/credential-path-mismatch.md`
   for diagnosis steps

## Migrating from the old shared `discord_dm` slot

When upgrading from a pre-isolation deployment:

1. The old `discord_dm` directory may still contain credentials from the
   last user who onboarded before the update
2. Each athlete must re-run `/start` to create their per-user directory
3. **Delete the old `discord_dm` directory** — the code path that used it
   was removed in PR #32. Leaving it in place is a latent risk: any future
   code that accidentally resolves to `discord_dm` could load stale credentials.
4. If an athlete's API key was stored in `discord_dm` and needs to be migrated
   manually (e.g. they can't re-onboard immediately), copy all three credential
   files to the new per-user directory, then delete `discord_dm/`.

## What `hermes pairing` does and doesn't do

- **Does:** Gates who can DM the bot (access control)
- **Does NOT:** Isolate credentials — that's handled by the per-user directory
  architecture described above
- Pairing + per-user isolation together provide full multi-user support:
  only approved users can talk to the bot, and each gets their own credential slot