# Training Summary Workflow

How to efficiently produce a comprehensive training period summary
(weekly, monthly, seasonal, or vacation block) using the Hermes coaching tools.

## When to Use

- Athlete asks for a summary of their training over a period
  ("summarize my summer", "how did June go?", "recap the last 4 weeks")
- Coach needs to present a period review with charts and metrics
- Pre-season or post-season analysis

## Procedure

### Phase 1: Parallel data pull (do ALL of these in one turn)

```
verify_athlete_identity()
get_wellness(days=42)         # 6 weeks of daily CTL/ATL/TSB/HRV/sleep
get_fitness_chart(days=90)    # long-range CTL/eFTP trends
get_recent_activities(days=N) # activities covering the period
get_sport_settings()           # current FTP, zones, LTHR
get_athlete_stats(start, end) # monthly totals per sport
get_power_curve(days=90)      # peak power, strengths/weaknesses
```

The parallel pull is the key optimization — 6+ calls in one turn
instead of sequential. All are independent reads.

### Phase 2: Monthly stat comparison

Pull `get_athlete_stats` for each month in the period. This gives:
- Total activities, distance, duration, calories, training load
- Per-sport breakdown (Ride, VirtualRide, Run, WeightTraining, etc.)

Present as a comparison table with delta percentages.

### Phase 3: Chart rendering

```
render_wellness_chart(wellness_json)   # CTL/ATL/TSB trend line
render_power_curve_chart(power_json)   # peak power curve
```

Include chart images in the response via MEDIA: paths.

### Phase 4: Narrative summary

Structure the output with these sections:

1. **Overview table** — monthly comparison with deltas
2. **Fitness (CTL) progression** — key milestones with dates
3. **FTP development** — start → end with intermediate checkpoints
4. **Peak load and recovery** — deepest TSB holes, recovery speed
5. **Quality sessions** — highlight the best/hardest workouts
6. **Endurance/Z2 training** — trend in discipline, HR efficiency
7. **Health signals** — resting HR, HRV, sleep trends
8. **Development areas** — what to improve next period
9. **Conclusion** — overall assessment, actionable next step

### Phase 5: Present the wellness chart

Attach the chart as MEDIA in the response for visual context.

## Pitfalls

- **Don't include today's activity as a past summary item.** In `get_recent_activities`,
  the most recent activity may be from today (if already completed). When summarizing
  a completed period (e.g. "June+July"), today is separate.
- **Use configured FTP from `get_sport_settings`, not eFTP from fitness chart** for zone
  calculations. eFTP is a model estimate; configured FTP is what the athlete's zones
  are actually based on.
- **Cross-reference power zones AND HR zones** when concluding ride intensity. See
  the main coaching SKILL.md pitfall on this.
- **Present both eFTP and configured FTP** when they disagree, and flag the discrepancy.
- **Weather context is optional for period summaries** — only include it if the athlete
  asks or if it explains a specific training decision (indoor vs outdoor).
- **Keep the summary in the athlete's language.** If the session is in Swedish, the
  entire summary should be in Swedish — including table headers and zone names.
  Exception: tool names and metric abbreviations (CTL, TSS, IF) stay in English.
- **Don't fabricate zone distribution charts without real data.** Computing accurate
  zone percentages requires pulling `get_activity_detail` for every activity, which
  is impractical for long periods. Skip the zone chart or estimate qualitatively
  from IF values — but be explicit that it's an estimate.
- **Planned events are NOT part of a historical summary.** The summary covers what
  was actually done, not what was planned. Only pull `get_planned_events` for
  forward-looking analysis.

## Example Output Structure (Swedish)

```
## 📊 [Period] — Träningssammanfattning

### Översikt: [Month1] vs [Month2]
| Kolumner | Månad1 | Månad2 | Förändring |

### 📈 Fitness (CTL) — från X till Y
| Datum | CTL | Händelse |

### 🔥 FTP-utveckling
| Period | eFTP | Kommentar |

### 🏔️ Toppbelastning och återhämtning
| Datum | TSB | Orsak |

### 🎯 Kvalitetspass
| Datum | Pass | Intensity |

### 🟢 Z2 / Distans
| Datum | Pass | Intensitet | Maxpuls |

### 🩺 Hälsosignaler
- Vilopuls, HRV, sömn

### ⚠️ Utvecklingsområden

### 🎯 Slutsats
```

## Related References

- `references/training-plan-creation.md` — forward-looking planning (the inverse)
- `references/ftp-testing.md` — FTP verification when summary reveals discrepancies
- `references/hr-based-training.md` — when the athlete lacks power data
