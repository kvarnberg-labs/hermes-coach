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


def _load_all() -> dict[str, Any]:
    """Load and merge all YAML files from the coach-brain directory."""
    try:
        import yaml
    except ImportError:
        logger.warning("pyyaml not installed; coach-brain unavailable")
        return {}

    brain: dict[str, Any] = {}
    d = _brain_dir()
    if not d.exists():
        logger.warning("coach-brain directory not found at %s", d)
        return {}

    for f in sorted(d.glob("*.yaml")):
        try:
            content = yaml.safe_load(f.read_text(encoding="utf-8"))
            if isinstance(content, dict):
                brain.update(content)
        except Exception as exc:
            logger.warning("Failed to load coach-brain file %s: %s", f.name, exc)

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

    matched: dict[str, Any] = {}
    for key, value in brain.items():
        key_lower = key.lower().replace("_", " ").replace("-", " ")
        # Match if any keyword appears in the key or the serialised content
        content_str = (key_lower + " " + json.dumps(value)).lower()
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
                "Topics include: threshold intervals, vo2max, base building, recovery, "
                "tapering, nutrition, injury, strength training, race preparation, "
                "power zones, periodization."
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
