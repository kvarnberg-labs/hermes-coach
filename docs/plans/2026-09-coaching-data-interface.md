# Coaching Agent Data-Interface Plan — 2026-09

# Coaching Agent Data-Interface Plan — 2026-09

**Status: implemented 2026-09-18.** All items below landed in one change set
(P0–P6 + the `get_athlete_stats` fix + the field-name contract test), with the
live-verification results recorded in §"Live verification results". Open decisions
D0.1, D1.1, D2.1, D3.1, D4.1 and D7 were resolved along the recommendations
below; D6.1 was settled by live data (option 2).

Source: architecture review of the coaching agent's data interface
(`plugins/training/`, `skills/coaching/`, `coach-brain/`), grounded in the official
intervals.icu OpenAPI 3.0.1 spec (`https://intervals.icu/api/v1/docs`, 118 paths /
109 schemas) and the official data model `@intervals-icu/js-data-model@1.2.0`
("Generated from Intervals.icu source, © 2025 Intervals.icu Ltd"). Review rendered to
`<tmpdir>/architecture-review-20260918-095901.html`.

**Every change below is proposed, not applied.** Per AGENTS.md the Lead reviews and
approves each diff before merge. The self-improvement loop may not touch plugin source
or tests (CONTRACT.md boundary) — these changes go through the normal dev workflow.

Test command for every item (per AGENTS.md):

```sh
PYTHONPATH=plugins python -m pytest tests/ -q --import-mode=importlib
```

## Coverage — every review candidate maps to an item

| Review candidate | Plan item |
|---|---|
| 1 · Deepen activity analysis onto API intervals | P2 |
| 2 · Wellness returns a subset of the documented record | P1 |
| 3 · Field names drift from the published model | P0 |
| 4 · Running is second-class (no pace/HR curve) | P3 |
| 5 · Sport settings drop the zone anchors | P1 |
| 6 · Athlete constraints and calendar history invisible | P4 |
| 7 · Plan/workout library reimplemented as event writes | P6 |
| 8 · Delete the hand-maintained API references | P5 |
| review sub-finding · `get_athlete_stats` requests all fields | Small independent fix |

## New findings from the official-documentation pass

These came out of reading the OpenAPI spec, the JS data model and the maintainer's
API thread after the review. None was in the original report; three change the plan.

| # | Finding | Effect on the plan |
|---|---|---|
| N1 | The two official sources disagree: `icu_intervals`, `icu_groups` and `laps` are in the JS data model but absent from the OpenAPI spec. Every other field the plan touches is in both. | **Changes D0.1** — the field-name source must be the JS data model, or the union, not the OpenAPI spec alone. P2 depends on it. |
| N2 | Per-app / per-athlete rate limits were added 2026-06-24 (maintainer, API thread posts 715–716): `429` + `Retry-After`, plus `X-RateLimit-*` headers, and 10 calls/s per IP. | The widened tool surface raises calls per session. `_http.py` already retries once on `429` and the cache TTLs bound the volume. No action unless the plan adds fan-out; if it does, read `X-RateLimit-Remaining` before fanning out. |
| N3 | `compliance` is now on the `Activity` schema. The maintainer said in 2022 (post 164) it was client-side only. | P2's `compliance` field is available; the reference should not repeat the stale claim. |
| N4 | The documented edit surface the reference misses: `PUT /events/{eventId}`; `PUT /events` (range, `hide_from_athlete` / `athlete_cannot_edit` only); `upsertOnUid` on `POST /events`; `POST /events/bulk` with `upsert` / `upsertOnUid` / `updatePlanApplied`; `POST /events/{eventId}/mark-done`. | **P6 reference correction**, and a third sub-option for D6.1 (an edit tool without delete-and-recreate). |
| N5 | `power-hr-curve` gained a `type` and `filters` param (maintainer, 2026-06-05, posts 710–711). | **P3** may have a fourth adapter (power-vs-HR), and `get_power_curve`'s endpoint now supports `type`. |
| N6 | `SPORT_SETTINGS_UPDATED` webhook type exists (maintainer, post 701). | The 6 h sport-settings cache TTL could be event-driven instead of polled. Out of scope: the repo has no webhook receiver. Record only. |
| N7 | The read side of planned-vs-actual pairing is documented: `Activity.paired_event_id` (maintainer, post 164). The write side is not in the API — the event endpoint has no pairing field, and pairing is client-side / automatic. | **P4** adds `paired_event_id`. No pairing write tool. |

## Live verification results (2026-09-18, read-only, 4 athletes)

Run against the live cluster (`kubectl exec` into `deployment/hermes`, GET only,
per-user credentials read in-process and never printed). Athletes: Joey (i3***,
cyclist), Aldrin (i6***), Wilma (i6***, runner), Campberg (i4***).

