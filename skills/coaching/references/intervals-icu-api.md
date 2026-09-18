# intervals.icu API — how to look it up

The **OpenAPI spec is authoritative** and is already in the tool surface. Never
guess field names, payload shapes, or URL paths — look them up.

| Tool | Use it for |
|------|-----------|
| `search_intervals_api_docs(query)` | Keyword search across operations, or a tag overview when the query is empty |
| `get_intervals_api_endpoint(operation_id=…)` or `(method=…, path=…)` | Full detail for one operation, with `$ref`s resolved |

Both fetch `https://intervals.icu/api/v1/docs` and memoise it for 6 hours. No API
key needed. This is the same source the server is generated from, so it is current.

## Field names

- The API returns `icu_`-prefixed names for derived data (`icu_training_load`,
  `icu_hr_zones`, `icu_zone_times`, `icu_weighted_avg_watts`).
- Strava-style names are used for the plain aggregates: `average_heartrate`,
  `average_cadence`, `pace` — **not** `avg_heartrate` / `avg_cadence` /
  `avg_pace`.
- The `fields=` query param is documented as "Comma separated list of field names
  to include in the returned objects (default is all), **also excludes null
  values**". An unknown name yields no key at all, so the projection reads `None`
  and the agent coaches on a missing value. `tests/test_intervals_field_contract.py`
  guards every `fields=` name against the published model.
- The published data model is `@intervals-icu/js-data-model` (generated from the
  Intervals.icu source). It is more complete than the OpenAPI spec: `icu_intervals`,
  `icu_groups` and `laps` exist there but **not** in the REST response — they are
  JS-script-only. Regenerate the contract snapshot with
  `scripts/gen-intervals-field-snapshot.py`.

## URL and method quirks (live-verified 2026-09-18)

- `GET /api/v1/activity/{id}/intervals` returns the athlete's own detected
  intervals (`icu_intervals`, `icu_groups`). This is the interval source; the
  activity detail endpoint does **not** return them.
- `{ext}` is a **required path segment** on the curve endpoints:
  `/activity/{id}/power-curve.json`, not `/activity/{id}/power-curve`.
- The streams endpoint uses the `/activity/` prefix, not `/athlete/`:
  `/api/v1/activity/{id}/streams`.
- Curve endpoints: `/athlete/{id}/power-curves` (Ride family),
  `/athlete/{id}/pace-curves` (Run family), `/athlete/{id}/hr-curves` (other
  sports). The response is `{"list": [{"secs": [...], "watts": [...]}]}` for
  power/HR and `{"list": [{"distance": [...], "values": [...]}]}` for pace,
  where pace `values` are **seconds to cover that distance**.
- `PUT /api/v1/athlete/{id}/events/{eventId}` **does** update an event
  (`EventEx` body). `PATCH` on that path is not mapped and returns 405.
- `Activity.paired_event_id` links a completed activity to the planned event it
  completed. Pairing itself is done automatically or in the UI — it is not settable
  on an existing activity through the API.

## Debugging a null field

Request the field you want **and** the name you think it might be, with no other
filter, and compare:

```python
# inside the pod, using the plugin's own _load_credentials + _request
data = _request(athlete_id, api_key, f"/athlete/{athlete_id}/activities",
                {"fields": "id,average_heartrate,avg_heartrate"})
print(sorted(data[0].keys()))
```

A field that is absent from the response is either misspelled or genuinely null —
the two are indistinguishable from a projection alone, so also fetch the record with
no `fields` param and list its keys.
