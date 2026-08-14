# Illness Plan Adjustment

When an athlete reports missing a session due to illness mid-training-block,
follow this workflow to assess impact and adjust the plan.

## Detection Signals

Before the athlete even reports illness, check for early-warning signs:

1. **Resting HR spike**: `get_wellness(days=7)` → compare `resting_hr` trend.
   A +10-15 bpm spike 2-3 days before the missed session is common. Example:
   Aug 1: 78 → Aug 3: 83 → Aug 5: 93 (clear illness signal).

2. **Missing activity**: `get_recent_activities(days=14)` — if a planned session
   date has no matching activity, confirm with the athlete.

## Coach-Brain Knowledge

The illness return guidelines live under `injury_return_to_training.illness`:

```
get_coaching_knowledge("injury return to training") → knowledge.illness
```

Key rules:
- **Above-the-neck only** (runny nose, mild sore throat, NO fever/body aches):
  Easy activity generally acceptable. Reduce intensity significantly.
- **Below-the-neck or fever** (chest symptoms, fever, body aches, GI illness):
  Complete rest. Do not train until fever-free for 48 hours.
- **Return timeline:**
  - Day 1-2: Easy walking or very light activity only
  - Day 3-4: Easy Z1 cycling if feeling well
  - Day 5-7: Return to normal easy training
  - Day 8+: Resume intensity with caution

## Adjustment Workflow

### Step 1: Verify the gap
```python
get_recent_activities(days=14)  # confirm no activity on the missed date
get_wellness(days=7)            # check resting HR trend for illness signal
```

### Step 2: Consult guidelines
```python
get_coaching_knowledge("injury return to training")
# Look for the `illness` key in the response
```

### Step 3: Determine return day
Count days FROM the missed session (or from when fever broke).
Example: Sick Friday Aug 7. Athlete messages Saturday Aug 8 (Day 1-2).
Next scheduled session is Monday Aug 10 (Day 3-4 from illness).

### Step 4: Patch the training plan file
Replace the missed session row and adjust upcoming sessions:

```
patch the plan file at /opt/data/training-plan-{athlete}.md:
  - Mark missed session: "SJUK ❌ | — | —"
  - Adjust next session per return timeline
  - If next session was a long run (120+ min) → reduce to 50-60 min Z2 low
  - If next session was threshold → push it out at least 5-7 days
```

### Step 5: Check if recovery week timing is favorable
If a recovery/deload week was already scheduled within the next 7 days,
the forced rest actually aligns well. Tell the athlete: the timing is
lucky — the body gets double recovery.

### Step 6: Present adjusted schedule
Short format (Swedish, max 4 lines for Aldrin-style athletes):
- Today: Vila
- Tomorrow: Light activity if feeling well
- Next session: Adjusted duration + zone + caveat
- Note if recovery week absorbs the disruption

## Example: Aldrin Aug 7 Illness

1. Verified: no activity on Aug 7 (confirmed)
2. Wellness: resting HR 78→83→93 over Aug 1-5 (early signal)
3. Coach-brain: "below-the-neck or fever → complete rest → Day 3-4 easy Z1"
4. Next session Mon Aug 10 = Day 3-4 → reduce 120 min long run to 50-60 min Z2 low
5. Next week (Aug 11-17) was already recovery week → favorable timing
6. Output:
```
Idag: Vila 🏠
Sön: Kort promenad eller 30 min Z1 om frisk
Mån 10/8: 50-60 min Z2 låg (121-128) — återgång efter sjukdom
Nästa vecka är redan återhämtning — perfekt tajming
```

## Masters-Specific Considerations (60+)

- Masters athletes need MORE conservative return: add 1-2 extra easy days
- Resting HR recovery is slower — don't trust a single normal reading
- Never compress the return timeline to "catch up" — accept the lost session
- If the athlete is 65+, consider extending the return by a full week
