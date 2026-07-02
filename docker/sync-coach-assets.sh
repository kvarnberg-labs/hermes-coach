#!/bin/sh
# Syncs coach assets from the baked image paths to /opt/data so Hermes
# picks them up at runtime. Runs as cont-init.d/05 (after stage2-hook).
set -eu

HERMES_HOME="${HERMES_HOME:-/opt/data}"

# Sync coach-brain knowledge files
if [ -d /opt/hermes/coach-brain ]; then
  mkdir -p "${HERMES_HOME}/coach-brain"
  cp -rn /opt/hermes/coach-brain/. "${HERMES_HOME}/coach-brain/"
fi

# Sync coaching skill (only if not already present, so user edits survive)
if [ -d /opt/hermes/coach-skills ]; then
  mkdir -p "${HERMES_HOME}/skills"
  for skill_dir in /opt/hermes/coach-skills/*/; do
    skill_name="$(basename "$skill_dir")"
    dest="${HERMES_HOME}/skills/${skill_name}"
    if [ ! -d "$dest" ]; then
      cp -r "$skill_dir" "$dest"
      echo "Installed coach skill: ${skill_name}"
    fi
  done
fi

# Sync AGENTS.md for the self-improvement cron loop workdir.
# Always overwrite so changes committed to the image are picked up.
if [ -f /opt/hermes/AGENTS.md ]; then
  cp /opt/hermes/AGENTS.md "${HERMES_HOME}/AGENTS.md"
fi

# Sync self-improvement loop files — CONTRACT.md is read by the cron agent every run.
# Worklog and signals are runtime-written; only seed them if absent.
if [ -f /opt/hermes/loops/self-improve/CONTRACT.md ]; then
  mkdir -p "${HERMES_HOME}/loops/self-improve" "${HERMES_HOME}/loops/signals"
  cp /opt/hermes/loops/self-improve/CONTRACT.md \
     "${HERMES_HOME}/loops/self-improve/CONTRACT.md"
  echo "Synced loops/self-improve/CONTRACT.md"
  if [ ! -f "${HERMES_HOME}/loops/worklog.md" ]; then
    printf '# Self-Improvement Worklog\n\n' > "${HERMES_HOME}/loops/worklog.md"
  fi
fi

# Ensure user plugins directory exists (Hermes discovers plugins from here)
mkdir -p "${HERMES_HOME}/plugins"
chown -R hermes:hermes "${HERMES_HOME}/coach-brain" \
  "${HERMES_HOME}/plugins" 2>/dev/null || true
