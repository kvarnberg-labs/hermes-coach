# Coaching-decision eval — cases

Trajectory cases for `scripts/eval_decisions.py`, graded by
`scripts/decision_predicates.py`.

## Why this exists

`tests/golden/cases.yaml` grades whether the *output* is corrupted. Nothing
graded whether the coach made the right *decision*: whether it verified
identity, read recovery data before calling an athlete ready, or wrote to the
calendar without approval. Without that, every improvement shipped on opinion.

## Rules for editing

- **Operator-owned.** Same ownership as `tests/golden/cases.yaml`: the
  self-improvement loop may not edit this directory, and
  `scripts/pr_guard.py` refuses a PR that touches it.
- **Fixtures come from the real API.** Every `fixtures/*.json` is a captured
  tool payload from the live `state.db`, anonymised. Do not hand-write a
  payload: a fixture that production never returns tests nothing. Shape is
  asserted against the projection in `plugins/training/intervals_icu.py`.
- **`transcripts/` are synthetic, and say so.** They test predicate semantics,
  not model behaviour. Every file carries `"synthetic": true`.
- **A case the gate cannot see must say so.** `gate_blind: true` (an
  informational predicate catches it, no gating predicate does) or
  `known_miss: [predicate]` (that predicate misses it). Both are wired to a
  strict xfail: the day the blindness ends, CI goes red and the marker has to
  be removed.

## What the gate cannot see

Most gating predicates are structural — tool order, identity result, calendar
writes, tool set for a DM — and language-independent by design.

`no_state_claim_without_this_turn_read` also gates, though it reads the reply
text. It does not grade wording: it grades whether this turn read the data it
quotes, and its trigger is a fixed technical vocabulary (`TSB|CTL|ATL|HRV|RHR|
resting HR|sleep score` followed by a number) that appears verbatim in a Swedish
reply — "TSB +10,2" is the same string in both languages. It fails in the safe
direction too: a figure it cannot parse is a miss, not a false fail.

`wellness_before_readiness_claim` and `referral_on_red_flag` read English
coaching prose, so they are **informational only**: they are computed and
reported, never counted in `pass_rate`. The coach replies in Swedish; an English
keyword list cannot be the gate. Four review rounds on the committed cases found
defects only in that layer.

`6 of 13` cases cannot turn the gate red by construction. The report prints
that number as `cases_that_can_fail` so the pass rate is not read as more
evidence than it is.

## Label sign-off

The 13 case labels were drafted from real incidents on 2026-11-10 and signed
off by the operator the same day. Changing a label is changing what the product
considers correct coaching — that is an operator decision, not a loop decision.
