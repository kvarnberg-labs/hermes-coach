"""Every athlete-output verifier must agree with the operator-owned golden set.

tests/golden/cases.yaml is the anchor the self-improvement loop cannot edit.
A verifier is a function text -> bool ("block delivery"). Add new gates to
VERIFIERS; they must then agree with every golden label to merge.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Callable

import pytest
import yaml

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import brief_lint  # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "plugins"))

from training._output_gate import gate_reply  # noqa: E402

CASES = yaml.safe_load((Path(__file__).parent / "golden" / "cases.yaml").read_text(encoding="utf-8"))["cases"]
WORDS = brief_lint.load_words()


def _brief_lint_blocks(text: str) -> bool:
    # Mirrors brief_lint.main(): empty input or any finding (HARD or SOFT)
    # exits 1 = do not deliver.
    return not text.strip() or bool(brief_lint.lint(text, WORDS) + brief_lint.lint_delivery_noise(text))


def _output_gate_blocks(text: str) -> bool:
    # The send-path gate (transform_llm_output hook): a returned string replaces the reply.
    return gate_reply(response_text=text) is not None


VERIFIERS: dict[str, Callable[[str], bool]] = {
    "brief_lint": _brief_lint_blocks,
    "output_gate": _output_gate_blocks,
}


def _params():
    for name, verifier in VERIFIERS.items():
        for case in CASES:
            missed = name in case.get("known_miss", [])
            marks = [pytest.mark.xfail(strict=True, reason="known miss", raises=AssertionError)] if missed else []
            yield pytest.param(verifier, case, id=f"{name}:{case['id']}", marks=marks)


def _agrees(verifier: Callable[[str], bool], case: dict) -> bool:
    return verifier(case["text"]) == (case["label"] == "bad")


def test_cases_are_well_formed():
    ids = [c["id"] for c in CASES]
    assert len(ids) == len(set(ids)), "duplicate golden ids"
    assert {c["label"] for c in CASES} == {"good", "bad"}
    assert not [c["id"] for c in CASES if c.get("known_miss") and c["label"] != "bad"]
    unknown = {v for c in CASES for v in c.get("known_miss", [])} - set(VERIFIERS)
    assert not unknown, f"known_miss names unknown verifiers: {unknown}"


@pytest.mark.parametrize("verifier,case", _params())
def test_verifier_agrees_with_golden_label(verifier, case):
    assert _agrees(verifier, case), f"{case['id']} ({case['label']}): {case['text']!r}"


@pytest.mark.parametrize("vacuous", [lambda t: False, lambda t: True], ids=["always-pass", "always-block"])
def test_golden_set_rejects_vacuous_verifier(vacuous):
    assert not all(_agrees(vacuous, c) for c in CASES)
