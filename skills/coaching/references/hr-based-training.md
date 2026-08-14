# HR-Based Training — Zone Calculation & Prescription

For athletes without a power meter. All zones anchored to LTHR (lactate threshold
heart rate), not max HR. LTHR is more stable and directly measurable.

## Zone derivation from LTHR

| Zone | %LTHR | RPE (1–10) | Conversational test |
|------|-------|------------|---------------------|
| Z1 Recovery | <80% | 1–2 | Full conversations, zero effort |
| Z2 Endurance | 80–89% | 3–4 | Full sentences, could do this all day |
| Z3 Tempo | 89–94% | 5–6 | Short sentences — grey zone, use sparingly |
| Z4 Threshold | 94–100% | 7–8 | Single words only |
| Z5 VO2max | 100–108% | 9 | Can't speak |

## Determining LTHR

Primary: `get_sport_settings(sport="Ride")` → `lthr` field.
Secondary: 30-min all-out field test — average HR of final 20 minutes.

## HR lag during intervals

HR responds with a 2–3 minute delay to intensity changes. For intervals shorter
than 5 minutes, prescribe by RPE, not HR. The athlete should go by feel for the
first 2 minutes, then verify HR has stabilized in the target zone.

## Translating power workouts to HR

When coach-brain returns power-based prescriptions:

1. Map intensity to HR zone using the table above
2. Add RPE anchor
3. For Z2: include the conversational test
4. Present both the HR range AND feel description

Example:
- Power input: "3×10 min @ 95–105% FTP"
- HR output: "3×10 min @ Z4 (tröskel), RPE 7–8. Ska kännas kontrollerat jobbigt —
  du ska kunna hålla samma ansträngning genom hela intervallen."

## Max HR verification

`get_sport_settings` returns `max_hr` from the athlete's intervals.icu settings.
This is manually entered and often wrong. Always ask the athlete. If they don't
know, use LTHR-based zones exclusively — they're more reliable than max-HR-derived
zones.

## Edge case: HR monitor failure mid-ride

Teach the athlete the conversational test as a backup. "Om pulsklockan lägger av:
kan du prata i hela meningar = Z2. Enstaka ord = Z4."
