# Ops Break-Glass — live-pod recovery recipes

NOT synced to the pod: docs/ is not copied into the image (see Dockerfile), so
athlete sessions never see this file. For humans and dev sessions only.
AGENTS.md rule: changes go through PRs — these recipes are for emergencies
and revert on pod restart.

## Credential recovery (live-pod fix)

If `verify_athlete_identity` returns `verified: false`, the athlete's credentials
are missing, stale, or were manually placed without onboarding. The proper fix is
for the athlete to re-run `/start` (coach_onboard), which writes to the per-user
directory at `/opt/data/users/<snowflake>/`.

For a **temporary live-pod fix** (reverts on pod restart) — this recipe was also
moved from `skills/coaching/references/credential-path-mismatch.md`
("Live-pod credential fix"), which was an identical copy:

```bash
mkdir -p $HERMES_HOME/users/<snowflake>
echo -n "<api_key>" > $HERMES_HOME/users/<snowflake>/intervals_key
echo -n "<athlete_id>" > $HERMES_HOME/users/<snowflake>/intervals_athlete_id
echo -n "<discord_name>" > $HERMES_HOME/users/<snowflake>/intervals_athlete_name
chmod 600 $HERMES_HOME/users/<snowflake>/intervals_*
rm -f $HERMES_HOME/users/<snowflake>/cache/*.json
```

Without the name file, `verify_athlete_identity` returns `verified: false` with
`mismatched_fields: ["no_stored_name"]`. See
`skills/coaching/references/identity-verification.md` and
`skills/coaching/references/credential-isolation.md` (repo paths — `docs/` and
`skills/` are different trees).

## Credential recovery for the removed discord_dm shared dir (legacy)

Moved from `skills/coaching/references/identity-verification.md` (2026-09-14).
`discord_dm` is LEGACY: the shared fallback was removed by PR #32 — sessions
without a valid user_id fail loudly instead of silently loading shared
credentials. Do NOT restore this pattern; use per-snowflake directories (the
section above). Preserved as a historical record only:

```bash
echo -n "<api_key>" > /opt/data/users/discord_dm/intervals_key
echo -n "<athlete_id>" > /opt/data/users/discord_dm/intervals_athlete_id
echo -n "<discord_name>" > /opt/data/users/discord_dm/intervals_athlete_name
chmod 600 /opt/data/users/discord_dm/intervals_*
```

## Live-pod plugin edit + end-to-end test (former SKILL.md tool-improvement steps 3–4; also from tool-improvement-workflow.md)

The `patch` and `write_file` tools block the live path `/opt/hermes/plugins/training/`,
but the sandbox path `/opt/data/plugins/training/` is writable.

1. **Copy the live plugin to the editable sandbox path, then patch:**
   ```bash
   cp /opt/hermes/plugins/training/<file>.py /opt/data/plugins/training/<file>.py
   ```
   Edit at `/opt/data/plugins/training/<file>.py`; after editing, sync back with
   `cp /opt/data/plugins/training/<file>.py /opt/hermes/plugins/training/<file>.py`.
   For test files, write directly to `/opt/data/tests/` — no sandbox copy needed.
2. **Test end-to-end on real data before writing unit tests.** The plugin at
   `/opt/data/plugins/training/` is importable and has access to live credentials
   (note: import via the `training` package — the plugin uses package-relative
   imports, so `PYTHONPATH` must point at the plugins dir, and the athlete is
   addressed by snowflake, never the legacy `discord_dm` slot):
   ```bash
   cd /opt/data && HERMES_HOME=/opt/data PYTHONPATH=/opt/data/plugins python3 -c "
   from training.intervals_icu import <new_fn>
   print(<new_fn>('<snowflake>', ...))
   "
   ```
   This catches API endpoint errors, field-name mismatches, and response-size
   issues before they become test debt.

## Reading credentials for manual API calls (from tool-improvement-workflow.md)

For verifying an endpoint's shape before implementing a tool (Step 0), reading
the athlete's key directly is acceptable FOR OPS ONLY:

```bash
ATHLETE_ID=$(cat /opt/data/users/<snowflake>/intervals_athlete_id)
API_KEY=$(cat /opt/data/users/<snowflake>/intervals_key)
AUTH=$(echo -n "API_KEY:${API_KEY}" | base64)

curl -s "https://intervals.icu/api/v1/activity/<activity_id>/streams" \
  -H "Authorization: Basic ${AUTH}" | python3 -m json.tool | head -30
```

(The original recipe read the legacy `discord_dm` dir; updated to per-snowflake.)

GitHub token, for manual git/API operations when create-pr.sh is unavailable:

```bash
export GITHUB_TOKEN=$(cat /opt/data/.github_token)
```

