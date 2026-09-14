# FTP Testing Protocols

## When to test
- eFTP and configured FTP differ by >10W and athlete disagrees with eFTP
- CTL is trending up but eFTP is trending down (suspected underestimation)
- No maximal or near-maximal effort in the past 4-6 weeks
- Athlete reports consistently failing prescribed intervals at current FTP
- Athlete reports consistently completing VO2max intervals at power levels eFTP says should be impossible

## Test methods

### 20-minute FTP test (gold standard, indoor)
1. 20 min warmup progressive Z1→Z3
2. 3×1 min fast spin (100+ rpm) with 1 min rest
3. 5 min all-out (clears anaerobic capacity)
4. 10 min easy spin recovery
5. 20 min ALL-OUT — maximal steady effort, pacing is critical
6. 10-15 min cooldown
7. FTP = 20-min avg power × 0.95

**Pacing tips:**
- First 5 min: hold back slightly, find rhythm
- Middle 10 min: settle into target, don't fade
- Last 5 min: empty the tank
- If you finish with anything left, the test is invalid

### Ramp test (Zwift, TrainerRoad)
1. Progressive resistance steps (typically 20W/min)
2. Ride until failure (cannot maintain cadence > 70 rpm)
3. FTP = max 1-min power × 0.75 (approximate)
4. Pros: Short (~20 min), no pacing skill needed. Cons: Less accurate for some athletes.

### Long climb max effort (outdoor)
1. Find a steady 10-15 min climb, no traffic lights
2. After thorough warmup, climb at max sustainable effort
3. FTP ≈ average power for the climb (no 0.95 factor needed for 10-15 min)
4. Hard to control variables (wind, traffic, gradient changes)

## Reading results

### eFTP is trustworthy when:
- Recent maximal or near-maximal effort exists in the power-duration curve
- eFTP trend matches CTL trend (both rising or both stable)
- eFTP and configured FTP agree within ±10W

### eFTP is likely WRONG when:
- No maximal efforts in 4+ weeks
- eFTP ↓ while CTL ↑ (the "getting fitter but looking weaker" paradox)
- Athletes who train mostly Z2 — the model lacks data to estimate the top end
- Recent illness or training interruption skewed the rolling average

### When athlete says "I feel my FTP is X" — take it seriously
Subjective feel is a legitimate data point. If an athlete consistently hits VO2max power targets at RPE 7-8 and says "I think my FTP is higher than eFTP says," they are usually right. The model sees their training rides, not their capacity.

---

## Moved from SKILL.md (2026-09-14)

- **FTP estimation — don't guess from non-maximal rides.** NP over 50+ minutes is only a reasonable FTP proxy when the effort was **maximal or near-maximal** (race, FTP test, hill climb PR, Zwift race). Do NOT estimate FTP from a routine endurance ride, a windy variable-effort ride, or any session where the athlete was not going all-out. NP on a variable 3h ride with headwind and climbs says nothing about what the athlete could hold for 20 minutes at max. Similarly, **decoupling is NOT an FTP estimator** — it's an individual physiological marker (some athletes decouple 5% at threshold, others 20%). Using it to back-calculate FTP is circular and invalid. Only suggest FTP adjustment if the athlete reports failing prescribed intervals at a given FTP, or if they complete a maximal 20-min effort. When in doubt, defer to the eFTP from wellness data rather than guessing.
- **FTP test analysis — always check intervals.icu's own FTP estimate before giving your verdict.** After a maximal TT or FTP test, intervals.icu's algorithm analyzes the full power-duration curve and may detect sustained efforts (e.g. 44 min @ 263W) that simple formulas like 95%-of-20-min miss. The platform's auto-estimate notification ("Your estimated FTP has increased by XW to YW based on Zm at QW") is often more accurate than the standard formula because it uses a longer duration window. Do NOT give an FTP recommendation based solely on 20-min peak power without first asking the athlete whether intervals.icu has reported its own estimate. If you give a conservative number and the platform later says +10W higher, you look like you don't trust the data — and the athlete will trust the platform over you. Present both numbers, but give the platform estimate MORE weight when it's based on a longer sustained effort than 20 minutes.
- **Never anchor watt prescriptions to an FTP value stored in memory — always re-pull FTP from get_sport_settings.** Memory anchors go stale silently: Millberg's store said "current FTP 252W" while his live intervals.icu FTP was 261W — every watt target derived from the stored value would be ~3.5% low. FTP also legitimately changes over time, so even a once-correct anchor decays. When you must cite FTP in text or memory, phrase it with its verification date ("FTP 261W, checked 2026-09-07") and re-verify against live sport settings before any prescription.
