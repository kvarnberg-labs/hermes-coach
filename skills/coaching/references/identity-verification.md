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

## Live credential fix with name file

When manually storing credentials (API key + athlete_id in chat), also write
the athlete's Discord name so `verify_athlete_identity` passes:

```bash
echo -n "<api_key>" > /opt/data/users/discord_dm/intervals_key
echo -n "<athlete_id>" > /opt/data/users/discord_dm/intervals_athlete_id
echo -n "<discord_name>" > /opt/data/users/discord_dm/intervals_athlete_name
chmod 600 /opt/data/users/discord_dm/intervals_*
```

Without the name file, `verify_athlete_identity` returns `verified: false`
even if the credentials are correct — it's a signal that onboarding never ran.

## How it prevents the wrong-athlete bug

**Before:** credentials silently loaded → API returns data for whichever
athlete_id is in the file → no way to detect mismatch without manually
checking profile name.

**After:** `verify_athlete_identity` called first → checks for stored name +
API match → if `verified: false`, the agent knows credentials are stale or
unverified and stops before pulling any training data.

## Credential persistence on pod restart

After a PR merge triggers Flux deployment, the credential files at
`/opt/data/users/discord_dm/` may revert to the baked-in image state.
The persistent volume survives the restart, but an init container or
ConfigMap apparently restores the default credentials (the original
onboarded athlete). **Impact:** the athlete must re-provide their API
key after every deploy until the root cause is found and fixed.

**Recovery checklist after every deploy:**
1. Call `verify_athlete_identity` — if `verified: false`, credentials reverted
2. Ask the athlete for their API key
3. Re-write all three files (key, athlete_id, athlete_name)
4. Clear the cache: `rm -f /opt/data/users/discord_dm/cache/*.json`
5. Call `verify_athlete_identity` again — should return `verified: true`
