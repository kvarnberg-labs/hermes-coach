# FIT Workout File Generation

How `create_planned_event` generates Garmin-native structured workouts.

## Why FIT files

The intervals.icu API parses structured workout data from FIT files uploaded
via `file_contents_base64`. The `workout_doc` PUT approach does NOT produce
correct pace/HR targets on Garmin — the API stores steps but never converts
them to proper Garmin workout targets.

## FIT file structure (for reference)

A minimal FIT workout file has this layout:

```
[Header 12B] [File ID def] [File ID data] [Workout def] [Workout data] [Step def] [Step data] × N [CRC 2B]
```

### Header (12 bytes)
| Offset | Size | Field | Description |
|--------|------|-------|-------------|
| 0 | 1 | header_size | Always 0x0C (12) |
| 1 | 1 | protocol_version | 0x23 |
| 2 | 2 | profile_version | Little-endian uint16 |
| 4 | 4 | data_size | Little-endian uint32, bytes after header excluding CRC |
| 8 | 4 | data_type | ".FIT" |

### Key value encoding in step data

| Field | FIT type | Encoding |
|-------|----------|----------|
| Duration | uint32 | seconds × 1000 (ms) |
| Speed (pace) | uint32 | m/s × 1000 |
| Heart rate | uint32 | % of max HR (NOT absolute BPM!) |
| Power | uint32 | **%FTP (NOT watts!)** — intervals.icu and Garmin both interpret the FIT power field as percentage of FTP. Sending 160 when FTP=286 displays as 160% → 457W on Garmin. When `power_pct_min`/`power_pct_max` is used, send the percentage directly. When `power_min`/`power_max` (watts) is used, convert: `round(watts / ftp * 100)`. |

### HR conversion: BPM → %max HR

intervals.icu stores HR targets as percentage of max HR. The tool fetches
`max_hr` from the athlete profile (`GET /athlete/{id}`) and converts:

```python
hr_pct = max(1, min(100, round(bpm / max_hr * 100)))
```

If the profile fetch fails, `max_hr` defaults to 193.

### Pace conversion: min:sec/km → m/s

The tool's `_parse_pace_to_ms()` converts human-readable pace:

```python
# "5:40" → 5×60 + 40 = 340 seconds/km → 1000/340 = 2.94 m/s
total_sec = minutes * 60 + seconds
m_per_s = round(1000.0 / total_sec, 2)
```

### Power: %FTP is the canonical format

The FIT file's `custom_target_power_low/high` fields are interpreted as
%FTP by both intervals.icu and Garmin. The tool ensures values are in %FTP:

```python
# If power_pct_min/power_pct_max is set → use directly (already %FTP)
# If power_min/power_max is set (watts) → convert to %FTP
if not is_pct and value > 20 and ftp > 0:
    value = round(value / ftp * 100)  # 160W → 56% at FTP 286
```

**Never** send watt values — Garmin will interpret them as %FTP (160 → 160%
of FTP = 457W).

### Sport mapping

| intervals.icu type | FIT sport | Default target type |
|--------------------|-----------|-------------|
| Run, TrailRun, VirtualRun | Running (1) | SPEED (pace) |
| Ride, VirtualRide, GravelRide, MountainBikeRide | Cycling (2) | POWER |

### One target type per step — FIT limitation

⚠️ **The FIT file format supports only ONE target type per workout step.**
A step can have a HR target, a power target, OR a pace target — not multiple.

The `create_planned_event` tool's auto-detection (in `_build_fit_file`)
prioritizes targets in this order: **HR > power > pace**. When a step has
both `hr_min/hr_max` and `pace_min/pace_max`, the tool selects HR and
**silently drops pace**.

**Practical rule:**
- **Running threshold/interval reps:** use `pace_min`/`pace_max` only (no HR fields)
- **Running warmup/cooldown/recovery:** use `hr_min`/`hr_max` only (no pace fields)
- **Cycling:** use `power_pct_min`/`power_pct_max` only (or `power_min`/`power_max`)
- **Need both pace and HR on a work step?** Put pace as the target and include
  the HR range in the step `description` text — Garmin shows the description

This is a FIT protocol limitation, not a tool bug.

### Intensity mapping

| Step type | FIT intensity |
|-----------|---------------|
| WARMUP | 2 |
| ACTIVE | 0 |
| REST | 1 |
| COOLDOWN | 3 |

**Easy runs and Z2 rides should be a single step.** Athletes prefer this — don't
add warmup/cooldown steps for steady-state workouts. Only use multi-step
workouts for structured sessions with meaningful intensity changes (intervals,
threshold, VO2max).

## Dependency

`fit-tool` (PyPI package `fit-tool>=0.9,<1`) is used to generate valid FIT
binary files. It's already in the repo's Dockerfile — check the Dockerfile
before claiming a missing dependency. The tool imports it at call time (not
module-level) so the plugin loads even without fit-tool installed.

## Template-based fallback (removed)

A byte-level template substitution approach was attempted but proved too
fragile — FIT file size varies with step name length and definition
message field counts, making offset-based patching unreliable. The
template code has been removed entirely.
