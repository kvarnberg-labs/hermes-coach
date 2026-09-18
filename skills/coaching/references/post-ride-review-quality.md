# Post-ride review: Garmin data integrity and useful depth

Use this when an athlete challenges a short or generic post-ride analysis.

## Minimum evidence to collect

1. `get_recent_activities` to identify the correct activity and basic load.
2. `get_activity_intervals` for the athlete's own detected intervals — the interval-by-interval source. `get_activity_detail` for duration, power/HR summaries, decoupling, VI, zone times, RPE, and `paired_event_id`.
3. `get_activity_streams` when the athlete asks about or supplies stream-level values such as cadence or pacing stability. The tool returns compact summaries plus computed peaks; it does not expose the full arrays.
4. `get_wellness` and recent activities to place the session in recovery context.
5. `get_sport_settings` before interpreting FTP-based intensity; compare configured FTP with eFTP.

## Response structure

- **Plan vs actual:** duration, target intensity, completed/missed components.
- **Intensity/pacing:** average and normalized power, IF, VI, zone distribution, and whether deviations are meaningful or terrain-related.
- **Aerobic response:** average/max HR, HR zone distribution, decoupling, RPE; explain what these do and do not prove.
- **Context:** previous hard sessions, current load, sleep/HRV/TSB, and the next planned session.
- **Judgment:** what was successful, what was imperfect, and whether the deviation matters.
- **Action:** exact guardrails for the next session, including a bail-out clause.

## Athlete-specific depth and left/right pedal balance

For this athlete, a normal post-ride review is a deep comparison of the power profile and pulse—not a generic congratulation. Always distinguish cardiovascular load from external/mechanical load. A ride can be almost entirely HR Z1 while still containing short high-power climbs, group-chasing surges, sprint peaks, and an elevated NP/TSS. Classify it as an easy aerobic ride with neuromuscular or local leg-load spikes when the data support that interpretation; do not call it a hard metabolic session from power-zone time alone.

When `get_activity_streams` exposes `left_right_balance`, explicitly report that pedal-balance data exists. But the compact response usually contains only sample count and first/last values, not the full array. Do not turn endpoint samples into a whole-ride mean or fatigue trend. Say what is supported (for example, available samples around 49–54% left) and state that a true average/median and segment-by-segment analysis require full-stream aggregation or a platform summary. If full samples are available later, compute mean, median, variability, and separate steady riding, climbs, sprints, and late-ride fatigue.

## Zone reconciliation and corrections

Convert zone seconds to percentages and verify the denominator before writing. If the athlete identifies a discrepancy, recalculate immediately, acknowledge the mistake plainly, and replace the affected conclusion. Avoid exact fat-versus-carbohydrate claims without metabolic testing; calories and intervals.icu carbohydrate use are estimates, not direct oxidation measurements.

Avoid generic praise and avoid overstating certainty. If cadence or HR is available, use it. If only a summary is available, state precisely what remains unknown; never say Garmin data is absent without checking streams. If the athlete corrects a metric, acknowledge the error directly and revise the conclusion.

---

## Moved from SKILL.md (2026-09-14)

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

**Required response quality:** A post-ride analysis must be substantive, not a generic congratulations. Structure it around: (1) planned versus actual execution, (2) intensity and pacing, (3) aerobic response, (4) load in context of the preceding and upcoming sessions, (5) what the athlete did well, (6) limitations or deviations, and (7) a concrete next-step recommendation. Match the athlete's language and give enough technical detail to be actionable. If the athlete explicitly asks for a fuller review, expand the analysis rather than repeating a short summary.

**Data integrity rule:** Never claim that Garmin/intervals.icu data is unavailable until checking the appropriate detail and stream tools. `get_activity_detail` may expose summary metrics, while `get_activity_streams` confirms available Garmin channels such as heart rate, cadence, power, temperature, and respiration. If the user supplies a metric that conflicts with a tool summary, acknowledge the discrepancy and verify the source rather than implying the data does not exist.

