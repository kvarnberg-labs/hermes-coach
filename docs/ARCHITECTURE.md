# Hermes Coach — Architecture

## Overview

Hermes Coach is a multi-user endurance coaching agent built on [hermes-agent](https://github.com/NousResearch/hermes-agent). It runs as a Discord bot that connects to [intervals.icu](https://intervals.icu) to retrieve athlete training data, then uses that data to deliver evidence-based coaching recommendations.

**Key design principle:** The coach brain (domain knowledge) is decoupled from the agent core. Knowledge lives in versioned YAML files, not in the system prompt. This preserves per-conversation prompt caching while keeping coaching advice consistent and updatable.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│ Discord Server                                                   │
│                                                                  │
│  #coach channel  ←→  Hermes Gateway (Discord adapter)           │
│                                                                  │
└────────────────────────────┬─────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ Hermes Pod (hermes namespace)                                    │
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────┐   │
│  │  AIAgent     │    │  Plugin      │    │  Coach Brain     │   │
│  │  (core)      │◄──►│  Registry    │    │  (YAML files)    │   │
│  └──────────────┘    └──────┬───────┘    └──────────────────┘   │
│                             │                                    │
│                    ┌────────┴────────┐                           │
│                    │  Training Tools │                           │
│                    ├─────────────────┤                           │
│                    │ intervals_icu   │ → intervals.icu API       │
│                    │ weather         │ → Open-Meteo API          │
│                    │ coaching        │ → coach-brain YAML        │
│                    │ onboarding      │ → credential storage      │
│                    │ sandbox_client  │ → k8s Jobs (hermes-sandbox)│
│                    └─────────────────┘                           │
│                                                                  │
│  PVC: /opt/data (20Gi, local-path)                               │
│    ├── coach-brain/        (synced from image at startup)        │
│    ├── skills/             (coaching skill)                      │
│    ├── users/<discord_id>/ (credentials, cache)                  │
│    └── plugins/generated/  (autonomously developed tools)        │
└────────────────────────────┬─────────────────────────────────────┘
                             │ k8s API (sandbox Jobs)
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ Hermes-Sandbox Pod (hermes-sandbox namespace)                    │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Isolated Python container (network: default-deny-all)   │   │
│  │  Runs pytest on submitted tool code + tests              │   │
│  │  Resources: 250m CPU, 256Mi RAM, 60s hard deadline      │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

## Component Breakdown

### 1. Hermes Agent Core (base image)

The base image `ghcr.io/nousresearch/hermes-agent:main` provides:
- **AIAgent**: Core conversation loop with tool calling, prompt caching, context management
- **Gateway**: Multi-platform messaging adapter (Discord, Telegram, Slack, etc.)
- **Plugin system**: Runtime discovery of tools via `ctx.register_tool()`
- **Memory**: SQLite-backed session store with FTS5 search
- **Skills**: Instruction files loaded as user messages (preserves prompt caching)

### 2. Training Plugin (`plugins/training/`)

Five modules, each registering tools with the Hermes plugin context:

| Module | Tools | Purpose |
|--------|-------|---------|
| `intervals_icu.py` | 6 tools | Fetch athlete data from intervals.icu API |
| `weather.py` | 1 tool | Open-Meteo forecast (free, no key) |
| `coaching.py` | 1 tool | Retrieve coach-brain knowledge by topic |
| `onboarding.py` | 1 tool | `/start` flow for connecting intervals.icu |
| `sandbox_client.py` | 1 tool | Autonomous tool development via k8s Jobs |

**Tool registration pattern:**
```python
def register_tools(ctx) -> None:
    ctx.register_tool(
        name="tool_name",
        toolset="training",
        schema={...},  # OpenAI-compatible tool schema
        handler=lambda args, **kw: tool_fn(...),
    )
```

### 3. Coach Brain (`coach-brain/`)

Structured coaching knowledge in YAML files. Loaded at runtime by `coaching.py`:

| File | Content |
|------|---------|
| `training-philosophies.yaml` | Training models, periodization, intensity zones |
| `recovery-heuristics.yaml` | TSB, HRV, sleep, fatigue management |
| `workout-library.yaml` | Session templates, race prep, tapering |
| `injury-return.yaml` | Return-to-training protocols, red flags |
| `nutrition.yaml` | Macros, hydration, intra-workout fueling |

**Sync mechanism:** At container startup, `docker/sync-coach-assets.sh` (cont-init.d/05) copies YAML files from the baked image path (`/opt/hermes/coach-brain/`) to the PVC (`$HERMES_HOME/coach-brain/`). The `-n` flag on `cp` preserves user edits across deployments.

### 4. Coaching Skill (`skills/coaching/SKILL.md`)

Hermes skill file that instructs the agent how to use coaching tools. Loaded automatically when the user is in the `#coach` Discord channel (configured via `DISCORD_FREE_RESPONSE_CHANNELS`).

### 5. Sandbox (`sandbox/`)

Isolated environment for autonomous tool development:
- Minimal Python 3.13-slim image with pytest
- NetworkPolicy: default-deny-all (no internet access)
- Resource limits: 250m CPU, 256Mi RAM, 60s deadline
- Read-only root filesystem except `/tmp`

## Data Flow

### Coaching Request Flow

1. User sends message in `#coach` on Discord
2. Discord gateway routes to Hermes agent
3. Agent loads coaching skill (channel-specific)
4. Agent calls `get_wellness(discord_id)` → intervals.icu API (cached 15min)
5. Agent calls `get_coaching_knowledge("threshold intervals")` → coach-brain YAML
6. Agent synthesizes advice from athlete data + coach-brain principles
7. Response sent to Discord

### Onboarding Flow

1. User runs `/start` in Discord
2. Agent calls `coach_onboard(discord_id, athlete_id, api_key)`
3. Credentials validated against intervals.icu API
4. Credentials stored in `$HERMES_HOME/users/<discord_id>/intervals_key` (mode 0600)
5. Athlete ID stored in `$HERMES_HOME/users/<discord_id>/intervals_athlete_id`

### Sandbox Tool Development Flow

1. Agent identifies capability gap during coaching
2. Agent calls `develop_tool(name, description, code, test_code)`
3. `sandbox_client.py` creates k8s Job in `hermes-sandbox` namespace
4. Job decodes base64 code/tests, runs pytest in isolated container
5. If tests pass: tool written to `$HERMES_HOME/plugins/generated/`
6. If tests fail: output returned to agent for iteration
7. Generated tools persist on PVC across restarts

## Configuration

### Environment Variables (ConfigMap)

| Variable | Purpose |
|----------|---------|
| `HERMES_HOME` | Data directory (`/opt/data`) |
| `HERMES_INFERENCE_PROVIDER` | LLM provider (`opencode-go`) |
| `HERMES_INFERENCE_MODEL` | Primary model (`deepseek-v4-pro`) |
| `HERMES_INFERENCE_BASE_URL` | Model API endpoint |
| `API_SERVER_ENABLED` | Enable health probe endpoint |
| `API_SERVER_PORT` | Health probe port (`8642`) |
| `DISCORD_REQUIRE_MENTION` | Not needed in DM-only mode (`false`) |
| `DISCORD_ALLOWED_USERS` | Space-separated Discord user IDs allowed to use the bot (in sealed secret) |

### Hermes Config (set by initContainer)

Set via `hermes config set` commands in the deployment initContainer:
- `model.provider`, `model.default`, `model.base_url`
- `auxiliary.<task>.provider/model/base_url` (cheap model for side tasks)
- `tools.discord.enabled` → `["training","weather","memory","skills","clarify"]`
- `memory.memory_char_limit` → 8000
- `memory.user_char_limit` → 12000
- `tool_loop_guardrails.hard_stop_enabled` → true

## Security Model

### Namespace Isolation

| Namespace | Purpose | Network Access |
|-----------|---------|----------------|
| `hermes` | Main agent pod | HTTPS + k8s API + DNS |
| `hermes-sandbox` | Isolated tool testing | None (default-deny-all) |

### RBAC

| Service Account | Namespace | Permissions |
|-----------------|-----------|-------------|
| `hermes-autonomy` | `hermes` | Leases (coordination lock) |
| `hermes-autonomy` | `hermes-sandbox` | Jobs CRUD, Pods/Logs read |

### Secrets

- Discord bot token: SealedSecret (`hermes-discord-secret`)
- Model API key: SealedSecret (`hermes-model-secret`)
- intervals.icu keys: Per-user files on PVC (mode 0600)

## Deployment

Flux CD watches `clusters/coach/` on the `main` branch. Push to deploy:
```bash
git push origin main
# Flux reconciles within 1 minute
```

See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed setup instructions.
