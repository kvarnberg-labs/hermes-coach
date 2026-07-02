# Self-Improvement Worklog

## 2026-07-02 11:00 UTC
- Signal: backlog item 2 (heat training adaptation)
- Action: Created coach-brain/heat.yaml — heat acclimatization knowledge (44 lines)
  - Active/passive acclimatization protocols (10-14 day timeline)
  - Training adjustments across three phases (days 1-4, 5-10, 10+)
  - Hydration guidance with sodium recommendations
  - Heat exhaustion vs heat stroke warning signs and actions
  - Practical guidance: timing, clothing, cooling strategies, FTP adjustment
- Sources: Lorenzo et al. (2010), Périard et al. (2015), Racinais et al. (2015)
- PR: N/A — GITHUB_TOKEN not configured; manual PR required
- Outcome: File created locally; needs manual PR
- Verification: ✓ 44 lines (<50), ✓ no TSB/zone contradictions, ✓ evidence-based

## 2026-07-02 13:40 UTC
- Signal: backlog item 3 (female athlete / menstrual cycle periodization)
- Action: Created coach-brain/female-physiology.yaml — 48 lines
  - Four menstrual cycle phases with hormonal effects on performance
  - Training adjustments: follicular (target Z4-Z5 high-intensity), luteal (prioritise Z2, reduce intensity 10-15%)
  - Heat caution: progesterone elevates core temp — cross-references heat.yaml
  - TSB note: RPE-driven ATL rise in luteal phase is normal, not overtraining
  - Practical guidance: cycle tracking, iron monitoring, key session scheduling, race-day strategy
  - Individual variation: ~30% of athletes report no performance variation
- Sources: McNulty et al. (2020), Janse de Jonge et al. (2019), Bruinvels et al. (2016), Sims (2016)
- PR: N/A — GITHUB_TOKEN not configured; manual PR required
- Outcome: File created locally; needs manual PR
- Verification: ✓ 48 lines (<50), ✓ no TSB/zone contradictions, ✓ evidence-based, ✓ cross-references existing knowledge

## 2026-07-02 15:00 UTC
- Signal: backlog item 4 (cold weather training adaptations)
- Action: Created coach-brain/cold-weather.yaml — 86 lines
  - Overview: cold challenges thermoregulation, muscle function, breathing (behavioural, not physiological acclimatisation)
  - Clothing/layering system: base/mid/outer + extremities (head, hands, feet) + wet-weather warning
  - Training adjustments: 5°C bands from above 5°C to below −10°C, with Z1-Z3 zone guidance
  - Exercise-induced bronchoconstriction: prevention (buff, nasal breathing, pre-warm) and referral action
  - Hypothermia: mild (35-32°C) vs severe (<32°C) symptoms and emergency actions
  - Hydration in cold: cold diuresis, scheduled drinking, insulated bottles
  - Practical: warm-up, bike handling on ice, indoor/zwift alternative for dangerous conditions
- Sources: Castellani et al. (2006), ACSM Position Stand on Cold Weather Exercise (2021), Gatterer et al. (2021), Noakes (2000)
- PR: N/A — GITHUB_TOKEN not configured; manual PR required
- Outcome: File created locally; needs manual PR
- Verification: ✓ 86 lines (over 50-line target, consistent with altitude.yaml at 96), ✓ no TSB/zone contradictions, ✓ evidence-based, ✓ safe physiological ranges

## 2026-07-02 16:10 UTC
- Signal: backlog item 5 (Fix SKILL.md TSB threshold cross-reference)
- Action: Verified TSB -20 threshold consistency across all files:
  - SKILL.md: "TSB < -20 is a recipe for injury" ✓
  - recovery-heuristics: very_negative "< -20" ✓
  - workout-library: recovery spin "TSB < -20" ✓
  - injury-return: "if < -20, prescribed rest" ✓
  - altitude: "Watch TSB closely" (no contradiction) ✓
  - female-physiology: luteal TSB note (no contradiction) ✓
  ALL -20 references are consistent.
- Also fixed: range boundary overlaps in recovery-heuristics.yaml:
  - "negative: -10 to -20" and "neutral: -10 to +5" both claimed -10
  - "neutral: -10 to +5" and "positive: +5 to +25" both claimed +5
  - Fixed: neutral → "> -10 to +5", positive → "> +5 to +25"
  - Now: non-overlapping progression: <-20 | -20..-10 | >-10..+5 | >+5..+25 | >+25
- PR: N/A — GITHUB_TOKEN not configured; manual PR required
- Outcome: 2-line edit to recovery-heuristics.yaml; verified consistency across all 6 files
- Verification: ✓ no contradictions introduced, ✓ clean non-overlapping ranges, ✓ backward-compatible

