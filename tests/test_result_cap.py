"""Tool-result cap (transform_tool_result hook) — plugins/training/_result_cap.py."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "plugins"))

from training import _result_cap  # noqa: E402
from training._result_cap import (  # noqa: E402
    BUDGETS,
    DEFAULT_BUDGET,
    cap_result,
    register_hooks,
)


def test_under_budget_is_left_alone():
    assert cap_result("read_file", "x" * 15_999) is None


def test_exactly_at_budget_is_left_alone():
    assert cap_result("terminal", "x" * BUDGETS["terminal"]) is None


@pytest.mark.parametrize("result", [None, b"bytes", 42, ["list"], {"dict": 1}])
def test_non_str_is_left_alone(result):
    assert cap_result("read_file", result) is None


def test_empty_is_left_alone():
    assert cap_result("read_file", "") is None


def test_100k_read_file_keeps_head_and_tail():
    original = "".join(f"{i:05d}|" for i in range(16_667))[:100_000]
    capped = cap_result("read_file", original)

    assert capped is not None
    assert capped.startswith(original[:9_600])
    assert capped.endswith(original[-6_400:])
    assert "read_file" in capped
    assert "100000" in capped
    assert "16000" in capped
    assert capped.count("[hermes:result_cap") == 1
    # 16k of payload plus the one-line marker, nothing more.
    assert len(capped) < 16_000 + 200


MARKER_RE = re.compile(r"\n\[hermes:result_cap [^\]\n]*\]\n")


@pytest.mark.parametrize("tool,budget", sorted(BUDGETS.items()))
def test_each_budget_is_honoured(tool, budget):
    original = "a" * (budget * 3)
    capped = cap_result(tool, original)

    assert capped is not None
    # budget chars of payload survive; the marker is the only addition.
    assert MARKER_RE.sub("", capped) == "a" * budget


def test_unknown_tool_uses_default_budget():
    original = "a" * (DEFAULT_BUDGET + 1)
    capped = cap_result("some_unlisted_tool", original)

    assert capped is not None
    assert f"budget={DEFAULT_BUDGET}" in capped


def test_marker_is_plain_ascii():
    capped = cap_result("get_fitness_chart", "a" * 20_000)
    assert capped is not None
    assert capped.isascii()


def test_json_result_keeps_head_prefix_intact():
    payload = json.dumps({"activities": [{"id": i, "name": f"ride-{i}"} for i in range(3_000)]})
    assert len(payload) > BUDGETS["read_file"]

    capped = cap_result("read_file", payload)
    assert capped is not None
    assert capped.startswith(payload[:100])
    # The head is untouched: the first key of the object survives verbatim.
    assert capped.startswith('{"activities": [{"id": 0, "name": "ride-0"}')


def test_error_tail_survives_truncation():
    body = "x" * 50_000 + json.dumps({"error": "401 Unauthorized"})
    capped = cap_result("session_search", body)

    assert capped is not None
    assert capped.endswith('{"error": "401 Unauthorized"}')


def test_registers_transform_tool_result_hook():
    hooks = {}

    class _Ctx:
        def register_hook(self, name, callback):
            hooks[name] = callback

    register_hooks(_Ctx())
    assert hooks == {"transform_tool_result": _result_cap._hook}


def test_hook_passes_args_through_to_cap():
    capped = _result_cap._hook(
        tool_name="terminal", args={"command": "ls"}, result="y" * 9_000,
        session_id="s1", duration_ms=12, status="ok",
    )
    assert capped is not None
    assert capped.startswith("y")
    assert "terminal" in capped


def test_hook_is_fail_open(monkeypatch):
    def _boom(tool_name, result):
        raise RuntimeError("cap exploded")

    monkeypatch.setattr(_result_cap, "cap_result", _boom)
    assert _result_cap._hook(tool_name="read_file", result="z" * 100_000) is None
