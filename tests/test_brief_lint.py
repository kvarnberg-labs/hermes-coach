"""Tests for scripts/brief_lint.py — corruption lint + delivery-noise leak checks.

Regression context (2026-09-14): three delivered coaching briefs ended with
verbatim internal Hermes error noise ("File-mutation verifier", write_file
denial for /tmp/brief_draft.md). The lint shipped in PR #97 passed those
briefs clean (exit 0). lint_delivery_noise() was added to HARD-flag internal
platform noise; main() extends its findings with it before returning.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import brief_lint  # noqa: E402


def _lint(text):
    return brief_lint.lint(text, brief_lint.load_words())


def _lint_full(text):
    return brief_lint.lint(text, brief_lint.load_words()) + brief_lint.lint_delivery_noise(text)


CLEAN_BRIEF = (
    "Måndag 14/9 — morgonbrief\n\n"
    "Sömn: 7,5 h, HRV 29, vilopuls 55.\n"
    "Idag: Z2 60–90 min @ 150–185 W. Väder: +8 °C, torrt.\n"
)


def test_clean_brief_passes():
    assert _lint_full(CLEAN_BRIEF) == []


def test_noise_leak_write_denial_flagged():
    body = CLEAN_BRIEF + (
        "\n⚠️ File-mutation verifier: 1 file(s) were NOT modified this turn.\n"
        "  • `/tmp/brief_draft.md` — [write_file] Write denied: outside "
        "HERMES_WRITE_SAFE_ROOT (/opt/data).\n"
    )
    findings = _lint_full(body)
    msgs = [m for _, m in findings]
    assert any("internal tool-error leak" in m for m in msgs)
    assert any(sev == "HARD" for sev, _ in findings)


def test_noise_leak_draft_reference_flagged():
    body = CLEAN_BRIEF + "\n(draft saved to brief_draft for lint)\n"
    msgs = [m for _, m in _lint_full(body)]
    assert any("draft-file reference" in m for m in msgs)


def test_noise_leak_traceback_flagged():
    body = CLEAN_BRIEF + "\nTraceback (most recent call last):\n"
    msgs = [m for _, m in _lint_full(body)]
    assert any("internal tool-error leak" in m for m in msgs)


def test_internal_warning_emoji_flagged():
    body = CLEAN_BRIEF + "\n⚠️ Bortglömd varningstext\n"
    msgs = [m for _, m in _lint_full(body)]
    assert any("warning-marker" in m for m in msgs)


def test_wordlist_loads():
    words = brief_lint.load_words()
    assert len(words) > 100000
    assert "sömn" in words


def test_known_hard_glitches_still_caught():
    body = "Vid livri och (133}.sget48-185 W - RegnarPlan\n"
    msgs = [m for _, m in _lint_full(body)]
    assert any("mismatched brackets" in m for m in msgs)
    assert any("CamelCase fused word" in m for m in msgs)
