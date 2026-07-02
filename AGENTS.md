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

Use `curl` with a fine-grained repo-scoped token for `kvarnberg-labs/hermes-coach`.

**Important:** Cron terminal sandboxes may strip env-var expansion. Resolve the token like this first:

```sh
TOKEN="$(printenv GITHUB_TOKEN 2>/dev/null)"
[ -n "$TOKEN" ] || TOKEN="$(cat /opt/data/.github_token 2>/dev/null)"
```

If both are empty, output the proposed diff to ops Discord instead and note that a human must apply it.

```sh
# 1. Create branch
curl -sX POST https://api.github.com/repos/kvarnberg-labs/hermes-coach/git/refs \
  -H "Authorization: Bearer $TOKEN" \
  -d "{\"ref\":\"refs/heads/improve/<slug>\",\"sha\":\"<base-sha>\"}"

# 2. Get current file SHA (needed to update)
curl -s https://api.github.com/repos/kvarnberg-labs/hermes-coach/contents/coach-brain/<file>.yaml \
  -H "Authorization: Bearer $TOKEN" | python3 -c "import sys,json; print(json.load(sys.stdin)['sha'])"

# 3. Update file (base64-encode content first)
curl -sX PUT https://api.github.com/repos/kvarnberg-labs/hermes-coach/contents/coach-brain/<file>.yaml \
  -H "Authorization: Bearer $TOKEN" \
  -d "{\"message\":\"improve: <title>\",\"content\":\"<base64>\",\"sha\":\"<file-sha>\",\"branch\":\"improve/<slug>\"}"

# 4. Open PR
curl -sX POST https://api.github.com/repos/kvarnberg-labs/hermes-coach/pulls \
  -H "Authorization: Bearer $TOKEN" \
  -d "{\"title\":\"improve: <title>\",\"body\":\"<body>\",\"head\":\"improve/<slug>\",\"base\":\"main\"}"
```

Do not use git clone/push inside the loop. Use the GitHub REST API only.
