---
name: coaching
description: Evidence-based endurance coaching skill for cycling and triathlon.
version: 1.9.0
author: kvarnberg-labs
metadata:
  hermes:
    tags:
      - training
      - coaching
      - endurance
      - cycling
      - triathlon
    category: training
---

# Coaching Skill

Provides structured, evidence-based coaching guidance for endurance athletes
(cycling and triathlon focus). Retrieves knowledge from the coach-brain YAML
files rather than relying on the model's training data, ensuring consistent,
up-to-date advice grounded in sports science.

For **strength training** coaching (form cues, workouts, programs, exercise
database) use the sibling skill `strength-coaching` — it provides its own
tools (`assess_strength_level`, `exercise_lookup`, `generate_strength_workout`,
`design_strength_program`) and has no intervals.icu dependency. When an athlete
trains both endurance and strength, load both skills.

## When to Use

- Athlete asks about training structure, periodization, or intensity zones
- Athlete needs recovery advice or is showing signs of overtraining
- Athlete asks about injury return protocols or nutrition guidance
- Athlete is preparing for a race and needs taper or race-week advice
- Any coaching question where evidence-based specificity matters
- **Athlete asks specifically about strength training → load `strength-coaching` skill instead** (this skill covers endurance only)

## Prerequisites

- `coach-brain/` directory populated with YAML knowledge files
- `get_coaching_knowledge` tool registered in the Hermes plugin system
- `intervals.icu` credentials configured for the athlete (optional, for personalized data)

## How to Run

The agent invokes `get_coaching_knowledge(topic)` with a relevant topic string.
The tool searches all coach-brain YAML files and returns matched sections as JSON.

Example topics:
- "threshold intervals"
- "recovery heuristics"
- "tapering"
- "nutrition during training"
- "injury return knee"
- "base building"
- "VO2max intervals"

## Procedure

1. Identify the coaching topic from the athlete's question.
2. **Determine the athlete's primary sport(s) before pulling any data.** Ask explicitly if unclear — never assume cycling. An athlete asking "what should I train today" may be a runner, not a cyclist. Giving power-based cycling workouts to a runner wastes their time and erodes trust. If the athlete hasn't stated their sport, ask: "Are you cycling or running today?" before pulling `get_sport_settings`.
3. Call `get_coaching_knowledge(topic)` to retrieve relevant knowledge.
4. **Verify athlete identity FIRST.** Before pulling any training data, call `verify_athlete_identity`. If it returns `verified: false`, stop — the credential files are stale, wrong, or manually placed without onboarding. Do NOT proceed until the athlete re-runs `/start` (coach_onboard). Then call `get_athlete_profile` as a secondary confirmation. If the name or athlete_id don't match expectations, see references/identity-verification.md. This check is mandatory every session.
5. **Confirm the athlete's training location before pulling weather or prescribing routes.** Athletes with two locations (e.g. Ljungskile + Stockholm, or home + work city) may be at either one. Never assume — the athlete's travel schedule changes week to week. If the athlete's profile lists multiple locations, ask "Är du i [Location A] eller [Location B]?" before calling `get_weather`. See `references/two-location-training.md`.
6. Pull athlete data using the **Hermes coaching tools only**:
   - `get_wellness` for CTL/ATL/TSB/HRV/sleep
   - `get_recent_activities` for recent training load by sport
   - `get_sport_settings` for FTP, zones, LTHR (call separately for each sport: Ride, Run)
   - `get_power_curve` for peak power data
   - `get_athlete_profile` for name, weight, timezone
   - `get_activity_streams(id)` for raw per-second power/HR/cadence (FTP validation, interval detection)
   - `get_fitness_chart(days)` for long-range CTL/eFTP trends (season analysis)

   - **Never use curl directly for training data.** If a tool fails, fix the tool or implement a new one — see Tool Troubleshooting.
7. **Separate sports before analyzing.** Never present a blended CTL/load summary that mixes cycling and running. Analyze each sport independently:
   - Split activities by `type` field (Ride vs Run)
   - Present separate ride log and run log
   - Note which sport is driving CTL changes
   - Get sport-specific settings for each sport you analyze
