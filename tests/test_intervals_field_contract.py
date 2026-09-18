"""Field-name contract for the intervals.icu `fields=` projections.

Every name in a `fields=` projection must be a property of the published data
model. The API documents `fields` as "Comma separated list of field names to
include in the returned objects (default is all)" — an unknown name yields no key
at all, so the projection reads None and the agent coaches on a missing value.

Live-verified 2026-09-18: `avg_heartrate`, `avg_cadence` and `avg_pace` were
requested but never returned (0/30 activities), while the published names
populated 30/30. `avg_hr` and `avg_cadence` were therefore always null.

Source of truth: tests/data/intervals_model_fields.json, generated from the
official @intervals-icu/js-data-model package by
scripts/gen-intervals-field-snapshot.py.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT = json.loads(
    (ROOT / "tests" / "data" / "intervals_model_fields.json").read_text()
)
SOURCE = (ROOT / "plugins" / "training" / "intervals_icu.py").read_text()

KNOWN = {name for props in SNAPSHOT["fields"].values() for name in props}

# `fields` values are tuple-of-string-literals, each a comma-separated list.
_FIELDS_BLOCK = re.compile(r'"fields":\s*\((.*?)\),', re.S)


def _requested_fields() -> set[str]:
    names: set[str] = set()
    for block in _FIELDS_BLOCK.findall(SOURCE):
        for literal in re.findall(r'"([^"]+)"', block):
            names.update(n for n in literal.split(",") if n)
    return names


def test_snapshot_is_populated():
    assert len(KNOWN) > 300, "snapshot looks truncated"


def test_projection_extraction_finds_fields():
    assert len(_requested_fields()) >= 20, "no fields= projections parsed"


def test_every_requested_field_is_in_the_published_model():
    unknown = sorted(_requested_fields() - KNOWN)
    assert not unknown, (
        "fields= requests names not in the published data model: "
        f"{unknown}. The API silently drops unknown names, so the projection "
        "reads None. Fix the name or regenerate the snapshot."
    )


def test_strava_style_aliases_are_not_requested():
    requested = _requested_fields()
    for alias in ("avg_heartrate", "avg_cadence", "avg_pace"):
        assert alias not in requested, (
            f"{alias} is not a published field name; use the published name "
            "(average_heartrate / average_cadence / pace)."
        )


def test_js_script_only_fields_are_documented_as_such():
    # icu_intervals / icu_groups / laps are in the JS data model but NOT in the
    # REST response, so they must never be requested via `fields=`.
    requested = _requested_fields()
    for js_only in ("icu_intervals", "icu_groups", "laps"):
        assert js_only not in requested, (
            f"{js_only} is JS-script-only and is not returned by the REST "
            "activity endpoint; use GET /activity/{id}/intervals instead."
        )
