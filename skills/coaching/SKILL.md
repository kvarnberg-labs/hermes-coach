---
name: coaching
description: Evidence-based endurance coaching skill for cycling and triathlon.
version: 1.5.0
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

## When to Use

- Athlete asks about training structure, periodization, or intensity zones
- Athlete needs recovery advice or is showing signs of overtraining
- Athlete asks about injury return protocols or nutrition guidance
- Athlete is preparing for a race and needs taper or race-week advice
- Any coaching question where evidence-based specificity matters

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
5. Pull athlete data using the **Hermes coaching tools only**:
   - `get_wellness` for CTL/ATL/TSB/HRV/sleep
   - `get_recent_activities` for recent training load by sport
   - `get_sport_settings` for FTP, zones, LTHR (call separately for each sport: Ride, Run)
   - `get_power_curve` for peak power data
   - `get_athlete_profile` for name, weight, timezone
   - `get_activity_streams(id)` for raw per-second power/HR/cadence (FTP validation, interval detection)
   - `get_fitness_chart(days)` for long-range CTL/eFTP trends (season analysis)
   - `create_planned_event` / `delete_planned_event` for calendar management — creating, updating, and removing planned workouts that sync to Garmin
   - **Never use curl directly for training data.** If a tool fails, fix the tool or implement a new one — see Tool Troubleshooting.
6. **Separate sports before analyzing.** Never present a blended CTL/load summary that mixes cycling and running. Analyze each sport independently:
   - Split activities by `type` field (Ride vs Run)
   - Present separate ride log and run log
   - Note which sport is driving CTL changes
   - Get sport-specific settings for each sport you analyze
7. Synthesize advice using coach-brain principles plus athlete data.
8. **Before prescribing intensity: ask how the athlete feels today.** TSB is a model estimate, not ground truth. Before recommending threshold/VO2max work, ask the athlete about fatigue, soreness, motivation, and sleep quality. If they report tiredness or heavy legs despite neutral/positive TSB, default to easy/recovery. The athlete's subjective report always overrides the model. This is especially important at the end of a recovery week — TSB may look ready but the nervous system may still be rebuilding.
9. Include caveats when athlete data contradicts standard guidance.

## Quick Reference