| Check | Result | Effect on the plan |
|---|---|---|
| **P0** — request both names, 30 activities | `average_heartrate` 30/30, `average_cadence` 30/30, `pace` 30/30; `avg_heartrate` **0**, `avg_cadence` **0**, `avg_pace` **0** | **Confirmed live bug.** The alias is not accepted; `avg_hr`/`avg_cadence` are always null. The rename is the fix, not a doc tidy-up. |
| **P2** — `icu_intervals` via `fields=` on the detail endpoint | `icu_intervals`, `icu_groups`, `laps` all **absent from the 183-key response**, even with no `fields` filter | **P2's proposed change is wrong.** These are JS-script-only fields. |
| **P2** — `GET /activity/{id}/intervals` | **18,191 chars**: `icu_intervals` 6–11, `icu_groups` 0–4. Interval keys include `average_watts`, `average_heartrate`, `average_cadence`, `intensity` (% FTP), `zone`, `moving_time`, `training_load`, `type` (WORK/RECOVERY), `wbal_start/end`, `joules_above_ftp` | **This is the endpoint P2 needs.** Campberg's VO2max 5×5 → 11 intervals + 1 group. |
| **P2** — other per-activity endpoints | `/interval-stats?start_index&end_index` works (1,836 chars); `/hr-curve.json` works (2,923); `/power-curves.json?types=watts` works but returned empty for the ride tested; `/power-curve.json` **404 — `{ext}` is a required path segment**; `/best-efforts` 422 even with `stream=watts&duration=300` (unresolved, low value) | `_compute_power_peaks` can be replaced by `/power-curves.json`; the `{ext}` quirk must be handled. |
| **P1** — extended wellness, 42 days | Payload **7.3–11.1 KB** vs current **5.3–9.1 KB** — ~2 KB more | **D1.2 resolved: option (a), no range split.** |
| **P1** — which fields populate | `ctlLoad`/`atlLoad` **43/43** (new, and they are the raw daily load behind CTL/ATL); `steps` 5–43; `vo2max` 11–37; `spO2` 40 (Wilma); `hrvSDNN` 41 (Wilma); `rampRate`/`sleepScore`/`sleepQuality` 41–43 | The highest-value additions are `ctlLoad`/`atlLoad`, `steps`, `vo2max`, `spO2`, `hrvSDNN` — not the health fields. |
| **P1** — health fields | `injury`, `menstrualPhase`, `stress`, `hydration`, `respiration`, `comments`, `systolic`/`diastolic`, `bloodGlucose`, `lactate`, `bodyFat`, `avgSleepingHR`, `baevskySI` — **null for all 4 athletes** | Available and null-excluded, so near-zero context cost. **D1.1 is moot today** — add them, no ADR urgency. |
| **P3** — sport-neutral curve | Wilma (runner): `/power-curves` **27 chars (empty)**, `/pace-curves?type=Run` **4,351 chars**. Campberg: power **26,179**, pace **27**. `/hr-curves` works (3,409–11,418) | **Confirmed.** `get_power_curve(sport="Run")` returns nothing for the runner whose data is on the pace endpoint. |
| **P4** — `Activity.paired_event_id` | Populates on 7/20, 2/3, 6/44, 13/20 activities in 30 days; **every paired activity matched an event in the window** (7/7, 2/2, 6/6, 13/13) | **Confirmed and high-value.** Planned-vs-actual adherence is directly computable. |
| **P4** — `Athlete.training_availability` | `null` ×3, `[]` ×1 — **unset for all 4 athletes** | Available and null-excluded, so cheap to add — but it will not help today. Keep the P4 addition, drop the expectation. |
| **P6 / D6.1** — plan builder | `training_plan: null` for all 4; one `Workouts` **folder with 0 workouts** | **D6.1 resolved: option 2.** The native plan builder is unused. |
| **stats fix** — 90-day activity list | All fields **100–356 KB**; current tool fields **8–27 KB**; minimal **2–7 KB** | **Confirmed, ~50×.** `get_athlete_stats` downloads 100–356 KB per 90-day query to add 5 numbers. |
| **P4** — past events | `/events` for the previous 14 days returns 2–14 events (7.7–29.6 KB) | `days_back` works and returns real data. |

**Still unverified:** `/best-efforts` (422 — the required-param combination is not documented clearly); whether
`/activity/{id}/power-curves.json` populates for a ride with power; whether `PUT /activity/{id}`
honours `paired_event_id`. All three are low-value.

## Guardrails that apply to every item

- **API is read-only in coaching paths.** The only writes remain `create_planned_event`
  and `delete_planned_event`. No new destructive call is introduced.
- **Identity comes from the gateway.** Any new tool must strip `discord_id` from the
  model-visible schema and read it from `kw["user_id"]` via `_require_user_id` (the
  existing `_tool` helper pattern).
- **Credentials never appear in output.** New tools reuse `_load_credentials` / `_request`
  only.
- **Cache keys must be distinct per projection.** Two tools hitting the same endpoint with
  different projections must not share a cache entry (the `get_athlete_stats` comment
  already documents this rule).
- **Skill and reference updates ship in the same PR as the tool change.** The skill
  references the tool contracts; a shape change without the doc change is a regression.
- **No live-pod mutation.** `git push → Flux → pod restart`, or PR.

## Dependency order

```
P0  field-name contract ──┬──> P1 wellness + sport settings ──> P3 athlete constraints + events
                          ├──> P2 activity intervals
                          └──> P4 best-effort curve
P5  delete hand-maintained references  (independent)
P6  plan/workout library decision      (independent, needs Lead)
```

P0 first: it is the only item that is a live correctness bug, and every later item
adds fields through the same `fields=` seam it fixes.

---

## P0 — Field-name contract against the published data model

**Find:** `get_recent_activities` and `get_activity_detail` request `avg_heartrate`,
`avg_cadence`, and `avg_pace`. The published `Activity` model defines
`average_heartrate`, `average_cadence`, and `pace`; `avg_heartrate` / `avg_cadence` /
`avg_pace` are not defined. The `fields` param is documented as "Comma separated list of
field names to include in the returned objects (default is all), also excludes null values",
so an undefined name yields no field and the projection reads `None`. The repo's own
`skills/coaching/references/intervals-icu-api-fields.md` asserts `avg_heartrate` is correct
and `tests/test_activity_detail_fields.py` mocks the same wrong names — so CI stays green
while the live model returns no average HR or cadence.

**Files**
- `plugins/training/intervals_icu.py` — `get_recent_activities` (fields string line ~281,
  projection ~323–328), `get_activity_detail` (fields string ~365–372, projection ~412–421)
- `skills/coaching/references/intervals-icu-api-fields.md` (HR/cadence table)
- `tests/test_activity_detail_fields.py` (mock keys)
- `tests/test_intervals_icu.py` — `TestGetRecentActivitiesParser`

**Change**
- `get_recent_activities`: request `average_heartrate,average_cadence`; drop `avg_pace`
  (`pace` is already requested). Read `act.get("average_heartrate")` and
  `act.get("average_cadence")`.
