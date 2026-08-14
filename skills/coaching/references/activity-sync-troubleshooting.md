# Activity Sync Troubleshooting — Missing Activities

When an athlete reports that activities visible in Garmin Connect are
missing from intervals.icu, use this diagnostic procedure.

## Step 1: Verify the gap is real

Pull 90 days of activities and identify gaps of 3+ days with no activity.
Map them against the athlete's training log or ask the athlete directly.

## Step 2: Check wellness CTL decay during gaps

The most reliable way to distinguish genuine rest from a sync failure is
to examine the CTL/ATL/TSB curves during the gap period.

**Genuine rest pattern:**
- CTL decays smoothly and continuously (e.g., 37.6 → 36.7 → 35.9 → 35.0)
- ATL drops sharply (fatigue dissipating)
- TSB rises steadily from negative toward positive
- No sudden jumps in CTL that would indicate a belatedly-synced activity

**Sync failure pattern (hypothetical):**
- CTL is flat or jumps suddenly mid-gap (activity arrived late)
- ATL spikes without a corresponding activity in the list
- TSB drops unexpectedly during the gap

Call `get_wellness` with `days` covering the gap period and inspect the
day-by-day CTL/ATL/TSB values. If CTL decays smoothly with no jumps,
the gap is genuine rest, not a sync problem.

## Step 3: Check Garmin sync settings

Fetch the athlete profile and verify:
- `icu_garmin_sync_activities` is `True`
- `garmin_sync_activity_types` is `None` (means all types sync)
- `icu_garmin_upload_filters` is `None` (no activity filtering)
- `icu_garmin_last_upload` is recent (within hours of the last activity)

If any of these are misconfigured, activities may be filtered out.

## Step 4: Check for sport-type mismatch

If the wrong athlete's credentials were active (see
`references/credential-path-mismatch.md`), you will see activities
belonging to a different person — potentially including sport types
the real athlete does not do. For example, if the athlete is a cyclist
and you see "Run" activities, this is a red flag that you are looking
at the wrong athlete's data.

## Step 5: Zwift integration — "Download Old Data" stuck

When an athlete connects Zwift to intervals.icu and clicks "Download
Old Data" but activities don't appear, check the following:

### Symptoms
- "downloading in progress, please be patient" message persists for hours
- No new VirtualRide activities appear despite the connection being active
- Existing VirtualRide activities may be from a different source (e.g.,
  Wahoo trainer + Garmin Edge, not Zwift) — don't assume "VirtualRide"
  means Zwift. Ask the athlete what device recorded each activity.

### Root cause: Zwift profile privacy

The most common cause is that the athlete's **Zwift profile is set to
private**. intervals.icu fetches Zwift activities via Zwift's public
profile API — if the profile is private, the import silently fails or
hangs indefinitely.

**Fix — check Zwift privacy settings:**
1. Go to **my.zwift.com** in a web browser (not the Zwift app)
2. Log in with Zwift credentials
3. Click profile picture (top right) → Settings / Profile
4. Look for **Privacy** section
5. Ensure **"Make my profile public"** (or "Public Profile") is enabled

**Verification:** Copy the Zwift profile URL (e.g.
`zwift.com/athlete/1234567`) and open it in an incognito/private window
where you are NOT logged in. If you can see activities, the profile is
public. If prompted to log in, it is private.

**Alternative — check in the Zwift app:**
1. Open Zwift app
2. Settings (gear icon)
3. Look under Profile or Privacy for a Public Profile toggle

### Other causes

- **Import still running:** "Download Old Data" runs on intervals.icu's
  server, not the athlete's computer. For athletes with extensive Zwift
  history, the import can take 12–24 hours. The "downloading in progress"
  message is legitimate — advise patience.
- **Cannot re-trigger while running:** If the athlete tries to click
  "Download Old Data" again while a download is in progress, intervals.icu
  shows "downloading in progress, please be patient." They must wait for
  the current import to finish or disconnect/reconnect Zwift.
- **Stuck import (24h+):** If import has been "in progress" for more than
  24 hours, advise the athlete to disconnect Zwift on intervals.icu
  (Settings → Integrations → Zwift → Disconnect), then reconnect and
  click "Download Old Data" again.
- **Wrong Zwift account:** Ensure the Zwift account linked to
  intervals.icu matches the athlete's actual Zwift profile. Check the
  Zwift athlete ID in the profile URL.

### Identifying Zwift-imported activities

Zwift-imported activities on intervals.icu typically appear with:
- Type: `VirtualRide`
- Name prefix: `Zwift -` followed by the Zwift activity name
- May include route name (e.g., "Tempus Fugit in Watopia")

However, not all `VirtualRide` activities are from Zwift — indoor
trainer sessions recorded via Garmin Edge (with Wahoo or other smart
trainers) also classify as VirtualRide. **Ask the athlete to confirm
the source** before assuming Zwift import is working.

## Common causes of genuinely missing activities

1. **Garmin Edge battery died mid-ride** — ride saved locally but never
   uploaded to Garmin Connect
2. **Manual activities** — if the athlete logs a ride manually in Garmin
   Connect without a .fit file, intervals.icu may not sync it
3. **GPS signal loss** — ride recorded but too short/corrupted to sync
4. **Strava deauthorization** — if `strava_authorized` is `False`,
   activities that used to sync via Strava will no longer appear
5. **Genuine rest periods** — most "gaps" are real rest, not sync failures

## When you cannot resolve it

If sync settings look correct and CTL shows genuine jumps without
corresponding activities, the issue is on Garmin's side. Ask the athlete
to:
1. Open Garmin Connect and verify the missing activity exists there
2. Check if the activity has a .fit file (not a manual entry)
3. Force a manual sync in Garmin Connect → Settings → Garmin Sync
4. Check intervals.icu web UI directly to see if the activity appears there
   but not via the API (rare but possible)