# Development Guide

## Prerequisites

- Python 3.13+ (pyenv recommended)
- Docker (for building the image)
- kubectl + k3s (for local cluster testing)
- Flux CLI (for GitOps management)

## Local Development

### 1. Clone and Set Up

```bash
git clone git@github.com:kvarnberg-labs/hermes-coach.git
cd hermes-coach
```

### 2. Run Tests

```bash
# All tests
PYTHONPATH=plugins python -m pytest tests/ -v --import-mode=importlib

# Single test file
PYTHONPATH=plugins python -m pytest tests/test_coaching.py -v

# Single test
PYTHONPATH=plugins python -m pytest tests/test_coaching.py::TestLoadAll::test_loads_single_yaml -v
```

Tests are hermetic — they do not require network access, API keys, or a running cluster. All external dependencies are mocked.

### 3. Build Docker Image

```bash
# Build locally
docker build -t ghcr.io/kvarnberg-labs/hermes-coach:dev .

# Build with specific base image (pin to a known-good SHA)
docker build --build-arg BASE_IMAGE=ghcr.io/nousresearch/hermes-agent@sha256:abc123 \
  -t ghcr.io/kvarnberg-labs/hermes-coach:dev .
```

### 4. Run Locally (Docker Compose)

```bash
# Create .env from example
cp .env.example .env
# Fill in DISCORD_BOT_TOKEN, OPENCODE_GO_API_KEY

# Start services
docker compose up -d

# View logs
docker compose logs -f hermes
```

## Plugin Development

### Adding a New Tool

1. Create `plugins/training/your_tool.py`:
```python
from __future__ import annotations
import json
from typing import Any

def your_function(param: str, **_: Any) -> str:
    """Your tool logic here. Must return a JSON string."""
    return json.dumps({"result": f"Processed: {param}"})

def register_tools(ctx) -> None:
    ctx.register_tool(
        name="your_tool",
        toolset="training",
        schema={
            "name": "your_tool",
            "description": "What this tool does.",
            "parameters": {
                "type": "object",
                "properties": {
                    "param": {
                        "type": "string",
                        "description": "Parameter description.",
                    }
                },
                "required": ["param"],
            },
        },
        handler=lambda args, **kw: your_function(param=args["param"]),
    )
```

2. Register in `plugins/training/__init__.py`:
```python
from .your_tool import register_tools as register_your_tool
# ... in register(ctx):
register_your_tool(ctx)
```

3. Write tests in `tests/test_your_tool.py`:
```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "plugins"))

from training.your_tool import your_function

def test_your_function():
    result = your_function("test")
    assert "Processed: test" in result
```

4. Run tests:
```bash
PYTHONPATH=plugins python -m pytest tests/test_your_tool.py -v
```

### Toolset Registration

Tools are grouped into toolsets. The training plugin uses two toolsets:
- `training` — intervals.icu tools, coaching knowledge, onboarding, sandbox
- `weather` — Open-Meteo weather tool

Toolsets are enabled per-platform in the Hermes config:
```yaml
tools:
  discord:
    enabled: ["training", "weather", "memory", "skills", "clarify"]
```

### Service-Gated Tools

If a tool should only appear when a prerequisite is configured, use `check_fn`:
```python
def check_fn() -> bool:
    return bool(os.getenv("SOME_API_KEY"))

ctx.register_tool(
    name="conditional_tool",
    check_fn=check_fn,
    # ...
)
```

## Coach-Brain Development

See [COACH-BRAIN.md](COACH-BRAIN.md) for the knowledge file format and extension guide.

## Sandbox Development

See [SANDBOX.md](SANDBOX.md) for the isolated tool development system.

## CI/CD

The GitHub Actions workflow (`.github/workflows/build.yml`) runs:

1. **test**: Run pytest on all test files
2. **build**: Build and push Docker image to GHCR (on push to main only)

Tests run with `PYTHONPATH=plugins` so plugin modules are importable.

## Git Workflow

This repo is a fork of `NousResearch/hermes-agent` with custom additions. To rebase onto upstream:

```bash
# Add upstream remote (if not already added)
git remote add upstream git@github.com:NousResearch/hermes-agent.git

# Fetch upstream
git fetch upstream main

# Rebase, preserving local commits
git rebase upstream/main main

# Resolve conflicts, preserving Hermes Coach customizations
# Key files to preserve: plugins/training/, coach-brain/, apps/hermes/

# Force push after successful rebase
git push --force-with-lease origin main
```

## Troubleshooting

### Tests fail with ImportError

Ensure `PYTHONPATH=plugins` is set:
```bash
PYTHONPATH=plugins python -m pytest tests/ -v --import-mode=importlib
```

### Docker build fails on base image

Pin to a specific SHA:
```bash
docker build --build-arg BASE_IMAGE=ghcr.io/nousresearch/hermes-agent@sha256:abc123 .
```

### Plugin not discovered at runtime

Check that `__init__.py` calls `register(ctx)` and that the plugin directory is in `$HERMES_HOME/plugins/` or `/opt/hermes/plugins/`.

### Coach-brain not loaded

Check that `docker/sync-coach-assets.sh` ran successfully at container startup:
```bash
kubectl logs <hermes-pod> -c cont-init | grep coach
```

Verify files exist on PVC:
```bash
kubectl exec -it <hermes-pod> -- ls -la /opt/data/coach-brain/
```
