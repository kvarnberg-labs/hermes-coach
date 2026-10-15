# Post-session review — frozen checklist

Load whenever an athlete reports a finished session ("dagens pass klart",
"passet gick bra", "kolla dagens") or asks for a post-ride/post-run analysis.
Work through every item; do not skip items because the session looks simple.
Response structure: `get_coaching_knowledge("post workout feedback")`.

## A. Pull (parallel where possible)

1. Identity verified this session (`verify_athlete_identity`).
2. `get_recent_activities(days=2, sport=<Ride|Run>)` — today's and yesterday's
   sessions. If today's is missing but wellness already moved, re-query with
   `days=3` or no sport filter before saying it has not synced.
3. `get_planned_events(days_back=1, days_ahead=7)` — what was planned today
   and the coming week.
4. `get_wellness(days=7)` — CTL/ATL/TSB trend, HRV, resting HR, sleep.
5. `get_activity_detail(id)` — zone times, decoupling, VI, IF, laps,
   `compliance`, `paired_event_id`.
6. `get_sport_settings(sport=<Ride|Run>)` — configured FTP, LTHR, max HR,
   zones. Mandatory before any IF or zone statement.
7. `get_activity_intervals(id)` for any structured session (work-interval
   power/pace/HR); `get_activity_streams(id)` when the athlete asks about
   stream-level detail or for FTP validation (compact summaries + peaks only).
8. Duplicate uploads: flag once, then use the first unique activity ID.

## B. Cross-check before writing

9. Configured FTP vs eFTP (`get_wellness → sport_info[].eftp`). Gap > 10 W →
   report it first; give IF against both (`IF_eFTP = NP / eFTP`) and say which
   FTP the zones use. If eFTP falls while CTL rises with no recent maximal
   effort, eFTP is probably low — ask which FTP feels right; offer a test
   (`references/ftp-testing.md`).
10. Never estimate FTP from a non-maximal session; decoupling is not an FTP
    estimator.
11. Convert zone seconds to percentages and check the denominator.
12. Reconcile power with HR: short climbs, surges and sprints can raise NP/TSS
    while HR stays in Z1. Classify as easy aerobic with brief neuromuscular
    load when the data say so — not as a hard metabolic session from power
    time alone.
13. Interval sessions: judge work intervals, not whole-session averages
    (`references/activity-detail-analysis.md`).
14. Before saying data is absent (cadence, HR, pedal balance), check detail and
    streams. Compact streams give only sample values: do not turn first/last
    samples into a whole-ride mean.

## C. Planned → actual → variance (always)

15. Goal of the session (from the planned event or the agreed plan).
16. Planned vs actual: duration, intensity (IF / pace / HR), load, interval
    structure — as a small table with the delta.
17. Variance verdict: on target / under / over, and whether it matters. Fix
    execution, not the plan, when easy days drift into the grey zone.
18. Where it sits in the week: previous hard session, current TSB trend, next
    planned session (weekday + date from the event's own date).

## D. Write

19. Sleep: comment if available; if null say "sömndata saknas", never "poor
    sleep".
20. HR zones always included for runs and HR-only sessions (zone, time, %).
21. Positives (1–3, data-backed), limitations, then one concrete next step with
    a bail-out clause.
22. Energy figures (calories, carbs) are estimates; no exact fat/carb claims.
23. If the athlete corrects a number, recalculate from source, say so plainly,
    and replace the conclusion.
24. Depth matches the request: a short check-in gets a compact review; "my
    usual analysis" gets the full depth. Use exact counts and the session
    language.

## Zwift / named-workout recommendations

You cannot browse the Zwift library. Never present a named Zwift workout as
verified from memory: give the interval structure (durations, %FTP, total time)
to build or pick, and ask the athlete to confirm a named workout's structure
from the app. State which FTP the percentages use. Same-day hard workouts still
need the feel check, not TSB alone.
