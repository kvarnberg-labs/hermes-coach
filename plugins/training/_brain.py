"""Shared coach-brain YAML loader.

Extracted from coaching.py and strength_coach.py to eliminate duplicated
loading, caching, and directory-resolution logic (Fowler's Duplicated Code
smell). Both modules now import `_load_all()` from here instead of
maintaining their own copies.

Interface:
    _load_all() → dict[str, Any]

The implementation handles HERMES_HOME resolution, YAML parsing, 60-second
TTL caching, missing-directory and missing-yaml grace, and pyyaml absence.
"""

from __future__ import annotations

import logging
import os
import time as _time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_brain_cache: dict[str, Any] | None = None
_brain_cache_mtime: float = 0.0
_brain_cache_dir: str | None = None
_BRAIN_CACHE_TTL: float = 60.0  # seconds


def _brain_dir() -> Path:
    hermes_home_raw = os.environ.get("HERMES_HOME")
    if not hermes_home_raw:
        raise RuntimeError(
            "HERMES_HOME is not set — cannot resolve coach-brain directory."
        )
    return Path(hermes_home_raw) / "coach-brain"


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
