# Calendar session notes — 2026-08

## Durable lessons

- An explicit request such as “Gör veckans pass …” authorizes immediate calendar creation; do not ask for a second confirmation.
- Before creating, verify athlete identity and pull recent activities, wellness, sport settings, and profile so the week accounts for recent load, fatigue, FTP, age, and life commitments.
- After creation, query the planned-event range and report what actually exists. This catches partial writes and malformed steps.
- Rest days stay empty in the calendar and are named in the plan table; `Rest` is not a valid intervals.icu type anyway.
- Validate generated step targets and load/intensity values. A malformed target string or unsupported percentage can be accepted while silently producing wrong Z1 labels/loads; compare the returned event description and planned values against the prescription.

## Calorie aggregation

For a date-range calorie question, use `get_athlete_stats` and sum only the requested sport categories. In this session, “cykling” meant both `Ride` and `VirtualRide`, excluding `WeightTraining`; report the date range and exact category sum, with a short breakdown only if useful.