- `get_activity_detail`: same rename; drop `avg_pace`.
- Correct the field table in `intervals-icu-api-fields.md` to match the published model.
- Update the two test mocks to the official field names.
- Add a contract test (see decision D0.1 below) that extracts every name from the
  `fields=` strings in `intervals_icu.py` and asserts each is defined by the published
  model.

**Confirmed live (2026-09-18) — do the rename.** Over 30 activities the official
names all populated (`average_heartrate` 30/30, `average_cadence` 30/30, `pace` 30/30)
while the requested aliases all returned nothing (`avg_heartrate` 0, `avg_cadence` 0,
`avg_pace` 0). This is a live correctness bug, not a doc discrepancy. The fix is the
rename; the contract test (D0.1) is what stops it recurring.

**Tests**
- `test_recent_activities_maps_average_heartrate` — mock `average_heartrate`, assert
  `avg_hr` populated.
- `test_recent_activities_maps_average_cadence`.
- `test_activity_detail_maps_average_heartrate`.
- `test_fields_names_are_in_published_model` — contract test (D0.1).
- Update the two existing mock fixtures.

**Risks / side effects**
- If intervals.icu happens to accept `avg_heartrate` as an alias, the current code is not
  broken — but it still depends on an undocumented name. The rename is correct either way.
- The contract test is the guard that stops this class of drift recurring. If it fetches the
  live spec it is non-hermetic; if it reads a snapshot, the snapshot can drift. **Lead
  decision D0.1.**

**Estimate:** ~10 lines + ~80 test lines + doc table.

---

## P1 — Wellness and sport settings return the documented records

**Find:** `get_wellness` projects 16 of the 46 documented `Wellness` fields. The dropped
ones (`menstrualPhase`, `menstrualPhasePredicted`, `injury`, `stress`, `hydration`,
`hydrationVolume`, `spO2`, `respiration`, `vo2max`, `comments`, `avgSleepingHR`,
`systolic` / `diastolic`, `bloodGlucose`, `lactate`, `bodyFat`, `steps`, `kcalConsumed`,
`carbohydrates` / `protein` / `fatTotal`, `ctlLoad` / `atlLoad`, `baevskySI`,
`tempWeight` / `tempRestingHR`) are exactly the ones `coach-brain/female-physiology.yaml`,
`injury-return.yaml`, `persistent-performance-decline.yaml` and `recovery-heuristics.yaml`
coach against. `get_sport_settings` returns zone arrays without their anchors:
`threshold_pace` (the running analog of FTP), `sweet_spot_min` / `sweet_spot_max`, `p_max`,
`load_order` / `tiz_order` (which stream drives load and zones), and the zone names.

**Files**
- `plugins/training/intervals_icu.py` — `get_wellness`, `get_fitness_chart`,
  `get_sport_settings`
- `skills/coaching/references/ftp-testing.md`, `hr-based-training.md`,
  `half-marathon-periodization.md`
- `tests/test_intervals_icu.py` — `TestGetWellnessParser`, sport-settings tests
- `tests/test_streams_and_fitness.py` — `get_fitness_chart`

**Change — wellness**
- Add a `fields=` param to the wellness request listing exactly the documented fields
  the coach-brain corpus uses (the endpoint supports `fields`, which also omits nulls — so
  the payload stays bounded even at `days=42`). Candidate list:
  `ctl,atl,rampRate,ctlLoad,atlLoad,hrv,hrvSDNN,restingHR,avgSleepingHR,sleepSecs,
  sleepScore,sleepQuality,readiness,weight,bodyFat,vo2max,respiration,spO2,
  menstrualPhase,menstrualPhasePredicted,injury,soreness,fatigue,stress,mood,motivation,
  hydration,hydrationVolume,kcalConsumed,carbohydrates,protein,fatTotal,comments,
  systolic,diastolic,bloodGlucose,lactate,baevskySI,steps,sportInfo`.
- Map to snake_case keys matching the corpus vocabulary
  (`menstrual_phase`, `injury`, `stress`, `hydration`, …).
- Keep the `today` convenience field and the CTL/ATL/TSB arithmetic unchanged.
- `get_fitness_chart` stays compact (weekly downsample) but carries `ctlLoad` /
  `atlLoad` / `vo2max` alongside CTL/ATL/TSB/eFTP.

**Change — sport settings**
- Add to the result: `threshold_pace`, `sweet_spot_min`, `sweet_spot_max`, `p_max`,
  `power_zone_names`, `hr_zone_names`, `pace_zone_names`, `load_order`, `tiz_order`,
  `gap_model`, `best_effort_distances`, `pace_curve_start`, `default_workout_time`,
  `hr_load_type`, `pace_load_type`, `use_gap_zone_times`, `types`.
- Keep `ftp_w_kg` as is.

**Tests**
- Extend `TestGetWellnessParser` with one assertion per newly surfaced field.
- Add `test_wellness_fields_param_excludes_dropped_fields` — assert the request
  `params["fields"]` contains the corpus-critical names.
- Add `test_sport_settings_returns_threshold_pace_and_zone_names`.
- Add a test that every `menstrual_phase` value maps from the official enum.

**Risks / side effects**
- **Context size.** 46 fields × 42 records is large. Mitigation: the `fields=` param
  omits nulls, and the corpus-critical set is smaller than all 46. Measure the payload
  at `days=42` before merge; if it exceeds budget, keep the extended fields only for
  `days<=7` and document that in the tool description.
- Adding `injury` / `menstrual_phase` to model context is athlete health data. It was
  already the corpus's subject matter, but confirm with the Lead that surfacing it in the
  model context is intended (same class of decision as ADR 0002). **Decision D1.1.**

**Estimate:** ~60 lines + ~70 test lines + reference updates.

---

## P2 — Activity analysis onto the intervals the API already computes

**Find:** `get_activity_detail` requests `laps` and `interval_summary` but not
`icu_intervals` / `icu_groups` — the published model's per-interval averages (power, HR,
cadence, zone, W′ balance, decoupling, joules). `get_activity_streams` instead pulls the
full per-second arrays (838 KB observed) and reimplements peak extraction with a
sliding-window over `watts`. The API's own interval detection is the feature the official
guide leads with ("Automatically detects intervals … comprehensive stats for each interval").

