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

---

## Moved from SKILL.md (2026-09-14)

- **Verify max HR with the athlete — do not trust intervals.icu's configured value blindly.** `get_sport_settings` returns a `max_hr` field from the athlete's intervals.icu settings. This value is manually entered by the athlete and is often outdated, guessed, or inherited from a default. **Always ask the athlete what their actual max HR is** before building HR-based zones. A 3 bpm difference (165 vs 162) shifts Z2 boundaries and can put the athlete in the wrong training zone. If the athlete doesn't know their max HR, use LTHR-based zones (anchored to `lthr` from `get_sport_settings`) which are more reliable than max-HR-derived zones.
- **Power is authoritative for cycling Z2 — HR is secondary and confirming.** For cyclists with a power meter, Z2 prescriptions should use power zones (56–75% FTP), not HR zones. The athlete's actual HR at a given Z2 power is a function of their individual aerobic efficiency, not a fixed %LTHR. An aerobically efficient cyclist riding at 148–165W (57–63% FTP) may see HR at ~120 bpm — well below the HR Z2 range prescribed by generic formulas. That is NOT a problem — it means the athlete has high stroke volume and is getting the intended stimulus. **Always prescribe Z2 by power first.** Include HR as an FYI with an explicit caveat: "Din puls kommer sannolikt ligga lägre, och det är helt rätt." If the athlete questions the HR number, explain the physiology (high stroke volume, power > HR for cycling Z2) and reinforce that the power target is the correct anchor. The conversational test (full sentences without gasping) is the final arbiter regardless of what either meter says.
### Zone derivation

Derive HR zones from **LTHR** (lactate threshold heart rate), not max HR. LTHR is
more stable and physiologically meaningful. Use `get_sport_settings` → `lthr` as
the anchor. If LTHR is missing/uncertain, use the 30-min all-out test: average HR
of the final 20 minutes of a maximal 30-min effort.

| Zone | %LTHR | Pulsexempel (LTHR 150) | RPE | Känsla |
|------|-------|------------------------|-----|--------|
| Z1 Recovery | <80% | <120 | 1–2 | "Kan knappt känna att jag cyklar" |
| Z2 Endurance | 80–89% | 121–133 | 3–4 | "Kan prata i hela meningar" |
| Z3 Tempo | 89–94% | 134–140 | 5–6 | "Korta meningar" — gråzon, använd sparsamt |
| Z4 Threshold | 94–100% | 141–150 | 7–8 | "Enstaka ord" |
| Z5 VO2max | 100–108% | 151–162 | 9 | "Kan inte prata" |

### Conversational test for Z2

The simplest field check: if the athlete can speak in full sentences without
gasping, they are in Z2. If they can only manage short phrases, they've drifted
into Z3. This works regardless of HR monitor accuracy.

### HR lag pitfall

HR takes 2–3 minutes to stabilize after a change in intensity. During intervals
shorter than 5 minutes, HR will lag behind the actual effort. Prescribe these by
**RPE, not HR**. Example: "3×10 min @ RPE 7–8 (tröskel)" rather than "3×10 min @
141–149 bpm". The athlete should go by feel for the first 2 minutes, then check
that HR has settled in the target zone.

### Rewriting power workouts to HR

When the coach-brain knowledge returns power-based prescriptions (e.g. "2×15 min @
88–94% FTP"), translate:
1. Map the intensity to the correct HR zone using the table above
2. Add an RPE anchor: "Z4, RPE 7–8 — jobbigt men kontrollerat"
3. Include the conversational test for Z2 prescriptions
4. Always present BOTH the HR range AND the feel description

Example translation:
- Power: "2×15 min @ 182–195W (88–94% FTP)"
- HR: "2×15 min @ Z4 (141–149 bpm), RPE 7–8. Ska kännas jobbigt men du ska kunna
  hålla samma ansträngning genom hela intervallen."

### Pace source priority for running

See `references/norwegian-singles.md` (pace source priority). For cycling with no power meter: LTHR from
`get_sport_settings` is the primary anchor. Max HR is secondary — verify with the
athlete (see the Pitfalls rules in SKILL.md).

