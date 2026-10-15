# Calendar writes — tool rules and pitfalls

Load before any `create_planned_event`, `create_planned_events_bulk`,
`update_planned_event` or `delete_planned_event` call.

## Before writing

- Approval first: show the plan table and wait for explicit approval. A direct
  instruction to create now ("Gör veckans pass", "lägg in det") is the
  approval — do not ask twice.
- Fresh data first: identity, recent activities, wellness, sport settings and
  profile, so the week reflects current load, fatigue, FTP, age and life
  commitments.
- Rest days get no event (there is no `REST` category); name them in the plan
  table. Valid categories are enforced by the tool.
- Only future dates.

## Which tool

| Need | Tool |
|---|---|
| One session, or any session with structured `steps` | `create_planned_event` (generates the Garmin FIT file) |
| Many unstructured sessions from an approved plan | `create_planned_events_bulk` (no FIT/steps) |
| Change name/date/duration/description/load of an existing event | `update_planned_event` — fetches the event and writes it back whole, so fields you omit are kept |
| Change a structured workout's steps | delete it and create it again with `create_planned_event` |
| Remove a superseded event | `delete_planned_event` |

There is no bulk edit: change events one at a time. Pairing a completed
activity to a planned event is not possible through the tools — the athlete
can drag-and-drop it in the intervals.icu UI; read `paired_event_id` to check
adherence. If a calendar capability is genuinely missing, say so; never fall
back to raw API calls.

## Structured steps

Step fields: `name`, `duration_sec`, `type` (`WARMUP`/`ACTIVE`/`REST`/`COOLDOWN`),
one target pair, optional `description` (shown on the device).

| Target | Fields | Notes |
|---|---|---|
| Power | `power_pct_min/max` (%FTP) | Preferred for rides |
| HR | `hr_min/hr_max` (BPM) | Tool converts with the sport's `max_hr`; refuses if none is set |
| Pace | `pace_min/pace_max` ("5:40" or m/s) | Pace targets work on Garmin — never tell an athlete otherwise |

- **One target type per step** (FIT limitation). If a step carries several,
  the sport's primary target wins (pace for runs, power for rides), otherwise
  HR > power > pace, and the rest is dropped silently. Runs: pace on work reps,
  HR on warm-up/cool-down/recovery. Need both on a rep? Pace as target, HR range
  in the step `description`.
- Easy runs and Z2 rides are a single step (see `references/pitfalls-calendar.md`).
- Event duration matches the prescription (35–50 min → 45 min), not a default.

## power_pct is against configured FTP, not eFTP

The trainer and Garmin compute watts from the **configured** FTP
(`get_sport_settings`). If configured FTP and eFTP (`get_wellness →
sport_info[].eftp`) differ by > 10 W:

1. Decide the intended real watts (from the FTP the athlete agrees is right).
2. Set `power_pct` = intended watts / configured FTP.
3. Reverse-check: configured FTP × pct / 100 = displayed watts, and confirm
   they sit in the intended zone. Example: configured 286 W, eFTP 274 W,
   sweet spot 240–257 W → `power_pct` 84–90 %, not 88–94 %.
4. The athlete's device is the arbiter: if they say the watts look wrong, check
   which FTP you used.

## Pace windows

Outdoor running: 15–20 s/km wide (e.g. threshold 4:40–4:55/km). Treadmill:
5–8 s/km. When an athlete says a window is too narrow, widen it at once and
save the preference to memory.

## After writing

- Re-read the range with `get_planned_events` and report what actually exists
  (count, key sessions, date range). This catches partial writes.
- Compare the returned names, descriptions, targets and planned load/intensity
  with your prescription; a malformed target can be accepted yet produce wrong
  zones or loads. Fix any mismatch before you report success.
- More events than days in the window usually means stale duplicates from an
  older plan — reconcile them (see `references/training-plan-creation.md`).

## Related data question: calorie sums

For "how many calories did I burn cycling between X and Y", use
`get_athlete_stats` and sum only the requested categories ("cycling" = `Ride`
+ `VirtualRide`, not `WeightTraining`). Report the date range and the exact sum.
