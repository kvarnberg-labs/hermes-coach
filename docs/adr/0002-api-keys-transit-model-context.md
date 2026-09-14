# ADR 0002 — Athlete API keys transit the model context (accepted risk)

Status: Accepted 2026-09-14 (ruling delegated to the implementing agent by the
Lead; reopen by editing this ADR if the threat model changes).

## Context

`coach_onboard` (plugins/training/onboarding.py) collects the athlete's
intervals.icu `athlete_id` and `api_key` through the DM conversation. The
model emits them as **tool-call arguments**, which means the key:

1. is part of the prompt sent to the model provider (opencode.ai),
2. is persisted by the hermes-agent gateway in the conversation transcript
   (`state.db`) — the exact storage format of tool-call args is
   gateway-owned and not verifiable from this repo,
3. is written by the plugin to the PVC as a plaintext chmod-0600 file
   (`_credentials.store_user_credentials`).

Facts established during the 2026-09 audit:

- The tool's *response* never echoes the key (onboarding.py:86–101).
- `scripts/scan-signals.sh` reads `messages` rows (role `user`/`tool`) from
  the same `state.db`; any key-bearing argument storage is within its reach,
  though no specific query there is known to surface the key.
- Mitigations already in place: `DISCORD_ALLOWED_USERS` allowlist, DM-only
  bot, per-user credential isolation (PR #32 removed the shared fallback),
  `verify_athlete_identity` at session start, and the onboarding response's
  `security_note` asking the athlete to delete the key-bearing Discord
  message.

## Decision

**Accept the risk for this deployment.**

- Redaction-at-persistence belongs to the hermes-agent gateway (base image),
  not this repo; we cannot fix it here.
- The in-repo alternative — moving key collection out of model-visible
  arguments (DM attachment or slash-command flow) — changes the athlete UX
  and depends on gateway features, for a single-tenant, allowlisted,
  low-adversary-interest threat model.

## Alternatives considered

- **Gateway-side tool-arg redaction** — right layer, wrong repo. File an
  upstream feature request with hermes-agent instead (optional follow-up).
- **Onboarding via non-model channel** — rejected for now: UX cost and
  gateway dependency outweigh the marginal exposure reduction given the
  allowlist and single-tenant PVC.

## Consequences

- The key's confidentiality rests on: the model provider's handling of
  prompts, the PVC's access control, and the gateway's transcript storage.
- Revisit this ADR if any of these change: multi-tenant deployment, a
  provider change, or the bot gaining channel (non-DM) surfaces.
- Related hardening already merged alongside this ADR: key files documented
  honestly as plaintext (the "(age-encrypted)" docstring claim was false and
  has been corrected), and `develop_tool` gained a mechanical static guard
  so generated code cannot read credential files via `os`/`subprocess`.
