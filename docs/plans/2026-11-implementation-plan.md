# Implementation plan — 2026-11

Decisions taken in the 2026-11-10 grill session, with the evidence that drove
them. Each phase must clear its exit gate before the next starts; each PR is
reviewed by an independent agent before merge.

Sources of record (operator-local, gitignored because they quote real athlete
telemetry — ask the operator for the files rather than expecting them in the repo):
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

## Phase 1 — coaching-decision eval (done 2026-11-10)

The repo could only grade output corruption (18 cases in
`tests/golden/cases.yaml`). Nothing graded a coaching *decision*, so the
self-improvement loop optimised the only thing it could measure.

- `tests/golden/decisions/*.yaml` — 12 trajectory cases. Operator-owned and
  loop-immutable, same rule as `tests/golden/cases.yaml`. Case = frozen real
  tool payloads from `state.db` (anonymised) + a written athlete line +
  `expect` predicates + `failure_class`.
- `scripts/decision_predicates.py` — two tiers, and the split is the design:
  - **GATING** (decides pass/fail): `identity_before_data`,
    `no_write_without_approval`, `no_coding_tools_in_dm`,
    `no_write_after_red_flag` (reads `red_flag: true` from the case, not the
    prose).
  - **INFORMATIONAL** (computed, reported, never gates):
    `wellness_before_readiness_claim`, `referral_on_red_flag`.
  Why: four review rounds found defects only in the prose-keyword layer, never
  in the structural layer, and the coach replies in Swedish so English keyword
  matching cannot converge. A case the gate cannot see carries `gate_blind` or
  `known_miss`, both wired to a strict xfail so the day a structural predicate
  catches it, CI goes red.
- `scripts/eval_decisions.py` — runner. Never in CI. The exit-gate report
  states `cases_that_can_fail` alongside the pass rate: 6 of 12 cases cannot
  turn the gate red by construction, and hiding that number is how a gate gets
  over-trusted.
- Prose judgement stays out of the gate. A judge report can be added later and
  must not use deepseek to judge deepseek — mimo-v2.6-flash or gpt-6-luna.

Exit gate: met offline. `baseline: "not run"` is honest — no live model run
has happened yet, so the gate has never been seen to go red against a model.

## Phase 2 — tool capability (gated on Phase 1)

In the research's ranked order: `get_athlete_state` (CTL/ATL/TSB, ramp, HRV
trend, provenance in one call) → data-provenance verifier → deterministic
metric library + unit tests → plan validator. Tool consolidation after the eval
shows it is not worse.

Stop rule: a new tool that cuts no ≥10 eval points and no ≥30% tokens is killed.

## Phase 3 — context, one lever per PR

1. **Tool-result cap — done.** `plugins/training/_result_cap.py` registers the
   `transform_tool_result` hook and caps every result at append time
   (12k default; 16k `read_file`, 24k `skill_view`, 15k knowledge, 8k
   `terminal`; 60% head / 40% tail so both the payload shape and the error
   tail survive). The hook is fail-open: a bug degrades to today's behaviour.
   This supersedes the old plan's separate knowledge cap — the hook caps
   `get_coaching_knowledge` too, so a second cap in `coaching.py` would be the
   same fix twice.
2. Memory block after the static prefix — open.
3. Compaction — **one config key, not a code change.** `compression.enabled`
   is true by default with a 0.50 threshold, i.e. 500k tokens on the 1M model,
   and the longest session reached 411,894 — it never fired because the line
   was never crossed, not because it is broken. `compression.threshold_tokens:
   300000` fires at the lower of ratio and this cap (read at
   `agent/agent_init.py:2325`). Ship it alone: it mutates the cached prefix, so
   one re-prefill per compaction.

Do not: inline `coach-brain/`, strip `reasoning_content` before verifying the
provider's tool-call protocol, trim functional input schemas, or compact cron
sessions.

## Phase 4 — loop contract and model (done 2026-11-10)

- `scripts/pr_guard.py` refuses a `coach-brain/` edit whose body names no
  signal path and no decision case. An edit without a traced failure is a
  guess.
- Signals stay on the PVC; the PR body inlines the signal text instead of a
  second file in the PR (no CONTRACT boundary change).
- **Model stays `deepseek-v4.1-flash`.** The catalog's `deepseek-v4-pro` is the
  previous-generation V4-Pro: V4.1-Flash beats it on agentic tasks
  (AutomationBench 54.8 vs 43.2, Terminal-Bench 3.0 30.0 vs 11.8), costs 4.4×
  less, and has a 7.3× cheaper cache-read. It is also region-gated — 2026-08-12
  (`fix/switch-model-off-deepseek`) records every request failing 403
  RegionError. If a strong tier is ever wanted, `mimo-v2.6-pro` is the only
  candidate with both the evidence (ExploitBench 47.9 vs 25.3) and acceptable
  cache economics, and only once the eval can measure a difference.

## Phase 5 — hygiene (done 2026-11-10)

- `scan-signals.sh` rotates `worklog.md` above 200 KB (it reached 437 KB at
  ~4 KB/day) and logs each rotation to `worklog.md.rotations`.
- Open signals are capped at 8 entries in the cron prompt.

## Open, operator-owned

- Whether compaction ships (now a one-key config change), and when.
- Who writes the case labels. The drafts are proposals until the operator signs
  them off.
- Whether a live model driver is built at all: `eval_decisions.py --live` needs
  a `--driver` that runs a model through the coaching tools, and until that
  exists every Phase 2 claim is unmeasurable.
- Corpus curation: consolidate and lint for contradictions, no new files, until
  a traced eval failure proves no tool can compute the fact.
