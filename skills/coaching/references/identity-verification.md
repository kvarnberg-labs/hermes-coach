# Identity Verification Flow

New tool: `verify_athlete_identity` (PR #15) — validates that stored credentials
belong to the expected athlete before any training data is pulled.

## What it checks

1. **Credentials exist** — key and athlete_id files present and non-empty
2. **Stored name exists** — `intervals_athlete_name` file present (proves onboarding ran)
3. **API matches** — the /athlete/{id} endpoint returns a valid profile

Returns `verified: true` only when all three pass.

## Verification output

```json
{
  "verified": false,
  "mismatched_fields": ["no_stored_name"],
  "error": "Credentials were not written through the onboarding flow...",
  "stored_athlete_id": "i494629",
  "stored_name": null,
  "api_name": "Millberg"
}
```

| Field | Signal |
|---|---|
| `verified: false, mismatched_fields: [no_stored_name]` | Credentials manually placed — unverified |
| `verified: false, mismatched_fields: [credentials]` | No key files at all — never onboarded |
| `verified: false, mismatched_fields: [api_request]` | Key is invalid or expired |
| `verified: true` | Everything matches — proceed |

## When to call

1. **Start of every coaching session** — before `get_athlete_profile`
2. **After manually writing credentials** — verify they took effect
3. **When athlete questions the data** — confirm the key belongs to them

## Manual credential placement

Credentials should arrive via onboarding only. If `verify_athlete_identity`
returns `verified: false` with `mismatched_fields: ["no_stored_name"]`,
credentials were placed without onboarding — the sanctioned fix is for the
athlete to re-run `/start` (coach_onboard), which writes the key, athlete_id,
and display name in one step and verifies against the API. Break-glass
recovery (ops only, not shipped to athlete sessions) lives in the repo's
`docs/OPS-BREAKGLASS.md`.

## How it prevents the wrong-athlete bug

**Before:** credentials silently loaded → API returns data for whichever
athlete_id is in the file → no way to detect mismatch without manually
checking profile name.

**After:** `verify_athlete_identity` called first → checks for stored name +
API match → if `verified: false`, the agent knows credentials are stale or
unverified and stops before pulling any training data.

## Credential persistence on pod restart

Historical incident: after a PR merge triggered a Flux deployment, an
athlete's credentials appeared to revert to a stale state (the persistent
volume survived, but credentials were evidently overwritten during
startup). **Impact as recorded then:** the athlete had to re-provide their
API key after deploys until the root cause was found.

**Recovery (sanctioned):** after any deploy, if `verify_athlete_identity`
returns `verified: false`, ask the athlete to re-run `/start` — onboarding
re-writes the per-user credential files and the stored name in one step,
then re-verify. Manual credential-file re-writing is a break-glass operation
and is documented only in the repo's `docs/OPS-BREAKGLASS.md` (not shipped
to athlete sessions).

---

## Moved from SKILL.md (2026-09-14)

- **Verify athlete identity every session — use `verify_athlete_identity` first.** Call `verify_athlete_identity` before pulling any training data. If it returns `verified: false`, stop — credentials are stale, wrong, or manually placed without onboarding. Do not proceed until the athlete re-runs `/start` (`coach_onboard`). After verification passes, call `get_athlete_profile` as secondary confirmation that the name and athlete_id match expectations. This has been the #1 recurring bug (wrong athlete's data silently returned).
