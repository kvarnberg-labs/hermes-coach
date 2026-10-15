# Activity sync troubleshooting — missing or empty activities

Load when an athlete says sessions are missing from intervals.icu, or activities
arrive with empty fields (no type, distance, duration or HR).

## Step 1: Is the gap real?

Pull `get_recent_activities(days=90)` and list gaps of 3+ days. Ask the athlete
what they did on those dates — most gaps are genuine rest.

## Step 2: Read CTL/ATL during the gap

`get_wellness(days=<covering the gap>)`, day by day:

- **Genuine rest:** CTL decays smoothly, ATL drops, TSB rises steadily.
- **Sync problem:** CTL flat or jumping mid-gap, ATL rising with no activity in
  the list, or TSB dropping unexpectedly.

If today's activity is missing but today's wellness already moved, widen the
window (`days=3`, no sport filter) before concluding it has not synced.

## Step 3: Check the device-side settings (ask the athlete)

The tools do not return the athlete's sync settings, so ask the athlete to
check in intervals.icu → Settings:

- Garmin: activity sync enabled, no activity-type or upload filters, and a
  recent "last upload" time.
- Strava: still authorised, if they rely on it.
- Then in Garmin Connect: the activity exists, has a recorded file (not a
  manual entry), and a manual sync has been tried.

## Step 4: Sports or names that do not fit

Activities that do not match the athlete (wrong sports, unknown names) are an
identity problem, not a sync problem: stop and follow
`references/identity-verification.md`.

## Apple Watch

Apple Watch has no direct intervals.icu integration. The reliable chain is
Apple Watch → Apple Health → HealthFit → intervals.icu. Syncing via Strava often
drops HR and detail.

**Signature of the broken Strava path:** CTL/ATL update but activities show
`type: null`, `distance_km: 0.0`, `duration_min: 0.0`, `avg_hr: null`, with
`training_load` populated. The athlete is training; you just cannot analyse it.

**Fix to recommend:** install HealthFit (one-time purchase) → Settings → sync to
intervals.icu → enable automatic upload; verify after the next session. It also
forwards HR, cadence, laps, sleep and HRV. Strava can stay for social use.
Alternatives: RunGap, HealthSync, or the Strava watch app (better than the
Health→Strava import, still less complete).

## Zwift "Download Old Data" stuck

- Most common cause: the Zwift profile is private. Ask the athlete to open
  my.zwift.com → profile → Settings/Privacy → enable the public profile, and
  test the profile URL in a private browser window.
- A first import can run 12–24 h on intervals.icu's side; "downloading in
  progress" is normal and blocks re-triggering. After 24 h+, disconnect Zwift
  in intervals.icu (Settings → Integrations), reconnect, retry.
- Check that the linked Zwift account is the athlete's.
- Not every `VirtualRide` is Zwift — Garmin Edge + smart trainer sessions are
  also `VirtualRide`. Zwift imports usually start with `Zwift -`. Ask which
  device recorded them before judging the import.

## Common causes of genuinely missing activities

Head unit battery died before upload; manual entries without a file; corrupted
or very short recordings; Strava deauthorised; genuine rest.

## When you cannot resolve it

If settings look right and CTL shows jumps without matching activities, the
problem is upstream (Garmin/Strava). Tell the athlete what you checked and ask
them to look at the intervals.icu web calendar directly.
