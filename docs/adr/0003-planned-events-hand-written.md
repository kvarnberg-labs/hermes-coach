# ADR 0003 — Planned events stay hand-written; native plan builder is not used

Status: Accepted 2026-09-18.

## Context

`create_planned_event` writes one event per call to
`POST /athlete/{id}/events`. The published intervals.icu API also exposes a
native plan/workout library: `GET/PUT /athlete/{id}/training-plan`,
`/folders`, `/workouts`, `POST /events/apply-plan`, `POST /events/bulk`.
An architecture review proposed moving to the native plan builder, which would let one
`apply-plan` call replace N event writes and remove plan/calendar drift.

Two facts settled it during the review's live-verification pass (2026-09-18,
read-only, four athletes):

- **Nobody uses the builder.** Every athlete returned `training_plan: null` and
  `training_plan_id: None`, with a single `Workouts` folder containing **0
  workouts**. Adopting the native model would add a surface nobody uses.
- **The edit endpoint works.** The review's earlier reference claimed "there is NO API
  endpoint for editing an existing planned event"; the spec and the maintainer's own
  API reference both document `PUT /athlete/{id}/events/{eventId}`. The `405` the
  reference recorded is explained by `PATCH`, which is not mapped on that path. So
  the delete-and-recreate workaround is not required.

## Decision

**Keep hand-written events; add the batch and edit tools over the documented
endpoints.**

- `create_planned_events_bulk` → `POST /events/bulk`, so an approved multi-week
  plan is one call instead of N.
- `update_planned_event` → `GET /events/{eventId}` then
  `PUT /events/{eventId}` with the complete `EventEx`. `PUT` is a full replace, so
  the tool reads the event first and applies only the supplied fields — an omitted
  field is preserved, not dropped.
- Do **not** adopt `/training-plan` / `/workouts` / `/events/apply-plan`. Revisit
  only if the athletes start using the builder.

`PUT /events` (the range form) only changes `hide_from_athlete` and
`athlete_cannot_edit`; it is not a general bulk edit and is not used.

## Consequences

- The agent remains responsible for the schedule, so plan/calendar drift is still
  possible. The mitigation is the adherence review: match an event `id` against an
  activity's `paired_event_id` (populated on 6-13 of 20-44 activities per athlete
  in 30 days, and every paired activity matched an event) via
  `get_planned_events(days_back=…)`.
- Structured `steps` (FIT generation) are not supported on the bulk path. A
  multi-week plan created in bulk has no Garmin-pushable workouts; create those
  individually. `# ponytail: no FIT generation in the bulk path.`
- `create_planned_event` keeps its existing behaviour and is not deprecated: it is
  the only path that generates FIT files.

## Alternatives considered

- **Native plan builder** — one `apply-plan` call, no plan/calendar drift. Rejected:
  no athlete uses it, so it adds a model and a failure surface for no gain.
- **Delete-and-recreate instead of `PUT`** — avoids depending on `PUT`. Rejected:
  the endpoint is documented and live, and a replace that lands on the wrong date
  recreates the weekday-label class of errors.
- **`PUT /events` for bulk edits** — rejected: it only changes
  `hide_from_athlete` and `athlete_cannot_edit`.
