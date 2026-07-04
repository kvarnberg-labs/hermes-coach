"""Coach Brain — structured coaching knowledge retrieval.

Loads YAML files from $HERMES_HOME/coach-brain/ and exposes a
get_coaching_knowledge tool that returns relevant sections by topic.

The coach-brain directory contains domain knowledge that supplements the
system prompt: training philosophies, workout descriptions, injury protocols,
nutrition guidelines, etc.  Hermes retrieves relevant sections at query time
rather than loading everything into the system prompt, keeping the context
lean and caching-friendly.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


def _brain_dir() -> Path:
    hermes_home = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
    return hermes_home / "coach-brain"


import time as _time

_brain_cache: dict[str, Any] | None = None
_brain_cache_mtime: float = 0.0
_brain_cache_dir: str | None = None
_BRAIN_CACHE_TTL: float = 60.0  # seconds


def _load_all() -> dict[str, Any]:
    """Load and merge all YAML files from the coach-brain directory.

    Results are cached for _BRAIN_CACHE_TTL seconds to avoid repeated
    disk I/O during multi-turn coaching sessions.  The cache is keyed
    by the brain directory path so that directory changes (e.g. in
    tests) invalidate stale entries.
    """
    global _brain_cache, _brain_cache_mtime, _brain_cache_dir
    now = _time.monotonic()
    current_dir = str(_brain_dir())
    if (
        _brain_cache is not None
        and _brain_cache_dir == current_dir
        and (now - _brain_cache_mtime) < _BRAIN_CACHE_TTL
    ):
        return _brain_cache

    try:
        import yaml
    except ImportError:
        logger.warning("pyyaml not installed; coach-brain unavailable")
        _brain_cache = {}
        _brain_cache_mtime = now
        _brain_cache_dir = current_dir
        return {}

    brain: dict[str, Any] = {}
    d = _brain_dir()
    if not d.exists():
        logger.warning("coach-brain directory not found at %s", d)
        _brain_cache = {}
        _brain_cache_mtime = now
        _brain_cache_dir = current_dir
        return {}

    for f in sorted(d.glob("*.yaml")):
        try:
            file_content = yaml.safe_load(f.read_text(encoding="utf-8"))
            if isinstance(file_content, dict):
                brain.update(file_content)
        except Exception as exc:
            logger.warning("Failed to load coach-brain file %s: %s", f.name, exc)

    _brain_cache = brain
    _brain_cache_mtime = now
    _brain_cache_dir = current_dir
    return brain


def get_coaching_knowledge(topic: str, **_: Any) -> str:
    """Retrieve coaching knowledge relevant to a topic.

    Searches all coach-brain YAML files for sections whose keys or content
    match the topic string.  Returns matched sections as structured JSON.

    Args:
        topic: Topic to search for, e.g. "threshold intervals", "recovery",
               "tapering", "nutrition", "injury", "base building".
    """
    brain = _load_all()
    if not brain:
        return json.dumps({
            "error": "Coach brain not loaded. Check $HERMES_HOME/coach-brain/ directory.",
            "topic": topic,
        })

    topic_lower = topic.lower()
    keywords = set(topic_lower.replace("-", " ").split())

    # Sections that are always returned in full regardless of topic match —
    # they are too large to usefully inject via keyword search and would
    # dominate the context window. The agent should request them explicitly.
    _OMNIBUS_SECTIONS = {"nutrition"}

    matched: dict[str, Any] = {}
    for key, value in brain.items():
        # Skip omnibus sections unless the topic explicitly names them
        if key in _OMNIBUS_SECTIONS:
            if not any(kw in key for kw in keywords):
                continue

        key_lower = key.lower().replace("_", " ").replace("-", " ")
        # Match if any keyword appears in the key
        if any(kw in key_lower for kw in keywords):
            matched[key] = value
        else:
            # Fuzzier fallback: keyword in serialised content (but only for
            # non-omnibus sections to avoid pulling nutrition into every query)
            if key not in _OMNIBUS_SECTIONS:
                content_str = json.dumps(value).lower()
                if any(kw in content_str for kw in keywords):
                    matched[key] = value

    if not matched:
        # Fall back: return top-level keys so the agent knows what's available
        return json.dumps({
            "topic": topic,
            "matched": False,
            "available_topics": list(brain.keys()),
            "note": "No direct match found. Use one of the available_topics above.",
        })

    return json.dumps({
        "source": "coach-brain",
        "topic": topic,
        "matched": True,
        "knowledge": matched,
    })


def register_tools(ctx) -> None:
    ctx.register_tool(
        name="get_coaching_knowledge",
        toolset="training",
        schema={
            "name": "get_coaching_knowledge",
            "description": (
                "Retrieve structured coaching knowledge for a specific topic. "
                "Use this when you need evidence-based principles, workout definitions, "
                "recovery heuristics, injury protocols, or race preparation guidelines. "
                "Topics include: altitude, cold weather, female physiology, heat, injury, "
                "nutrition, power zones, recovery, sleep, strength training, "
                "tapering, training philosophies, vo2max, workout library."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": (
                            "The coaching topic to look up, e.g. 'threshold intervals', "
                            "'recovery heuristics', 'tapering', 'nutrition during training'."
                        ),
                    }
                },
                "required": ["topic"],
            },
        },
        handler=lambda args, **kw: get_coaching_knowledge(topic=args["topic"]),
    )
