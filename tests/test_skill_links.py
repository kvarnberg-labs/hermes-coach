"""Link integrity for the coaching skill's reference system.

Three directions, all stdlib:
  1. Forward:  every references/<file>.md mentioned in SKILL.md exists.
  2. Reverse:  every file in references/ is mentioned in SKILL.md
               (unreachable guidance fails CI instead of silently rotting).
  3. Cross:    every references/<file>.md mentioned by a reference file exists.

The 2026-09 restructure moved ~60KB of pitfalls and method essays out of the
skill body; every moved section is reachable only via these links, and the
de-weaponization pass moved break-glass recipes out of the shipped tree —
so a dangling mention now means either lost guidance or lost ops content.
"""

from __future__ import annotations

import re
from pathlib import Path

SKILL = Path(__file__).parent.parent / "skills" / "coaching" / "SKILL.md"
REFS = SKILL.parent / "references"

MENTION = re.compile(r"references/([\w.-]+\.md)")


def _mentions(text: str) -> set[str]:
    return set(MENTION.findall(text))


def test_every_referenced_file_exists():
    text = SKILL.read_text(encoding="utf-8")
    mentioned = _mentions(text)
    assert mentioned, "expected SKILL.md to reference at least one file"
    missing = sorted(name for name in mentioned if not (REFS / name).exists())
    assert not missing, f"SKILL.md references missing files: {missing}"


def test_every_reference_is_reachable_from_skill():
    skill_text = SKILL.read_text(encoding="utf-8")
    mentioned = _mentions(skill_text)
    shipped = {p.name for p in REFS.glob("*.md")}
    unreachable = sorted(shipped - mentioned)
    assert not unreachable, (
        f"reference files not mentioned anywhere in SKILL.md (unreachable "
        f"guidance — link them or delete them): {unreachable}"
    )


def test_reference_cross_links_resolve():
    for ref in sorted(REFS.glob("*.md")):
        text = ref.read_text(encoding="utf-8")
        missing = sorted(
            name for name in _mentions(text) if not (REFS / name).exists()
        )
        assert not missing, f"{ref.name} references missing files: {missing}"
