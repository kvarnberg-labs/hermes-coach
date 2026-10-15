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


# Omnibus sections are returned ONLY on an explicit key-match, never via
# content-fallback. Two reasons a section is listed here (see ADR 0001):
#   1. Large databases (nutrition, exercise_database, strength_programming)
#      that would dominate the context window on every fuzzy match.
#   2. Strength knowledge (strength_standards/principles/training) the
#      endurance skill must NOT pull via fuzzy match — the strength-coaching
#      skill owns strength topics. Explicit key-match still serves the
#      strength skill (e.g. get_coaching_knowledge("strength principles")).
_OMNIBUS_SECTIONS = {
    "nutrition", "strength_programming", "exercise_database",
    "strength_standards", "strength_principles", "strength_training",
}
# Key words too generic to count as naming a section (omnibus or not).
_GENERIC_KEY_WORDS = {"training"}


# Words with no topic signal; "to" alone substring-matched most keys.
_STOPWORDS = {
    "a", "an", "and", "the", "to", "for", "of", "in", "on", "with", "during",
    "after", "before", "och", "för", "med", "under", "efter", "före", "i", "på",
    "av", "till",
}
# ~4k tokens. Irrelevant context degrades answers even when the relevant part
# is present (Du et al., arXiv:2510.05381); before this cap a topic containing
# "training" returned ~70 KB of mostly unrelated sections.
_MAX_KNOWLEDGE_CHARS = 15_000


def _size(value: Any) -> int:
    return len(json.dumps(value, ensure_ascii=False))


def _key_score(key: str, keywords: set[str]) -> int:
    """Number of topic keywords found in the section key (0 = no key match)."""
    # Omnibus sections need a non-generic key word in the topic (ADR 0001):
    # "polarized training" must not pull strength_training.
    if key in _OMNIBUS_SECTIONS and not keywords & (set(key.split("_")) - _GENERIC_KEY_WORDS):
        return 0
    # Generic words ("training") only count when the topic has nothing else:
    # "nutrition during training" must rank nutrition, not every *_training key.
    specific = keywords - _GENERIC_KEY_WORDS or keywords
    key_text = key.lower().replace("_", " ").replace("-", " ")
    return sum(1 for kw in specific if kw in key_text)


def _rank(brain: dict[str, Any], keywords: set[str]) -> list[str]:
    """Key matches, best first; content matches only when no key names the topic."""
    scores = {key: _key_score(key, keywords) for key in brain}
    hits = [key for key, score in scores.items() if score]
    if hits:
        return sorted(hits, key=lambda k: (-scores[k], _size(brain[k])))
    # Content fallback keeps only the sections mentioning the MOST topic words
    # (any-word matching pulled most of the corpus) and never serves omnibus.
    content = {
        key: sum(1 for kw in keywords if kw in json.dumps(value, ensure_ascii=False).lower())
        for key, value in brain.items() if key not in _OMNIBUS_SECTIONS
    }
    best = max(content.values(), default=0)
    if not best:
        return []
    return sorted((k for k, n in content.items() if n == best), key=lambda k: _size(brain[k]))


def _within_budget(brain: dict[str, Any], ranked: list[str]) -> tuple[dict[str, Any], list[str]]:
    """Best match always; further sections while under the size budget."""
    picked: dict[str, Any] = {}
    more: list[str] = []
    used = 0
    for key in ranked:
        size = _size(brain[key])
        if picked and used + size > _MAX_KNOWLEDGE_CHARS:
            more.append(key)
            continue
        picked[key] = brain[key]
        used += size
    return picked, more


def get_coaching_knowledge(topic: str, **_: Any) -> str:
    """Retrieve coaching knowledge relevant to a topic.

    Ranks coach-brain sections by how many topic words their key contains;
    falls back to sections whose content mentions every topic word. Returns
    the best matches within a size budget and names the rest.

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

    keywords = set(topic.lower().replace("-", " ").split()) - _STOPWORDS
    ranked = _rank(brain, keywords) if keywords else []

    if not ranked:
        # Fall back: return top-level keys so the agent knows what's available
        return json.dumps({
            "topic": topic,
            "matched": False,
            "available_topics": list(brain.keys()),
            "note": "No direct match found. Use one of the available_topics above.",
        })

    knowledge, more = _within_budget(brain, ranked)
    result: dict[str, Any] = {
        "source": "coach-brain",
        "topic": topic,
        "matched": True,
        "knowledge": knowledge,
    }
    if more:
        result["more_sections"] = more
        result["note"] = "More sections matched; call again with one of more_sections as the topic."
    return json.dumps(result)


def register_tools(ctx) -> None:
    ctx.register_tool(
        name="get_coaching_knowledge",
        toolset="training",
        schema={
            "name": "get_coaching_knowledge",
            "description": (
                "Retrieve structured coaching knowledge for a specific topic. "
                "Use this when you need evidence-based principles, workout definitions, "
                "recovery heuristics, injury protocols, race preparation guidelines, "
                "post-workout feedback, performance decline assessment, or data validation. "
                "Topics include: altitude, cold weather, coaching safety, cycling hand numbness, "
                "exercise database, female physiology, goal continuity, headless coaching failures, "
                "heat, injury, nutrition, persistent performance decline, post-workout feedback, "
                "power zones, race course verification, recovery, sleep, strength principles, "
                "strength programming, strength standards, strength training, tapering, "
                "temporal load validation, training philosophies, vo2max, workout library."
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
