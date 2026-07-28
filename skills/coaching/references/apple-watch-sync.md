# Apple Watch Sync Troubleshooting

When an athlete uses Apple Watch for run tracking, the sync path to intervals.icu
requires a bridge app — Apple Watch has no direct intervals.icu integration.

## The sync chain

```
Apple Watch → Apple Health → HealthFit → intervals.icu
```

Strava alone is insufficient: it often drops HR data from Apple Watch and may
sync only skeletal activity records (type, date, training load) without full
detail (distance, duration, pace, HR zones).

## Recommended setup: HealthFit

**[HealthFit](https://apps.apple.com/se/app/healthfit/id1202650514)** (~50 kr,
one-time purchase) reads ALL data from Apple Health and pushes to intervals.icu
directly. It preserves HR, pace, cadence, elevation, and sleep/HRV data.

### Setup steps

1. Install HealthFit from App Store
2. Open HealthFit → Settings → Sync to intervals.icu
3. Log in with intervals.icu credentials
4. Enable "Automatic Upload"
5. Verify: after the next run, check intervals.icu for full activity data

### What HealthFit sends that Strava often misses

- Heart rate (Apple Watch records HR but Strava frequently drops it)
- Cadence / steps per minute
- Sleep data and HRV (from Apple Health overnight)
- Full lap/interval data
- Accurate pace and distance (Apple Watch GPS data)

## Detection: is the athlete on Apple Watch?

**Clues that the athlete uses Apple Watch and needs HealthFit:**
- Activities appear in intervals.icu with `type: null`, `duration_min: 0.0`,
  `distance_km: 0.0` — but CTL/ATL values update (training load arrives, details don't)
- Athlete says they sync via Strava but have no Garmin device
- Athlete mentions Apple Watch explicitly
- Wellness data (CTL/ATL/TSB) is populated but all activity fields are null

**When you detect this pattern:**
1. Confirm the athlete uses Apple Watch
2. Check if they synced via Strava (the likely broken path)
3. Recommend HealthFit as the fix
4. Note that Strava can be kept for social features — HealthFit handles the
   intervals.icu sync independently

## Apple Watch and HRV/sleep

Apple Watch measures HRV and sleep data natively (stored in Apple Health).
HealthFit forwards these to intervals.icu automatically once configured.
This fills the HRV/sleep gap that many Apple Watch athletes have — they
often have the data but it's stuck in Apple Health with no path out.

## Strava-as-bridge: the null-field problem

When an athlete syncs Apple Watch → Strava → intervals.icu (the most common
but broken path), the symptoms are distinctive:

| Field | intervals.icu value | Why |
|-------|-------------------|-----|
| `type` | `null` | Strava sends activity type, but intervals.icu can't map it |
| `distance_km` | `0.0` | Distance not forwarded in the format intervals.icu expects |
| `duration_min` | `0.0` | Moving time dropped in Strava→intervals.icu sync |
| `avg_hr` / `max_hr` | `null` | Apple Watch HR data dropped by Strava |
| `icu_training_load` | populated | intervals.icu estimates load from whatever minimal data arrives |

**Key diagnostic:** CTL/ATL update (so intervals.icu sees *something*) but every
detail field is null. This means the athlete IS training, but the coach can't
analyze pace, HR, power, or zone distribution.

**The fix is always the same:** switch from Apple Watch → Strava → intervals.icu
to Apple Watch → Apple Health → HealthFit → intervals.icu. Strava can stay for
social features, but HealthFit handles the intervals.icu sync properly.

**Wilma case (2026-07-27):** 18 activities with all-null fields, CTL 20.9.
Strava sync was the broken path. Recommended HealthFit. Athlete confirmed
Apple Watch + Strava and that Apple Watch doesn't connect directly to
intervals.icu. This is the expected pattern for every Apple Watch user who
initially syncs through Strava.

## Alternative apps

If HealthFit isn't available, these also work:
- **RunGap** — broader device support, subscription model
- **HealthSync** — simpler, focused on health metrics
- **Strava app on Apple Watch** — improves data fidelity vs. Apple
  Workout → Health → Strava import, but still less complete than HealthFit

HealthFit is preferred because it's a one-time purchase, auto-syncs in
background, and has the best intervals.icu support of the options.
