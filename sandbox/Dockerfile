# Sandbox runner — minimal Python image for isolated tool testing.
# Network-isolated by k8s NetworkPolicy (default-deny-all in hermes-sandbox ns).
# Read-only root filesystem except /tmp.

FROM python:3.13-slim

# Install pytest (only runtime dependency)
RUN pip install --no-cache-dir pytest && \
    rm -rf /root/.cache

# Non-root user
RUN groupadd -g 1000 runner && useradd -u 1000 -g runner -m runner
USER runner

WORKDIR /tmp

# Default command — overridden by k8s Job manifest
ENTRYPOINT ["python", "-m", "pytest", "-v", "--tb=short", "--import-mode=importlib"]
