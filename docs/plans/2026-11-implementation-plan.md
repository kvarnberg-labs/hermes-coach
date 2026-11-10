# Implementation plan — 2026-11

Decisions taken in the 2026-11-10 grill session, with the evidence that drove
them. Each phase must clear its exit gate before the next starts; each PR is
reviewed by an independent agent before merge.

Sources of record:
- `outputs/hermes-knowledge-vs-tools-vs-evals.md` — knowledge vs tools vs evals
- `outputs/model-selection-evidence-review.md` — model tiers by role
- `outputs/hermes-context-management-advisory-2026-11-10.md` — context levers
- `experiments/context_budget_calc.py` — the arithmetic behind those numbers

## Phase 0 — Discord tool surface (done)

`platform_toolsets.discord` replaced the inert `tools.discord.enabled`. DM
requests now carry coaching toolsets only. Self-improve delivers to the
operator's DM instead of guild `#general`. `scan-signals.sh` worklog block
capped at 4 KB.

Exit gate: after deploy, `hermes config get platform_toolsets` returns a list
and a live DM request carries ~20 tools, not 54.

## Phase 1 — coaching-decision eval

The repo can only grade output corruption today (18 cases in
`tests/golden/cases.yaml`). Nothing grades a coaching *decision*, so the
self-improvement loop optimises the only thing it can measure.

- `tests/golden/decisions/*.yaml` — 10–20 trajectory cases. Operator-owned and
  loop-immutable, same rule as `tests/golden/cases.yaml`. Case = frozen real
  tool payloads from `state.db` (anonymised) + a written athlete line +
  `expect` predicates + `failure_class`.
- `scripts/eval_decisions.py` — runner. Never in CI (costs a model call per
  case); weekly cron writes failures to `loops/signals/`.
- Predicates are mechanical and gate pass/fail: `identity_before_data`,
  `wellness_before_readiness_claim`, `no_write_without_approval`,
  `referral_on_red_flag`, `no_coding_tools_in_dm`.
- An LLM judge may summarise *why* a case failed, as a non-gating report only.
  It must not be deepseek judging deepseek — use mimo-v2.6-flash or gpt-6-luna.
- Publish a variance baseline: run twice on identical inputs, count predicate
  flips. A predicate that flips is not a gate.

Exit gate: pass rate + variance per predicate exist on disk.

## Phase 2 — tool capability (gated on Phase 1)

In the research's ranked order: `get_athlete_state` (CTL/ATL/TSB, ramp, HRV
trend, provenance in one call) → data-provenance verifier → deterministic
metric library + unit tests → plan validator. Tool consolidation after the eval
shows it is not worse.

Stop rule: a new tool that cuts no ≥10 eval points and no ≥30% tokens is killed.

## Phase 3 — context, one lever per PR

Order and caps from the context advisory:
1. Tool-result caps at append time — 12k default, 16k `read_file`, 24k
   `skill_view`, 15k knowledge, 8k `terminal`. Expected −35.5% on a long DM.
2. Memory block moved after the static prefix, append-only per session.
3. Hard-cap `_within_budget` (`plugins/training/coaching.py`) — it currently
   always keeps the best section regardless of size, so `exercise_database`
   (25,556 chars) bypasses the 15k cap.
4. Compaction — last, its own week, never in the same PR as (1), because it
   mutates the cached prefix and has never executed on this deployment.

Do not: inline `coach-brain/` (37.5k tokens/request for 85 calls in 4 months),
strip `reasoning_content` before verifying the provider's tool-call protocol,
trim functional input schemas, or compact cron sessions.

## Phase 4 — loop contract and model

- `scripts/pr_guard.py`: a `coach-brain/` edit must cite a signal path or a
  decision-case id. Knowledge without a traced failure is refused.
- Self-improve cron runs `deepseek-v4-pro`, still 11:00 UTC (outside the
  Mon–Fri 06:00–10:00 UTC 2× window).
- Corpus work is curation only: consolidate and lint for contradictions, no new
  files, until a traced eval failure proves no tool can compute the fact.

## Phase 5 — hygiene

- `loops/worklog.md` is 437 KB at ~4 KB/day in production; needs rotation.
- `loops/signals/` lives only on the PVC, so PR bodies cite paths no reviewer
  can open; needs committing.

## Open, operator-owned

- Whether compaction ever ships.
- Who writes the case labels. The drafts are proposals until the operator signs
  them off.
