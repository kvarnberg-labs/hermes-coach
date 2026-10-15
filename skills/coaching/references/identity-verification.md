# Identity verification and credential isolation

Load when `verify_athlete_identity` returns `verified: false`, a tool returns
"User identity not available", or the athlete says the data is not theirs.

## Rules

- Call `verify_athlete_identity` before any training data, every session, then
  `get_athlete_profile` as a secondary check (name, athlete ID).
- `verified: false` → stop all training-data calls. The only fix you offer is
  for the athlete to re-run `/start` (coach_onboard), which writes key,
  athlete ID and display name in one step. Re-verify afterwards.
- Never use, infer or mention another athlete's credentials, IDs or data, and
  never fall back to a shared slot. Each Discord user has their own credential
  directory; the plugin refuses calls without a valid Discord identity.
- If the athlete says "that's not me" or the data shows sports or names that do
  not fit, re-verify immediately. Do not defend the data.

## What `verify_athlete_identity` returns

| Result | Meaning | Say / do |
|---|---|---|
| `verified: true` | Key, athlete ID, stored name and API profile all match | Proceed |
| `mismatched_fields: [credentials]` | No key files — never onboarded | Ask for `/start` |
| `mismatched_fields: [no_stored_name]` | Credentials not written by onboarding | Ask for `/start` |
| `mismatched_fields: [api_request]` | Key invalid or expired | Ask for `/start` with a fresh intervals.icu API key |

A stored Discord display name may legitimately differ from the intervals.icu
account name; the athlete ID match and the presence of a stored name are what
count.

## "User identity not available — the Discord gateway did not provide a valid user ID"

The session lost its Discord identity; the credentials are fine. In a DM, tell
the athlete to start a new conversation with `/new`. Do not attempt any
credential repair. (Scheduled runs: see `references/cron-coaching-runtime-recipe.md`.)

## After a deploy

If verification fails right after a bot update, the sanctioned recovery is the
same: `/start`, then re-verify. Manual credential repair is an operator
break-glass procedure (repo `docs/OPS-BREAKGLASS.md`, not available in chat).
