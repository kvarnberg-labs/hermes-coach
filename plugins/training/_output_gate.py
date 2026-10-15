"""Pre-send output gate — runs brief_lint on every reply before delivery.

SKILL.md told the model to lint its own drafts, but Discord sessions have no
terminal tool, so the lint could not run there (skill audit 2026-10-15).
Hermes' `transform_llm_output` hook fires once per turn, after the tool loop,
for every platform (Discord DMs and cron alike); the returned string replaces
the reply. Corrupted text is worse than a delayed clean reply
(coach-brain/headless-coaching-failures.yaml), so a blocking finding replaces
the reply with a short notice and logs the findings.

Only high-precision rules block. Rules tuned for cron briefs that misfire on
ordinary chat (CamelCase product names, the ⚠️ emoji, the English phrase
"to confirm") are logged only, until the logs show how often they fire on
real replies. Unknown-word (SOFT) findings are ignored here.
"""

from __future__ import annotations

import functools
import importlib.util
import logging
from pathlib import Path
from types import ModuleType
from typing import Any

logger = logging.getLogger(__name__)

BLOCKED_NOTICE = (
    "Mitt svar blev tekniskt skadat och stoppades innan det skickades. "
    "Skriv gärna igen så gör jag ett nytt försök."
)

# Finding-message prefixes that are logged but never block.
_SHADOW_PREFIXES = (
    "CamelCase fused word",
    "internal warning-marker emoji",
    "verdict-prose leak",
)
# Greek capital delta is ordinary sport notation ("ΔCTL"); the non-Latin rule
# targets injected script runs, not this single symbol.
_NOTATION = str.maketrans({"Δ": "D"})

# plugins/training/ -> <root>/scripts in the repo, /opt/hermes and /opt/data.
_SCRIPT_DIRS = (
    Path(__file__).resolve().parents[2] / "scripts",
    Path("/opt/hermes/scripts"),
)


@functools.lru_cache(maxsize=1)
def _lint_module() -> ModuleType:
    for d in _SCRIPT_DIRS:
        path = d / "brief_lint.py"
        if path.is_file():
            spec = importlib.util.spec_from_file_location("brief_lint", path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
    raise FileNotFoundError(f"brief_lint.py not found in {[str(d) for d in _SCRIPT_DIRS]}")


@functools.lru_cache(maxsize=1)
def _words() -> frozenset[str]:
    return frozenset(_lint_module().load_words())


def classify(text: str) -> tuple[list[str], list[str]]:
    """Return (blocking, shadow) HARD finding messages for an outgoing reply."""
    lint = _lint_module()
    text = text.translate(_NOTATION)
    findings = lint.lint(text, _words()) + lint.lint_delivery_noise(text)
    hard = [msg for sev, msg in findings if sev == "HARD"]
    shadow = [m for m in hard if m.startswith(_SHADOW_PREFIXES)]
    return [m for m in hard if m not in shadow], shadow


def gate_reply(response_text: str = "", session_id: str = "", platform: str = "", **_: Any) -> str | None:
    """transform_llm_output hook: None leaves the reply unchanged."""
    if not response_text or not response_text.strip():
        return None
    blocking, shadow = classify(response_text)
    if shadow:
        logger.info("OUTPUT-GATE shadow session=%s platform=%s findings=%s",
                    session_id, platform, shadow)
    if not blocking:
        return None
    logger.warning("OUTPUT-GATE blocked session=%s platform=%s findings=%s",
                   session_id, platform, blocking)
    return BLOCKED_NOTICE


def register_hooks(ctx) -> None:
    ctx.register_hook("transform_llm_output", gate_reply)
