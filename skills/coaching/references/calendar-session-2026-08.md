# Calendar session notes — 2026-08

## Durable lessons

- An explicit request such as “Gör veckans pass …” authorizes immediate calendar creation; do not ask for a second confirmation.
- Before creating, verify athlete identity and pull recent activities, wellness, sport settings, and profile so the week accounts for recent load, fatigue, FTP, age, and life commitments.
- After creation, query the planned-event range and report what actually exists. This catches partial writes and malformed steps.
- Rest days should be explicit calendar events, but validate the accepted event type before writing; `Rest` was rejected as an invalid intervals.icu type in this session. If a rest event cannot be created, state that plainly rather than claiming it was added.
- Validate generated step targets and load/intensity values. A malformed target string or unsupported percentage can be accepted while silently producing wrong Z1 labels/loads; compare the returned event description and planned values against the prescription.

## Calorie aggregation

For a date-range calorie question, use `get_athlete_stats` and sum only the requested sport categories. In this session, “cykling” meant both `Ride` and `VirtualRide`, excluding `WeightTraining`; report the date range and exact category sum, with a short breakdown only if useful.
