"""Schema / integrity tests for coach-brain/*.yaml knowledge files.

These guard the YAML the coach actually reads at runtime. They catch:
  - malformed YAML (parse errors) before deploy
  - a regression of the training-philosophies.yaml bug where a missing
    ``threshold_focused:`` key caused threshold-focused content to silently
    overwrite ``norwegian_singles``
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

try:
    import yaml
except ImportError:  # pragma: no cover - pyyaml is a runtime dep
    pytest.skip("pyyaml not installed", allow_module_level=True)

sys.path.insert(0, str(Path(__file__).parent.parent / "plugins"))

COACH_BRAIN = Path(__file__).parent.parent / "coach-brain"
YAML_FILES = sorted(COACH_BRAIN.glob("*.yaml"))


def _load(name: str) -> dict:
    return yaml.safe_load((COACH_BRAIN / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize("path", YAML_FILES, ids=lambda p: p.name)
def test_every_yaml_parses_to_dict(path: Path):
    """Every knowledge file must parse to a non-empty mapping."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict), f"{path.name} root is {type(data).__name__}, not a dict"
    assert data, f"{path.name} is empty"


class TestTrainingPhilosophies:
    """Regression guard for the threshold_focused/norwegian_singles overwrite bug."""

    def setup_method(self):
        self.data = _load("training-philosophies.yaml")
        self.phil = self.data["training_philosophies"]

    def test_has_expected_top_level_sections(self):
        for key in ("training_philosophies", "periodization", "intensity_zones"):
            assert key in self.data, f"missing top-level section: {key}"

    EXPECTED = ["polarized", "pyramidal", "norwegian_singles",
                "threshold_focused", "base_building"]

    @pytest.mark.parametrize("name", EXPECTED)
    def test_each_philosophy_present(self, name):
        assert name in self.phil, f"philosophy {name!r} missing"

    @pytest.mark.parametrize("name", EXPECTED)
    def test_each_philosophy_has_summary(self, name):
        entry = self.phil[name]
        assert isinstance(entry, dict), f"{name} is not a dict"
        assert "summary" in entry and entry["summary"], f"{name} has no summary"

    def test_norwegian_singles_distinct_from_threshold_focused(self):
        """The bug: missing threshold_focused: key made norwegian_singles
        inherit threshold-focused content. After the fix both are separate
        entries with their own distinct summaries."""
        ns = self.phil["norwegian_singles"]
        tf = self.phil["threshold_focused"]
        # norwegian_singles should keep its running-specific keys
        assert "structure" in ns or "key_principles" in ns, (
            "norwegian_singles lost its running-specific fields (regression)"
        )
        # the two must not be byte-identical (would indicate the overwrite returned)
        assert ns != tf, "norwegian_singles == threshold_focused (overwrite bug returned)"

    def test_norwegian_singles_has_paces(self):
        ns = self.phil["norwegian_singles"]
        assert "paces_from_running_data" in ns, (
            "norwegian_singles missing paces_from_running_data (regression: "
            "content was clobbered by orphaned threshold_focused block)"
        )
