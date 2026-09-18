#!/bin/sh
# Syncs coach assets from the baked image paths to /opt/data so Hermes
# picks them up at runtime. Runs as cont-init.d/05 (after stage2-hook).
set -eu

HERMES_HOME="${HERMES_HOME:-/opt/data}"
# Image root holding the baked coach assets. Overridable so tests can run
# the sync against a temp tree instead of the real /opt/hermes.
IMAGE_ROOT="${COACH_IMAGE_ROOT:-/opt/hermes}"

# Sync coach-brain knowledge files.
# The image copy is the source of truth (built from main). The PVC copy can
# drift ahead ONLY via runtime-state edits (e.g. a cron agent fixing a stale
# YAML directly on the PVC). Mirror the image into the PVC so merged updates
# to EXISTING files propagate: `cp -rn` (no-clobber) skipped files that
# already existed, so a merged edit to a coach-brain YAML was never applied
# to a long-lived PVC — the pod then served stale knowledge indefinitely
# (live instance: training-philosophies.yaml served without norwegian_singles
# for weeks after the update merged). Per-file copy makes the image win for
# every file it ships; PVC-only files (runtime-added, not in the image) are
# untouched by this loop and survive.
if [ -d ${IMAGE_ROOT}/coach-brain ]; then
  mkdir -p "${HERMES_HOME}/coach-brain"
  for f in ${IMAGE_ROOT}/coach-brain/*.yaml; do
    [ -e "$f" ] || continue
    name="$(basename "$f")"
    dest="${HERMES_HOME}/coach-brain/${name}"
    if [ -f "$dest" ] && ! cmp -s "$f" "$dest"; then
      echo "Updating coach-brain/${name} (image newer than PVC copy)"
    fi
    cp "$f" "$dest"
  done
fi

# Sync bot-facing skills: the image is the source of truth (built from main).
# - Mirror shipped skills into the PVC so merged updates propagate. The old
#   install-only-if-absent skipped existing dirs, so a restructured SKILL.md
#   never reached a long-lived PVC (same bug class the coach-brain sync fixed).
# - Prune skill dirs the image no longer ships: stale rollout artifacts and
#   runtime skills-hub installs (re-installable on demand). This is what
#   keeps the athlete-session <available_skills> index lean.
if [ -d ${IMAGE_ROOT}/coach-skills ]; then
  mkdir -p "${HERMES_HOME}/skills"
  for skill_dir in ${IMAGE_ROOT}/coach-skills/*/; do
    [ -d "$skill_dir" ] || continue
    skill_name="$(basename "$skill_dir")"
    dest="${HERMES_HOME}/skills/${skill_name}"
    rm -rf "$dest"
    cp -r "$skill_dir" "$dest"
    echo "Synced coach skill: ${skill_name}"
  done
  for dest_dir in "${HERMES_HOME}/skills"/*/; do
    [ -d "$dest_dir" ] || continue
    skill_name="$(basename "$dest_dir")"
    if [ ! -d "${IMAGE_ROOT}/coach-skills/${skill_name}" ]; then
      rm -rf "$dest_dir"
      echo "Pruned skill not shipped by image: ${skill_name}"
    fi
  done
fi

# Sync AGENTS.md for the self-improvement cron loop workdir.
# Always overwrite so changes committed to the image are picked up.
if [ -f ${IMAGE_ROOT}/AGENTS.md ]; then
  cp ${IMAGE_ROOT}/AGENTS.md "${HERMES_HOME}/AGENTS.md"
fi

# Sync self-improvement loop files — CONTRACT.md is read by the cron agent every run.
# Worklog and signals are runtime-written; only seed them if absent.
if [ -f ${IMAGE_ROOT}/loops/self-improve/CONTRACT.md ]; then
  mkdir -p "${HERMES_HOME}/loops/self-improve" "${HERMES_HOME}/loops/signals"
  cp ${IMAGE_ROOT}/loops/self-improve/CONTRACT.md \
     "${HERMES_HOME}/loops/self-improve/CONTRACT.md"
  echo "Synced loops/self-improve/CONTRACT.md"
  if [ ! -f "${HERMES_HOME}/loops/worklog.md" ]; then
    printf '# Self-Improvement Worklog\n\n' > "${HERMES_HOME}/loops/worklog.md"
  fi
fi

# Sync the training plugin: the image is the source of truth (built from main).
# Hermes discovers plugins from BOTH the bundled dir (<image root>/plugins) and
# ${HERMES_HOME}/plugins (user), and the user copy wins on a name collision
# (`hermes plugins list` reports training as Source: user). Nothing synced the
# plugin to the PVC, so a stale copy from an older deploy shadowed the image and
# a merged fix never reached the running gateway (live instance: the PVC copy was
# 3 days older than the image copy and the gateway loaded the stale one). Mirror
# the shipped files so the image wins for every file it ships; PVC-only dirs
# (generated/) are untouched.
if [ -d ${IMAGE_ROOT}/plugins/training ]; then
  mkdir -p "${HERMES_HOME}/plugins/training"
  for f in ${IMAGE_ROOT}/plugins/training/*; do
    [ -e "$f" ] || continue
    name="$(basename "$f")"
    [ "$name" = "__pycache__" ] && continue
    dest="${HERMES_HOME}/plugins/training/${name}"
    if [ -d "$f" ]; then
      rm -rf "$dest"
      cp -r "$f" "$dest"
      continue
    fi
    if [ -f "$dest" ] && ! cmp -s "$f" "$dest"; then
      echo "Updating plugins/training/${name} (image newer than PVC copy)"
    fi
    cp "$f" "$dest"
  done
fi

# Ensure user plugins directory exists (Hermes discovers plugins from here)
mkdir -p "${HERMES_HOME}/plugins"
chown -R hermes:hermes "${HERMES_HOME}/coach-brain" \
  "${HERMES_HOME}/plugins" 2>/dev/null || true