## Snowflake enumeration for ops (from cron-coaching.md)

Human/ops use only — an athlete session must never be able to enumerate other
users. Lists every onboarded athlete's snowflake and display name:

```bash
ls -d /opt/data/users/*/intervals_athlete_name | while read f; do
  dir=$(dirname "$f")
  snowflake=$(basename "$dir")
  name=$(cat "$f")
  echo "$snowflake → $name"
done
```

The snowflake is the 17–20 digit directory name under `/opt/data/users/`.

## Direct API access + identity-check bypass (from references/intervals-icu-direct-api.md — DELETED from the shipped skill)

Historical troubleshooting record for the `User identity check failed` error.
**CAUTION:** the `_require_user_id` fallback below restores the `discord_dm`
shared slot that PR #32 deliberately removed — restoring it reintroduces the
cross-athlete data leak (all users silently sharing one credential directory).
Do not apply; kept as a record of the old (bad) workarounds.

Historical root cause: `handle_function_call()` in `/opt/hermes/model_tools.py`
passed `task_id`, `session_id`, and `user_task` to `registry.dispatch()` but
never `user_id`, so `_require_user_id(kw)` always saw an empty string.

Old workaround 1 — store credentials in the shared dir (DO NOT USE):

```bash
mkdir -p $HERMES_HOME/users/discord_dm
echo -n "<api_key>" > $HERMES_HOME/users/discord_dm/intervals_key
echo -n "<athlete_id>" > $HERMES_HOME/users/discord_dm/intervals_athlete_id
chmod 600 $HERMES_HOME/users/discord_dm/intervals_key
chmod 600 $HERMES_HOME/users/discord_dm/intervals_athlete_id
```

Old workaround 2 — patch the identity check (DO NOT USE). In
`/opt/hermes/plugins/training/intervals_icu.py`, `_require_user_id` was modified
to fall back to `"discord_dm"` when `kw["user_id"]` is empty:

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

Old workaround 3 — develop_tool identity bypass (DO NOT USE; now also
mechanically rejected): "use `develop_tool` to create standalone tools that
load credentials from filesystem/env vars without depending on the Discord
identity check." The develop_tool static guard bans exactly this class of
code, and the identity check exists to prevent cross-athlete data access.

## Direct event POST (from event-creation-pitfalls.md)

Fallback when `create_planned_event` is unavailable — reads the athlete's key
directly; ops use only (athlete sessions must use the tool):

```bash
cd /opt/data && python3 -c "
import urllib.request, json, base64

base = '/opt/data/users/<snowflake>'
with open(f'{base}/intervals_key') as f:
    api_key = f.read().strip()
with open(f'{base}/intervals_athlete_id') as f:
    athlete_id = f.read().strip()

url = f'https://intervals.icu/api/v1/athlete/{athlete_id}/events'
auth = base64.b64encode(f'API_KEY:{api_key}'.encode()).decode()

payload = {
    'name': 'Workout Name',
    'type': 'Ride',
    'category': 'WORKOUT',
    'start_date_local': '2026-07-31T09:00:00',
    'description': 'Description text.',
    'icu_training_load': 110,
    'icu_intensity': 100
}

req = urllib.request.Request(url, data=json.dumps(payload).encode(),
    headers={'Authorization': f'Basic {auth}', 'Content-Type': 'application/json',
             'User-Agent': 'hermes-coach/1.0'}, method='POST')

resp = urllib.request.urlopen(req)
print(json.loads(resp.read()))
"
```

## Long-range raw queries (from references/long-range-queries.md — DELETED; get_athlete_stats now covers YTD aggregation)

Historical escape hatch for date ranges beyond the tools' built-in limits.
`get_athlete_stats` now covers year-to-date aggregation through the tool path;
keep this only for ops diagnostics:

```bash
python3 -c "
import os, json, urllib.request, base64
d = '/opt/data/users/<snowflake>'
ak = open(f'{d}/intervals_key').read().strip()
aid = open(f'{d}/intervals_athlete_id').read().strip()
auth = base64.b64encode(f'API_KEY:{ak}'.encode()).decode()
url = f'https://intervals.icu/api/v1/athlete/{aid}/activities?oldest=2026-01-01&newest=2026-07-22'
req = urllib.request.Request(url, headers={'Authorization': f'Basic {auth}', 'Accept': 'application/json', 'User-Agent': 'hermes-coach/1.0'})
data = json.loads(urllib.request.urlopen(req).read())
print(sum(a.get('calories', 0) or 0 for a in data))
"
```

Gotcha preserved from the original: using the api_key directly as the Basic
token (without the `API_KEY:` username prefix and base64) returns HTTP 401.
The Basic-auth username is the literal string `API_KEY`.