**Files**
- `plugins/training/intervals_icu.py` — `get_activity_detail`, `get_activity_streams`,
  `_compute_power_peaks`
- `skills/coaching/references/activity-detail-analysis.md`,
  `cycling-activity-analysis.md`, `post-ride-review-quality.md`, `ftp-testing.md`
- `tests/test_activity_detail_fields.py`, `tests/test_streams_and_fitness.py`

**Change — corrected by live verification.** The original proposal (add `icu_intervals`
to the detail endpoint's `fields=`) does not work: those names are **JS-script-only**
and are absent from the 183-key REST response even with no `fields` filter.

- Add a **new tool** over `GET /api/v1/activity/{id}/intervals`, which returns
  `icu_intervals` and `icu_groups` directly (live: 6–11 intervals, 0–4 groups).
- Project each interval to `type`, `zone`, `average_watts`, `average_heartrate`,
  `average_cadence`, `intensity`, `moving_time`, `training_load`, `wbal_start`,
  `wbal_end`, `joules_above_ftp`, `label`, `start_index`, `end_index`.
- `get_activity_detail`: add the fields that *are* on the REST response —
  `icu_rolling_ftp`, `compliance`, `polarization_index`, `strain_score`,
  `icu_training_load_data`, `icu_ignore_hr`, `paired_event_id`, `gap`,
  `icu_hrr`, `icu_pm_ftp`, `icu_pm_w_prime`, `icu_pm_cp`, `icu_max_wbal_depletion`,
  `gap_zone_times`, `icu_achievements`, `coach_tick`, `icu_power_hr_z2`.
- Do **not** request `icu_intervals`, `icu_groups` or `laps` in `fields=` — they are
  silently dropped. `laps` is a JS-script field, not a REST field.
- `get_activity_streams`: keep it as the *nuance* adapter — sub-second pacing and
  interval-boundary confirmation — and replace `_compute_power_peaks` with
  `GET /activity/{id}/power-curves.json?types=watts` (note: `{ext}` is a required
  path segment, so `.json` is mandatory).

**Tests**
- `test_activity_intervals_returns_icu_intervals` — mock the intervals endpoint.
- `test_activity_intervals_projects_work_recovery`.
- `test_activity_detail_returns_compliance_and_paired_event_id`.
- Keep the existing streams tests as the adapter's contract.

**Risks / side effects**
- `icu_intervals` is a second endpoint call per activity. It returns ~18 KB, so
  project it, do not return the raw object.
- If the athlete has manually edited intervals, `icu_intervals` reflects the athlete's
  own boundaries — that is the point, and the skill must say so.
- **Decision D2.1 resolved:** `_compute_power_peaks` is replaced by
  `/activity/{id}/power-curves.json`. Keep the streams tool for the nuance it alone
  answers; delete the sliding-window algorithm.

---

## P3 — Best-effort curve is sport-neutral

**Find:** the only curve adapter is the power curve. The published model has
`/athlete/{id}/pace-curves` and `/athlete/{id}/hr-curves`; the skill coaches
half-marathons and Norwegian singles but the runner's best-pace curve is unreachable, and
`get_activity_streams` computes peaks from `watts` only. The published
`SportSettings.best_effort_distances` and `pace_curve_start` are unread.

**Files**
- `plugins/training/intervals_icu.py` — `get_power_curve`
- `skills/coaching/SKILL.md` (quick-reference row),
  `references/half-marathon-periodization.md`, `norwegian-singles-paces.md`
- `tests/test_intervals_icu.py` or a new `tests/test_best_effort_curve.py`

**Change**
- Add `get_best_effort_curve(discord_id, sport="Ride", days=42)` that dispatches:
  `Ride` → `/power-curves`, `Run` → `/pace-curves`, everything else →
  `/hr-curves`. One interface, three adapters.
- Keep `get_power_curve` as a thin alias (delegates with `sport="Ride"`) so the skill
  and cron references keep working — or update all callers and delete it (D3.1).
- Surface `best_effort_distances` / `pace_curve_start` from sport settings so the
  runner's curve durations are the athlete's own.

**Tests**
- `test_best_effort_curve_run_uses_pace_endpoint`.
- `test_best_effort_curve_ride_uses_power_endpoint`.
- `test_best_effort_curve_other_uses_hr_endpoint`.
- `test_power_curve_alias_delegates_to_ride`.

**Risks / side effects**
- The pace-curve response shape differs from the power-curve shape (`curves` /
  `filters` params, `distance`-based). The adapter must map both to one shape; document
  the mapping in the tool description.
- **Decision D3.1:** keep `get_power_curve` as an alias or delete it and update every
  caller (SKILL.md, `cron-coaching.md`, `cron-prompt-templates.md`).

**Estimate:** ~70 lines + ~50 test lines + reference updates.

---

## P4 — Athlete constraints and planned-vs-actual history

**Find:** `Athlete.training_availability[]` (day of week, `max_training_time`,
`can_train_sports`) is documented and never read; the skill tells the agent to keep
weekday sessions inside the athlete's availability. `get_planned_events` only looks forward,
so planned-vs-actual adherence — procedure step 15's feedback loop — has no data path.
`Activity.paired_event_id` is unread, so an activity can't be tied to its planned event.

**Files**
- `plugins/training/intervals_icu.py` — `get_athlete_profile`, `get_planned_events`,
  `get_recent_activities`
- `skills/coaching/SKILL.md` (procedure step 15, quick-reference row),
  `references/training-plan-creation.md`, `weekday-verification.md`
- `tests/test_intervals_icu.py`

**Change**
- `get_athlete_profile`: add `training_availability` (and `height`).
- `get_planned_events`: add an optional `days_back: int = 0`; `oldest` becomes
  `today - days_back`, `newest` stays `today + days_ahead`. Backwards compatible —
  default reproduces today's behaviour.
- `get_recent_activities`: add `paired_event_id` to `fields=` and the projection.

**Tests**
- `test_athlete_profile_returns_training_availability`.
- `test_planned_events_days_back_extends_oldest`.
- `test_planned_events_default_days_back_unchanged`.
- `test_recent_activities_maps_paired_event_id`.

**Risks / side effects**
- **Live-verified:** `paired_event_id` populated on 7/20, 2/3, 6/44 and 13/20 activities
  in 30 days, and **every** paired activity matched an event in the same window
  (7/7, 2/2, 6/6, 13/13). Planned-vs-actual adherence is directly computable —
  this is the highest-value single addition in the plan.
- **Live-verified:** `training_availability` is `null` for three athletes and `[]`
  for the fourth. Add it (cheap, null-excluded) but do not expect it to carry a plan
  yet; the agent still has to ask.
- A past-events query can return many events. Live: the previous 14 days returned
  2–14 events (7.7–29.6 KB). Bound `days_back` at 90, matching `days_ahead`.
- **Decision D4.1:** is the interface `days_back` on the existing tool, or a separate
  `get_event_history(start, end)` tool? Adding the param is the smaller diff; the separate
  tool is the deeper one if the history projection diverges from the forward one.

**Estimate:** ~25 lines + ~50 test lines + reference updates.

---

## P5 — Delete the hand-maintained API references

**Find:** two markdown files describe the same interface as the runtime spec module
`intervals_docs.py` (which fetches the official OpenAPI spec and caches it 6 h). One is
stale (`intervals-icu-api-coverage.md` says the training-plan endpoint's existence is
unknown, and lists past events as a remaining gap), one is wrong
(`intervals-icu-api-fields.md` asserts field names the published model does not define).
The agent cannot tell which source is authoritative.

**Files**
- delete `skills/coaching/references/intervals-icu-api-coverage.md`
- delete `skills/coaching/references/intervals-icu-api-fields.md`
- add `skills/coaching/references/intervals-icu-api.md` (short: "the spec is
  authoritative; use `search_intervals_api_docs` / `get_intervals_api_endpoint`; never
  guess field names")
- `skills/coaching/SKILL.md` — quick-reference rows and pitfall bullets that link the
  deleted files
- `tests/test_skill_links.py` — validates reference links

**Change**
- Delete both files, add the one short reference, update every link.
- Update the "MANDATORY: Consult the API docs" pitfall to point at the spec tool only.

**Tests**
- `test_skill_links.py` must pass after the links are rewritten (it already checks that
  every referenced file exists).
- Add a case asserting the two deleted paths are no longer referenced.

**Risks / side effects**
- Any judgment content buried in the two files must be moved, not deleted. Read both fully
  and move the non-field-name guidance into the relevant topic reference before deleting.
- This is the cheapest item and can ship first if P0 slips.

**Estimate:** −2 files, +1 file, link updates.

---

## P6 — Plan / workout library decision (Lead decision + ADR)

**Find:** the published spec exposes `/athlete/{id}/training-plan`, `/folders`,
`/workouts`, `/workouts/{id}`, `/events/apply-plan`, `/events/{planId}`,
`/events/bulk`, `/events/bulk-delete`, `/events/{eventId}` (PUT) and
`/events/{eventId}/mark-done`. The module builds every event by hand, one call at a
time, and its own coverage reference says the training-plan endpoint's existence is
unknown.

**Resolved by official documentation — the reference is wrong.**
The official OpenAPI spec (`https://intervals.icu/api/v1/docs`, generated from the
server source) maps `PUT /api/v1/athlete/{id}/events/{eventId}` → "Update an event
(planned workout, note etc.)", request body `EventEx`. Only `GET`, `PUT` and `DELETE`
are mapped on that path — there is no `PATCH`. The site owner's own API reference
(forum.intervals.icu/t/609, post 4, 2020-04-13) states "`PUT
/api/v1/athlete/{id}/events/{eventId}` Update event and return it", and post 700
(2026-03-15) shows a user actively calling it.

So `planned-event-editing-limits.md` is wrong on two counts, and its own evidence
explains why:

1. "There is NO API endpoint for editing an existing planned event" is contradicted by
   the spec and by the maintainer's own reference.
2. The `405` is fully consistent with a **`PATCH`** — the path exists with no `PATCH`
   mapping, which is exactly what a framework returns for 405. The reference writes
   "`PATCH`/`PUT` … returns 405" and then generalizes the `PATCH` result to `PUT`;
   that generalization does not follow from its own observation.

The reference also misses the documented edit surface:
- `PUT /events/{eventId}` — update one event (`EventEx` body).
- `PUT /events` — update **all** events in a date range, but **only**
  `hide_from_athlete` and `athlete_cannot_edit`; not a general bulk edit.
- `POST /events` with `upsertOnUid` — update an event with a matching `uid`
  instead of creating a new one (already the create tool's endpoint).
- `POST /events/bulk` with `upsert` / `upsertOnUid` / `updatePlanApplied`.
- `POST /events/{eventId}/mark-done` — create a manual activity to match a
  planned workout.

**Change (reference correction, no new tool yet).** Rewrite
`planned-event-editing-limits.md`: the edit operation exists; `PATCH` is not
supported; `PUT` replaces the whole event, so fetch it first with
`GET /events/{eventId}` and send the complete `EventEx` back. Keep the caution about
athlete-added notes/structure — a replace can drop fields you do not resend — but drop
the absolute "the API cannot edit" claim and the "never invent an edit tool" rule.

**The pairing sub-question is also settled — from the activity side.**
Post 700 asks how to pair a completed activity to a planned workout via the event
endpoint. The docs and the maintainer answer it:

- **Read side (documented).** `Activity.paired_event_id` (int32) is on the activity
  list/detail response. Maintainer, post 164 (2022-06-17): *"There is a field on
  activity 'paired_event_id' that is the ID of the paired workout if any."* So the agent
  can tell whether a planned workout was completed by matching activity
  `paired_event_id` against the event `id`. P4 already adds this field.
- **Write side is not in the API.** The event endpoint has no pairing field (schema
  confirmed), so `updateEvent` cannot pair. Post 164: *"Unfortunately that is
  currently done client side so its not in the API. Would be nice if it was though."*
  Pairing is done automatically when the workout matches the activity closely enough
  (sport and load/time), and manually by drag-and-drop in the UI.
- **The only documented write path is at upload time.**
  `POST /api/v1/athlete/{id}/activities` takes a `paired_event_id` form parameter
  ("Workout to pair with activity"). That uploads a file; it cannot re-pair an
  existing activity.

**One narrow unknown remains:** whether `PUT /activity/{id}` honours a changed
`paired_event_id` in the body. The request body schema is `Activity`, which contains
the field, but no doc states the server applies it. Settling that needs one benign
write on a throwaway activity — **explicit Lead approval required**, and not needed
by the coaching agent: it only needs the read side, because pairing already happens
automatically or in the UI.

**Action: record it, do not implement a write tool.** Add `paired_event_id` to the
activity projection (P4) and one line to the reference: pairing is readable from the
activity; setting it on an existing activity is not in the API; do not invent an
event-side field.

**Files**
- `plugins/training/create_planned_event.py`
- `skills/coaching/references/planned-event-editing-limits.md`,
  `training-plan-creation.md`, `event-creation-pitfalls.md`
- `docs/adr/` (new ADR)

**Decision (Lead, D6.1)** — pick one, record as an ADR:
1. **Native plan builder.** Add `get_training_plan`, `list_workouts`, `apply_plan`
   tools; use `/events/bulk` for batch creation. Removes the one-event-per-call
   pattern and the plan/calendar drift. Larger change; couples to the plan-builder
   model.
2. **Hand-written events, keep as is.** Add bulk creation via `/events/bulk` and
   an edit tool over `PUT /events/{eventId}`. Smaller change; keeps the current
   model.

Do not implement either until the Lead picks. This item is speculative; the correct
move depends on whether the athletes use the intervals.icu plan builder at all.

**Estimate:** decision first; implementation ~100 lines (option 1) or ~40 lines
(option 2) + reference/ADR.

---

## Small independent fix — `get_athlete_stats` requests all 183 fields

**Confirmed live (2026-09-18), ~50×.** A 90-day `/activities` query with no
`fields` returned **100,755–356,373 chars**; the tool's current field list returns
**8,422–27,732**; the five-field minimum returns **2,184–7,040**. The fix is a real
cost cut on live systems, not a micro-optimisation.

**Files:** `plugins/training/get_athlete_stats.py`, `tests/test_get_athlete_stats.py`

**Change:** pass `fields=distance,moving_time,calories,icu_training_load,type` and
`limit` (a documented param). Cache key already differs from `get_recent_activities`
(different projection) — keep that.

**Tests:** `test_athlete_stats_requests_minimal_fields` — assert `params["fields"]` and
`params["limit"]` are set.

**Risks:** a future aggregate that needs a new field must add it to `fields=`; the
contract test from P0 does not cover this module, so the field list is local.

**Estimate:** ~5 lines + ~15 test lines.

---

## Test matrix

| Item | New tests | Existing tests touched |
|------|-----------|----------------------|
| P0 | field-name contract, 3 mapping tests | `test_activity_detail_fields.py`, `TestGetRecentActivitiesParser` |
| P1 | ~8 wellness field tests, sport-settings anchor test | `TestGetWellnessParser` |
| P2 | 3 `icu_intervals` tests | `test_activity_detail_fields.py` |
| P3 | 4 curve-dispatch tests | `test_streams_and_fitness.py` (unchanged) |
| P4 | 4 tests | `test_intervals_icu.py` |
| P5 | link test | `test_skill_links.py` |
| P6 | none until decision | none |
| stats | 1 test | `test_get_athlete_stats.py` |

## Decisions for the Lead

Each decision is stated as: the question, why it is genuinely open, the options with
their trade-offs, the evidence that settles it, and my recommendation. The decision is
yours; nothing below is applied.

### D0.1 — How does the field-name contract test get its field names?

**Question.** The test that stops P0 recurring needs a list of fields the published
model defines. Where does that list come from at test time?

**Why it is open.** `intervals_docs.py` already fetches the authoritative spec and
caches it 6 h, so the list is available for free — but the existing test suite is
described as hermetic (`tests/test_intervals_docs.py` docstring: "hermetic, no network").
Fetching in a test breaks that property and makes CI depend on intervals.icu being up.

**The two official sources disagree — this constrains the answer.** Comparing the
OpenAPI spec against the JS data model (`@intervals-icu/js-data-model@1.2.0`, also
generated from the Intervals.icu source) for the fields the plan touches:

| Field | OpenAPI spec | JS data model |
|---|---|---|
| `icu_intervals` | absent | present |
| `icu_groups` | absent | present |
| `laps` | absent | present |
| all other P1/P2/P4 fields | present | present |

So a contract test keyed to the OpenAPI spec alone would reject `icu_intervals`
(P2's core field) and `laps` (which the code already requests and which works).
The field-name source must be the **JS data model**, or the union of both — not the
OpenAPI spec alone.

**Options.**

| Option | Trade-off |
|---|---|
| (a) Fetch the live spec in the test; skip on network error only | Zero new files, uses the module that already exists. Misses `icu_intervals` / `icu_groups` / `laps`, so it cannot guard P2 and would falsely reject `laps`. |
| (b) Checked-in field-name snapshot from the **JS data model** + a regeneration script + a scheduled CI job that diffs the snapshot against the live npm package | Hermetic, deterministic, fast, and covers the fields P2 needs. Adds a Node/npm step or a vendored generated JSON; drifts silently between runs. |
| (c) Snapshot the **union** of both sources | No false rejections from either source. Still drifts, and the union hides a real disagreement rather than surfacing it. |

**What settles it.** Whether the repo accepts non-hermetic tests, and which source is
canonical for "does this field exist". The JS model is the more complete of the two.

**Recommendation: (b), snapshotting the JS data model, not the OpenAPI spec.** The JS
model is the source that documents `icu_intervals` / `icu_groups` / `laps` — the fields P2
and the existing `laps` request depend on. Start with `Activity`, `Wellness`,
`SportSettings` and `Athlete` property names only — a few hundred strings, not the 243 KB
spec. Record the OpenAPI-vs-JS-model disagreement in the snapshot's header so the next
reader does not re-litigate it.

### D1.1 — Should `injury` and `menstrualPhase` reach the model context?

**Question.** P1 surfaces the athlete's logged injury state and menstrual phase. Should
those fields be in the wellness projection for every athlete, or only on request?

**Why it is open.** These are special-category health data. Once surfaced they transit to
the model provider (opencode.ai) and are persisted in the gateway transcript — the same
path ADR 0002 already accepted for API keys, but for a more sensitive data class. The
counter-argument: the corpus already coaches on both
(`coach-brain/female-physiology.yaml`, `injury-return.yaml`), and coaching without the
data means guessing the phase, which is the current failure mode.

**Options.**

| Option | Trade-off |
|---|---|
| (a) Always include in the wellness projection | Best coaching: the corpus's phase-based and injury-return guidance becomes usable. Widens the set of health data transiting the model context. |
| (b) Include only on explicit athlete request (a `get_wellness_detail(date)` tool or an `include_health` param) | The athlete controls the flow. The agent must ask before it can coach on the phase, which is a worse experience and easy to forget. |
| (c) Never include; coach generically | No new data flow. The corpus files stay half-usable and the current guessing failure persists. |

**What settles it.** Two facts, both checkable read-only. First, whether the athletes
actually log these fields — the `fields=` param "also excludes null values", so a field
that is never logged costs nothing in context and the decision is nearly free. Second,
whether the athletes want the coach to use them.

**Recommendation: (a), with a new ADR that extends ADR 0002 to special-category
wellness fields, plus one line in the onboarding flow stating that the coach reads them.**
The `fields=` null-exclusion makes the context cost close to zero, and the corpus is
already written against these fields. Do this only after confirming the athletes log them.

### D1.2 — Extended wellness for all ranges, or only short ranges?

**Question.** Should the extended wellness projection apply at `days=42`, or only at
`days<=7`?

**Why it is open.** Context budget versus completeness. But the `fields=` param
documentation ("also excludes null values") changes the calculus: the payload grows only
by the fields the athlete actually logs, not by the 46-field maximum.

**Options.**

| Option | Trade-off |
|---|---|
| (a) Extended set at every range | One shape, no mode for the caller to learn. Largest payload when many fields are logged daily. |
| (b) Extended at `days<=7`, compact at longer ranges | Bounded context. Two shapes behind one interface — the caller must know which range returns which fields. |
| (c) Extended set plus a separate `get_wellness_detail(date)` | One record, full fidelity, no range dependence. One more tool. |

**What settles it.** Measure the real payload. Run `get_wellness(days=42)` for an
athlete who logs the most fields and count the characters. `get_fitness_chart` (the
long-range tool) is already downsampled and only needs CTL/ATL/TSB/eFTP, so the
long-range shape is not the one that grows.

**Recommendation: (a).** Live-verified: extended 42-day payloads are **7.3–11.1 KB**
vs **5.3–9.1 KB** today — about 2 KB more for 4 athletes. The `fields=` param omits
nulls, so the health fields cost nothing when unset. No range split.

### D2.1 — Does `_compute_power_peaks` survive?

**Question.** Once `icu_intervals` is the interval source, does the hand-rolled
sliding-window peak extraction in `get_activity_streams` stay as a fallback?

**Why it is open.** The published spec has a per-activity endpoint,
`GET /api/v1/activity/{id}/power-curve{ext}`, that returns the whole max-mean-power
curve. If that endpoint returns the same numbers as the sliding window, the hand-rolled
version is a second implementation of an official one and fails the deletion test.

**Options.**

| Option | Trade-off |
|---|---|
| (a) Keep `_compute_power_peaks` as a fallback | Covers any case where `icu_intervals` is empty. Two implementations of peak extraction that can disagree. |
| (b) Delete it; take per-activity peaks from `/activity/{id}/power-curve` | One implementation, official, and the per-activity capability is kept. One more endpoint to map, and the response shape differs from the athlete-level curve. |
| (c) Delete it entirely; rely on `icu_intervals` + athlete-level `/power-curves` | Least code. Loses per-activity peaks, which the FTP-validation workflow uses. |

**What settles it.** Compare the official per-activity curve against the sliding
window on one real ride: if they agree, (b) is a pure deletion.

**Recommendation: (b).** It deletes the hand-rolled algorithm and keeps the
capability, which is the deepening this plan is after. Verify the numbers agree first.

### D3.1 — Does `get_power_curve` survive as an alias?

**Question.** P3 replaces the power-only curve with a sport-neutral best-effort curve.
Does the old name stay?

**Why it is open.** Cron jobs persist their prompts outside this repo (in the gateway's
scheduler), and the self-improvement loop may not edit them (CONTRACT.md boundary).
A scheduled job whose stored prompt calls `get_power_curve` breaks if the tool is
deleted, with no repo-visible warning.

**Options.**

| Option | Trade-off |
|---|---|
| (a) Keep `get_power_curve` as a thin alias that delegates with `sport="Ride"` | No caller breaks, including stored cron prompts. Two names for one interface — the drift pattern this plan removes elsewhere. |
| (b) Delete it and update every repo caller | One name. Silently breaks any stored cron prompt that references it. |

**What settles it.** Whether any scheduled job's stored prompt calls it. Check the
scheduler's jobs (read-only) before deleting.

**Recommendation: (a), and mark it deprecated in the tool description** ("use
`get_best_effort_curve`; kept for existing scheduled jobs"). The alias is a few
lines; a silently broken morning brief is a much worse cost.

### D4.1 — `days_back` param or a separate history tool?

**Question.** P4 unlocks planned-vs-actual adherence. Does `get_planned_events` grow a
`days_back` param, or does a separate `get_event_history(start, end)` tool carry it?

**Why it is open.** Both cross the same endpoint. The right answer depends on whether
the history projection differs from the forward one.

**Options.**

| Option | Trade-off |
|---|---|
| (a) `days_back` on the existing tool | Smallest diff, backwards compatible (default 0 reproduces today's behaviour), no new name. One tool with a direction flag, and the forward and history projections must stay the same shape. |
| (b) Separate `get_event_history(start, end)` | Deeper if history needs the paired activity, compliance, or a different projection. A second name for the same endpoint. |

**What settles it.** Whether adherence needs the activity side. If the agent must
compare planned load against the completed activity, the projection differs and (b) is
justified; `Activity.paired_event_id` (also in P4) is the link.

**Recommendation: (a) now.** Add `paired_event_id` to the activity projection, and
split into (b) only if the history shape actually diverges. Do not add a second tool
for a param that already fits.

### D6.0 — RESOLVED: the `PUT` 405 reference is wrong (official documentation)

**Settled.** The official OpenAPI spec maps `PUT
/api/v1/athlete/{id}/events/{eventId}` → "Update an event (planned workout, note
etc.)" with an `EventEx` body, and maps no `PATCH` on that path. The site owner's own
API reference (forum.intervals.icu/t/609, post 4) states the same, and a user is
actively calling it in post 700. The reference's absolute claim ("no API endpoint for
editing"; "the API cannot edit an existing event") is false, and its `405` is explained
by the unsupported `PATCH`.

**Remaining work:** correct the reference (P6) and add the missing documented edit
surface (`PUT /events/{eventId}`; `PUT /events` range limited to `hide_from_athlete` /
`athlete_cannot_edit`; `upsertOnUid` on `POST /events`). A live read-only check is
no longer a prerequisite — it is optional confirmation.

**Also settled: pairing.** Read side is documented (`Activity.paired_event_id`; maintainer
post 164) and P4 adds it. Write side is not in the API — the event endpoint has no
pairing field, and the maintainer confirms pairing is client-side (post 164). The only
documented write path is the `paired_event_id` form parameter on
`POST /athlete/{id}/activities`, at upload time. The one narrow unknown — whether
`PUT /activity/{id}` honours a changed `paired_event_id` — needs a benign write and is
not needed by the coaching agent. Record it; do not build a write tool.

### D6.1 — Native plan builder or hand-written events?

**Question.** Does the coaching agent drive intervals.icu's own plan/workout library, or
keep building events one at a time?

**Why it is open.** It is a product decision about how the athletes work, not a code
decision. The published spec exposes the whole plan surface
(`/training-plan`, `/folders`, `/workouts`, `/events/apply-plan`, `/events/bulk`), but
using it only pays off if the athletes actually use the plan builder.

**Options.**

| Option | Trade-off |
|---|---|
| (1) Native plan builder | One apply-plan call replaces N event writes; plan and calendar cannot drift. Couples the agent to the plan-builder model and to `/events/apply-plan` semantics; larger change; wasted if the athletes' folders are empty. |
| (2) Hand-written events, add `/events/bulk` | Keeps the current model and control; one call replaces N creates. Plan and calendar can still drift; the agent remains responsible for the schedule. |

**What settles it.** Read-only: `GET /athlete/{id}/training-plan` and
`GET /athlete/{id}/folders`. If both are empty, the athletes do not use the builder
and option 1 adds a model nobody uses.

**Settled live (2026-09-18) — option (2).** All four athletes: `training_plan`
`null`, `training_plan_id` `None`, and a single `Workouts` folder with
**0 workouts**. Nobody uses the native plan builder, so option (1) adds a model
nobody uses. **Decision D6.1 resolved: option (2)** — hand-written events plus
`/events/bulk`, recorded as an ADR. Revisit only if the athletes start using the
builder.

### D7 — How far along the deep-module direction do we go?

**Question.** The review's thesis is "stop mirroring endpoints one-for-one; deepen the
modules". Which items are in scope?

**Why it is open.** It is the roadmap decision, and it sets how much interface churn and
test surface the repo takes on at once.

**Options.**

| Option | Trade-off |
|---|---|
| (a) Full direction — P0 through P6 | Best coaching and smallest tool surface at the end. Largest change, most test surface, and P6 still needs a product decision. |
| (b) Correctness only — P0 + the `get_athlete_stats` fix | Smallest diff, fixes the live bug, leaves the coaching gaps. |
| (c) Data core — P0, P1, P2, P5, plus the stats fix | Covers the data-utilisation core and the deletion, defers the sport-neutral curve and the plan-builder decision. |

**What settles it.** How the athletes' questions actually fail today. P0 is a live bug;
P1/P2 are gaps the corpus is written against; P3/P4 are capabilities nobody has
asked for yet; P6 is a product decision.

**Recommendation: (c) first, then re-read the signals.** P0, P1, P2 and P5 are all
load-bearing for questions the agent already gets, and they shrink the tool surface rather
than grow it. P3 and P4 wait for a signal naming them, and P6 waits for the folder
check. Re-run the review after (c) lands to see whether P3/P4/P6 are still worth doing.

## Out of scope

- Gear, routes, custom items, chats, connections, `fitness-model-events`,
  `/activity/{id}/best-efforts`, `/activity/{id}/weather-summary`, `/athlete/{id}/profile`.
  Each is documented, none is load-bearing for a coaching decision the agent currently
  makes. Revisit only if a signal names it.
- `apps/hermes/deployment.yaml`, secrets, NetworkPolicy — untouched.
- `coach-brain/*.yaml` — no knowledge change is required by any item above.
