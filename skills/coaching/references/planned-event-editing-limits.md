# Planned-event editing — PUT works, PATCH does not

## The constraint

The intervals.icu planned-events API supports these write operations:

| Operation | Endpoint | Works |
|---|---|---|
| Create | `POST /athlete/{id}/events` | ✓ — also `upsertOnUid` to update a matching `uid` |
| Create batch | `POST /athlete/{id}/events/bulk` | ✓ — `upsert` / `upsertOnUid` / `updatePlanApplied` |
| Edit one | `PUT /athlete/{id}/events/{eventId}` | ✓ — `EventEx` body, returns the updated event |
| Edit a range | `PUT /athlete/{id}/events` | ✓ — **only** `hide_from_athlete` and `athlete_cannot_edit` |
| Delete one | `DELETE /athlete/{id}/events/{eventId}` | ✓ |
| Delete a range | `DELETE /athlete/{id}/events` | ✓ — optional `category`, `createdById` |
| Delete batch | `PUT /athlete/{id}/events/bulk-delete` | ✓ — by `id` or `external_id` |
| Mark done | `POST /athlete/{id}/events/{eventId}/mark-done` | ✓ — creates a manual activity to match |

`PATCH` on `/athlete/{id}/events/{eventId}` is **not mapped** and returns
`405 Method Not Allowed`. A `405` means the path exists but the method is not
allowed — so a `PATCH` result is not evidence that `PUT` is unavailable.

**Source:** OpenAPI spec at `https://intervals.icu/api/v1/docs` (generated from the
server source), and the maintainer's own API reference in the
"API access to Intervals.icu" forum thread, post 4.

## Editing an event

`PUT` is a **full replace**, not a patch: fetch the event first with
`GET /athlete/{id}/events/{eventId}`, change the fields you want, and send the
complete `EventEx` object back. A partial body can drop fields you did not resend —
in particular athlete-added notes and structure. Read the event, then write it back.

`PUT /events` (the range form) is **not** a general bulk edit — it only changes
`hide_from_athlete` and `athlete_cannot_edit`. To change load, duration or
structure across a range, edit the events one at a time.

## Pairing a completed activity to a planned workout

`Activity.paired_event_id` is the ID of the planned event an activity completed.
Read it to check adherence; it is set automatically when the workout matches the
activity closely enough (sport and load/time), or manually by drag-and-drop in the
UI. **Setting it is not exposed on the event endpoint** — the maintainer confirms
pairing is done client-side (forum thread, post 164). `POST
/athlete/{id}/activities` accepts a `paired_event_id` form parameter, but only when
uploading the activity file.

## Class-level rule: migrate reusable API facts out of athlete memory

API behaviour discovered in a session belongs in class-level references like this
file, not in one athlete's private memory store — otherwise every other session (and
main-side agent) lacks it. When a session discovers an API constraint, add it to the
relevant reference (or `intervals-icu-api.md`) in the same improvement pass.
