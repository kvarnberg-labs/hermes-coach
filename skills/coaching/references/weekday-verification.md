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

---

## Moved from SKILL.md (2026-09-14)

- **Date/weekday accuracy — always cross-reference.** When presenting dates alongside weekday names, verify the mapping against a calendar or the athlete's timezone before writing. A mismatch between date and weekday erodes trust and forces the athlete to correct you. If unsure, use the date alone or ask. Always use the athlete's configured timezone (from get_athlete_profile) when resolving "today" or planning future sessions. When fixing weekday mismatches across a multi-week training plan, follow the systematic workflow — patch weeks individually, then fix any cron rules that reference weekday names.
- **Weekday labels must match the record's date, not the response day.** Derive weekday names ("onsdag", "i tisdags", "fredagen") from each activity/measurement's actual date — 2026-09-02 is a Wednesday — never from the day the brief or analysis is written. A Sep 5 brief cited a Wednesday Sep 2 threshold session as "tors 3/9" and Friday Sep 4 resting HR as "i tisdags" while every value was correct: correct values with mislabeled weekdays erode trust. Re-check every weekday label before sending.
- **Derive every weekday name mechanically — never by recall.** Weekday mislabels ("tisdagens 58 min/10 km" written for the Monday 7/9 run, Sep 9 morning brief) recur because models derive weekday words by recall even when every value is correct. For each date you name in a brief or plan, derive the weekday in the terminal (e.g. `python3 -c "import datetime as d; print({0:'måndag',1:'tisdag',2:'onsdag',3:'torsdag',4:'fredag',5:'lördag',6:'söndag'}[d.date(2026,9,7).weekday()])"`); headless cron prompts embed this rule. Verify Studio Echelon's live schedule via its public no-auth Zoezi API (`echelon.zoezi.se/api/public/workout/get/all?fromDate=…&toDate=…`, verified 2026-09-09) in headless sessions — the schema pages are JS apps that render nothing over plain HTTP. See `references/studio-echelon-classes.md` → 'Headless schedule check'.
