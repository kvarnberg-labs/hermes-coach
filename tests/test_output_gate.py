"""Pre-send output gate (transform_llm_output hook) — plugins/training/_output_gate.py."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent / "plugins"))

from training._output_gate import BLOCKED_NOTICE, classify, gate_reply, register_hooks  # noqa: E402

GOLDEN = yaml.safe_load((Path(__file__).parent / "golden" / "cases.yaml").read_text(encoding="utf-8"))["cases"]


@pytest.mark.parametrize("case", [c for c in GOLDEN if c["label"] == "good"], ids=lambda c: c["id"])
def test_golden_good_replies_pass_unchanged(case):
    assert gate_reply(response_text=case["text"]) is None


@pytest.mark.parametrize("text", [
    "Vid livri och (133}.sget48-185 W\n",
    "men pulsen uppenbarade betydande stress.地位Tänk Datum: du har inte returnerat\n",
    "Hej� vi ses\n",
    "Idag vila.\nTraceback (most recent call last):\n",
    "Idag vila.\n(draft saved to brief_draft for lint)\n",
])
def test_structural_corruption_is_replaced(text):
    assert gate_reply(response_text=text, session_id="s1", platform="discord") == BLOCKED_NOTICE


@pytest.mark.parametrize("text", [
    "Appar: TrainingPeaks, WhatsApp och MyFitnessPal fungerar.",
    "⚠️ Viktigt: vila om du har feber.",
    "Could you confirm? I need you to confirm your FTP first.",
    "ΔCTL +5 senaste veckan, bra progression.",
])
def test_chat_false_positive_rules_only_log(text):
    assert gate_reply(response_text=text) is None


def test_shadow_findings_are_reported():
    blocking, shadow = classify("Appar: TrainingPeaks fungerar.")
    assert blocking == [] and any("TrainingPeaks" in m for m in shadow)


def test_blocked_notice_itself_passes_the_gate():
    assert gate_reply(response_text=BLOCKED_NOTICE) is None


def test_empty_reply_is_left_alone():
    assert gate_reply(response_text="") is None


def test_registers_transform_llm_output_hook():
    hooks = {}

    class _Ctx:
        def register_hook(self, name, callback):
            hooks[name] = callback

    register_hooks(_Ctx())
    assert hooks == {"transform_llm_output": gate_reply}
