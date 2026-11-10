"""Cap tool results at append time — `transform_tool_result` hook.

Measured on captured request bodies (experiments/context_budget_model.py): tool
results were 50.1% of a long Discord DM request (151,539 of 302,481 chars), the
largest single result 100,966 chars. Hermes re-sends every earlier tool result
on each turn, so one oversized result is paid again on every following call.
Capping it before it enters conversation context cuts ~35% of that request
without removing a tool or changing what the coach is able to do.

Budgets are per tool, by how the coach actually reads the result:
  - read_file 16k, skill_view 24k — the dev loop legitimately reads a whole
    source or skill file; a partial read there costs a second tool call.
  - get_coaching_knowledge 15k, get_fitness_chart 16k — long YAML sections
    and chart metadata, useful only up to the relevant part.
  - terminal 8k — logs and pytest output are read at their tail (the failure),
    so a smaller budget loses less.
  - session_search 12k, default 12k — no reason to hold more of a listing than
    the default.

Truncation keeps HEAD + TAIL and drops the middle, because both ends carry
signal: the head holds the shape of the payload (a JSON object's opening keys,
the first records of a listing) and the tail holds the last records and the
final error line.

Fail-open by construction: the hook dispatch already treats an exception as
"keep the original result", and `_hook` returns None on any error, so a bug in
this module degrades to the uncapped behaviour rather than a lost tool result.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

BUDGETS: dict[str, int] = {
    "read_file": 16_000,
    "skill_view": 24_000,
    "get_coaching_knowledge": 15_000,
    "get_fitness_chart": 16_000,
    "session_search": 12_000,
    "terminal": 8_000,
}
DEFAULT_BUDGET = 12_000

# Share of the budget kept at the head; the tail takes the rest.
HEAD_SHARE = 6  # 60% head, 40% tail

MARKER = "\n[hermes:result_cap tool={tool} original={original} budget={budget} dropped={dropped} middle-removed]\n"


def cap_result(tool_name: str, result: Any) -> str | None:
    """Return a capped copy of `result`, or None to leave it unchanged."""
    if not isinstance(result, str) or not result:
        return None
    budget = BUDGETS.get(tool_name, DEFAULT_BUDGET)
    if len(result) <= budget:
        return None
    head = budget * HEAD_SHARE // 10
    tail = budget - head
    marker = MARKER.format(
        tool=tool_name, original=len(result), budget=budget, dropped=len(result) - budget
    )
    return result[:head] + marker + result[-tail:]


def _hook(tool_name: str = "", args: Any = None, result: Any = None, **_: Any) -> str | None:
    """transform_tool_result hook: None leaves the result unchanged."""
    try:
        return cap_result(tool_name, result)
    except Exception:
        logger.debug("RESULT-CAP failed tool=%s", tool_name, exc_info=True)
        return None


def register_hooks(ctx) -> None:
    ctx.register_hook("transform_tool_result", _hook)
