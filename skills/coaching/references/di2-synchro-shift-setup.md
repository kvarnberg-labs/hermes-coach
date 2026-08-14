# Di2 Synchro Shift — Setup Guide

Quick reference for helping athletes configure Shimano Di2 Synchro Shift.
Applies to R9200/R8100/R7100 (12-speed). Slightly different UI for older 11-speed.

## Goal

Athlete wants to shift ONLY with right-hand buttons (up/down on cassette),
with the front derailleur handled automatically to avoid cross-chain.

## Setup via E-Tube App

### 1. Connect
- Open **E-Tube Project** or **E-Tube Ride** on phone
- Wake the bike: turn crank backward a quarter turn or shift any gear
- Pair if not already connected

### 2. Navigate to Shift Mode
Path: **Drive Unit → Shift mode settings** (NOT "Switch settings" — that's button remapping)

Three options:
| Mode | Behavior |
|------|----------|
| **Manual (M)** | Athlete controls front + rear manually (default) |
| **Synchro Shift S1** | Auto front shift — earlier shift to big ring (~mid-cassette) |
| **Synchro Shift S2** | Auto front shift — waits longer, more time on small ring, less cross-chain |
| **Semi-Synchro S1** | Athlete shifts front manually, system adjusts rear to smooth the jump |

**Recommend S2** for cross-chain avoidance — it delays the front shift until deeper in the cassette.

### 3. Customize the Shift Map (optional)
Under Synchro Shift Map, set which cassette cogs are allowed for each chainring:
- Large ring: block the 3 largest cogs (28T, 31T, 34T typically)
- Small ring: block the 3 smallest cogs (11T, 12T, 13T typically)
This is usually default for S2 but verify.

### 4. Apply
Tap **Apply** or **Save to bike**. Setting persists permanently — app not needed while riding.

## Switching Modes on the Bike (no app)

Double-click the small button on the **inside top of the left brake hood**.
Garmin displays a brief overlay: **M → S1 → S2**.

To always see current mode, add the **"Di2 Shift Mode"** data field to any Garmin screen.

## BT Disconnection Fix

E-Tube disconnects when the Di2 system goes to sleep (~30s of inactivity).
**Workaround:** keep the bike awake while navigating the app:
- Turn the crank backward slightly every 20–30 seconds
- Or tap any shift button periodically
- Each input resets the 30s sleep timer

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Can't find Synchro Shift | You're in "Switch Settings" (button remapping) — back out to "Shift mode settings" |
| E-Tube disconnects constantly | Wake bike by shifting or turning crank, then navigate faster |
| S2 active (Garmin confirms), manual front shifting works perfectly, but front derailleur NEVER auto-shifts in S2 | **Shift map allows all cassette cogs on small chainring.** Go to E-Tube → Customize → Shift → Synchronized Shift → tap S2. If all 11 cogs are white/enabled on the small ring, S2 never detects a reason to shift front — you can ride small-small indefinitely and it won't care. Fix: tap the 2–3 smallest cogs to block them (they turn grey/red), or use "Reset to default." This is the #2 most common S2 failure after "not activated." |
| S2 active but front still won't shift (full diagnostic) | **(1) Verify front derailleur works in Manual mode first:** switch Garmin to M, use left buttons — if it shifts, derailleur is fine. Skip to (2). If NOT, front derailleur has a hardware/pairing/firmware issue — fix that first. **(2) Check cassette sprocket range:** Customize → Shift → Synchronized Shift → S2 → verify tooth count matches actual cassette. If E-Tube thinks it's 11-28 but bike has 11-34, the system believes all gears fit on one ring and never triggers a front shift. **(3) Check shift map:** even if cassette range is correct, verify 2–3 smallest cogs are blocked on small ring (see row above). **(4) Software:** verify E-Tube → Customize → Shift → Synchronized Shift is toggled ON, and both derailleurs have current firmware. |
| Garmin doesn't show shift mode | Add "Di2 Shift Mode" or "Växelläge" data field |
| D-Fly channels shown in Switch settings | Normal — those are button functions in manual mode, irrelevant when Synchro is active |

## Pitfalls

- **Shift map is the silent killer.** Garmin can show S2, manual shifting works, cassette range is correct — and S2 still won't auto-shift if the shift map allows all cogs on the small ring. This is easily missed because shift map configuration is buried under Customize (not the main dashboard), and the default map can be corrupted without looking obviously wrong. Always check the shift map before concluding S2 is broken.
- **E-Tube UX is awful.** The app disconnects every 30 seconds, buries activation under a different menu than configuration, and uses confusing toggle states. Athletes frequently give up in frustration — that's normal, not a failure of instruction. If the athlete hits the wall, fall back to Garmin-only setup and skip E-Tube entirely. S2 via Garmin with default shift map works for 90% of riders.
