# Coach Brain

The coach brain is a collection of YAML files containing structured, evidence-based coaching knowledge. It is the authoritative source for training principles, recovery heuristics, workout definitions, injury protocols, and nutrition guidelines.

## Design Philosophy

**Knowledge is decoupled from the agent core.** Coach brain files live in the repository, are baked into the Docker image, and synced to the PVC at container startup. This means:

- Coaching advice is consistent across all users and sessions
- Knowledge can be updated by pushing YAML changes (no code deployment needed)
- The system prompt stays lean — knowledge is retrieved at query time, not loaded into context
- Per-conversation prompt caching is preserved

## File Format

All files use standard YAML. Each file contributes its top-level keys to a merged dictionary. The `get_coaching_knowledge(topic)` tool searches all merged keys and their serialized content for keyword matches.

### Naming Conventions

| Convention | Example |
|------------|---------|
| File names: `kebab-case.yaml` | `training-philosophies.yaml` |
| Top-level keys: `snake_case` | `training_philosophies:` |
| Nested keys: `snake_case` | `polarized:`, `best_for:` |
| String values: plain text or YAML lists | `summary: "..."` or `- item` |

### Structure Pattern

```yaml
---
# Human-readable comment describing the file's purpose

top_level_key:
  subsection:
    field_name: value
    list_field:
      - item 1
      - item 2
    nested:
      deeper: value
```

## Current Knowledge Files

### `training-philosophies.yaml`

Training distribution models and periodization frameworks.

```yaml
training_philosophies:
  polarized:
    summary: ~80% low intensity, ~20% high intensity
    best_for: [athletes with 8+ hours/week, experienced athletes]
    evidence: Strong support from Seiler et al. research
    caution: Requires honest zone enforcement

  pyramidal:
    summary: Most volume at low intensity, progressively less at moderate/high
    best_for: [athletes building base, recreational athletes]

periodization:
  linear:
    summary: Gradual progressive increase in load
    cycle: "4 weeks: 3 build + 1 recovery"

  block:
    phases: [accumulation, intensification, realization]

intensity_zones:
  coggan_power_7_zone:
    zones: [Z1-Z7 with FTP percentages]

  heart_rate_3_zone:
    zones: [Z1-Z3 based on ventilatory thresholds]
```

### `recovery-heuristics.yaml`

Metrics and guidelines for managing athlete fatigue and recovery.

```yaml
recovery_heuristics:
  tsb_interpretation:
    ranges: [very_negative, negative, neutral, positive, very_positive]
    # Each range has: value, meaning, action

  ramp_rate:
    safe_range: "+3 to +8 CTL points per week"
    warning: "> +10 per week increases injury risk"

  hrv_interpretation:
    guidance: [well_recovered, mildly_fatigued, fatigued, very_fatigued]

  sleep:
    minimum_for_adaptation: "7 hours"
    optimal: "8-9 hours during heavy blocks"

fatigue_management:
  overtraining_syndrome_warning_signs: [list of signs]
  non_functional_overreaching: [prevention guidelines]
```

### `workout-library.yaml`

Structured session templates with purpose, execution, and prescribing guidelines.

```yaml
workout_library:
  z2_endurance:
    duration: "60-180 min"
    intensity: "56-75% FTP"
    purpose: Primary aerobic base builder
    when_to_prescribe: [most training days, day after hard session]
    avoid_when: [TSB < -25]

  threshold_intervals:
    intensity: "95-105% FTP"
    structure: "2-4 x 8-20 min @ FTP, 5 min easy"
    session_load: High
    recovery_needed: 48 hours

  vo2max_intervals:
    intensity: "106-120% FTP"
    structure: [classic: 5x3-5min, short: 30/15s repeats]

race_preparation:
  taper_guidelines: [volume reduction, intensity maintenance]
  race_week: [day-by-day schedule]
```

### `injury-return.yaml`

Return-to-training protocols for common injuries.

