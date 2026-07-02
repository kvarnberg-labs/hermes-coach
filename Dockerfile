# Hermes Coach — extends the official hermes-agent image with the training plugin.
#
# Build args:
#   BASE_IMAGE  — base hermes-agent image (override to pin a specific SHA)
#
# The training plugin and coach-brain knowledge are baked into the image.
# User-specific data (API keys, workout cache) lives on the PVC at /opt/data.

ARG BASE_IMAGE=ghcr.io/johanmillberg/hermes-agent:main
FROM ${BASE_IMAGE}

# Switch to root for plugin installation
USER root

# Copy training plugin into the Hermes plugins directory so it is
# auto-discovered at gateway startup.
COPY --chown=hermes:hermes plugins/training/ /opt/hermes/plugins/training/

# Copy coach-brain knowledge files and the coaching skill.
# These live on the image so they are versioned alongside the code.
# At runtime they are also synced to /opt/data so Hermes can update them.
COPY --chown=hermes:hermes coach-brain/ /opt/hermes/coach-brain/
COPY --chown=hermes:hermes skills/ /opt/hermes/coach-skills/

# Copy sandbox runner script used by the Job containers
COPY --chown=hermes:hermes sandbox/ /opt/hermes/sandbox/

# Copy self-improvement loop scripts (scan-signals.sh, etc.)
COPY --chmod=0755 scripts/ /opt/hermes/scripts/

# Copy AGENTS.md for the cron loop workdir (synced to /opt/data at startup)
COPY --chown=hermes:hermes AGENTS.md /opt/hermes/AGENTS.md

# Install training plugin Python dependencies into the existing venv.
# httpx is already in hermes-agent; pyyaml and kubernetes are new.
RUN uv pip install --python /opt/hermes/.venv/bin/python \
    "httpx>=0.28.1,<1" \
    "pyyaml>=6.0,<7" \
    "kubernetes>=29.0.0,<32"

# stage2-hook (already in base image) runs at container start and syncs
# /opt/hermes/coach-brain → /opt/data/coach-brain and
# /opt/hermes/coach-skills → /opt/data/skills so Hermes picks them up.
# We write a cont-init.d script to do the sync.
COPY --chmod=0755 docker/sync-coach-assets.sh /etc/cont-init.d/05-sync-coach-assets

USER hermes
