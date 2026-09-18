"""Functional test for docker/sync-coach-assets.sh.

Runs the real sync script against a temp image root and a temp HERMES_HOME and
asserts the PVC ends up matching the image. The bug this guards: nothing synced
`plugins/training` to the PVC, so a stale PVC copy shadowed the bundled plugin
(`hermes plugins list` reported training as Source: user) and a merged fix never
reached the running gateway.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "docker" / "sync-coach-assets.sh"


def _run_sync(tmp_path: Path) -> tuple[Path, Path]:
    """Run the sync with a temp image root and HERMES_HOME; return both."""
    image = tmp_path / "image"
    home = tmp_path / "home"
    (image / "coach-brain").mkdir(parents=True)
    (image / "coach-brain" / "heat.yaml").write_text("image: new\n")
    (image / "coach-skills" / "coaching").mkdir(parents=True)
    (image / "coach-skills" / "coaching" / "SKILL.md").write_text("new\n")
    (image / "plugins" / "training").mkdir(parents=True)
    (image / "plugins" / "training" / "intervals_icu.py").write_text("NEW = 1\n")
    (image / "plugins" / "training" / "__pycache__").mkdir(parents=True)
    (image / "plugins" / "training" / "__pycache__" / "x.pyc").write_text("junk")
    (image / "AGENTS.md").write_text("agents\n")
    (image / "loops" / "self-improve").mkdir(parents=True)
    (image / "loops" / "self-improve" / "CONTRACT.md").write_text("contract\n")

    # A stale PVC: an older plugin copy, a PVC-only generated tool, a drifted
    # coach-brain YAML, and a runtime-written worklog that must survive.
    (home / "plugins" / "training").mkdir(parents=True)
    (home / "plugins" / "training" / "intervals_icu.py").write_text("OLD = 1\n")
    (home / "plugins" / "generated").mkdir(parents=True)
    (home / "plugins" / "generated" / "mine.py").write_text("keep\n")
    (home / "coach-brain").mkdir(parents=True)
    (home / "coach-brain" / "heat.yaml").write_text("pvc: drifted\n")
    (home / "loops").mkdir(parents=True)
    (home / "loops" / "worklog.md").write_text("runtime worklog\n")

    subprocess.run(
        ["sh", str(SCRIPT)],
        check=True,
        env={
            **os.environ,
            "HERMES_HOME": str(home),
            "COACH_IMAGE_ROOT": str(image),
        },
        capture_output=True,
    )
    return image, home


def test_training_plugin_is_mirrored_from_the_image(tmp_path: Path) -> None:
    image, home = _run_sync(tmp_path)
    assert (
        (home / "plugins" / "training" / "intervals_icu.py").read_text()
        == (image / "plugins" / "training" / "intervals_icu.py").read_text()
    ), "a stale PVC plugin copy would shadow the bundled plugin"


def test_pycache_is_not_synced(tmp_path: Path) -> None:
    _run_sync(tmp_path)
    home = tmp_path / "home"
    assert not (home / "plugins" / "training" / "__pycache__").exists()


def test_pvc_only_dirs_survive(tmp_path: Path) -> None:
    _run_sync(tmp_path)
    home = tmp_path / "home"
    assert (home / "plugins" / "generated" / "mine.py").exists()


def test_drifted_coach_brain_is_overwritten(tmp_path: Path) -> None:
    image, home = _run_sync(tmp_path)
    assert (
        (home / "coach-brain" / "heat.yaml").read_text()
        == (image / "coach-brain" / "heat.yaml").read_text()
    )


def test_runtime_worklog_survives(tmp_path: Path) -> None:
    _run_sync(tmp_path)
    home = tmp_path / "home"
    assert (home / "loops" / "worklog.md").read_text() == "runtime worklog\n"