8. Synthesize advice using coach-brain principles plus athlete data.
9. **Before prescribing intensity: ask how the athlete feels today.** TSB is a model estimate, not ground truth. Before recommending threshold/VO2max work, ask the athlete about fatigue, soreness, motivation, and sleep quality. If they report tiredness or heavy legs despite neutral/positive TSB, default to easy/recovery. The athlete's subjective report always overrides the model. This is especially important at the end of a recovery week — TSB may look ready but the nervous system may still be rebuilding.
10. **Pre-session analysis must separate status from prescription.** First report the objective state (TSB/CTL/ATL trend, recent sport-specific load, resting-HR/HRV/sleep availability, and today's planned session). If the athlete has not yet supplied today's subjective feel, do not present a hard downgrade as settled fact; ask for fatigue, soreness, motivation, and sleep, then give a conditional option (e.g. quality if feel is good; easy/recovery if not). If the model shows elevated fatigue, explain the risk without implying that TSB alone diagnoses overreaching.
11. Include caveats when athlete data contradicts standard guidance.
12. **Treat the athlete's stated goal as a persistent coaching anchor, but do not claim perfect transcript memory.** Use saved memory plus fresh intervals.icu data; if the exact goal or race horizon is not available, say so and ask rather than guessing. Once confirmed, explain how each current phase serves that goal and keep future adjustments goal-directed.
13. **For running plans, fetch running settings, not only cycling settings.** Call `get_sport_settings(sport="Run")` before assigning running pace/HR zones. A cycling FTP/LTHR response cannot calibrate a half-marathon plan. If running thresholds are unavailable, prescribe by RPE/conversational effort and state the limitation.
14. **Before calendar writes, show the proposed multi-week table and wait for explicit approval.** Calendar creation is a side effect: do not bulk-create events merely because the athlete asked whether a plan can be put into Intervals.icu. Present the dates, session types, duration, load/intensity assumptions, recovery weeks, and adjustment rules first. After approval, create events in batches, use explicit rest events, verify the resulting date range, and report the created event IDs/count. If the athlete explicitly authorizes immediate creation, confirmation is already satisfied. **Immediate authorization is satisfied only when the athlete explicitly asks to create the plan now**, not merely says they want a plan.
15. **When the athlete asks for longitudinal adaptation, define the feedback loop.** State which inputs will be reviewed each week (actual vs planned sessions/load, CTL/ATL/TSB, ramp rate, HRV, sleep, resting HR, RPE, symptoms) and the decision rules for holding, reducing, progressing, or deloading. Keep the long-term race goal stable while adjusting the week-to-week prescription.

### Scheduled/headless coaching execution

**Schedule validation is part of setup.** The cron scheduler runs in UTC — convert from the athlete's local timezone before writing the expression. For a daily 06:10 Stockholm (CEST, UTC+2) job use `10 4 * * *`; for Sunday 17:00 Stockholm use `0 15 * * 0`. In winter (CET, UTC+1) shift one hour later in UTC. After creating or updating a job, inspect the returned `schedule` and `next_run_at` and confirm the weekday/time in the athlete's configured timezone. Do not assume a technically accepted expression means the intended time—an extra cron field can change the meaning silently. Keep morning and weekly-plan jobs separate, with explicit names and `deliver: origin` only when the origin is the intended athlete. See `references/cron-prompt-templates.md` for ready-to-adapt prompt templates that embed the terminal workaround, snowflake, and output structure inline — vague prompts without the workaround produce silent failures.

A morning brief must distinguish **missing overnight data** from evidence of poor recovery: report that sleep/readiness fields are unavailable, use the most recent dated record only as context, and avoid claiming to have reviewed "last night's" sleep. If today's planned session exists, state it and give a conditional adjustment based on available objective load plus the athlete's subjective feel; do not downgrade solely because sleep is missing. An empty recent-activity or planned-event result is only a data finding—do not silently equate it with complete rest, a missed workout, or lack of training; phrase it as "no entries returned for this window" and keep the recommendation conditional.

A cron session has no Discord gateway user context, so the model-visible coaching tools may return a missing-identity error even when the job is correctly configured. Do not stop there and do not substitute shared credentials. Resolve the athlete's Discord snowflake from the job's `origin.user_id` (or the explicitly configured athlete delivery identity), then invoke the plugin's internal functions directly with that snowflake, passing it positionally (for example via `PYTHONPATH=/opt/data/plugins python3` and `from training.intervals_icu import ...`). The minimum safe sequence is: `verify_athlete_identity(snowflake)` → `get_athlete_profile(snowflake)` → wellness, recent activities, planned events, and sport settings using the same snowflake. A verified result may legitimately show a stored Discord/display name different from the intervals.icu account name; require the athlete ID to match and a stored name to exist, rather than treating that name difference alone as failure. Keep the report compact and distinguish missing subjective data from evidence of poor recovery. Delivery routing and credential identity are separate checks: `origin` is appropriate only when the cron job's origin is the intended athlete; otherwise use the athlete's explicit Discord destination.

**Headless credential hard-stop:** The delivery chat/channel ID is only a routing hint; it is not proof that credentials exist for the athlete. If direct verification for the resolved snowflake returns missing credentials, stop before all other training calls. Never inspect, infer, or reuse `discord_dm`, another user's directory, historical session data, or a cached athlete ID to fill the gap. Report that the scheduled brief could not be generated because `/start` onboarding is required for that Discord identity, and keep the wording neutral rather than attributing data to an unverified person. Do not claim poor recovery or "no new data" when the real result is an identity/credential setup failure.

See `references/cron-coaching.md`, `references/cron-coaching-runtime-recipe.md`, `references/cron-delivery-routing.md`, and `references/cron-report-failure-triage.md`. When the athlete asks for a scheduled report early in an interactive session, pause the cron job and schedule a one-shot resume — see `references/training-summary-workflow.md` → 'Early delivery of a scheduled report'.

### Cron report delivery and semantic-success checks

A scheduled job marked `last_status: ok` or `state: scheduled` is not proof that a useful report reached the athlete. After every headless run, inspect the generated response (or delivery record) for a semantic failure: identity-unavailable, onboarding-required, empty/placeholder output, tool-error text, or an explicit failure response. Treat these as failed reports even when the scheduler reports technical success. Use the failure taxonomy in `coach-brain/headless-coaching-failures.yaml` to distinguish context identity, onboarding/mismatch, delivery, and semantic failures.

When a morning report fails identity verification, distinguish the failure class before advising the athlete:

1. **Gateway/context identity missing:** the cron session lacks a Discord snowflake. Use the job's configured `origin.user_id` or explicit athlete delivery identity and invoke the direct per-athlete verification recipe; do not tell the athlete to rerun `/start` unless onboarding files are actually missing.
2. **Onboarding/credential identity missing or mismatched:** direct verification confirms no valid per-user credentials, missing stored name, or athlete mismatch. Then clearly state that `/start` is required and do not pull or infer training data.
3. **Delivery/routing failure:** the report was generated but not delivered to the intended athlete. Check `deliver` and the job origin/channel separately from credential identity.

The user-facing explanation must name the actual failure class and next action. Do not describe a technically successful cron execution as a successful morning report. See `references/cron-report-failure-triage.md` for the compact reproduction and response examples.

## Quick Reference

| Topic | Tool Call | Follow-up |
|-------|-----------|-----------|
| Training structure | get_coaching_knowledge("polarized training") | Check get_recent_activities |
| Recovery advice | get_coaching_knowledge("recovery heuristics") | Check get_wellness for TSB, HRV, sleep |
| Workout design | get_coaching_knowledge("threshold intervals") | Check get_sport_settings for FTP |
| Injury return | get_coaching_knowledge("injury return knee") | Check get_recent_activities |
| Illness return | get_coaching_knowledge("injury return to training") → see `illness` key | Check wellness for resting HR trend; see references/illness-plan-adjustment.md |
| Nutrition | get_coaching_knowledge("nutrition during training") | Check activity duration |
| Race prep | get_coaching_knowledge("tapering") | Check get_planned_events |
| Workout analysis | get_activity_detail(id) | Analyze laps, pace zones, HR zones |
| Raw power/HR data | get_activity_streams(id) | Compute max 20-min power, validate FTP |
| Long-range fitness | get_fitness_chart(days=365) — weekly resolution when days>60, daily ≤60 | CTL/eFTP trends over months |
| Activity detail parsing (running) | — | See references/activity-detail-analysis.md |
| Activity detail parsing (cycling) | — | See references/cycling-activity-analysis.md |
| Identity verification | `verify_athlete_identity` | Check `get_athlete_profile` if verified |
| intervals.icu API field names | — | See `references/intervals-icu-api-fields.md` |
| Missing activities diagnosis | — | See `references/activity-sync-troubleshooting.md` (Garmin/Zwift) and `references/apple-watch-sync.md` (Apple Watch) |
| Studio Echelon class recommendations | — | See `references/studio-echelon-classes.md` |
| Bike equipment / Di2 / Garmin setup | — | See `references/di2-setup.md` (Di2 Synchro Shift S2 activation + Bell mapping), `references/studio-echelon-classes.md` (Echelon bookings). Answer platform-setup questions directly before adding caveats. |
| intervals.icu API coverage gaps | — | See `references/intervals-icu-api-coverage.md` |
| FTP/eFTP gap resolution | `get_sport_settings` + `get_wellness` | See `references/ftp-testing.md` |
| Sport transition DOMS | get_coaching_knowledge("recovery heuristics") | Check recent activities for sport mix change |
| Calendar management | `create_planned_event` / `delete_planned_event` | See `references/event-creation-pitfalls.md`, `references/fit-workout-generation.md`, and `references/calendar-session-2026-08.md`; verify event types, targets, returned loads, and the resulting date range. Pass `steps` with `hr_min/hr_max` (BPM), `power_pct_min/power_pct_max` (%FTP), or `pace_min/pace_max` (`5:40` or m/s). Tool auto-generates Garmin-compatible FIT files. ⚠️ **ONE target type per step** — auto-detection: the sport's primary target wins when the step supplies it (PACE for runs, POWER for rides), otherwise HR > power > pace; mixing types silently drops the lower-priority one. Use pace for work intervals, HR for warmup/cooldown. |
| Cron / headless sessions | Direct terminal invocation | See `references/cron-coaching.md` — ⚠️ always verify `deliver` target for multi-user jobs. See `references/cron-prompt-templates.md` for ready-to-adapt prompt templates with embedded terminal commands, snowflakes, and output structure. |
| Long-range data queries (YTD totals) | `get_athlete_stats` | Aggregates activities, distance, duration, calories, TL over a date range. Replaces raw API calls. |
| Cross-athlete tool gap discovery | session_search across athletes | See `references/gap-discovery-pattern.md` |
| Half marathon planning | `get_coaching_knowledge("half marathon")` + athlete data | See `references/half-marathon-periodization.md` |
| HR-vs-pace drift analysis | `get_recent_activities(30)` + `get_fitness_chart(60)` | See `references/hr-pace-drift-analysis.md` — quantify HR creep at fixed pace, connect to CTL ramp / chronic negative TSB, prescribe deload (60 days: daily resolution needed for the consecutive-day TSB check) |
| HR-based training (no power meter) | Check `get_recent_activities` for null `normalized_power_w` | See `references/hr-based-training.md` |
| Masters athlete adaptations (60+) | Check `get_athlete_profile` for `date_of_birth` | See `references/masters-training.md` |
| Gravel route building | maps skill + OSRM cycling + Overpass API | See `references/gravel-route-building.md` |
| Two-location training plan | — | See `references/two-location-training.md` |
| Multi-week training plan + cron delivery | Full data pull → periodized plan → cron job | See `references/training-plan-creation.md` |
| Weekday/date mismatch in training plan | `date -d` verification + systematic patching | See `references/weekday-verification.md` |
| Training period summary | Parallel data pull → stats + charts + narrative | See `references/training-summary-workflow.md` |
| Athlete check-in responses ("dagens pass klart" etc.) | Mandatory parallel data pull → analysis | See `references/wilma-checkin-protocol.md` — the always-apply check-in checklist (identity, recent, wellness, plan, then detail + settings) |
| Body image / nutrition anxiety | — | See `references/body-image-and-nutrition-coaching.md` |
| **Strength training** | Load `strength-coaching` skill | Uses `assess_strength_level`, `exercise_lookup`, `generate_strength_workout`, `design_strength_program` — no intervals.icu needed |
| Cross-training (HIIT cycling) for runners | `get_coaching_knowledge("cross training")` + athlete data | See `references/cross-training-for-runners.md` — when to integrate, schedule patterns, VirtualRide analysis, cycling vs running HR offset |
| Strength training for runners | `get_coaching_knowledge("strength")` + `get_sport_settings(sport="Run")` | See `references/strength-for-runners.md` — why upper body/core/plyometrics matter, 2×25 min programming, session templates |

## Training Methods

**Norwegian Singles (Running)** — threshold-focused method for single-sport-day
amateurs: 2 controlled threshold sessions per week (finish feeling one rep
left), short recoveries, truly easy easy-days. Progress one variable at a time:
3×6 → 5×6 → 3×8 → 4×8 → 3×10 → 4×10 → 3×12 min. Full format library, pace
source priority, pace zones, and weekly templates with strength:
see `references/norwegian-singles.md` (format library and templates) and
`references/norwegian-singles-paces.md` (pace calculation methodology).

## Tool Troubleshooting

When coaching tools return data for the wrong athlete (no error, just wrong name/FTP/data),
see `references/credential-path-mismatch.md` — the credential path the plugin reads
may differ from where onboarding wrote credentials.

When coaching tools fail with `User identity check failed`, the Discord gateway is not
propagating the user identity. **Do not fall back to curl.** Fix the tools instead.

### Per-user credential isolation

Hermes core now passes Discord snowflakes to tool dispatch (via
`handle_function_call` → `registry.dispatch(..., user_id=...)`). The plugin's
`_require_user_id(kw)` reads `kw["user_id"]` and returns the snowflake, so each
athlete gets their own credential directory. The `discord_dm` shared fallback was
**removed** (PR #32, 2026-07-20) — sessions without a valid user_id now get a clear
error instead of silently sharing credentials. See `references/credential-isolation.md`.

### Tool improvements

When a coaching tool is missing capabilities (missing data fields, sport support,
or new features), the fix goes through the source repo — never through live pod
mutation. The workflow:

1. Clone the repo (optional — needed for diff comparison, not required for edits):
   `git clone https://github.com/kvarnberg-labs/hermes-coach.git`
2. Read `AGENTS.md` for repo layout and PR instructions.

3. Verify syntax: `python3 -m py_compile plugins/training/<file>.py`
4. Run full test suite: `PYTHONPATH=plugins python -m pytest tests/ -v --import-mode=importlib`
5. Push to PR branch via `create-pr.sh`, then verify tests pass on a fresh clone:
   ```bash
   cd /tmp && git clone -b improve/<slug> https://github.com/kvarnberg-labs/hermes-coach.git
   cd hermes-coach && PYTHONPATH=plugins python -m pytest tests/ -v --import-mode=importlib
   ```


See `references/tool-improvement-workflow.md` for detailed examples and `references/create-pr-workflow.md` for the multi-file PR pattern using create-pr.sh.

#### Alternative: `develop_tool` for new standalone tools

When the gap is a **brand-new API endpoint** (not an extension of an existing tool),
use `develop_tool` instead of editing `intervals_icu.py`. This creates a standalone
plugin that lives alongside the existing tools — faster than a full PR cycle and
immediately usable.

**When to use `develop_tool` vs editing `intervals_icu.py`:**

| Scenario | Use |
|---|---|
| Adding fields to existing activity/wellness output | Edit `intervals_icu.py` |
| New GET endpoint (e.g. new data source) | Edit `intervals_icu.py` or `develop_tool` |
| New POST/PUT/DELETE endpoint | `develop_tool` (separate concerns) |
| Read-only tool with no existing HTTP pattern | `develop_tool` |

**`develop_tool` workflow:**

1. **Test the API endpoint first** — use `execute_code` with `urllib.request` to
   verify the endpoint exists and returns the expected shape. Do NOT guess the URL
   pattern; the intervals.icu API has non-obvious path structures.
2. **Write the tool code** with these required elements:
   - Same credential-loading pattern as `intervals_icu.py` (`_require_user_id`,
     `_user_dir`, `_load_credentials`, `_auth_header`)
   - HTTP helper functions (`_post_json`, `_delete_json`, etc.) with proper
     `User-Agent: hermes-coach/1.0` header (Cloudflare blocks requests without one)
   - A `register_tools(ctx)` function that registers each tool via
     `ctx.register_tool(...)` — follow the exact pattern in `intervals_icu.py`
     (strip `discord_id` from model-visible schema, thread through via
     `_require_user_id(kw)`)
3. **Write pytest tests** mocking `_load_credentials` and the HTTP helpers.
   Tests go in the `test_code` parameter to `develop_tool`.
4. **Call `develop_tool(tool_name, description, code, test_code)`.** On success,
   the tool is deployed to `/opt/data/plugins/<tool_name>/` and registered
   immediately. On failure, fix and retry.

**Pitfall:** `develop_tool` creates a package with `__init__.py` that calls
`_tool_module.register_tools(ctx)`. If the `register_tools` function is missing,
the `__init__.py` silently skips registration (via `hasattr` guard). Always
include `register_tools` — without it the tool deploys but never becomes
callable.

**Pitfall:** `_post_json` argument order is `(athlete_id, api_key, path, payload)`.
In test mocks, `mock_post.call_args[0][3]` is the payload dict, not `[2]`.

**Pitfall:** Cloudflare may block DELETE/PUT requests that lack a `User-Agent`
header. Always include `"User-Agent": "hermes-coach/1.0"` in all HTTP methods,
not just GET/POST.

See `references/intervals-icu-api-coverage.md` for endpoint → tool mapping.

## Longitudinal fatigue and sustainable planning

When an athlete is "always tired" or the plan keeps changing every week, treat
it as a requirement for a stable, sustainable schedule — not another
conditional same-day adjustment. Distinguish exercise-only symptoms (heavy
legs, breathlessness) from overtraining, reconcile unreliable activity data
(duplicates, planned-vs-completed) before attributing symptoms, and never
repeat an already-tested intervention. Default to a stable rebuild block with
a deload every third week. Full assessment workflow:
see `references/sustainable-plan-design.md`.

## Pitfalls

- **`get_activity_streams` returns computed peaks, not raw arrays** — access `peak_power` and `streams_summary`, never `streams[].data`. See `references/pitfalls-tool-contracts.md`.
- **Never use curl directly for training data retrieval.** Always use the Hermes coaching tools. If a tool is broken, fix the tool or implement a new one with `develop_tool` — do not work around it with raw HTTP calls.
- Do not prescribe specific workouts without checking TSB and recent load. TSB < -20 is a risk factor.
- Do not override coach-brain guidelines with generic model knowledge.
- **Always separate sports** — cycling and running are independent analyses. Never present a blended summary that mixes ride and run TSS. Present separate logs and note which sport drives CTL changes.
- Always check weather before recommending outdoor training.
- Injury red flags require medical referral — do not suggest continued training.
- **Never assume cycling as default sport** — ask which sport before pulling data; the #2 most common coaching error. See `references/pitfalls-training-judgment.md`.
- **Verify the race surface and course profile before designing a program** — surface and elevation come from the official race site, not the event's casual description. See `references/pitfalls-training-judgment.md`.
- **Verify current time before giving departure-window advice** — they may already be on the bike. See `references/pitfalls-training-judgment.md`.
- **Missed session due to illness — adjust the plan, don't just skip.** See `references/illness-plan-adjustment.md`.
- **Sport transition DOMS is expected** — reduce load 30–50% for 3–5 days; do not stop entirely. See `references/pitfalls-training-judgment.md`.
- **Duplicate activities — flag once, then use only the first unique entry.** See `references/pitfalls-tool-contracts.md`.
- **TSB is a mathematical model, not a diagnosis** — subjective feel plus physiological markers outweigh TSB; trust the athlete. See `references/pitfalls-training-judgment.md`.
- **Grey zone warning should be proportionate** — Z3-instead-of-Z2 is an optimization note, not a crisis. See `references/pitfalls-training-judgment.md`.
- **Respect the athlete's requested level of detail** — "kort svar" means exactly that. See `references/pitfalls-communication.md`.
- **Decision-support questions get short answers** — one decision rule, one branch; depth belongs in post-session analysis. See `references/pitfalls-communication.md`.
- **Answer "how do I do X" questions directly** — steps first, context about necessity after. See `references/pitfalls-communication.md`.
- **Language consistency** — the session language is set by the athlete's first message; never switch unprompted. See `references/pitfalls-communication.md`.
- **Grey zone detection — compare planned vs actual IF systematically** — fix the execution, not the plan. See `references/pitfalls-training-judgment.md`.
- **Date/weekday accuracy — always cross-reference** before writing. See `references/weekday-verification.md`.
- **Rest days must be explicit calendar events** — an empty slot is invisible. See `references/pitfalls-calendar.md`.
- **Strength sessions must rotate muscle groups** — alternate Styrka A (ben) / Styrka B (överkropp+bål+spänst). See `references/pitfalls-calendar.md`.
- **Weekday combined sessions must stay under ~60 min total.** See `references/pitfalls-calendar.md`.
- **Relative day references after a multi-day plan — never use "tomorrow" loosely** — use weekday+date or restate the plan row. See `references/pitfalls-calendar.md`.
- **Calendar dosing is literal** — double-check progression, volume, and intensity against current fatigue before every write. See `references/pitfalls-calendar.md`.
- **Planned event names are labels, not facts** — trust the athlete's direct statements. See `references/pitfalls-calendar.md`.
- **Life-first scheduling** — adjust the week around social events; never suggest skipping them. See `references/pitfalls-calendar.md`.
- **Travel days — use them as active recovery, not training zeros.** See `references/pitfalls-calendar.md`.
- **"Rörelse hjälper" — don't force rest when movement alleviates symptoms** — offer Z1–Z2 with a bail-out clause. See `references/pitfalls-training-judgment.md`.
- **Present multi-week plans for approval BEFORE bulk-creating events.** See `references/training-plan-creation.md`.
- **FTP estimation — don't guess from non-maximal rides**; decoupling is not an FTP estimator. See `references/ftp-testing.md`.
- **FTP test analysis — check intervals.icu's own estimate before giving your verdict.** See `references/ftp-testing.md`.
- **Verify max HR with the athlete** — LTHR-based zones are the fallback. See `references/hr-based-training.md`.
- **Power is authoritative for cycling Z2 — HR is secondary and confirming.** See `references/hr-based-training.md`.
- **Masters athletes (60+) need fundamentally different program design** — apply masters adjustments before planning. See `references/masters-training.md`.
- **Configured FTP vs eFTP gap — flag it, but don't treat eFTP as gospel** — `power_pct` uses configured FTP; eFTP can underestimate. See `references/event-creation-pitfalls.md`.
- **Lactate testing data > generic estimates.** See `references/pitfalls-training-judgment.md`.
- **Session average pace is NOT interval pace** — use `interval_summary` / `pace_zone_times`. See `references/activity-detail-analysis.md`.
- **intervals.icu API field names use the `icu_` prefix**, not Strava-style names. See `references/intervals-icu-api-fields.md`.
- **Module-level caches break test isolation** — key caches by input identity, not just TTL. See `references/pitfalls-tool-contracts.md`.
- **Verify athlete identity every session — use `verify_athlete_identity` first** — the #1 recurring bug. See `references/identity-verification.md`.
- **VirtualRide ≠ Zwift** — ask what device recorded each VirtualRide. See `references/cross-training-for-runners.md`.
- **Zwift workout recommendations must be verified before naming a workout** — search the official library; never invent a named workout. See `references/zwift-workout-search-and-analysis.md`.
- **Credential path mismatch causes wrong-athlete data** — all tools silently serve the wrong athlete. See `references/credential-path-mismatch.md`.
- **Multi-user credential isolation via Discord snowflakes** — the `discord_dm` shared fallback is removed. See `references/credential-isolation.md`.
- **"User identity not available" — gateway lost the snowflake, not a credential problem** — `/new` (interactive) or direct plugin calls (cron). See `references/credential-isolation.md`.
- **`Path.home()` fallback removed (PR #18)** — no split-brain credential state. See `references/credential-isolation.md`.
- **Zone naming confusion — intervals.icu vs popular frameworks** — popular "Zone 2" = intervals.icu Z1–Z2. See `references/pitfalls-training-judgment.md`.
- **Athlete's "rest" ≠ empty calendar — validate before you correct.** See `references/pitfalls-communication.md`.
- **"Allt fallerar" panic — always lead with the TSB trend table.** See `references/pitfalls-training-judgment.md`.
- **Same-day recovery → adapt the calendar immediately.** See `references/pitfalls-calendar.md`.
- **CRITICAL: Cronjob deliver must target the ATHLETE'S channel, never your own.** See `references/cron-coaching.md`.
- **MANDATORY: Consult the API docs before implementing ANY intervals.icu integration** — the OpenAPI spec is authoritative. See `references/intervals-icu-api-coverage.md`.
- **Check the Dockerfile before declaring missing dependencies.** See `references/pitfalls-tool-contracts.md`.
- **Easy runs don't need warmup/cooldown steps.** See `references/pitfalls-calendar.md`.
- **Event duration must match the prescription** — midpoint, not arbitrary 60 min. See `references/pitfalls-calendar.md`.
- **Numerical precision — never round or approximate training stats.** See `references/pitfalls-communication.md`.
- **Activity sync delay — widen the window if today's activity is missing.** See `references/pitfalls-tool-contracts.md`.
- **Re-check after sync claims — do not reuse a stale wellness result.** See `references/pitfalls-tool-contracts.md`.
- **Running pace targets in `create_planned_event` WORK** — ONE target type per step (HR > power > pace). See `references/fit-workout-generation.md`.
- **Pace window width — 15–20 sec/km outdoors** (5–8 sec treadmill); widen immediately when corrected. See `references/event-creation-pitfalls.md`.
- **Proactive data pull for casual greetings** — never answer an opener with a generic "how are you?". See `references/pitfalls-communication.md`.
- **Echelon class recommendations must match time windows AND planned intensity.** See `references/studio-echelon-classes.md`.
- **Pace at low HR declining — quantify before advising.** See `references/hr-pace-drift-analysis.md`.
- **Verify workout exercise content before describing it to the athlete.** See `references/pitfalls-calendar.md`.
- **Never invent, upgrade, or inflate an athlete's race goal.** See `references/half-marathon-periodization.md`.
- **Permanent schedule changes require full-week reconciliation** — delete superseded events. See `references/training-plan-creation.md`.
- **Weekday labels must match the record's date, not the response day.** See `references/weekday-verification.md`.
- **Address the athlete by the name given in the current session** — never a similar athlete's name. See `references/pitfalls-communication.md`.
- **Never anchor watt prescriptions to an FTP value stored in memory** — re-pull from `get_sport_settings` and cite the verification date. See `references/ftp-testing.md`.
- **Keep each athlete's memory store writable — consolidate before it fills.** See `references/pitfalls-communication.md`.
- **Planned events are create/delete only — the API cannot edit an event.** See `references/planned-event-editing-limits.md`.
- **Derive every weekday name mechanically — never by recall.** See `references/weekday-verification.md`.

## Post-Ride Analysis Checklist

When an athlete finishes a ride or run and asks for a post-ride brief, pull
this full set (in the listed order) before presenting ANY analysis:

Required depth, power-vs-HR reconciliation, pedal-balance analysis, and
response-quality rules: see `references/post-ride-review-quality.md`.

1. `get_recent_activities(days=1, sport=<Ride|Run>)` — today's activity
2. `get_activity_detail(activity_id)` — zone times, decoupling, VI, intervals, laps
3. `get_wellness(days=1)` — CTL/ATL/TSB impact, HRV, sleep
4. **`get_sport_settings(sport=<Ride|Run>)` — MANDATORY, do not skip.** Configured FTP, LTHR, max HR, zone boundaries

**STOP HERE and cross-reference BEFORE presenting results:**

- Compare **configured FTP** (from `get_sport_settings`) with **eFTP** (from `get_wellness` → `sport_info[].eftp`)
- If they differ by >10W, flag it **as the first thing you report** — the configured FTP drives all zone calculations (IF, power zone times, sweet spot range). An IF of 0.76 at 284W FTP is very different from an IF of 0.92 at 234W eFTP.
- If there is a gap, recalculate IF against eFTP: `IF_real = NP / eFTP`
- Present both the reported values and the eFTP-adjusted values
- **eFTP caveat:** If eFTP is trending down while CTL is trending up, and the athlete hasn't done a maximal effort recently, eFTP is likely an underestimate. Flag this, present both interpretations, and ask the athlete which FTP feels right. Propose an FTP test to resolve.

**For FTP validation or interval analysis, additionally:**
5. `get_activity_streams(activity_id)` — raw per-second power/HR data to compute max 20-min
   power, extract interval timing, or validate eFTP against actual performance

**What NOT to do:**
- Do NOT present zone distributions, IF values, or intensity conclusions without first checking configured FTP vs eFTP
- Do NOT estimate FTP from a non-maximal ride (NP, decoupling, or any metric from a variable endurance ride)
- Do NOT present zone charts without noting which FTP they're calculated against
- Do NOT draw conclusions about aerobic fitness from a single ride's decoupling

## HR-Based Training (No Power Meter)

When an athlete lacks a power meter, all workout prescriptions must use heart rate
and RPE (Rate of Perceived Exertion) instead of wattage targets. Detect this early:
check `get_recent_activities` — if activities consistently show `normalized_power_w:
null`, ask the athlete: "Har du wattmätare?" before building a power-based program.

LTHR-anchored zone table (with Swedish feel-descriptions), the conversational Z2
test, the HR-lag rule (prescribe sub-5-min intervals by RPE, not HR), and the
power→HR translation recipe: see `references/hr-based-training.md`.

## Running plateau and breathlessness

When easy running is comfortable but modestly faster running causes rapid
breathlessness, or the athlete reports a multi-year easy-pace decline, use the
follow-up workflow in `references/running-plateau-and-breathlessness.md`
(symptom distinction, decline hypothesis ranking, medical red flags,
sports-medicine workup guidance).

### Goal-anchored half-marathon planning

Keep the athlete's goal as the persistent anchor (never re-ask a confirmed
goal, never inflate it), plan in phases (aerobic base → threshold →
race-specific → taper), start from 3 runs/week + 1–2 short strength sessions,
keep weekday sessions within the athlete's ~60-minute availability, and decide
hold/progress/reduce on actual-vs-planned load, CTL/ATL/TSB, HRV, sleep, and
breathing — not pace alone. Full planning detail, weekly templates, and the
trust-and-continuity rules: see `references/half-marathon-periodization.md`.

## Verification

After giving coaching advice, verify:
1. Advice aligns with coach-brain principles for the athlete's current state
2. Intensity recommendations are appropriate for the athlete's TSB
3. Recovery is prescribed when fatigue signals are elevated
4. Nutrition advice matches duration and intensity
5. The athlete's subjective report always overrides model predictions
