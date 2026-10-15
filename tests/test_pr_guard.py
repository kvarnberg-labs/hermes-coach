"""CONTRACT.md enforcement for the self-improvement loop's PR path (scripts/pr_guard.py)."""

from __future__ import annotations

import base64
import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import pr_guard  # noqa: E402

BODY = "Failure class: knowledge_gap · Anchor: signal x · Golden check: n/a · Evidence: Lorenzo 2010"


@pytest.mark.parametrize("path", ["coach-brain/heat.yaml", "plugins/training/new_tool.py"])
def test_allowed_paths(path):
    assert pr_guard.check(path, "improve: x", BODY) == []


@pytest.mark.parametrize("path", [
    "tests/golden/cases.yaml",
    "tests/test_golden_verifiers.py",
    "skills/coaching/SKILL.md",
    "skills/self-improvement/SKILL.md",
    "loops/self-improve/CONTRACT.md",
    "scripts/brief_lint.py",
    "apps/hermes/deployment.yaml",
    "coach-brain/../tests/golden/cases.yaml",
    "plugins/training/sub/x.py",
])
def test_forbidden_paths(path):
    assert pr_guard.check(path, "improve: x", BODY)


def test_title_and_body_fields_required():
    errors = pr_guard.check("coach-brain/heat.yaml", "add heat", "what changed")
    assert any("improve: " in e for e in errors)
    assert any("Failure class:" in e and "Evidence:" in e for e in errors)


def test_existing_plugin_file_refused_new_one_allowed():
    assert pr_guard.existing_file("plugins/training/intervals_icu.py", "abc123")
    assert pr_guard.existing_file("plugins/training/new_tool.py", "") == []
    assert pr_guard.existing_file("coach-brain/heat.yaml", "abc123") == []


def test_added_lines_limit():
    base = "a\n" * 10
    assert pr_guard.added_lines(base + "b\n" * 49, base) == []
    assert pr_guard.added_lines(base + "b\n" * 50, base)


def test_one_improve_pr_per_day():
    today = dt.date(2026, 10, 15)
    prs = [{"html_url": "u1", "head": {"ref": "improve/heat"}, "created_at": "2026-10-15T05:00:00Z"},
           {"html_url": "u2", "head": {"ref": "feat/x"}, "created_at": "2026-10-15T06:00:00Z"}]
    assert pr_guard.open_today(prs, today)
    assert pr_guard.open_today(prs, dt.date(2026, 10, 16)) == []
    assert pr_guard.open_today(prs[1:], today) == []


def test_base_file_decodes_content_and_sha(tmp_path):
    raw = json.dumps({"sha": "s1", "content": base64.b64encode("x: 1\n".encode()).decode()})
    out = tmp_path / "base"
    assert pr_guard.base_file(raw, str(out)) == "s1"
    assert out.read_text() == "x: 1\n"
    assert pr_guard.base_file("", str(out)) == "" and out.read_text() == ""


def test_open_today_cli_refuses_unparseable_github_response():
    r = subprocess.run([sys.executable, str(SCRIPTS / "pr_guard.py"), "open-today"],
                       input="", capture_output=True, text=True)
    assert r.returncode == 1 and "could not list open PRs" in r.stderr


def test_create_pr_refuses_before_any_network_call(tmp_path):
    env = {**os.environ, "GITHUB_TOKEN": "", "HERMES_HOME": str(tmp_path), "PATH": os.environ["PATH"]}
    r = subprocess.run(["sh", str(SCRIPTS / "create-pr.sh"), "tests/golden/cases.yaml", "x",
                        "improve: x", BODY], capture_output=True, text=True, env=env)
    assert r.returncode == 1
    assert "REFUSED" in r.stderr and "no GitHub token" not in r.stderr
