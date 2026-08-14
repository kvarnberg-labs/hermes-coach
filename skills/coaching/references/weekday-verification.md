# Weekday Verification in Training Plans

Systematic workflow for detecting and fixing weekday/date mismatches in training plans.

## Problem Pattern

Training plans often list sessions as "Tis 5/8", "Tor 7/8" etc. When the weekday
name doesn't match the calendar date, it erodes athlete trust and forces
corrections. The typical cause: the plan was generated with a mental model of
"Tuesday, Thursday, Sunday" without cross-referencing actual calendar dates.

## Detection

1. Verify ALL dates in the plan against the system clock:
   ```bash
   for d in 2026-08-05 2026-08-07 2026-08-10; do
     printf "%s → " "$d"
     date -d "$d" "+%a %d/%m"
   done
   ```
2. Compare each row's weekday label to the actual weekday.
3. Note the pattern — mismatches are often systematic (e.g., all shifted by +1 day).

## Fix Workflow

When mismatches found across multiple weeks:

### 1. Fix the plan file
Use `patch` to update weekday labels week by week. Keep the same rhythm
(e.g., Tue/Thu/Sun → Wed/Fri/Mon preserves 2-day + 3-day spacing).

### 2. Fix cron rules
If the plan's cron rules section mentions specific weekdays (e.g.,
"Söndagar = långpass"), update them to match the new pattern:
- "Söndagar = långpass" → "Måndagar = långpass"
- "Tisdag/torsdag tröskel" → "Onsdag/fredag tröskel"

### 3. Check intervals.icu events
`get_planned_events` — verify that event dates match the corrected plan.
Events use ISO dates (YYYY-MM-DD) which are typically correct; the issue
is in the human-readable labels in the plan file, not in the API data.
Only update events if the actual dates are wrong.

### 4. Consider the cron job
If a cron job uses the plan file, it will pick up the corrected weekdays
on next run. No cron job update needed unless the job's own prompt
hardcodes weekday names.

## Pitfall: Assuming "nearby" weekdays

"Tor 7/8" looks plausible — Thursday and the 7th feel close. Always
verify with `date -d`, never trust intuition about which weekday a
date falls on. This is especially error-prone across month boundaries
and in plans created months in advance.