| Topic | Tool Call | Follow-up |
|-------|-----------|-----------|
| Training structure | get_coaching_knowledge("polarized training") | Check get_recent_activities |
| Recovery advice | get_coaching_knowledge("recovery heuristics") | Check get_wellness for TSB, HRV, sleep |
| Workout design | get_coaching_knowledge("threshold intervals") | Check get_sport_settings for FTP |
| Injury return | get_coaching_knowledge("injury return knee") | Check get_recent_activities |
| Nutrition | get_coaching_knowledge("nutrition during training") | Check activity duration |
| Race prep | get_coaching_knowledge("tapering") | Check get_planned_events |
| Workout analysis | get_activity_detail(id) | Analyze laps, pace zones, HR zones |
| Raw power/HR data | get_activity_streams(id) | Compute max 20-min power, validate FTP |
| Long-range fitness | get_fitness_chart(days=365) | CTL/eFTP trends over months |
| Activity detail parsing (running) | — | See references/activity-detail-analysis.md |
| Activity detail parsing (cycling) | — | See references/cycling-activity-analysis.md |
| Identity verification | `verify_athlete_identity` | Check `get_athlete_profile` if verified |
| intervals.icu API field names | — | See `references/intervals-icu-api-fields.md` |
| Missing activities diagnosis | — | See `references/activity-sync-troubleshooting.md` (Garmin/Zwift) and `references/apple-watch-sync.md` (Apple Watch) |
| Studio Echelon class recommendations | — | See `references/studio-echelon-classes.md` |
| intervals.icu API coverage gaps | — | See `references/intervals-icu-api-coverage.md` |
| FTP/eFTP gap resolution | `get_sport_settings` + `get_wellness` | See `references/ftp-testing.md` |
| Sport transition DOMS | get_coaching_knowledge(\"recovery heuristics\") | Check recent activities for sport mix change |
| Calendar management | `create_planned_event` / `delete_planned_event` | See `references/intervals-icu-api-coverage.md` and `references/event-creation-pitfalls.md` |
| Event creation pattern | `develop_tool` | See Tool Troubleshooting → develop_tool alternative |
| Zwift workout (.zwo) | — | See `templates/zwift-workout.zwo` |
| Cron / headless sessions | Direct terminal invocation | See `references/cron-coaching.md` — ⚠️ always verify `deliver` target for multi-user jobs |
| Long-range data queries (YTD totals) | Terminal Python + intervals.icu REST API | See `references/long-range-queries.md` |
| Half marathon planning | `get_coaching_knowledge("half marathon")` + athlete data | See `references/half-marathon-periodization.md` |
| HR-based training (no power meter) | Check `get_recent_activities` for null `normalized_power_w` | See `references/hr-based-training.md` |
| Masters athlete adaptations (60+) | Check `get_athlete_profile` for `date_of_birth` | See `references/masters-training.md` |
| Gravel route building | maps skill + OSRM cycling + Overpass API | See `references/gravel-route-building.md` |
| Multi-week training plan + cron delivery | Full data pull → periodized plan → cron job | See `references/training-plan-creation.md` |

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

**Weekly template:**
```
Mon: Easy run 35-45 min
Tue: Threshold session #1 (e.g. 4×8 min)
Wed: Easy run 40 min or rest
Thu: Easy run 35-45 min (or rest)
Fri: Rest or easy cross-train
Sat: Threshold session #2 (e.g. 5×6 min)
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

## Pitfalls

- **`get_activity_streams` returns computed peaks, not raw arrays.** The tool computes peak power at 5s, 1min, 5min, 20min, 60min and an eFTP estimate (95% of 20-min) server-side from the raw 10K+ data-point arrays. It returns compact sample points (first 5, last 5 per stream) for validation, not the full arrays. Do NOT expect to iterate through `streams[].data` — the `data` key is not in the response. Access `peak_power` for computed metrics and `streams_summary` for stream metadata. The response is ~2KB, not 838KB.
- **Never use curl directly for training data retrieval.** Always use the Hermes coaching tools. If a tool is broken, fix the tool or implement a new one with `develop_tool` — do not work around it with raw HTTP calls.
- Do not prescribe specific workouts without checking TSB and recent load. TSB < -20 is a risk factor.
- Do not override coach-brain guidelines with generic model knowledge.
- **Never assume cycling as default sport.** When an athlete asks an open-ended question like "what should I train today," confirm which sport before pulling data. Cycling, running, and strength training require fundamentally different analyses. A threshold session prescribed in watts is useless to a runner. Ask explicitly: "Are you cycling, running, or both?" before fetching sport-specific settings. This is the #2 most common coaching error after identity mismatches.
- **Verify the race surface and course profile before designing a program.** Athletes often describe their event generically ("90k motionslopp," "gran fondo") without specifying surface or elevation. BEFORE building a training plan: (a) ask for the race name and look up the official website, (b) verify surface (asphalt, gravel, dirt, mixed?), (c) check elevation profile (flat railway embankment vs hilly gravel). Klarälvsloppet, for example, is on an old asphalted railway embankment — not gravel as the word "motionslopp" might suggest. Surface determines: bike/tire choice, expected speed → finish time → nutrition plan, and whether the athlete should train on similar terrain. A gravel-focused program with dirt-road routes is wrong for an asphalt time-trial-style event, and vice versa. The race website's description ("bilfritt, platt och snabbt" or "nio mil asfalterad naturupplevelse") is authoritative — trust it over the athlete's casual description.
- **Always separate sports** — cycling and running are independent analyses. Never present a blended summary that mixes ride and run TSS. Present separate logs and note which sport drives CTL changes.
- Always check weather before recommending outdoor training.
- **Verify current time before giving departure-window advice.** When an athlete says "I have to do a ride today" without specifying when, do not assume they're still planning — they may already be on the bike or about to step out. Check the current time (system clock or ask the athlete) before recommending specific departure windows, best times of day, or weather windows that assume the ride hasn't started. If it's late or they're leaving now, skip time-based planning and focus on real-time conditions and pacing guidance.
- Injury red flags require medical referral — do not suggest continued training.
- **Sport transition DOMS is expected.** When an athlete returns to running after a cycling-dominant period (or vice versa), delayed onset muscle soreness is normal for the first 1–2 weeks. Running has eccentric loading that cycling lacks. Management: reduce load 30–50% for 3–5 days, easy movement helps (do not skip sessions entirely), ensure 1.6–2.0 g/kg protein daily. Escalate if DOMS persists beyond 5–7 days or is sharp/pinpoint rather than diffuse.\n- **TSB is a mathematical model, not a diagnosis.** When TSB is deeply negative but RPE is low, resting HR is at baseline, HRV is stable or improving, and the athlete reports feeling strong, TRUST THE ATHLETE. Subjective feel plus physiological markers outweigh TSB. Before concluding overtraining: (1) verify resting HR trend (not elevated >5 bpm above baseline), (2) check HRV trend (not suppressed >10% below 7-day average), (3) inspect sleep quality and duration, (4) check if ATL is inflated by grey-zone riding on "endurance" days (see Grey zone detection pitfall below). If markers (1)-(3) are normal and (4) is present, TSB is overstating fatigue — fix the execution, not the training load. Do not label an athlete "trött" based on TSB when they say they are fine.
- **Grey zone warning should be proportionate.** Long rides at 79-85% FTP instead of 56-75% (Z3 instead of Z2) is an optimization opportunity, not a crisis. If the athlete's RPE is 2, frame it as a suggestion, not a correction.
- **Respect the athlete's requested level of detail.** When an athlete explicitly says "just the number" / "no details needed" / "kort svar" / "räcker med en siffra", deliver exactly that — the answer, nothing more. Do not append a table, breakdown, or analysis they just told you they don't want. You can offer follow-up ("Vill du ha detaljer?") but only after delivering the requested minimal answer. Over-formatting a simple answer after being told to keep it short is frustrating and erodes trust.
- **Language consistency — match the session's language, never switch unprompted.** If the athlete starts the session in English, stay in English. If they start in Swedish, stay in Swedish. Do NOT let Swedish from cronjob prompts, other athletes' conversations, or coach-brain files bleed into an English session. Multi-language context is common (Swedish athletes, English documentation and users), but the session language is set by the athlete's first message — follow it. A mid-session language switch without the athlete initiating it erodes trust and looks buggy.
- **Grey zone detection — compare planned vs actual IF systematically.** When an athlete's TSB is deeply negative without corresponding physiological stress signals, suspect grey-zone inflation. Method: for every ride labeled endurance/Z2, compare actual NP/IF against the planned Z2 range (56-75% FTP). A ride at IF 0.80-0.87 instead of 0.56-0.75 generates ~40-70% more TSS than planned. Cumulative effect across a training block can drive ATL 10-20 points higher than intended — producing alarming TSB values that do NOT reflect genuine overtraining. When detected: (a) present a planned-vs-actual comparison table with IF delta, (b) note that TSB is overstated, (c) adjust future Z2 prescriptions to emphasize strict watt caps (e.g. "148-185W" not just "Z2"), (d) do NOT add extra rest days to compensate — fix the execution, not the plan.
- **Date/weekday accuracy — always cross-reference.** When presenting dates alongside weekday names, verify the mapping against a calendar or the athlete's timezone before writing. A mismatch between date and weekday erodes trust and forces the athlete to correct you. If unsure, use the date alone or ask. Always use the athlete's configured timezone (from get_athlete_profile) when resolving "today" or planning future sessions.
- **FTP estimation — don't guess from non-maximal rides.** NP over 50+ minutes is only a reasonable FTP proxy when the effort was **maximal or near-maximal** (race, FTP test, hill climb PR, Zwift race). Do NOT estimate FTP from a routine endurance ride, a windy variable-effort ride, or any session where the athlete was not going all-out. NP on a variable 3h ride with headwind and climbs says nothing about what the athlete could hold for 20 minutes at max. Similarly, **decoupling is NOT an FTP estimator** — it's an individual physiological marker (some athletes decouple 5% at threshold, others 20%). Using it to back-calculate FTP is circular and invalid. Only suggest FTP adjustment if the athlete reports failing prescribed intervals at a given FTP, or if they complete a maximal 20-min effort. When in doubt, defer to the eFTP from wellness data rather than guessing.
- **Verify max HR with the athlete — do not trust intervals.icu's configured value blindly.** `get_sport_settings` returns a `max_hr` field from the athlete's intervals.icu settings. This value is manually entered by the athlete and is often outdated, guessed, or inherited from a default. **Always ask the athlete what their actual max HR is** before building HR-based zones. A 3 bpm difference (165 vs 162) shifts Z2 boundaries and can put the athlete in the wrong training zone. If the athlete doesn't know their max HR, use LTHR-based zones (anchored to `lthr` from `get_sport_settings`) which are more reliable than max-HR-derived zones. See `references/hr-based-training.md` for zone calculation methodology.\n- **Masters athletes (60+) need fundamentally different program design.** When `get_athlete_profile` shows `date_of_birth` indicating age ≥60 (or the athlete tells you their age), apply masters-specific adjustments BEFORE building any training plan. Key differences from standard programming: (1) recovery weeks every 2nd–3rd week instead of 3rd–4th, (2) conservative ramp rate +3–5 CTL/week instead of +3–8, (3) max 1 intensity session per week — never stack two quality days, (4) strength training is year-round maintenance, not seasonal, (5) longer warm-ups (15+ min before any intensity), (6) total volume ceiling ~5.5h/week peak. Do NOT apply a generic polarized/pyramidal template designed for a 30-year-old to a 66-year-old — it will cause overtraining. See `references/masters-training.md` for the full evidence base and program templates.
- **Configured FTP vs eFTP gap — flag it, but don't treat eFTP as gospel.** On every post-ride analysis, cross-reference `get_sport_settings` configured FTP with eFTP from `get_wellness` → `sport_info`. A gap >10W means zone times, IF, and sweet-spot ranges are all calculated against potentially the wrong baseline. Flag the gap first, then present both interpretations. An IF of 0.76 at 284W FTP is very different from an IF of 0.92 at 234W eFTP.\n\n  **eFTP is a model estimate, not a measurement.** It derives from the power-duration curve across ALL rides and cannot distinguish maximal efforts from training rides. **Warning signs that eFTP is UNDERESTIMATING:** (1) eFTP is trending DOWN while CTL is trending UP — the athlete is getting fitter, not weaker; (2) no recent maximal efforts (FTP test, race, hill-climb PR, Zwift race) in the past 4–6 weeks; (3) the athlete reports feeling strong at power levels that eFTP says should be VO2max. In these cases: flag the discrepancy, present both interpretations, **explicitly ask the athlete which FTP feels right**, and if they push back on eFTP — trust them. Propose a structured FTP test (20-min all-out or ramp test) to resolve the question definitively. Do NOT insist on eFTP when the athlete disagrees and the data context supports their position.
- **Lactate testing data > generic estimates.** When an athlete shares a lactrace or lactate test result (e.g., a screenshot showing paces at measured mmol/L), those paces are the ground truth. Do not give a generic pace recommendation like "5:00-5:05/km" if the athlete has actual lactate-tested threshold pace. Ask for their data first, or pause and read the image they share. Generic zone math is a fallback, not the default.
- **Session average pace is NOT interval pace.** When analyzing a threshold/interval run, the `pace_mps` and `distance_km / duration_min` from `get_recent_activities` give the session average including warm-up, recovery jogs, and cool-down — which can be 20-30 sec/km slower than the actual work intervals. Always pull `get_activity_detail(activity_id)` and use `interval_summary` (Garmin auto-detection, e.g. "6x 4m43s 4:44") and `pace_zone_times` for the real work-interval paces. Never prescribe today's interval pace based on yesterday's session average.
- **intervals.icu API field names use `icu_` prefix, not Strava-style names.** If `get_activity_detail` returns null for `hr_zones`, `hr_zone_times`, `power_zones`, or `power_zone_times`, the plugin is likely using wrong field names. The intervals.icu API returns `icu_hr_zones`, `icu_hr_zone_times`, `icu_power_zones`, `icu_zone_times` — NOT `heartrate_zones`, `heartrate_zone_times`, `power_zones`, `power_zone_times`. See `references/intervals-icu-api-fields.md` for the full field mapping and debugging technique.
- **Module-level caches break test isolation.** `_load_all()` in `coaching.py` uses a time-based cache (`_brain_cache`, `_BRAIN_CACHE_TTL`). When tests monkeypatch `_brain_dir()` to point at temp directories, the cache from the first test persists and all subsequent tests get stale data. The cache must be keyed by directory path (`_brain_cache_dir`) so directory changes invalidate it. Any future module-level cache in the plugins must follow the same pattern — include the identity of the input source in the cache key, not just a TTL.
- **Verify athlete identity every session — use `verify_athlete_identity` first.** Call `verify_athlete_identity` before pulling any training data. If it returns `verified: false`, stop — credentials are stale, wrong, or manually placed without onboarding. Do not proceed until the athlete re-runs `/start` (`coach_onboard`). After verification passes, call `get_athlete_profile` as secondary confirmation that the name and athlete_id match expectations. This has been the #1 recurring bug (wrong athlete's data silently returned). See `references/identity-verification.md`.
- **VirtualRide ≠ Zwift.** Not all `VirtualRide` activities on intervals.icu are from Zwift. Indoor trainer sessions recorded via Garmin Edge (with Wahoo or other smart trainers) also classify as VirtualRide. When an athlete reports Zwift import issues, ask what device recorded each VirtualRide before assuming Zwift import is working. Zwift-imported activities typically have names prefixed with `Zwift -`.
- **Credential path mismatch causes wrong-athlete data.** The plugin resolves credentials from `Path(HERMES_HOME) / "users" / discord_id`. With `HERMES_HOME=/opt/data`, it reads from `/opt/data/users/discord_dm/`. If wrong credentials are in that path, ALL tools silently return the wrong athlete's data. **Prevention:** `verify_athlete_identity` catches this — it returns `verified: false` when credentials lack a stored name (manually placed) or the API profile mismatches. The permanent fix (PR #15) adds identity verification. **Live fix:** copy correct credential files AND write `intervals_athlete_name` (Discord username), then call `verify_athlete_identity`. This reverts on pod restart. See `references/credential-path-mismatch.md` and `references/identity-verification.md`.
- **Multi-user credential isolation is now supported via Discord snowflakes.** Hermes core (model_tools.py `handle_function_call`) now accepts a `user_id` parameter and threads it through to `registry.dispatch()`. The Discord adapter passes `source.user_id` (the athlete's snowflake) into tool dispatch, so `_require_user_id(kw)` returns the real snowflake instead of falling back to `discord_dm`. Each athlete gets their own credential directory at `/opt/data/users/<snowflake>/`. **Before this fix (pre-PR #18 + Hermes core update):** all users shared the `discord_dm` slot and silently overwrote each other's credentials. **After:** onboarding via `/start` writes to the per-user directory automatically. The `discord_dm` shared fallback was **removed** (PR #32, 2026-07-20) — sessions without a valid user_id now raise `ValueError` and return a clear JSON error instead of silently loading shared credentials. See `references/credential-isolation.md`.
- **\"User identity not available\" error — gateway lost the snowflake, not a credential problem.** Since PR #32, every coaching tool requires a valid Discord snowflake in `kw[\"user_id\"]`. When a tool returns `{\"error\": \"User identity not available — the Discord gateway did not provide a valid user ID.\"}`, the session has lost its identity context. This error replaces the old silent cross-athlete data leak where a dropped snowflake would load the shared `discord_dm` credentials. See `references/credential-isolation.md` for architecture background.\n\n  **Interactive session (gateway hiccup):** Tell the athlete to `/new` (restart the conversation). Do NOT attempt a credential recovery or live-pod fix — the credentials are fine, the gateway context is broken.\n\n  **Cron/headless session (expected — no gateway at all):** This error is unavoidable. Work around it by calling the plugin functions directly via `terminal()` with the athlete's snowflake hard-coded as a positional argument — the internal functions accept `discord_id` directly and bypass `_require_user_id(kw)`. See `references/cron-coaching.md` for the exact invocation pattern, function signatures, and how to discover the snowflake.
- **`Path.home()` fallback removed (PR #18).** The plugin's `_user_dir` no longer falls back to `Path.home() / ".hermes"` when `HERMES_HOME` is unset. Instead it raises `RuntimeError`. This eliminates the split-brain credential state where `/opt/data/users/discord_dm/` and `/opt/data/home/.hermes/users/discord_dm/` could hold different athletes' credentials. **Historical context:** `Path.home()` resolved to `/opt/data/home` (not `/opt/data`), creating a second credential directory on the same PVC that persisted across restarts. If `HERMES_HOME` was ever unset during a process (cron, plugin reload), the plugin silently switched paths.
- **Zone naming confusion — intervals.icu vs popular frameworks.** Athletes who follow popular "Zone 2" training content (Attia, San Millán, Norwegian method) use a 3-zone or 5-zone model where "Zone 2" means conversational endurance pace. intervals.icu uses the Coggan 7-zone power model where the same effort falls in Z1 or low Z2. When an athlete asks "Inga zon 2 pass?" or questions why their easy days aren't "Zone 2", explain the mapping: popular "Zone 2" = intervals.icu Z1-Z2 (conversational, <75% FTP for cycling or <80% LTHR for running). Do NOT assume the athlete is confused — they may be using the popular framework correctly and mapping it to intervals.icu terminology. Just clarify which system you're using and why both are "right."
- **CRITICAL: Cronjob `deliver` must target the ATHLETE'S channel, never your own.** When creating or updating a cron job for another athlete (e.g. "Morgonbrief Millberg"), you MUST set `deliver` to the athlete's explicit Discord channel ID — NEVER use `deliver: "origin"` (which resolves to YOUR chat, not the athlete's). `deliver: "origin"` means "deliver back to the chat where this cronjob was created" — if you are creating it from Joey's DM for Millberg, it will land in Joey's DM forever. **How to find the athlete's channel ID:** check gateway logs: `grep "user=<Name>" /opt/data/logs/gateway.log | tail -1` — the `chat=<id>` field is the channel ID. Format: `deliver: "discord:<channel_id>:<channel_id>"`. **In cron sessions, coaching tools fail** because there is no Discord gateway — use the terminal workaround from `references/cron-coaching.md` to pull real data. Do NOT ship cron prompts that instruct the agent to call `get_wellness` or `verify_athlete_identity` in cron — they will fail silently and the model will fabricate data. **Before creating any cronjob for another athlete, verify the delivery target by listing all user directories and their channels.**

## Post-Ride Analysis Checklist

When an athlete finishes a ride or run and asks for a post-ride brief, pull this
full set **in the listed order** before presenting ANY analysis:

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

See `references/hr-based-training.md` for full zone calculation methodology and
edge cases.

## Verification

After giving coaching advice, verify:
1. Advice aligns with coach-brain principles for the athlete's current state
2. Intensity recommendations are appropriate for the athlete's TSB
3. Recovery is prescribed when fatigue signals are elevated
4. Nutrition advice matches duration and intensity
5. The athlete's subjective report always overrides model predictions