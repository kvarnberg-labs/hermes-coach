# HR-based training (no power meter) and HR vs power

Load when an athlete has no power meter (activities show
`normalized_power_w: null`; ask "Har du wattmätare?" before a power-based plan),
when translating power workouts to HR, or when HR and power disagree on a ride.

## Anchor zones to LTHR, not max HR

LTHR: `get_sport_settings(sport=<Ride|Run>) → lthr` for the sport in question.
If missing, a 30-min all-out test: average HR of the final 20 min.

| Zone | % LTHR | Example (LTHR 150) | RPE | Talk test |
|---|---|---|---|---|
| Z1 Recovery | < 80 % | < 120 | 1–2 | Barely feels like riding |
| Z2 Endurance | 80–89 % | 121–133 | 3–4 | Full sentences |
| Z3 Tempo | 89–94 % | 134–140 | 5–6 | Short sentences — grey zone, sparingly |
| Z4 Threshold | 94–100 % | 141–150 | 7–8 | Single words |
| Z5 VO2max | 100–108 % | 151–162 | 9 | Cannot talk |

Coach-brain HR zone background: `get_coaching_knowledge("power zones")` →
`heart_rate_zones`.

## Max HR

`max_hr` in sport settings is typed in by the athlete and often wrong. Ask the
athlete for their real max HR before building max-HR-based zones; if they do
not know, use LTHR zones only. Age formulas (220 − age) are not acceptable.

## HR lag

HR needs 2–3 min to settle. Prescribe intervals shorter than ~5 min by RPE, not
HR; for longer reps ride by feel for the first 2 min, then check HR.

## Translating power prescriptions

1. Map the intensity to the HR zone above. 2. Add the RPE anchor. 3. Add the
talk test for Z2. 4. Give both the HR range and the feel.
Example: "2×15 min @ 88–94 % FTP" → "2×15 min Z4 (141–149), RPE 7–8 — jobbigt
men kontrollerat, samma ansträngning hela intervallen."

## Cyclists with power: power leads Z2

Prescribe cycling Z2 by power (56–75 % FTP). HR at that power is individual; an
aerobically efficient rider may sit well below generic HR Z2 — that is fine.
Give HR as an FYI ("din puls kommer sannolikt ligga lägre, och det är rätt"). The
talk test is the final arbiter.

If the HR monitor fails mid-session: full sentences = Z2, single words = Z4.
