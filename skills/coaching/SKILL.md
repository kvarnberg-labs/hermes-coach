name: coaching
description: Evidence-based endurance coaching skill for cycling and triathlon.
version: 1.0.0
author: kvarnberg-labs
metadata:
  hermes:
    tags: ["training", "coaching", "endurance", "cycling", "triathlon"]
    category: "training"

# Coaching Skill

Provides structured, evidence-based coaching guidance for endurance athletes
(cycling and triathlon focus). Retrieves knowledge from the coach-brain YAML
files rather than relying on the model's training data, ensuring consistent,
up-to-date advice grounded in sports science.

## When to Use

- Athlete asks about training structure, periodization, or intensity zones
- Athlete needs recovery advice or is showing signs of overtraining
- Athlete asks about injury return protocols or nutrition guidance
- Athlete is preparing for a race and needs taper or race-week advice
- Any coaching question where evidence-based specificity matters

## Prerequisites

- `coach-brain/` directory populated with YAML knowledge files
- `get_coaching_knowledge` tool registered in the Hermes plugin system
- `intervals.icu` credentials configured for the athlete (optional, for personalized data)

## How to Run

The agent invokes `get_coaching_knowledge(topic)` with a relevant topic string.
The tool searches all coach-brain YAML files and returns matched sections as JSON.

Example topics:
- "threshold intervals"
- "recovery heuristics"
- "tapering"
- "nutrition during training"
- "injury return knee"
- "base building"
- "VO2max intervals"

## Procedure

1. **Identify the coaching topic** from the athlete's question.
2. **Call `get_coaching_knowledge(topic)`** to retrieve relevant knowledge.
3. **Cross-reference with athlete data** (if available):
   - Call `get_wellness(discord_id)` for CTL/ATL/TSB/HRV
   - Call `get_recent_activities(discord_id)` for recent training load
   - Call `get_sport_settings(discord_id)` for FTP and zones
4. **Synthesize advice** using coach-brain principles + athlete data.
5. **Include caveats** when athlete data contradicts standard guidance.

## Quick Reference

| Topic | Tool Call | Follow-up |
|-------|-----------|-----------|
| Training structure | `get_coaching_knowledge("polarized training")` | Check `get_recent_activities` for current distribution |
| Recovery advice | `get_coaching_knowledge("recovery heuristics")` | Check `get_wellness` for TSB, HRV, sleep |
| Workout design | `get_coaching_knowledge("threshold intervals")` | Check `get_sport_settings` for FTP |
| Injury return | `get_coaching_knowledge("injury return knee")` | Check `get_recent_activities` for load history |
| Nutrition | `get_coaching_knowledge("nutrition during training")` | Check activity duration to tailor advice |
| Race prep | `get_coaching_knowledge("tapering")` | Check `get_planned_events` for race dates |

## Pitfalls

- **Do not prescribe specific workouts** without checking the athlete's current TSB and recent load. A hard session when TSB < -20 is a recipe for injury.
- **Do not override coach-brain guidelines** with generic model knowledge. The YAML files contain curated, evidence-based ranges.
- **Always check weather** before recommending outdoor training in extreme conditions.
- **Injury red flags** in coach-brain require medical referral — do not suggest continued training.

## Verification

After giving coaching advice, verify:
1. The advice aligns with coach-brain principles for the athlete's current state
2. Intensity recommendations are appropriate for the athlete's TSB
3. Recovery is prescribed when fatigue signals are elevated
4. Nutrition advice matches the duration and intensity of the session
