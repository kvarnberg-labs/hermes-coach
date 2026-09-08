# Planned-event editing limits — create/delete only, no API edit

## The constraint

The intervals.icu planned-events API supports exactly two write operations:

| Operation | Endpoint | Works |
|---|---|---|
| Create | `POST /athlete/{id}/events` | ✓ (via `create_planned_event`) |
| Delete | `DELETE /athlete/{id}/events/{id}` | ✓ (via `delete_planned_event`) |
| Edit | `PATCH`/`PUT /athlete/{id}/events/{event_id}` | ✗ — returns `405 Method Not Allowed` |

There is NO API endpoint for editing an existing planned event. Attempting
PATCH/PUT (directly or by inventing an "edit" tool call) fails with 405 and
wastes turns; worse, a failed attempt can tempt fabricated workarounds.

## Correct workflows when an event must change

1. **Delete + recreate (preferred for coach-created events):** delete the
   event by ID, then `create_planned_event` with the corrected fields.
   Always re-verify the resulting date range afterward — a recreate that
   lands on the wrong date recreates the weekday-label class of errors.
2. **Manual edit in the intervals.icu web UI (preferred when the event has
   athlete-added history, notes, or completed-workout attachment):** ask the
   athlete to edit the event themselves and confirm the change.

## Class-level rule: migrate reusable API facts out of athlete memory

This fact was discovered in a live session (2026-08) and stored only in one
athlete's private memory store — every other session (and main-side agents)
lacked it. General intervals.icu API behavior belongs in class-level
references like this file, not in per-athlete memory. When a session
discovers an API constraint, add it to the relevant reference (or
`intervals-icu-api-coverage.md`) in the same improvement pass.
