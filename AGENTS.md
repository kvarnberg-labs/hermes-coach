# Hermes Coach — Agent Reference

This file is loaded by the self-improvement cron loop (`--workdir /opt/data` injects it).
It orients agents working on this codebase.

## What is this?

Hermes Coach is an AI endurance cycling coach on Discord. It runs as a k8s Deployment
(k3s on Hetzner) managed by Flux CD (GitOps). Athletes message the bot via Discord DMs,
it reads their intervals.icu training data, and gives evidence-based coaching advice.

Source: `github.com/kvarnberg-labs/hermes-lab`

## Repo layout

```
apps/hermes/            k8s manifests (Deployment, NetworkPolicy, Secrets, ConfigMaps)
apps/hermes-sandbox/    k8s manifests for the sandbox Job namespace
plugins/training/       training plugin source
  intervals_icu.py      intervals.icu HTTP API integration (6 tools)
  coaching.py           get_coaching_knowledge tool (reads coach-brain/)
  onboarding.py         coach_onboard tool (first-time setup)
  sandbox_client.py     develop_tool (toolset: self-improve, not discord)
  weather.py            weather integration
coach-brain/            YAML knowledge files consumed by get_coaching_knowledge()
skills/                 Hermes skill files synced to /opt/data/skills/ at startup
  coaching/SKILL.md     coaching instructions loaded in the #coach channel
  self-improvement/SKILL.md  this cron loop's instructions (READ THIS)
loops/                  self-improvement loop infrastructure
  self-improve/CONTRACT.md  loop contract — READ FIRST every run
  worklog.md            append-only log — read last 10 entries before major changes
  signals/              open gap reports from coaching sessions
scripts/
  scan-signals.sh       discovery script injected by the cron trigger
docker/
  sync-coach-assets.sh  syncs image assets → /opt/data/ at container start
Dockerfile              image definition
tests/                  pytest suite
```

## Key rules

- **Knowledge changes**: edit `coach-brain/*.yaml` only.
- **New tools**: use `develop_tool` (toolset `self-improve`); it runs sandbox pytest first.
- **Deploy path**: `git push → Flux detects → applies manifests → pod restarts`.
- **Never mutate live pod plugins directly**. Changes go through PRs.

## Running tests

```sh
PYTHONPATH=plugins python -m pytest tests/ -q --import-mode=importlib
```

## Creating a GitHub PR (in the loop)

Use the helper script — it handles token resolution, branch creation, file upload, and PR opening in one call:

```sh
sh /opt/data/scripts/create-pr.sh <file-path> <branch-slug> <pr-title> [pr-body]
```

Arguments:
- `file-path` — path relative to repo root, e.g. `coach-brain/heat.yaml`
- `branch-slug` — short identifier, e.g. `add-heat-knowledge`
- `pr-title` — must start with `improve: `
- `pr-body` — optional; defaults to the title

The file must exist at `$HERMES_HOME/<file-path>` (i.e. `/opt/data/<file-path>`).
The script reads the token from `GITHUB_TOKEN` env or `/opt/data/.github_token`.
It exits 0 and prints the PR URL on success, exits 1 with a clear error on failure.

Example:
```sh
sh /opt/data/scripts/create-pr.sh \
  coach-brain/heat.yaml \
  add-heat-knowledge \
  "improve: heat acclimatization knowledge" \
  "Adds heat.yaml. Evidence: Lorenzo et al. (2010)."
```

If the script fails (no token, API error), output the proposed diff to ops Discord and note that a human must apply it.
