# Headless brief weather-sourcing rule

## Finding (2026-09-11 run)

Millberg's 11 Sep morning brief prescribed "Z2 60–90 min i Ljungskile (kustvägen/Bokenäset)"
for today, but the brief never checked current weather for either of Millberg's two
locations. Open-Meteo at 12:00 UTC 2026-09-11:
- Ljungskile (58.21 N, 11.93 E): 14.7 °C, wind 16.2 km/h, no precipitation
- Stockholm (59.33 N, 18.06 E): 16.6 °C, wind 11.5 km/h

Conditions were fine, so no athlete harm this time — but the gap is structural:
a headless brief that prescribes an OUTDOOR session without reading a weather flag
can send an athlete out into a storm, icing risk, or heat, with no interactive
session to course-correct. The interactive procedure (SKILL.md step 5) confirms
location before weather; the headless path did not include any weather step.

Existing knowledge coverage:
- coach-brain/heat.yaml and cold-weather.yaml cover heat acclimatization and
  autumn/winter training adjustments, but have NO wind/rain threshold for"should
  this ride be indoors today" decisions in the mild-autumn band (0–15 °C windy/wet).

## Rules (verbatim, added to coaching SKILL.md Pitfalls section)

- **Headless briefs that prescribe an outdoor session must include a weather flag.**
  In a cron brief, fetch current conditions for the athlete's CONFIRMED location
  (for multi-location athletes use the session's location context, e.g. last
  stated location or the location in the plan) and add one line: "+12 °C, vind
  16 km/h, torrt". If conditions are unsafe for the prescribed session type
  (strong wind/gusts, icing, high heat), swap in the indoor/alternative and say
  why — weather is a valid reason to restructure a headless brief without
  asking first.
- **Velocity-check every route mention in a headless brief.** A named segment or
  climb (e.g. "kustvägen/Bokenäset") implies cover and wind exposure assumptions
  the model did not verify. If wind is >40 km/h or gusts exceed 60 km/h, drop
  exposed-coast/route names from the brief.

## Location-confirmation onboarding addition (coaching SKILL.md Environment/profile)

- During first-time onboarding, confirm the athlete's primary training location(s)
  and any second home. Persist the location list in athlete memory with an
  explicit CONFIRMED marker, e.g. `Primary: Ljungskile. Second: Stockholm
  (work weeks). Verified by millberg 2026-09-01.` Headless briefs must never
  invent a location: when no confirmed location and no session context exists,
  write today's brief sport-generic and add "(om du är i X idag: ...)".
