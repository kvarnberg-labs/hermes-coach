---
name: coaching
description: Evidence-based endurance coaching skill for cycling and triathlon.
version: 1.8.1
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

See `references/cron-coaching.md`, `references/cron-coaching-runtime-recipe.md`, `references/cron-delivery-routing.md`, and `references/cron-report-failure-triage.md`.

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
| Long-range fitness | get_fitness_chart(days=365) | CTL/eFTP trends over months |
| Calendar management | `create_planned_event` / `delete_planned_event` | See `references/event-creation-pitfalls.md`, `references/fit-workout-generation.md`, and `references/calendar-session-2026-08.md`; verify event types, targets, returned loads, and the resulting date range |
| Activity detail parsing (running) | — | See references/activity-detail-analysis.md |
| Activity detail parsing (cycling) | — | See references/cycling-activity-analysis.md |
| Identity verification | `verify_athlete_identity` | Check `get_athlete_profile` if verified |
| intervals.icu API field names | — | See `references/intervals-icu-api-fields.md` |
| Missing activities diagnosis | — | See `references/activity-sync-troubleshooting.md` (Garmin/Zwift) and `references/apple-watch-sync.md` (Apple Watch) |
| Studio Echelon class recommendations | — | See `references/studio-echelon-classes.md` |
| Bike equipment / Di2 / Garmin setup | — | See `references/di2-setup.md` (Di2 Synchro Shift S2 activation + Bell mapping), `references/studio-echelon-classes.md` (Echelon bookings). Answer platform-setup questions directly before adding caveats. |
| intervals.icu API coverage gaps | — | See `references/intervals-icu-api-coverage.md` |
| FTP/eFTP gap resolution | `get_sport_settings` + `get_wellness` | See `references/ftp-testing.md` |
| Sport transition DOMS | get_coaching_knowledge(\"recovery heuristics\") | Check recent activities for sport mix change |
| Calendar management | `create_planned_event` / `delete_planned_event` | See `references/event-creation-pitfalls.md` and `references/fit-workout-generation.md`. Pass `steps` with `hr_min/hr_max` (BPM), `power_pct_min/power_pct_max` (%FTP), or `pace_min/pace_max` (`5:40` or m/s). Tool auto-generates Garmin-compatible FIT files. ⚠️ **ONE target type per step** — auto-detection prioritizes HR > power > pace; if both HR and pace are present, pace is silently dropped. Use pace for work intervals, HR for warmup/cooldown. |
| Cron / headless sessions | Direct terminal invocation | See `references/cron-coaching.md` — ⚠️ always verify `deliver` target for multi-user jobs. See `references/cron-prompt-templates.md` for ready-to-adapt prompt templates with embedded terminal commands, snowflakes, and output structure. |
| Long-range data queries (YTD totals) | `get_athlete_stats` | Aggregates activities, distance, duration, calories, TL over a date range. Replaces raw API calls. |
| Cross-athlete tool gap discovery | session_search across athletes | See `references/gap-discovery-pattern.md` |
| Half marathon planning | `get_coaching_knowledge("half marathon")` + athlete data | See `references/half-marathon-periodization.md` |
| HR-vs-pace drift analysis | `get_recent_activities(30)` + `get_fitness_chart(90)` | See `references/hr-pace-drift-analysis.md` — quantify HR creep at fixed pace, connect to CTL ramp / chronic negative TSB, prescribe deload |
| HR-based training (no power meter) | Check `get_recent_activities` for null `normalized_power_w` | See `references/hr-based-training.md` |
| Masters athlete adaptations (60+) | Check `get_athlete_profile` for `date_of_birth` | See `references/masters-training.md` |
| Gravel route building | maps skill + OSRM cycling + Overpass API | See `references/gravel-route-building.md` |
| Two-location training plan | — | See `references/two-location-training.md` |
| Multi-week training plan + cron delivery | Full data pull → periodized plan → cron job | See `references/training-plan-creation.md` |
| Weekday/date mismatch in training plan | `date -d` verification + systematic patching | See `references/weekday-verification.md` |
| Training period summary | Parallel data pull → stats + charts + narrative | See `references/training-summary-workflow.md` |
| Body image / nutrition anxiety | — | See `references/body-image-and-nutrition-coaching.md` |
| **Strength training** | Load `strength-coaching` skill | Uses `assess_strength_level`, `exercise_lookup`, `generate_strength_workout`, `design_strength_program` — no intervals.icu needed |

## Training Methods

### Norwegian Singles (Running)

A threshold-focused training approach popularized by Norwegian endurance athletes,
adapted for single-sport-day amateurs (the "singles" variant, as opposed to the elite
"double threshold" model).

**Core principles:**
- 2 threshold sessions per week, separated by at least one easy day
- Threshold intervals are **controlled** — at or just below lactate threshold,
  never all-out. Athlete should finish feeling they could do one more rep.
- Short recoveries between intervals (typically 60 seconds)
- Easy days are **truly easy** — conversational pace, no grey zone

**Threshold format library** (pick format based on athlete's fitness, fatigue, and preference):

| Format | Total Work | Character | Best when... |
|---|---|---|---|
| 5×6 min | 30 min | Short, snappy. Less mental grind per rep. Good for maintaining form at pace. | Athlete wants variety from longer intervals; fresher feel |
| 4×8 min | 32 min | Balanced. More reps than 3×10, slightly more total work. | Smooth progression from 3×10 |
| 3×10 min | 30 min | Classic Norwegian format. Proven balance of stimulus and sustainability. | Default starting point; well-tested |
| 3×12 min | 36 min | Longer blocks, volume bump. Builds endurance at threshold. | Athlete ready for volume increase from 3×10 |
| 2×15 min | 30 min | Long sustained blocks. Tests concentration and pacing discipline. | Athlete wants fewer, longer intervals |
| 6×5 min | 30 min | Very short reps, high density. Sharpens form at target pace. | Peaking or when freshness is high |

**Progressive overload path:** 3×6 min → 5×6 min → 3×8 min → 4×8 min → 3×10 min → 4×10 min → 3×12 min
Start conservatively and extend only when the athlete consistently finishes sessions
feeling they had one more rep left.

**⚠️ Never skip progression steps.** Each step increases one variable at a time (total work, rep length, or rep count). Jumping from 3×6 directly to 3×8 skips 5×6 and increases both rep length (+33%) and total work (+20%) simultaneously — the athlete may be forced to pause mid-interval as HR drifts above threshold. When an athlete tolerates their current level, the temptation is to jump ahead — resist it. Move one step at a time. If an athlete fails a step (pauses, HR drifts above zone, RPE exceeds target), drop back to the previous step and rebuild.

**Pace source priority:**
1. **Lactate testing data first** — if the athlete has lactrace or lab lactate test results
   with actual mmol/L paces, those are authoritative. Ask before giving generic estimates.
2. intervals.icu running FTP from `get_sport_settings(sport="Run")`
3. Recent threshold session data from `get_recent_activities(sport="Run")`

**Pace zones** (derived from threshold pace, ~60-min race pace):

| Zone | Offset from threshold | Use |
|---|---|---|
| Easy/Recovery | +60–90 sec/km | Most days. Conversational. |
| Moderate | +30–45 sec/km | Optional bridge, use sparingly |
| Threshold | ±0 | Quality sessions (3-5×6-10 min, 60s rest) |
| 10K pace | −15–20 sec/km | Rare progression test |

**Weekly template (with strength):**
```
Mon: Easy run 35-40 min + 💪 Styrka A (ben) 25 min     → ~60 min total
Tue: Threshold session #1 (e.g. 4×8 min)                → ~60 min
Wed: Easy run 35-40 min                                  → ~40 min
Thu: 🛌 Rest / optional easy run 0-25 min
Fri: 💪 Styrka B (överkropp+bål+spänst) 25 min          → ~25 min
Sat: Threshold session #2 (e.g. 5×6 min)                → ~60 min
Sun: Long run 60-90 min progressive                      → 60-90 min
```

**Strength variety rules:**
- Styrka A = lower body focus (split squats, deadlifts, hip thrusts, lunges — rotate exercises weekly)
- Styrka B = upper body + core + plyometrics (rows, presses, anti-rotation, box jumps — rotate weekly)
- No single weekday session exceeds 60 min total
- Rest day (Thursday) is explicitly labeled in the calendar, never left as an empty slot

**Template without strength** (athlete prefers 0-1 strength sessions):
```
Mon: Easy run 35-45 min
Tue: Threshold session #1
Wed: Easy run 40 min or rest
Thu: Rest or easy run 30-40 min
Fri: Easy run 35-45 min
Sat: Threshold session #2
Sun: Long run 60-90 min progressive
```

**Common mistake:** Running easy days too fast, turning them into "grey zone" junk mileage
that adds fatigue without stimulus. Easy days must stay easy.

See `references/norwegian-singles-paces.md` for pace calculation methodology.

## Tool Troubleshooting

When coaching tools return data for the wrong athlete (no error, just wrong name/FTP/data),
see `references/credential-path-mismatch.md` — the credential path the plugin reads
may differ from where onboarding wrote credentials.

When coaching tools fail with `User identity check failed`, the Discord gateway is not
propagating the user identity. **Do not fall back to curl.** Fix the tools instead.

### Credential recovery (live-pod fix)

If `verify_athlete_identity` returns `verified: false`, the athlete's credentials
are missing, stale, or were manually placed without onboarding. The proper fix is
for the athlete to re-run `/start` (coach_onboard), which writes to the per-user
directory at `/opt/data/users/<snowflake>/`.

For a **temporary live-pod fix** (reverts on pod restart):

```bash
mkdir -p $HERMES_HOME/users/<snowflake>
echo -n "<api_key>" > $HERMES_HOME/users/<snowflake>/intervals_key
echo -n "<athlete_id>" > $HERMES_HOME/users/<snowflake>/intervals_athlete_id
echo -n "<discord_name>" > $HERMES_HOME/users/<snowflake>/intervals_athlete_name
chmod 600 $HERMES_HOME/users/<snowflake>/intervals_*
rm -f $HERMES_HOME/users/<snowflake>/cache/*.json
```

Without the name file, `verify_athlete_identity` returns `verified: false` with
`mismatched_fields: ["no_stored_name"]`. See `references/identity-verification.md`
and `references/credential-isolation.md`.

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
3. **Copy the live plugin to the editable sandbox path, then use `patch`:**
   `patch` and `write_file` block the live path `/opt/hermes/plugins/training/`,
   but the sandbox path `/opt/data/plugins/training/` is writable.  Workflow:
   ```bash
   cp /opt/hermes/plugins/training/<file>.py /opt/data/plugins/training/<file>.py
   ```
   Then use `patch(mode='replace', path='/opt/data/plugins/training/<file>.py', ...)`.
   After editing, sync back: `cp /opt/data/plugins/training/<file>.py /opt/hermes/plugins/training/<file>.py`.
   For test files, write directly to `/opt/data/tests/` — no sandbox copy needed.
4. **Test end-to-end on real data before writing unit tests.**  The plugin at
   `/opt/data/plugins/training/` is importable and has access to live credentials:
   ```bash
   cd /opt/data && python3 -c "
   import sys; sys.path.insert(0,'plugins/training'); import os
   os.environ['HERMES_HOME']='/opt/data'
   from intervals_icu import <new_fn>
   print(<new_fn>('discord_dm', ...))
   "
   ```
   This catches API endpoint errors, field-name mismatches, and response-size
   issues before they become test debt.
5. Verify syntax: `python3 -m py_compile /opt/data/plugins/training/<file>.py`
6. Run full test suite: `cd /opt/data && PYTHONPATH=plugins /opt/data/.test-venv/bin/python -m pytest tests/ -v --import-mode=importlib`
7. Push to PR branch via `create-pr.sh`, then verify tests pass on a fresh clone:
   ```bash
   cd /tmp && git clone -b improve/<slug> https://github.com/kvarnberg-labs/hermes-coach.git
   cd hermes-coach && PYTHONPATH=plugins /opt/data/.test-venv/bin/python -m pytest tests/ -v --import-mode=importlib
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

When an athlete says they are "always tired" or that they cannot keep changing the plan every week, treat that as a direct requirement for a more sustainable schedule—not as a prompt for another conditional same-day adjustment.

### Exercise-only fatigue and breathlessness

When symptoms occur only during training—not in ordinary daily life—do not automatically label them overtraining or prescribe another generic rest block. First distinguish the symptom: heavy legs, unusual heart-rate response, muscular fatigue, energy depletion, or disproportionate breathlessness. If the athlete reports persistent heavy breathing during running despite already completing a genuinely easy/recovery block, stop repeating the same advice and broaden the assessment. Normal routine blood tests reduce the likelihood of anemia, iron deficiency, and thyroid disease but do not exclude exercise-induced bronchoconstriction/asthma, post-viral or autonomic issues, altered running economy, pacing mismatch, or other sport-specific causes. Recommend medical follow-up for persistent exertional breathlessness (ask specifically about spirometry/bronchodilator testing where appropriate), while giving urgent-care red flags: breathlessness at rest, chest pain, syncope/near-syncope, cyanosis, or marked palpitations.

### Reconcile activity data before attributing symptoms

Intervals.icu logs can contain duplicate uploads, wrong sport labels, and planned workouts that were never completed. When the athlete says the log contradicts their actual training (for example, interval sessions appearing despite no intervals for weeks), acknowledge the correction plainly and treat the athlete's account as authoritative for completed-session history. Do not use ATL/TSB or a raw activity count to prove recent intensity until duplicates are deduplicated and planned versus completed sessions are separated. If the data is unreliable, say so and base the next step on symptoms, verified unique activities, and a short prospective observation period—not on the misleading log.

### Do not repeat an already-tested intervention

Before recommending "another few easy days," establish whether the athlete has already done that. If they have, explicitly state that more of the same is not yet justified and move to differential assessment, sport-specific symptom review, or medical follow-up. A positive TSB/recovery block is evidence against treating modelled training load as the sole explanation, not a reason to keep extending rest indefinitely. Review the 6–12 week load trajectory, CTL ramp, ATL peaks, consecutive negative TSB days, hard-session density, and actual-vs-planned load. Normal sleep, HRV, resting HR, nutrition, and medical values do not invalidate recurring subjective fatigue; they make a training-design mismatch more likely. Do not diagnose overtraining from TSB alone.

For a recurring-fatigue athlete, default to a stable rebuild block: one key intensity session per week initially, one easy non-progressive long run, explicit rest/easy days, at least 48 hours between hard sessions, and a deload every third week (or earlier when the trend warrants it). Do not prescribe an aggressive block followed by a distant recovery week and call that sustainable. Present the revised block as a complete table before changing many calendar events. See `references/sustainable-plan-design.md`.

## Pitfalls

- **`get_activity_streams` returns computed peaks, not raw arrays.** The tool computes peak power at 5s, 1min, 5min, 20min, 60min and an eFTP estimate (95% of 20-min) server-side from the raw 10K+ data-point arrays. It returns compact sample points (first 5, last 5 per stream) for validation, not the full arrays. Do NOT expect to iterate through `streams[].data` — the `data` key is not in the response. Access `peak_power` for computed metrics and `streams_summary` for stream metadata. The response is ~2KB, not 838KB.
- **Never use curl directly for training data retrieval.** Always use the Hermes coaching tools. If a tool is broken, fix the tool or implement a new one with `develop_tool` — do not work around it with raw HTTP calls.
- Do not prescribe specific workouts without checking TSB and recent load. TSB < -20 is a risk factor.
- Do not override coach-brain guidelines with generic model knowledge.
- **Never assume cycling as default sport.** When an athlete asks an open-ended question like "what should I train today," confirm which sport before pulling data. Cycling, running, and strength training require fundamentally different analyses. A threshold session prescribed in watts is useless to a runner. Ask explicitly: "Are you cycling, running, or both?" before fetching sport-specific settings. If the athlete wants strength training, load `strength-coaching` — it has its own tools and no intervals.icu dependency. This is the #2 most common coaching error after identity mismatches.
- **Verify the race surface and course profile before designing a program.** Athletes often describe their event generically ("90k motionslopp," "gran fondo") without specifying surface or elevation. BEFORE building a training plan: (a) ask for the race name and look up the official website, (b) verify surface (asphalt, gravel, dirt, mixed?), (c) check elevation profile (flat railway embankment vs hilly gravel). Klarälvsloppet, for example, is on an old asphalted railway embankment — not gravel as the word "motionslopp" might suggest. Surface determines: bike/tire choice, expected speed → finish time → nutrition plan, and whether the athlete should train on similar terrain. A gravel-focused program with dirt-road routes is wrong for an asphalt time-trial-style event, and vice versa. The race website's description ("bilfritt, platt och snabbt" or "nio mil asfalterad naturupplevelse") is authoritative — trust it over the athlete's casual description.
- **Always separate sports** — cycling and running are independent analyses. Never present a blended summary that mixes ride and run TSS. Present separate logs and note which sport drives CTL changes.
- Always check weather before recommending outdoor training.
- **Verify current time before giving departure-window advice.** When an athlete says "I have to do a ride today" without specifying when, do not assume they're still planning — they may already be on the bike or about to step out. Check the current time (system clock or ask the athlete) before recommending specific departure windows, best times of day, or weather windows that assume the ride hasn't started. If it's late or they're leaving now, skip time-based planning and focus on real-time conditions and pacing guidance.
- Injury red flags require medical referral — do not suggest continued training.
- **Missed session due to illness — adjust the plan, don't just skip.** When an athlete reports missing a session because they were sick: (a) verify by checking `get_recent_activities` — the missing date confirms their report, (b) check `get_wellness(days=7)` for resting HR trend — a +10-15 bpm spike 2-3 days before the missed session is a common early-warning signal, (c) consult `get_coaching_knowledge("injury return to training")` → `illness` key for the return timeline (Day 1-2: light walk only, Day 3-4: Z1 if feeling well, Day 5-7: normal easy training, Day 8+: intensity with caution), (d) patch the training plan file to replace the missed session with "SJUK ❌" and adjust upcoming sessions per the return timeline — a 120-min long run 3 days after illness becomes 50-60 min Z2 low, (e) if a recovery week was already scheduled next, note that the timing is actually favorable — the forced rest lines up with the planned deload. See `references/illness-plan-adjustment.md`.
- **Sport transition DOMS is expected.** When an athlete returns to running after a cycling-dominant period (or vice versa), delayed onset muscle soreness is normal for the first 1–2 weeks. Running has eccentric loading that cycling lacks. Management: reduce load 30–50% for 3–5 days, easy movement helps (do not skip sessions entirely), ensure 1.6–2.0 g/kg protein daily. Escalate if DOMS persists beyond 5–7 days or is sharp/pinpoint rather than diffuse.
- **Duplicate activities on intervals.icu — flag once, then use only the first unique entry.** When `get_recent_activities` returns multiple entries with identical names, dates, and stats (different IDs), the workout was uploaded multiple times — common with HealthFit → Apple Watch sync. Flag it to the athlete once ("du har dubbletter"), then always use only the first unique activity ID for `get_activity_detail` and `get_activity_streams`. Do NOT re-analyze or re-flag duplicates every session — the athlete already knows, and re-reporting makes the agent look inattentive.\n- **TSB is a mathematical model, not a diagnosis.** When TSB is deeply negative but RPE is low, resting HR is at baseline, HRV is stable or improving, and the athlete reports feeling strong, TRUST THE ATHLETE. Subjective feel plus physiological markers outweigh TSB. Before concluding overtraining: (1) verify resting HR trend (not elevated >5 bpm above baseline), (2) check HRV trend (not suppressed >10% below 7-day average), (3) inspect sleep quality and duration, (4) check if ATL is inflated by grey-zone riding on "endurance" days (see Grey zone detection pitfall below). If markers (1)-(3) are normal and (4) is present, TSB is overstating fatigue — fix the execution, not the training load. Do not label an athlete "trött" based on TSB when they say they are fine.
- **Grey zone warning should be proportionate.** Long rides at 79-85% FTP instead of 56-75% (Z3 instead of Z2) is an optimization opportunity, not a crisis. If the athlete's RPE is 2, frame it as a suggestion, not a correction.
- **Respect the athlete's requested level of detail.** When an athlete explicitly says "just the number" / "no details needed" / "kort svar" / "räcker med en siffra", deliver exactly that — the answer, nothing more. Do not append a table, breakdown, or analysis they just told you they don't want. You can offer follow-up ("Vill du ha detaljer?") but only after delivering the requested minimal answer. Over-formatting a simple answer after being told to keep it short is frustrating and erodes trust.
- **Answer "how do I do X" questions directly — don't lead with why they don't need to.** When an athlete asks how to change a setting in Garmin, intervals.icu, Zwift, or any platform, answer the question FIRST with clear step-by-step instructions. Only after you've answered should you add context about whether the change is necessary. Leading with "you don't need to" when they asked HOW is dismissive and wastes their time — if they're asking, they've already decided they want to do it. This applies to all platform/settings questions: Garmin, Zwift, intervals.icu, TrainerRoad, etc.
- **Language consistency — match the session's language, never switch unprompted.** If the athlete starts the session in English, stay in English. If they start in Swedish, stay in Swedish. Do NOT let Swedish from cronjob prompts, other athletes' conversations, or coach-brain files bleed into an English session. Multi-language context is common (Swedish athletes, English documentation and users), but the session language is set by the athlete's first message — follow it. A mid-session language switch without the athlete initiating it erodes trust and looks buggy.
- **Grey zone detection — compare planned vs actual IF systematically.** When an athlete's TSB is deeply negative without corresponding physiological stress signals, suspect grey-zone inflation. Method: for every ride labeled endurance/Z2, compare actual NP/IF against the planned Z2 range (56-75% FTP). A ride at IF 0.80-0.87 instead of 0.56-0.75 generates ~40-70% more TSS than planned. Cumulative effect across a training block can drive ATL 10-20 points higher than intended — producing alarming TSB values that do NOT reflect genuine overtraining. When detected: (a) present a planned-vs-actual comparison table with IF delta, (b) note that TSB is overstated, (c) adjust future Z2 prescriptions to emphasize strict watt caps (e.g. "148-185W" not just "Z2"), (d) do NOT add extra rest days to compensate — fix the execution, not the plan.
- **Date/weekday accuracy — always cross-reference.** When presenting dates alongside weekday names, verify the mapping against a calendar or the athlete's timezone before writing. A mismatch between date and weekday erodes trust and forces the athlete to correct you. If unsure, use the date alone or ask. Always use the athlete's configured timezone (from get_athlete_profile) when resolving "today" or planning future sessions. When fixing weekday mismatches across a multi-week training plan, follow the systematic workflow in `references/weekday-verification.md` — patch weeks individually, then fix any cron rules that reference weekday names.
- **Rest days must be explicit calendar events — an empty slot is invisible.** When the athlete looks at their calendar and sees nothing on a day, they don't know if it's a planned rest day, an oversight, or a gap. Always create a named event (e.g. "🛌 Vilodag / lätt löpning") on rest days. Include a brief note about optional light activity (walk, 20–25 min Z1) so they have permission to move but know quality work is not expected. An invisible rest day causes the question "varför har jag aldrig vilodag?" — even when rest days technically exist. This is one of the most common athlete complaints about auto-generated plans.
- **Strength sessions must rotate muscle groups — never default to leg-only every session.** Four identical leg exercises (knäböj, marklyft, utfall, höftlyft) repeated every strength session is monotonous, increases overuse injury risk, and ignores upper body, core, and plyometrics that runners need for posture, arm drive, and running economy. Minimum viable variety: alternate between "💪 Styrka A (ben)" and "💪 Styrka B (överkropp+bål+spänst)" across the week. Each session should be short (20–30 min) to fit a weekday. When the athlete asks "varför är styrka alltid ben?", the coach defaulted to the laziest template — fix it immediately.
- **Weekday combined sessions must stay under ~60 min total.** An easy run (35–40 min) plus strength (40–45 min) = 80+ min — too long for a working athlete. Solutions: (a) split strength into two short 25-min sessions on different days, (b) move one strength to a weekend day, or (c) drop to one quality strength session. For Norwegian Singles athletes who want 2 strength sessions, the pattern that works: Monday easy run + short leg strength (~60 min total), Friday short upper/core strength only (~25 min). Present the trade-off to the athlete rather than silently scheduling 80+ min weekday doubles that they'll skip or resent.

- **Relative day references after a multi-day plan — NEVER use "tomorrow" loosely.** After laying out a weekly plan in a table, do not drop casual relative-day words ("tomorrow", "the day after", "next session") in follow-up messages without verifying they match the plan. A message saying "tomorrow you're ready for quality" when the plan says tomorrow is strength training forces the athlete to catch your contradiction — this erodes trust and wastes their time. Instead: (a) use weekday+date ("lördag 1/8"), or (b) restate the relevant row from the plan table so the athlete sees the consistency. The athlete must be able to act on your answer immediately — not cross-check against earlier messages to spot your errors.
- **Calendar dosing is literal — athletes follow the plan, not their own judgment.** When a workout is in the calendar, the athlete executes it as written. A dosing error (wrong progression step, too much volume, too high intensity) has direct physical consequences — the athlete will push through rather than self-correct, because they trust the coach. Treat every calendar write as a prescription: double-check the progression step, the volume, and the intensity against the athlete's current fatigue state before creating the event. If the athlete reports failing a session (pauses, HR drift, RPE exceeding target), the fault is the coach's dosing, not the athlete's execution. Own it, fix the calendar, and adjust the progression.

- **Planned event names are labels, not facts — never derive conclusions from them.** A planned event named "Sista semesterpasset!" does not mean the athlete's vacation ends after that session. The name was written by a human (or an earlier agent) as a casual label — it may be aspirational, outdated, or just poorly chosen. Always cross-reference names against what the athlete has explicitly told you about their schedule. When in doubt, state what the planned event says AND what the athlete told you separately, and ask which is correct. Trust the athlete's direct statements over any text in a planned event name or description.
- **Life-first scheduling — training serves the athlete's life, not the reverse.** When the athlete mentions social events, dinners, alcohol, travel, or family commitments that conflict with planned sessions: (a) acknowledge the priority of life over training immediately — never pressure the athlete to skip or minimize social events, (b) ask or use the stated timing of the commitment before moving a session — an evening wedding does not conflict with a short morning/e-daytime run, (c) restructure only the genuinely conflicting sessions by protecting key quality workouts, swapping days, compressing the week, or dropping one session, (d) present the adjusted plan with unambiguous day-name+date labeling, and (e) reassure the athlete that one adjusted week has zero impact on long-term development. The right answer to "should I skip this session for a dinner with friends" is always "yes, let's adjust the week" only when the session actually conflicts with the event; do not invent a conflict from the date alone. Default pattern for an evening social event + alcohol: keep or move a light workout to the morning/earlier that day if practical, make the following day explicit rest/recovery, and never suggest the athlete skip the social event. Never infer that the entire event day must be rest without checking event timing. For a three-day off-bike block, front-load at most one key session before the block, retain the other days as explicit recovery/no-bike events, and do not try to compensate with extra intensity afterward. If the athlete requests moving a quality session onto an existing rest day, first check the preceding 7–10 days and current wellness, then replace/update the conflicting rest event, create the workout, and verify the resulting calendar so two contradictory events are not left on the same date. A user-requested practical constraint can justify a controlled VO2 session, but for a masters athlete after a recent high-load ride it should be reduced in volume (e.g. 4×3 min rather than 5×5) and include a warm-up checkpoint and a bail-out clause.
- **Travel days — use them as active recovery, not training zeros.** When an athlete has a travel day (long drive, flight) that conflicts with a planned session: (a) move the key quality session to the day before travel, (b) keep the travel day itself as active recovery — a short light jog (20–25 min Z1) before departure keeps blood flowing and prevents stiffness from prolonged sitting, (c) the travel day then becomes passive recovery for the rest of the day. This preserves the week's stimulus without adding fatigue. The alternative (forcing quality on travel day at 5 AM) usually fails.
- **"Rörelse hjälper" — don't force rest when the athlete says movement alleviates symptoms.** When an athlete reports non-illness symptoms (headache, stiffness, low mood) and explicitly says movement makes it better, do NOT override them with TSB data and a rest prescription. The correct flow: (1) present the TSB trend and physiological context, (2) acknowledge their self-knowledge — "du känner din kropp bäst", (3) offer a light session with clear Z1–Z2 guardrails and a bail-out clause ("bryt om det blir värre"). The default is to ask, not assume — present the data, then let the athlete decide. Only enforce rest when symptoms worsen with exertion or the athlete is undecided. This applies especially to headache, DOMS, and mental fatigue — movement often helps where forced rest doesn't.
- **Present multi-week plans for approval BEFORE bulk-creating events.** When an athlete asks for a training program spanning weeks or months, present the full plan as a table first and wait for explicit confirmation. If the athlete wants changes, iterating on a table is trivial — deleting and recreating 25+ events because you jumped the gun is not. Only call `create_planned_event` after the athlete explicitly approves. See `references/training-plan-creation.md` for the full workflow including TL estimation and batch creation patterns.
- **FTP estimation — don't guess from non-maximal rides.** NP over 50+ minutes is only a reasonable FTP proxy when the effort was **maximal or near-maximal** (race, FTP test, hill climb PR, Zwift race). Do NOT estimate FTP from a routine endurance ride, a windy variable-effort ride, or any session where the athlete was not going all-out. NP on a variable 3h ride with headwind and climbs says nothing about what the athlete could hold for 20 minutes at max. Similarly, **decoupling is NOT an FTP estimator** — it's an individual physiological marker (some athletes decouple 5% at threshold, others 20%). Using it to back-calculate FTP is circular and invalid. Only suggest FTP adjustment if the athlete reports failing prescribed intervals at a given FTP, or if they complete a maximal 20-min effort. When in doubt, defer to the eFTP from wellness data rather than guessing.
- **FTP test analysis — always check intervals.icu's own FTP estimate before giving your verdict.** After a maximal TT or FTP test, intervals.icu's algorithm analyzes the full power-duration curve and may detect sustained efforts (e.g. 44 min @ 263W) that simple formulas like 95%-of-20-min miss. The platform's auto-estimate notification ("Your estimated FTP has increased by XW to YW based on Zm at QW") is often more accurate than the standard formula because it uses a longer duration window. Do NOT give an FTP recommendation based solely on 20-min peak power without first asking the athlete whether intervals.icu has reported its own estimate. If you give a conservative number and the platform later says +10W higher, you look like you don't trust the data — and the athlete will trust the platform over you. Present both numbers, but give the platform estimate MORE weight when it's based on a longer sustained effort than 20 minutes.
- **Verify max HR with the athlete — do not trust intervals.icu's configured value blindly.** `get_sport_settings` returns a `max_hr` field from the athlete's intervals.icu settings. This value is manually entered by the athlete and is often outdated, guessed, or inherited from a default. **Always ask the athlete what their actual max HR is** before building HR-based zones. A 3 bpm difference (165 vs 162) shifts Z2 boundaries and can put the athlete in the wrong training zone. If the athlete doesn't know their max HR, use LTHR-based zones (anchored to `lthr` from `get_sport_settings`) which are more reliable than max-HR-derived zones. See `references/hr-based-training.md` for zone calculation methodology.

- **Power is authoritative for cycling Z2 — HR is secondary and confirming.** For cyclists with a power meter, Z2 prescriptions should use power zones (56–75% FTP), not HR zones. The athlete's actual HR at a given Z2 power is a function of their individual aerobic efficiency, not a fixed %LTHR. An aerobically efficient cyclist riding at 148–165W (57–63% FTP) may see HR at ~120 bpm — well below the HR Z2 range prescribed by generic formulas. That is NOT a problem — it means the athlete has high stroke volume and is getting the intended stimulus. **Always prescribe Z2 by power first.** Include HR as an FYI with an explicit caveat: "Din puls kommer sannolikt ligga lägre, och det är helt rätt." If the athlete questions the HR number, explain the physiology (high stroke volume, power > HR for cycling Z2) and reinforce that the power target is the correct anchor. The conversational test (full sentences without gasping) is the final arbiter regardless of what either meter says.\n- **Masters athletes (60+) need fundamentally different program design.** When `get_athlete_profile` shows `date_of_birth` indicating age ≥60 (or the athlete tells you their age), apply masters-specific adjustments BEFORE building any training plan. Key differences from standard programming: (1) recovery weeks every 2nd–3rd week instead of 3rd–4th, (2) conservative ramp rate +3–5 CTL/week instead of +3–8, (3) max 1 intensity session per week — never stack two quality days, (4) strength training is year-round maintenance, not seasonal, (5) longer warm-ups (15+ min before any intensity), (6) total volume ceiling ~5.5h/week peak. Do NOT apply a generic polarized/pyramidal template designed for a 30-year-old to a 66-year-old — it will cause overtraining. See `references/masters-training.md` for the full evidence base and program templates.
- **Configured FTP vs eFTP gap — flag it, but don't treat eFTP as gospel.** On every post-ride analysis, cross-reference `get_sport_settings` configured FTP with eFTP from `get_wellness` → `sport_info`. A gap >10W means zone times, IF, and sweet-spot ranges are all calculated against potentially the wrong baseline. Flag the gap first, then present both interpretations. An IF of 0.76 at 284W FTP is very different from an IF of 0.92 at 234W eFTP.\n\n  **When creating planned events: `power_pct_min/max` uses configured FTP, not eFTP.** If you prescribe 88-94% of eFTP 274W (241-258W) but set `power_pct` to 88-94%, the trainer displays 252-269W (88-94% of configured 286W). Always compute percentages against configured FTP for the event payload, then verify the displayed watts match the intended physiological zone. Cross-reference after creation: ask \"what does Zwift/Garmin show for the target?\" — the athlete's device is the final arbiter. See `references/event-creation-pitfalls.md`.\n\n  **eFTP is a model estimate, not a measurement.** It derives from the power-duration curve across ALL rides and cannot distinguish maximal efforts from training rides. **Warning signs that eFTP is UNDERESTIMATING:** (1) eFTP is trending DOWN while CTL is trending UP — the athlete is getting fitter, not weaker; (2) no recent maximal efforts (FTP test, race, hill-climb PR, Zwift race) in the past 4–6 weeks; (3) the athlete reports feeling strong at power levels that eFTP says should be VO2max. In these cases: flag the discrepancy, present both interpretations, **explicitly ask the athlete which FTP feels right**, and if they push back on eFTP — trust them. Propose a structured FTP test (20-min all-out or ramp test) to resolve the question definitively. Do NOT insist on eFTP when the athlete disagrees and the data context supports their position.
- **Lactate testing data > generic estimates.** When an athlete shares a lactrace or lactate test result (e.g., a screenshot showing paces at measured mmol/L), those paces are the ground truth. Do not give a generic pace recommendation like "5:00-5:05/km" if the athlete has actual lactate-tested threshold pace. Ask for their data first, or pause and read the image they share. Generic zone math is a fallback, not the default.
- **Session average pace is NOT interval pace.** When analyzing a threshold/interval run, the `pace_mps` and `distance_km / duration_min` from `get_recent_activities` give the session average including warm-up, recovery jogs, and cool-down — which can be 20-30 sec/km slower than the actual work intervals. Always pull `get_activity_detail(activity_id)` and use `interval_summary` (Garmin auto-detection, e.g. "6x 4m43s 4:44") and `pace_zone_times` for the real work-interval paces. Never prescribe today's interval pace based on yesterday's session average.
- **intervals.icu API field names use `icu_` prefix, not Strava-style names.** If `get_activity_detail` returns null for `hr_zones`, `hr_zone_times`, `power_zones`, or `power_zone_times`, the plugin is likely using wrong field names. The intervals.icu API returns `icu_hr_zones`, `icu_hr_zone_times`, `icu_power_zones`, `icu_zone_times` — NOT `heartrate_zones`, `heartrate_zone_times`, `power_zones`, `power_zone_times`. See `references/intervals-icu-api-fields.md` for the full field mapping and debugging technique.
- **Module-level caches break test isolation.** `_load_all()` in `coaching.py` uses a time-based cache (`_brain_cache`, `_BRAIN_CACHE_TTL`). When tests monkeypatch `_brain_dir()` to point at temp directories, the cache from the first test persists and all subsequent tests get stale data. The cache must be keyed by directory path (`_brain_cache_dir`) so directory changes invalidate it. Any future module-level cache in the plugins must follow the same pattern — include the identity of the input source in the cache key, not just a TTL.
- **Verify athlete identity every session — use `verify_athlete_identity` first.** Call `verify_athlete_identity` before pulling any training data. If it returns `verified: false`, stop — credentials are stale, wrong, or manually placed without onboarding. Do not proceed until the athlete re-runs `/start` (`coach_onboard`). After verification passes, call `get_athlete_profile` as secondary confirmation that the name and athlete_id match expectations. This has been the #1 recurring bug (wrong athlete's data silently returned). See `references/identity-verification.md`.
- **VirtualRide ≠ Zwift.** Not all `VirtualRide` activities on intervals.icu are from Zwift. Indoor trainer sessions recorded via Garmin Edge (with Wahoo or other smart trainers) also classify as VirtualRide. When an athlete reports Zwift import issues, ask what device recorded each VirtualRide before assuming Zwift import is working. Zwift-imported activities typically have names prefixed with `Zwift -`.
| Zwift workout recommendations must be verified before naming a workout. If an athlete asks for a suitable workout "from the Zwift store/library," distinguish the Zwift game workout library from the equipment/product store. Search the official Zwift workout/library source first; if it is unavailable or search results are inconclusive, say so and give the workout structure to recreate rather than inventing or asserting a named workout. Do not rely on a third-party page returning a 404, a blocked search page, or an unverified memory of a workout title. Before recommending a same-day hard session, still check recent load/wellness and ask how the athlete feels today; model readiness alone is insufficient. When a named workout is verified, state its exact interval structure, total duration, and FTP basis, and flag any configured-FTP versus eFTP discrepancy before translating watts. See `references/zwift-workout-search-and-analysis.md` for the compact search and post-ride workflow.
- **Credential path mismatch causes wrong-athlete data.** The plugin resolves credentials from `Path(HERMES_HOME) / "users" / discord_id`. With `HERMES_HOME=/opt/data`, it reads from `/opt/data/users/discord_dm/`. If wrong credentials are in that path, ALL tools silently return the wrong athlete's data. **Prevention:** `verify_athlete_identity` catches this — it returns `verified: false` when credentials lack a stored name (manually placed) or the API profile mismatches. The permanent fix (PR #15) adds identity verification. **Live fix:** copy correct credential files AND write `intervals_athlete_name` (Discord username), then call `verify_athlete_identity`. This reverts on pod restart. See `references/credential-path-mismatch.md` and `references/identity-verification.md`.
- **Multi-user credential isolation is now supported via Discord snowflakes.** Hermes core (model_tools.py `handle_function_call`) now accepts a `user_id` parameter and threads it through to `registry.dispatch()`. The Discord adapter passes `source.user_id` (the athlete's snowflake) into tool dispatch, so `_require_user_id(kw)` returns the real snowflake instead of falling back to `discord_dm`. Each athlete gets their own credential directory at `/opt/data/users/<snowflake>/`. **Before this fix (pre-PR #18 + Hermes core update):** all users shared the `discord_dm` slot and silently overwrote each other's credentials. **After:** onboarding via `/start` writes to the per-user directory automatically. The `discord_dm` shared fallback was **removed** (PR #32, 2026-07-20) — sessions without a valid user_id now raise `ValueError` and return a clear JSON error instead of silently loading shared credentials. See `references/credential-isolation.md`.
- **\"User identity not available\" error — gateway lost the snowflake, not a credential problem.** Since PR #32, every coaching tool requires a valid Discord snowflake in `kw[\"user_id\"]`. When a tool returns `{\"error\": \"User identity not available — the Discord gateway did not provide a valid user ID.\"}`, the session has lost its identity context. This error replaces the old silent cross-athlete data leak where a dropped snowflake would load the shared `discord_dm` credentials. See `references/credential-isolation.md` for architecture background.\n\n  **Interactive session (gateway hiccup):** Tell the athlete to `/new` (restart the conversation). Do NOT attempt a credential recovery or live-pod fix — the credentials are fine, the gateway context is broken.\n\n  **Cron/headless session (expected — no gateway at all):** This error is unavoidable. Work around it by calling the plugin functions directly via `terminal()` with the athlete's snowflake hard-coded as a positional argument — the internal functions accept `discord_id` directly and bypass `_require_user_id(kw)`. See `references/cron-coaching.md` for the exact invocation pattern, function signatures, and how to discover the snowflake.

  **Cron execution sequence:** Do not stop when the model-visible `verify_athlete_identity` tool reports missing gateway identity. In a scheduled job, resolve the athlete's snowflake from the job's `origin.user_id`/delivery configuration (not from empty session environment variables), then call the internal `verify_athlete_identity(snowflake)` directly via the plugin. If verified, call `get_athlete_profile(snowflake)` before any wellness/activity/calendar pulls, and use the same snowflake for every subsequent direct plugin call. The direct-call pattern is: `PYTHONPATH=<plugins> python3 -c ... from training.intervals_icu import ...; fn(snowflake, ...)`; parse the JSON and keep only the fields needed for the brief. Never substitute another user's credentials or the shared `discord_dm` directory. Keep the resulting JSON compact when assembling the brief, and preserve the report's conditional-intensity rule when today's subjective feel or sleep data is absent. See `references/cron-coaching.md` for the verified recipe.
- **`Path.home()` fallback removed (PR #18).** The plugin's `_user_dir` no longer falls back to `Path.home() / ".hermes"` when `HERMES_HOME` is unset. Instead it raises `RuntimeError`. This eliminates the split-brain credential state where `/opt/data/users/discord_dm/` and `/opt/data/home/.hermes/users/discord_dm/` could hold different athletes' credentials. **Historical context:** `Path.home()` resolved to `/opt/data/home` (not `/opt/data`), creating a second credential directory on the same PVC that persisted across restarts. If `HERMES_HOME` was ever unset during a process (cron, plugin reload), the plugin silently switched paths.
- **Zone naming confusion — intervals.icu vs popular frameworks.** Athletes who follow popular "Zone 2" training content (Attia, San Millán, Norwegian method) use a 3-zone or 5-zone model where "Zone 2" means conversational endurance pace. intervals.icu uses the Coggan 7-zone power model where the same effort falls in Z1 or low Z2. When an athlete asks "Inga zon 2 pass?" or questions why their easy days aren't "Zone 2", explain the mapping: popular "Zone 2" = intervals.icu Z1-Z2 (conversational, <75% FTP for cycling or <80% LTHR for running). Do NOT assume the athlete is confused — they may be using the popular framework correctly and mapping it to intervals.icu terminology. Just clarify which system you're using and why both are "right."
- **Athlete's "rest" ≠ empty calendar — validate before you correct.** When an athlete says "jag har vilat i fyra dagar" but the data shows light runs and strength sessions, they're defining "rest" as "no quality/hard sessions" — not literal inactivity. Validate their perspective FIRST ("du har rätt, det har varit lätt träning") before showing the physiological data explaining why light work was the right bridge. Arguing about definitions ("måndag var inte vila, du körde styrka") makes the athlete feel unheard. Instead: "Jag förstår vad du menar — det har inte varit kvalitetspass. Men här är vad kroppen signalerar..." Then present TSB trend as evidence, not correction.

- **"Allt fallerar" panic — always lead with the TSB trend table.** When an athlete catastrophizes about missed sessions ("allt fallerar," "tappar all form," "hela veckan förstörd"), the first data you show should be a TSB trend table proving the accumulated fatigue that made rest necessary. Frame one skipped quality session as strategic, not failure.

- **Same-day recovery → adapt the calendar immediately.** When an athlete reports feeling better same-day, pivot: move a future workout to today, free up a later day, and update the calendar in real-time.

- **CRITICAL: Cronjob deliver must target the ATHLETE'S channel, never your own.** When creating or updating a cron job for another athlete, you MUST set `deliver` to the athlete's explicit Discord channel ID. Use `grep "user=<Name>" /opt/data/logs/gateway.log | tail -1` to find it. In cron sessions, coaching tools fail — use terminal workaround from `references/cron-coaching.md`. 

- **MANDATORY: Consult the API docs before implementing ANY intervals.icu integration.** When debugging a tool, adding a new endpoint, or figuring out payload structure, call `search_intervals_api_docs` + `get_intervals_api_endpoint` FIRST. The OpenAPI spec is the authoritative reference. Guessing field names, schemas, or formats wastes sessions. For workout creation: the EventEx schema documents `file_contents_base64` (for FIT/ZWO/MRC/ERG files) and `workout_doc` (internal format). The endpoint description: "This endpoint accepts workouts in native Intervals.icu format as well as zwo, mrc, erg and fit files."

- **Check the Dockerfile before declaring missing dependencies.** When adding a new Python package or claiming something needs to be installed, check the repo's Dockerfile first — many packages are already installed via the `RUN uv pip install` line. Claiming a missing dependency that's already present wastes trust and creates unnecessary PR churn.

- **Easy runs don't need warmup/cooldown steps.** Z1/Z2 steady runs should be a single step with the full duration. Only add warmup/cooldown for workouts with meaningful intensity changes (intervals, threshold, VO2max). A 35-50 min easy run is one block.

- **Event duration must match the prescription.** If you recommended 35-50 min, the event duration should be the midpoint (e.g. 45 min = 2700s), not an arbitrary 60 min. Double-check before calling create_planned_event.

- **Numerical precision — never round or approximate training stats.** When presenting how many days an athlete trained, count exactly from the data — do not estimate, do not round up. Saying "6 av 7 dagar" when the actual count is 5 runs + 1 strength = 6 sessions (but 5 run days) is sloppy and the athlete WILL notice and correct you. Present the precise breakdown: "5 löppass + 2 styrkepass" not "du har sprungit 6 av 7 dagar." When in doubt, undercount rather than overcount — the athlete trusts you less with every imprecise statement.

- **Activity sync delay — widen the window if today's activity is missing.** When `get_recent_activities(days=1)` doesn't return today's activity but `get_wellness` shows updated CTL/ATL for today, the activity exists but hasn't appeared in the 1-day window yet (HealthFit → intervals.icu sync lag). Re-query with `days=3` or without sport filter — the activity usually appears within the wider window. Do NOT tell the athlete "passet har inte synkats" based on a single narrow query when wellness data proves it's already registered.
- **Re-check after sync claims — do not reuse a stale wellness result.** If an athlete says sleep/HRV or another metric is now visible in Apple Health/Intervals.icu after an earlier query showed `null`, make a fresh `verify_athlete_identity` and `get_wellness` call immediately (prefer a narrow 1–2 day window). Compare the new `today` record directly; sync may complete between turns. Report the exact newly available fields and distinguish remaining null fields (for example, sleep duration present while sleep score/quality remain absent). Do not repeat the earlier "not synced" conclusion without re-querying.
- **Running pace targets in `create_planned_event` WORK — do NOT tell the athlete otherwise.** The `pace_min`/`pace_max` parameters produce correct pace targets in the generated FIT file and sync to Garmin. The old bug was in the `workout_doc` code path (pre-PR #53), NOT in the current FIT-based `file_contents_base64` approach. **CRITICAL: FIT format allows only ONE target type per step.** Auto-detection prioritizes HR > power > pace — if you include both `hr_min/hr_max` and `pace_min/pace_max` on the same step, pace is silently dropped. Use pace OR HR per step, never both: pace for threshold/interval reps, HR for warmup/cooldown/recovery. If you need both on a work interval, put pace as the target and include the HR range in the step `description`. Do not recall the old `workout_doc` pace bug and apply it to the current tool — they are different code paths. If you are unsure whether pace works, check `references/fit-workout-generation.md` and `references/event-creation-pitfalls.md` BEFORE telling the athlete it can't be done.
- **Pace window width — use 15–20 sec/km for outdoor running prescriptions.** Narrow pace windows (e.g. 4:44–4:52/km, an 8-second band) are unrealistic for outdoor GPS running where pacing granularity, terrain, and GPS drift make hitting a tight range frustrating. Use **15–20 second pace windows** for all running prescriptions: threshold (e.g. 4:40–4:55/km), easy (e.g. 5:20–5:40/km), and interval work. This applies to both `create_planned_event` step targets and verbal pace guidance in coaching messages. Indoor/treadmill running can use tighter windows (5–8 sec) since pace is machine-controlled. When an athlete corrects a pace window as too narrow, widen immediately and save the preference — do not re-prescribe narrow windows in future sessions.
- **Proactive data pull for casual greetings — don't wait for a training question.** When an athlete opens with "Hur mår du?" or similar casual check-in, do NOT respond with a generic greeting and ask how they are. Pull `get_recent_activities`, `get_wellness`, and `get_planned_events` immediately and reference their current state — including whether today is a planned rest day. The athlete expects the coach to already know their schedule and recent training. A generic "Hur är det med dig?" response to an opener forces the athlete to prompt you ("det har du väl koll på?"), which erodes trust.
- **Echelon class recommendations must match both time windows AND planned intensity.** When checking the live Echelon schedule for an athlete, filter to their available time slots (e.g. 07:00 and 18:00+ for Millberg) AND cross-reference against the day's planned workout type. Do NOT present a threshold class (Thin Red Line) when the plan calls for Z2, even if the time slot fits. If no class matches both constraints, say so and recommend outdoor or self-directed training. See `references/studio-echelon-classes.md` for the live schedule checking procedure.
- **Pace at low HR declining — quantify before advising.** When an athlete reports "I'm getting slower at the same heart rate" or "my HR is creeping up at my usual easy pace," do NOT dismiss it as perception or tell them to just run slower. This is a real physiological signal: cardiovascular efficiency regression from accumulated fatigue. Pull 30 days of easy runs, tabulate pace vs max HR vs RPE (controlling for elevation), and compare early vs late periods. Connect to CTL ramp rate and consecutive negative-TSB days via `get_fitness_chart(90)`. If the data confirms drift (e.g., +5–10 bpm at same pace, +1 RPE, stagnant threshold pace with rising HR), prescribe a deload — typically two consecutive light weeks if the athlete has had >6–8 weeks of negative TSB. See `references/hr-pace-drift-analysis.md` for the full method. Do not confuse this with the ventilatory-threshold breathlessness plateau (`references/running-plateau-and-breathlessness.md`) — different cause, different fix.
- **Verify workout exercise content before describing it to the athlete.** When summarizing a planned event (e.g. "Styrka B — överkropp+bål+spänst"), always read the actual exercises listed in the event description field — do not assume the event name or label accurately describes the content. A workout labeled "överkropp+bål+spänst" may contain lunges and hip thrusts (leg exercises), or a description mentioning "spänst" may list no plyometric exercise at all. Before telling the athlete "det är överkropp idag", scan the exercise list and verify each exercise matches the claimed muscle group. If the label and content don't match, either fix the event or describe what's actually there. Mismatched descriptions force the athlete to correct you repeatedly, eroding trust — each correction is a visible quality failure.

- **Never invent, upgrade, or inflate an athlete's race goal.** The athlete's goal is a durable coaching anchor stored in memory, cron prompts, and conversation history. Do NOT infer a more ambitious target than what is recorded. For example, if the recorded goal is "halvmaraton under 1:40 (4:44/km)", do NOT write "sub-1:38 (4:39/km)" or "elit-aktigt halvmaramål" unless the athlete has explicitly stated a new goal in the current conversation. Goal inflation is a fabrication — the athlete did not say it, and it shifts all training prescriptions toward intensities the athlete has not targeted. If you are unsure of the exact goal, retrieve it from saved memory or the verified profile, and if still unclear, ask the athlete directly. When an athlete DOES state a new or revised goal, save it to memory immediately and update any cron prompts that reference the old goal.

## Post-Ride Analysis Checklist

When an athlete finishes a ride or run and asks for a post-ride brief, pull this
full set (in the listed order) before presenting ANY analysis:

### Athlete-specific depth and data reconciliation

For this athlete, a post-ride analysis must be a genuinely deep review when they
ask for their usual analysis—not a short congratulations. Always reconcile the
**power profile against the HR response** before classifying the session. In
particular, do not infer cardiovascular intensity from power-zone time alone:
short climbs, sprint efforts, chasing a group, and terrain can raise TSS/NP while
HR remains almost entirely Z1. Report both dimensions explicitly:

- **Cardiovascular load:** HR zone times, max HR, HR trend/response, and whether
  the athlete stayed aerobically controlled.
- **External/mechanical load:** duration, elevation, average and normalized power,
  VI, power-zone distribution, surges, sprint peaks, and time above FTP.
- **Execution vs plan:** planned duration/power/load versus actual values, with
  the reason for deviations when the athlete supplied one.
- **Physiological interpretation:** distinguish an easy aerobic ride with brief
  neuromuscular/leg-load spikes from a genuinely hard metabolic session.
- **Energy and recovery:** calories, estimated carbohydrate use, likely fuel mix
  (state clearly that intervals.icu's carbohydrate figure is an estimate),
  current CTL/ATL/TSB and preceding load, then give a concrete next-session
  recommendation.

If the athlete corrects a zone interpretation, recalculate from the raw seconds
and acknowledge the correction plainly. Never silently preserve a conclusion
that conflicts with the displayed zone totals.

### Pedal balance / left-right analysis

When `get_activity_streams` includes `left_right_balance`, say so explicitly and
analyze it when relevant. Use the stream's actual sample values and report the
mean/median plus variability if computable; a few first/last samples are not a
whole-ride average. Separate steady riding from climbs, sprints, and fatigue if
raw samples permit. Do not claim that a balanced-looking tail proves whole-ride
symmetry. If the compact tool response does not include enough samples to compute
an overall statistic, state that limitation and offer only the supported
observation (for example, "available samples are around 49–54% left").

See `references/post-ride-review-quality.md` for the required deep-review structure
and the left/right-balance evidence rules.

**Required response quality:** A post-ride analysis must be substantive, not a generic congratulations. Structure it around: (1) planned versus actual execution, (2) intensity and pacing, (3) aerobic response, (4) load in context of the preceding and upcoming sessions, (5) what the athlete did well, (6) limitations or deviations, and (7) a concrete next-step recommendation. Match the athlete's language and give enough technical detail to be actionable. If the athlete explicitly asks for a fuller review, expand the analysis rather than repeating a short summary.

**Data integrity rule:** Never claim that Garmin/intervals.icu data is unavailable until checking the appropriate detail and stream tools. `get_activity_detail` may expose summary metrics, while `get_activity_streams` confirms available Garmin channels such as heart rate, cadence, power, temperature, and respiration. If the user supplies a metric that conflicts with a tool summary, acknowledge the discrepancy and verify the source rather than implying the data does not exist.

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

### Zone derivation

Derive HR zones from **LTHR** (lactate threshold heart rate), not max HR. LTHR is
more stable and physiologically meaningful. Use `get_sport_settings` → `lthr` as
the anchor. If LTHR is missing/uncertain, use the 30-min all-out test: average HR
of the final 20 minutes of a maximal 30-min effort.

| Zone | %LTHR | Pulsexempel (LTHR 150) | RPE | Känsla |
|------|-------|------------------------|-----|--------|
| Z1 Recovery | <80% | <120 | 1–2 | "Kan knappt känna att jag cyklar" |
| Z2 Endurance | 80–89% | 121–133 | 3–4 | "Kan prata i hela meningar" |
| Z3 Tempo | 89–94% | 134–140 | 5–6 | "Korta meningar" — gråzon, använd sparsamt |
| Z4 Threshold | 94–100% | 141–150 | 7–8 | "Enstaka ord" |
| Z5 VO2max | 100–108% | 151–162 | 9 | "Kan inte prata" |

### Conversational test for Z2

The simplest field check: if the athlete can speak in full sentences without
gasping, they are in Z2. If they can only manage short phrases, they've drifted
into Z3. This works regardless of HR monitor accuracy.

### HR lag pitfall

HR takes 2–3 minutes to stabilize after a change in intensity. During intervals
shorter than 5 minutes, HR will lag behind the actual effort. Prescribe these by
**RPE, not HR**. Example: "3×10 min @ RPE 7–8 (tröskel)" rather than "3×10 min @
141–149 bpm". The athlete should go by feel for the first 2 minutes, then check
that HR has settled in the target zone.

### Rewriting power workouts to HR

When the coach-brain knowledge returns power-based prescriptions (e.g. "2×15 min @
88–94% FTP"), translate:
1. Map the intensity to the correct HR zone using the table above
2. Add an RPE anchor: "Z4, RPE 7–8 — jobbigt men kontrollerat"
3. Include the conversational test for Z2 prescriptions
4. Always present BOTH the HR range AND the feel description

Example translation:
- Power: "2×15 min @ 182–195W (88–94% FTP)"
- HR: "2×15 min @ Z4 (141–149 bpm), RPE 7–8. Ska kännas jobbigt men du ska kunna
  hålla samma ansträngning genom hela intervallen."

### Pace source priority for running

See Norwegian Singles section above. For cycling with no power meter: LTHR from
`get_sport_settings` is the primary anchor. Max HR is secondary — verify with the
athlete (see Pitfalls).

See `references/hr-based-training.md` for full zone calculation methodology and edge cases.

## Running plateau and breathlessness

When easy running is comfortable but modestly faster running causes rapid breathlessness or a sharp endurance drop, use the follow-up workflow in `references/running-plateau-and-breathlessness.md`. Respect previously reported normal iron/blood tests and a strong exercise test; do not repeatedly return to those as the main explanation. Preserve one controlled quality stimulus alongside easy aerobic running, and verify the athlete's stated goal from conversation/context before giving a goal-specific plan.

### Long-term performance decline: answer the causal question directly

When an athlete reports a multi-year decline in easy-run pace (for example, 5:00/km becoming 6:00/km) despite unchanged training volume, do not respond with a generic list or imply that normal aging explains it. First acknowledge the magnitude and state plainly that it is not explained by age alone. Then rank hypotheses by fit: (1) running-specific economy, threshold, leg durability, injury/biomechanical change, or altered body composition; (2) chronic under-recovery or low energy availability/RED-S; (3) post-viral/autonomic or other medical causes not captured by routine blood tests; and (4) measurement/context changes (surface, terrain, heat, watch, pacing). A normal cycling work ECG does not establish normal running economy or running threshold, especially when the test stopped for leg fatigue below predicted maximal heart rate. Treat it as reassuring for major cardiac ischemia/arrhythmia, not as an explanation for the running decline.

Use intervals.icu only to support claims it can actually support: verify identity, fetch the athlete profile instead of asking for age/weight when those fields exist, separate Run from Ride, and inspect the date range before attributing a multi-year trend. A recent CTL/ATL/TSB series—especially one dominated by cycling or beginning only recently—cannot explain a decline that started years ago. Present current fatigue as a possible amplifier, not the root cause, unless a longer sport-specific trend supports it. For a large unexplained decline, recommend a targeted sports-medicine workup (running CPET/lactate threshold, running economy, biomechanics/strength, and energy availability review) without diagnosing.

### Goal-anchored half-marathon planning

For a runner targeting a spring 2027 half-marathon under 1:40 (4:44/km), keep the goal as the persistent anchor while adapting the current week. **Continuity requirement:** if the goal was already confirmed and saved, do not ask the athlete to repeat it. Retrieve/use saved memory and the verified profile, then acknowledge the goal briefly before planning. If the athlete says the same discussion has happened repeatedly or expresses frustration, stop the loop: state the known goal and constraints, give the concrete next-step plan, and do not ask another generic intake question unless a genuinely blocking detail is missing.

**Plan quality requirement:** a practical plan must explain the causal hypothesis it is testing (for example, reducing accumulated fatigue while preserving one controlled quality stimulus), define a short initial block with exact weekly structure, and specify what observation will trigger progression or reduction. Do not present a generic multi-phase outline as if it were a sufficient answer when the athlete asks "what do you think?" Use current sport-specific data only as evidence: recent TSB/ATL can support current fatigue, but cannot explain a decline that began years earlier. Avoid overclaiming that a recent load spike is the root cause.

For a runner targeting a spring 2027 half-marathon under 1:40 (4:44/km), keep the goal as the persistent anchor while adapting the current week. Do not prescribe goal pace as everyday training pace when current data is substantially slower; use phases: aerobic consistency and easy-volume tolerance first, threshold/volume development next, race-specific pace later, then taper. A suitable early template is 3 runs/week (two easy, one controlled quality) plus 1–2 short strength sessions, with the long run on the weekend. Progress toward four runs and 40–50 km/week only when recovery and breathing tolerate it; build the long run gradually toward 18–22 km. Schedule a deload every 3rd–4th week, and use actual-vs-planned load, CTL/ATL/TSB, HRV, sleep, resting HR, RPE, and breathing—not pace alone—to decide whether to hold, progress, or reduce.

### Time and cross-training constraints

Treat a weekday availability of about 60 minutes as a hard practical constraint. Keep weekday runs, quality sessions, and combined sessions within that limit; place longer long runs on weekends. Strength is support work for the half-marathon: early phases may use two controlled sets at RPE 6–7 to limit DOMS and interference with running, progressing to three sets only after stable tolerance. A 15–25 minute easy crosstrainer block at RPE 3–4 may be added before or after short strength as low-intensity aerobic volume, but it is not a replacement for the key running stimulus and should not compromise the next run.

### Trust and continuity

If the athlete asks whether the plan has a purpose, explicitly connect every component to the race goal (easy running = aerobic base, quality = threshold/fart, long run = durability, strength = economy/resilience, recovery = adaptation). Never promise perfect recall of every conversation: state what is saved, use fresh intervals.icu data, and say when a detail is missing instead of guessing. If a goal is confirmed, save the goal and key constraints, but still re-check current data before each progression.
edge cases.

## Verification

After giving coaching advice, verify:
1. Advice aligns with coach-brain principles for the athlete's current state
2. Intensity recommendations are appropriate for the athlete's TSB
3. Recovery is prescribed when fatigue signals are elevated
4. Nutrition advice matches duration and intensity
5. The athlete's subjective report always overrides model predictions