```yaml
injury_return_to_training:
  general_principles: [pain rules, load management]

  knee_pain:
    types: [patellofemoral, it_band]
    return_protocol: [step-by-step]
    red_flags: [swelling, locking, giving way]
    medical_referral: timeline

  illness:
    above_the_neck_rule: easy activity acceptable
    below_the_neck_or_fever: complete rest
    return_after_illness: [progressive steps]
```

### `nutrition.yaml`

Evidence-based nutritional guidance.

```yaml
nutrition:
  daily_baseline:
    carbohydrates: [easy_day, moderate_training, hard_training]
    protein: [general, heavy_training]
    hydration: [baseline, add_for_training]

  during_exercise:
    under_60_min: water sufficient
    over_90_min: 60-90g carbs/hour, glucose+fructose 2:1

  supplements:
    evidence_based: [caffeine, creatine, beetroot, vitamin_d, iron]
    limited_evidence: [beta_alanine, sodium_bicarbonate]
```

## Retrieval Mechanism

The `get_coaching_knowledge(topic)` tool in `plugins/training/coaching.py`:

1. Loads all YAML files from `$HERMES_HOME/coach-brain/`
2. Merges them into a single dictionary
3. Searches for keyword matches in keys and serialized content
4. Returns matched sections as JSON

### Search Behavior

- Topic string is split on hyphens and spaces into keywords
- Each keyword is searched against top-level keys (normalized to spaces)
- If no keyword matches, falls back to searching serialized JSON content
- Returns all matching top-level keys and their nested content
- If nothing matches, returns available top-level keys for the agent to try

### Example Queries

| Query | Matches |
|-------|---------|
| `"threshold intervals"` | `workout_library → threshold_intervals` |
| `"recovery"` | `recovery_heuristics`, `fatigue_management` |
| `"tapering"` | `race_preparation → taper_guidelines` |
| `"knee pain"` | `injury_return → knee_pain` |
| `"nutrition during training"` | `nutrition → during_exercise` |

## Adding New Knowledge

### 1. Create a New YAML File

```bash
# Create the file in coach-brain/
touch coach-brain/new-topic.yaml
```

### 2. Follow the Structure Pattern

```yaml
---
# Brief description of the knowledge domain

new_topic:
  subsection:
    field_name: value
    guidance:
      condition_a: "Advice for condition A"
      condition_b: "Advice for condition B"
```

### 3. Test Retrieval

```python
import sys, json
sys.path.insert(0, "plugins")
from training.coaching import get_coaching_knowledge

result = json.loads(get_coaching_knowledge("new topic"))
print(json.dumps(result, indent=2))
```

### 4. Commit and Deploy

```bash
git add coach-brain/new-topic.yaml
git commit -m "docs: add new coaching knowledge for X"
git push origin main
# Flux deploys within 1 minute
```

## Sync Mechanism

At container startup, `docker/sync-coach-assets.sh` (cont-init.d/05) runs:

```bash
# Sync coach-brain (cp -n preserves existing files)
mkdir -p "${HERMES_HOME}/coach-brain"
cp -rn /opt/hermes/coach-brain/. "${HERMES_HOME}/coach-brain/"
```

The `-n` (no-clobber) flag means:
- **First deployment:** All files are copied from image to PVC
- **Subsequent deployments:** Only new files are copied; existing files on PVC are preserved
- **User edits:** Survive across deployments

To force a refresh after user edits:
```bash
kubectl exec -it deployment/hermes -n hermes -- rm -rf /opt/data/coach-brain/*
kubectl rollout restart deployment/hermes -n hermes
```

## Best Practices

1. **Keep files focused.** One domain per file (e.g., nutrition, recovery, workouts).
2. **Use actionable language.** Write guidance that the agent can directly relay to athletes.
3. **Include conditions.** Specify when to apply guidance and when to avoid it.
4. **Cite evidence.** Reference research or established guidelines where applicable.
5. **Avoid duplicates.** If knowledge overlaps across files, prefer one authoritative source.
6. **Test retrieval.** Always verify that `get_coaching_knowledge(topic)` returns expected content.
7. **Keep values serializable.** Avoid YAML anchors, aliases, or binary data.
