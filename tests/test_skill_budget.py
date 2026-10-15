"""Size and directive-count budget for the coaching skill.

SKILL.md grew to 98 KB once and was cut to 39 KB on 2026-09-14; nothing
stopped it regrowing (40.7 KB on 2026-10-15). The binding constraint is not
tokens but the number of standing directives: instruction-following benchmarks
find compliance declining from ~40 simultaneous rules and collapsing by ~80
(VeyraBench, arXiv:2607.19257). See outputs/hermes-agent-context-research.md
§5.1 for the original count.

The caps are a ratchet: lower them when the skill shrinks, never raise them
to make a PR pass — move content to references/ or deterministic gates instead.
"""

from __future__ import annotations

import re
from pathlib import Path

SKILL = Path(__file__).parent.parent / "skills" / "coaching" / "SKILL.md"
REFS = SKILL.parent / "references"

SKILL_MAX_BYTES = 45_000
# 2026-10-15: training-plan-creation.md (13.4 KB) and event-creation-pitfalls.md
# (13.1 KB) exceed 12 KB. Lower to 12_000 once they are split.
REFERENCE_MAX_BYTES = 14_000
# Measured 63 on 2026-10-15 with the definition below. Lower as rules move
# into deterministic gates.
DIRECTIVE_MAX = 70

BULLET = re.compile(r"^\s*([-*]|\d+\.)\s+")
PROHIBITION = re.compile(r"\b(never|do not|must not|forbidden)\b", re.IGNORECASE)
MODAL = re.compile(r"\b(must|should|always|required|ensure|verify)\b", re.IGNORECASE)
IMPERATIVE = re.compile(
    r"^\s*(?:[-*]|\d+\.)\s+(?:\*\*)?(Use|Call|Verify|Check|Stop|Read|Run|Add|Keep|Ensure)\b"
)


def count_directives(text: str) -> int:
    """Bullet lines that are a prohibition, a modal obligation, or start imperative."""
    return sum(
        1
        for line in text.splitlines()
        if BULLET.match(line)
        and (PROHIBITION.search(line) or MODAL.search(line) or IMPERATIVE.match(line))
    )


def test_count_directives_classifies_lines():
    text = "\n".join([
        "- NEVER send raw tool output",  # prohibition
        "- You should log the run",  # modal
        "1. **Run** the lint",  # imperative
        "- Athletes like coffee",  # not a directive
        "NEVER outside a bullet",  # not a bullet
    ])
    assert count_directives(text) == 3


def test_skill_size_within_budget():
    size = SKILL.stat().st_size
    assert size <= SKILL_MAX_BYTES, (
        f"SKILL.md is {size} B > {SKILL_MAX_BYTES} B. Move detail to references/."
    )


def test_every_reference_within_budget():
    over = {
        p.name: p.stat().st_size
        for p in sorted(REFS.glob("*.md"))
        if p.stat().st_size > REFERENCE_MAX_BYTES
    }
    assert not over, f"references over {REFERENCE_MAX_BYTES} B: {over}. Split them."


def test_skill_directive_count_within_budget():
    n = count_directives(SKILL.read_text(encoding="utf-8"))
    assert n <= DIRECTIVE_MAX, (
        f"SKILL.md has {n} directive bullets > {DIRECTIVE_MAX}. Move rules into "
        "deterministic gates or references/ instead of raising the cap."
    )
