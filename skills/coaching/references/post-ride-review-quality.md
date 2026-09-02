# Post-ride review: Garmin data integrity and useful depth

Use this when an athlete challenges a short or generic post-ride analysis.

## Minimum evidence to collect

1. `get_recent_activities` to identify the correct activity and basic load.
2. `get_activity_detail` for duration, power/HR summaries, decoupling, VI, zone times, RPE, and intervals.
3. `get_activity_streams` when the athlete asks about or supplies stream-level values such as average HR, cadence, pacing stability, or Garmin channels. The tool returns compact summaries plus computed peaks; it does not expose the full arrays.
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
