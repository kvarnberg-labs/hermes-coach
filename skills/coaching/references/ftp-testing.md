# FTP: eFTP gaps, estimates and tests

Load when configured FTP and eFTP disagree, after a maximal effort or test, or
before changing FTP.

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

## Rules for estimating FTP

- **No estimates from non-maximal rides.** NP over 50+ min approximates FTP only
  for a maximal or near-maximal effort (race, test, hill-climb PR). Never from a
  routine endurance ride or a windy variable ride. Decoupling is not an FTP
  estimator. Suggest an FTP change only when the athlete repeatedly fails
  intervals at the current FTP or has done a maximal effort; otherwise prefer
  the wellness eFTP over a guess.
- **Ask for the platform's own estimate after a test.** intervals.icu analyses
  the whole power-duration curve and may detect a longer sustained effort
  (e.g. 44 min) that 95 % of 20-min power misses. Before your verdict, ask
  whether intervals.icu reported a new estimate; present both and weight the
  one based on the longer effort more.
- **Never anchor watts to an FTP from memory.** Stored values go stale silently
  (one stored 252 W vs live 261 W ≈ 3.5 % low targets). Re-pull
  `get_sport_settings` before any watt prescription and cite FTP with its check
  date ("FTP 261 W, checked 2026-09-07").
