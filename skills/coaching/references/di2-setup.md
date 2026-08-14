# Shimano Di2 Setup Guide

Quick reference for helping athletes configure Di2 electronic shifting, developed during
a live troubleshooting session.

## Synchro Shift S2 — Single-side Shifting

**Goal:** Shift only with right-hand buttons. Front derailleur moves automatically to
avoid cross-chain. Left-hand buttons become free for Garmin page control or other uses.

### Activation Path (priority order)

1. **Via Garmin Edge (easiest, works without hoods button):**
   - Menu → Sensors → Di2 → Shift Mode → S2 (Synchro Shift 2)
   - S2 is preferred over S1: it waits longer before front shifts, minimizing cross-chain

2. **Via hoods button (if equipped):**
   - Double-click the small round button on top/inside of LEFT hoods
   - Overlay pops up on Garmin showing M → S1 → S2
   - Stop at S2
   - NOT ALL Di2 setups have this button — check first, don't assume

3. **Via E-Tube app:**
   - Connect to bike (wake system by turning crankarm backward)
   - On main/dashboard screen, look for "Shift Mode" dropdown
   - Select S2
   - Note: Customize → Shift → Synchronized Shift is CONFIGURATION, not activation
   - If E-Tube keeps disconnecting: wake bike by shifting a gear, keep tapping a button
     every ~25 seconds while navigating

### Cross-Chain Prevention (S2 Map Configuration)

Under Customize → Shift → Synchronized Shift → tap S2 row:
- Set cassette range and tooth count
- Default S2 map already prevents large-large and small-small combos
- Verify: largest 3 cassette cogs should NOT be reachable on big ring, smallest 3 on small ring

## Bell/Ringklocka via Garmin

**Goal:** Map a hoods button to trigger Garmin's bell sound.

### Mapping (done in Garmin, NOT E-Tube)

1. E-Tube: confirm the desired button is set to **D-Fly Ch.1** or **Ch.2** (this is default)
2. Garmin: Menu → Sensors → Di2 → scroll to **D-Fly Channel 1** (or 2) → select **Bell**
3. Ensure Garmin has sounds enabled under Audio/Sound Settings

The button function is configured on the GARMIN side, not in E-Tube. E-Tube only
determines which D-Fly channel the button sends on.

## Switch Settings (E-Tube)

Customize → Shift → Switch shows button mappings for MANUAL mode (M). These are
irrelevant when Synchro Shift is active — front shift buttons are ignored and
the system handles everything.

## Pitfalls

- **E-Tube disconnects rapidly** — Di2 sleeps after ~30s of inactivity. Wake it by
  shifting a gear or rotating the crankarm backward. Keep tapping a button while
  navigating the app.
- **Customize ≠ Activate** — "Synchronized Shift" under Customize only configures HOW
  S2 behaves. To turn it ON, use Garmin or the hoods button or the E-Tube dashboard.
- **Don't assume the hoods button exists** — some Di2 setups omit it. Always ask what the
  athlete sees before giving button-based instructions. Fall back to Garmin activation.
- **Right hoods button = D-Fly Ch.2 by default** (left = Ch.1). When mapping bell,
  check which channel the athlete's desired button is on.
- **Synchro Shift is per-bike** — must be configured separately on each bike. BMC and
  Pinarello need independent setup even with same Garmin head unit.

## Quick Setup Checklist (new bike)

1. Wake Di2 (crank turn + shift)
2. Garmin → Sensors → Di2 → Shift Mode → S2
3. Garmin → Sensors → Di2 → D-Fly Ch.2 → Bell
4. Verify: ride around block, confirm front shifts auto, bell works
