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

# Ensure user plugins directory exists (Hermes discovers plugins from here)
mkdir -p "${HERMES_HOME}/plugins"
chown -R hermes:hermes "${HERMES_HOME}/coach-brain" \
  "${HERMES_HOME}/plugins" 2>/dev/null || true
