# Long-Range intervals.icu Queries (Beyond Tool Limits)

When the athlete asks for data spanning more than 90 days (e.g. "all calories in 2026"),
the built-in coaching tools can't cover the full range. The intervals.icu REST API
supports arbitrary date ranges via `oldest`/`newest` query params.

## When to Use

- Year-to-date aggregations (calories, TSS, hours, distance)
- Season-level summaries beyond `get_recent_activities(days=90)` max
- Any query where the athlete explicitly wants "all of 2026" or "since January"

## API Endpoint

```
GET https://intervals.icu/api/v1/athlete/{athlete_id}/activities?oldest=YYYY-MM-DD&newest=YYYY-MM-DD
```

Returns the full unfiltered activity list for the date range. Each activity includes
`calories`, `training_load`, `duration_min`, `distance_km`, etc.

## Auth Pattern

intervals.icu uses HTTP Basic Auth with a fixed username:

```python
import base64

auth = base64.b64encode(f"API_KEY:{api_key}".encode()).decode()
headers = {
    "Authorization": f"Basic {auth}",
    "Accept": "application/json",
    "User-Agent": "hermes-coach/1.0",
}
```

**Gotcha:** Using `{api_key}` directly as the Basic token (without `API_KEY:` prefix and
base64 encoding) returns HTTP 401. The username must be the literal string `API_KEY`.

## One-liner Template

Replace `<snowflake>` with the Discord snowflake and `oldest`/`newest` as needed:

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

## Pitfalls

- **This is for read-only aggregation queries only.** Do not use for routine training
  data retrieval — use the coaching tools (`get_recent_activities`, `get_wellness`, etc.)
  for all standard coaching workflows. This escape hatch is only for date ranges beyond
  the tools' built-in limits.
- **`get_activity_detail` still works for individual activities.** If you need
  per-activity zone data, fetch IDs via this method then call `get_activity_detail(id)`
  for each. Avoid doing that for more than ~10 activities — it's slow.
- **The response includes ALL activities unfiltered.** Summing only `calories` from
  activities where `type` is `Ride` or `VirtualRide` gives cycling-only totals.
  Use `a.get("calories")` and handle `None` — the field may be null for some types.
