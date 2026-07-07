"""Shared test fixtures and helpers for the hermes-coach test suite."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _clear_coaching_cache() -> None:
    """Clear the coach-brain module-level cache before every test.

    Without this, a previous test that hit _load_all() and cached {}
    (e.g. because pyyaml was missing) would poison subsequent tests
    for up to 60 seconds.
    """
    try:
        from training import coaching
    except ImportError:
        return

    coaching._brain_cache = None
    coaching._brain_cache_mtime = 0.0
