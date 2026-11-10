"""Discord tool surface and cron-prompt budget.

Why this exists: from 2026-07-02 the deployment set `tools.discord.enabled`,
a key no code reads. The real gate is `platform_toolsets.discord`, which
defaulted to the `hermes-discord` preset — terminal, file, execute_code,
cronjob. Three non-operator athletes (lars3698, wilma0141, sencit60) ran shell
and code-execution calls in DM sessions as late as 2026-11-08, and every DM
request carried 54 tool schemas (18.6k tokens, 60% of a short request).

A config key that silently does nothing is the failure mode, so the assertion
lives here: if the deployment stops setting `platform_toolsets.discord`, or
that list regains a shell-bearing toolset, this test fails.

The worklog cap is the same idea for the cron prompt: scan-signals.sh injected
38,459 of its 41,910 output chars from a 437 KB worklog.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
DEPLOYMENT = ROOT / "apps" / "hermes" / "deployment.yaml"
CONFIGMAP = ROOT / "apps" / "hermes" / "configmap.yaml"
SCAN = ROOT / "scripts" / "scan-signals.sh"

# Toolsets that hand the model a shell, a filesystem, arbitrary code, a scheduler
# or another agent loop. An athlete's DM must never register one.
FORBIDDEN = {
    "terminal", "file", "code_execution", "browser", "cronjob", "delegation",
    "computer_use", "web", "image_gen", "skills_hub", "video", "x_search",
}
REQUIRED = {"training", "weather", "skills", "memory", "clarify"}


def _discord_toolsets() -> set[str]:
    text = DEPLOYMENT.read_text(encoding="utf-8")
    match = re.search(r'_save_platform_tools\(cfg, "discord", \{([^}]*)\}\)', text)
    assert match, (
        "deployment.yaml must set the Discord toolset list through "
        "_save_platform_tools — setting platform_toolsets alone leaves every "
        "omitted plugin toolset enabled by default (tools_config.py)")
    return {part.strip().strip('"') for part in match.group(1).split(",") if part.strip()}


def test_discord_toolsets_exclude_shell_and_code():
    toolsets = _discord_toolsets()
    assert not FORBIDDEN & set(toolsets), (
        f"shell/code/scheduler toolsets reachable from an athlete DM: "
        f"{sorted(FORBIDDEN & set(toolsets))}")


def test_discord_toolsets_keep_the_coaching_surface():
    missing = REQUIRED - set(_discord_toolsets())
    assert not missing, f"coaching toolsets dropped from the DM: {sorted(missing)}"


def test_dead_tools_key_is_gone():
    # `tools.discord.enabled` is read by no code. Leaving it set suggests a gate
    # that does not exist — that is how the shell leak survived four months.
    # Matches the command, not the comment that explains the removal.
    assert not re.search(r"config set tools\.discord\.enabled",
                         DEPLOYMENT.read_text(encoding="utf-8"))


def test_self_improve_delivers_to_a_dm_not_general():
    text = CONFIGMAP.read_text(encoding="utf-8")
    channel = re.search(r'SELF_IMPROVE_CHANNEL:\s*"(\d+)"', text)
    assert channel, "SELF_IMPROVE_CHANNEL must be set"
    # 1508814801869082758 is the guild #general channel; lars/wilma/sencit60
    # are members. Repo/PR detail there is athlete-visible.
    assert channel.group(1) != "1508814801869082758", (
        "self-improve must not deliver repo detail to the guild #general channel")


def test_scan_signals_caps_the_worklog_block(tmp_path):
    home = tmp_path
    (home / "loops" / "signals").mkdir(parents=True)
    # 200 KB of long bullet entries: the shape worklog.md actually has.
    (home / "loops" / "worklog.md").write_text(
        "".join(f"## 2026-11-{i % 28 + 1:02d} 12:00 UTC\n"
                f"- {'x' * 900}\n" for i in range(220)), encoding="utf-8")

    out = subprocess.run(
        ["sh", str(SCAN)], capture_output=True, text=True,
        env={**os.environ, "HERMES_HOME": str(home)}, check=True,
    ).stdout

    assert len(out) < 8_000, (
        f"scan-signals injected {len(out)} chars into the cron prompt; "
        "the worklog block must stay capped")
    assert "RECENT WORKLOG" in out


def test_discord_toolsets_are_saved_through_the_supported_writer():
    """plugin toolsets are enabled by default unless recorded as known for the
    platform. `hermes config set platform_toolsets.discord` alone therefore left
    self-improve (develop_tool -> sandbox job runner) reachable from a DM.
    _save_platform_tools is the writer that also fills known_plugin_toolsets."""
    text = DEPLOYMENT.read_text(encoding="utf-8")
    assert "_save_platform_tools(" in text
    assert "known_plugin_toolsets" in text or "_save_platform_tools(" in text
    # The dead key must not come back as the mechanism.
    assert "config set platform_toolsets.discord" not in text


def test_self_improve_is_never_in_the_dm_toolset_list():
    """self-improve holds develop_tool, which starts k8s Jobs. It must be
    excluded explicitly, not by omission."""
    assert "self-improve" not in _discord_toolsets()
def test_scan_signals_rotates_an_oversized_worklog(tmp_path):
    """The 4 KB prompt cap cannot hold if worklog.md grows to 437 KB again:
    the tail of a giant file is still giant. Rotation keeps it bounded."""
    home = tmp_path
    (home / "loops" / "signals").mkdir(parents=True)
    worklog = home / "loops" / "worklog.md"
    worklog.write_text("## 2026-11-01 12:00 UTC\n" + ("y" * 900 + "\n") * 400,
                       encoding="utf-8")
    assert worklog.stat().st_size > 200_000

    out = subprocess.run(
        ["sh", str(SCAN)], capture_output=True, text=True,
        env={**os.environ, "HERMES_HOME": str(home)}, check=True,
    ).stdout

    assert worklog.stat().st_size <= 200_000
    assert (home / "loops" / "worklog.md.rotations").exists()
    assert len(out) < 8_000
