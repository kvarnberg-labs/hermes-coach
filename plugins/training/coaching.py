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
from typing import Any

from ._brain import _load_all

# Re-export for backward compatibility (tests import these from coaching)
from ._brain import _brain_dir  # noqa: F401

logger = logging.getLogger(__name__)


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
                "Topics include: altitude, cold weather, exercise database, female physiology, "
                "heat, injury, nutrition, power zones, recovery, sleep, "
                "strength principles, strength programming, strength standards, "
                "strength training, tapering, training philosophies, vo2max, workout library."
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
