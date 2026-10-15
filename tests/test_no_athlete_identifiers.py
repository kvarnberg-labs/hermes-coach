"""Shipped bot content must not carry real athlete identifiers.

Every file under the shipped skills and coach-brain/ can be loaded into any
athlete's session. Before 2026-10-15 a reference carried a registry of four
athletes' Discord snowflakes, DM channel IDs and intervals.icu athlete IDs, so
one athlete's chat could pull in another athlete's identifiers. Use the
placeholders below in examples; real mappings live only on the PVC.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
SHIPPED = [
    ROOT / "skills" / "coaching",
    ROOT / "skills" / "strength-coaching",
    ROOT / "skills" / "self-improvement",
    ROOT / "coach-brain",
]
# Discord snowflakes / channel IDs (17-20 digits) and intervals.icu athlete IDs.
IDENTIFIER = re.compile(r"\b(\d{17,20}|i\d{6})\b")
PLACEHOLDERS = {"123456789012345678", "i000000"}


def _hits(text: str) -> set[str]:
    return set(IDENTIFIER.findall(text)) - PLACEHOLDERS


def test_pattern_catches_identifiers_and_allows_placeholders():
    assert _hits("deliver='discord:1531542557677322342' athlete i627207") == {
        "1531542557677322342", "i627207",
    }
    assert _hits("snowflake 123456789012345678, athlete i000000") == set()


def test_shipped_content_has_no_athlete_identifiers():
    found = {
        str(p.relative_to(ROOT)): sorted(hits)
        for base in SHIPPED
        for p in sorted(base.rglob("*"))
        if p.is_file() and p.suffix in {".md", ".yaml", ".yml"}
        and (hits := _hits(p.read_text(encoding="utf-8")))
    }
    assert not found, f"real identifiers in shipped content (use placeholders): {found}"
