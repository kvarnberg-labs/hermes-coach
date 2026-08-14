"""Tests for the training plugin — sandbox client."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "plugins"))

from training import sandbox_client


@pytest.fixture
def fake_hermes_cli(monkeypatch):
    """Inject a fake hermes_cli.plugins.discover_plugins so the hot-reload
    path can be exercised without the real hermes package installed."""
    import types

    pkg = types.ModuleType("hermes_cli")
    sub = types.ModuleType("hermes_cli.plugins")
    sub.discover_plugins = lambda force=False: None
    monkeypatch.setitem(sys.modules, "hermes_cli", pkg)
    monkeypatch.setitem(sys.modules, "hermes_cli.plugins", sub)


class TestJobName:
    def test_generates_slug_from_name(self):
        name = sandbox_client._job_name("calculate_monotony")
        assert name.startswith("sandbox-calculate-monotony-")
        assert len(name) <= 50  # 40 slug + 7 prefix + 6 hash

    def test_different_names_produce_different_slugs(self):
        n1 = sandbox_client._job_name("tool_alpha")
        n2 = sandbox_client._job_name("tool_beta")
        # The slug portion (second segment) must differ
        slug1 = n1.split("-", 3)[2]  # "alpha-<hash>"
        slug2 = n2.split("-", 3)[2]  # "beta-<hash>"
        assert slug1 != slug2

    def test_same_name_rapid_calls_produce_different_jobs(self):
        # Two same-name submissions back-to-back must not collide on the
        # time-based suffix (was a real risk with time.time() second resolution).
        n1 = sandbox_client._job_name("calculate_monotony")
        n2 = sandbox_client._job_name("calculate_monotony")
        assert n1 != n2


class TestBuildJobManifest:
    def test_manifest_has_required_fields(self):
        manifest = sandbox_client._build_job_manifest(
            "test-job", "Y29kZQ==", "dGVzdA=="
        )
        assert manifest["apiVersion"] == "batch/v1"
        assert manifest["kind"] == "Job"
        assert manifest["metadata"]["namespace"] == "hermes-sandbox"
        assert manifest["spec"]["activeDeadlineSeconds"] == 60
        assert manifest["spec"]["backoffLimit"] == 0

    def test_manifest_includes_code_and_tests(self):
        manifest = sandbox_client._build_job_manifest(
            "test-job", "Y29kZQ==", "dGVzdA=="
        )
        container = manifest["spec"]["template"]["spec"]["containers"][0]
        args = container["args"][0]
        assert "Y29kZQ==" in args
        assert "dGVzdA==" in args
        assert "pytest" in args
        assert "/tmp/generated_tool/tool.py" in args
        assert "/tmp/generated_tool/__init__.py" in args
        assert "PYTHONPATH=/tmp " in args
        assert "/opt/hermes/plugins" not in args

    def test_manifest_is_self_contained(self):
        manifest = sandbox_client._build_job_manifest(
            "test-job", "Y29kZQ==", "dGVzdA=="
        )
        args = manifest["spec"]["template"]["spec"]["containers"][0]["args"][0]
        assert "from .tool import *" in args
        # training plugins are NOT mounted — generated tools must be self-contained
        assert "/opt/hermes/plugins" not in args

    def test_manifest_includes_ghcr_pull_secret(self):
        manifest = sandbox_client._build_job_manifest(
            "test-job", "Y29kZQ==", "dGVzdA=="
        )
        pull_secrets = manifest["spec"]["template"]["spec"]["imagePullSecrets"]
        assert {"name": "ghcr-registry-secret"} in pull_secrets

    def test_manifest_has_security_context(self):
        manifest = sandbox_client._build_job_manifest(
            "test-job", "Y29kZQ==", "dGVzdA=="
        )
        sec = manifest["spec"]["template"]["spec"]["securityContext"]
        assert sec["runAsNonRoot"] is True
        container = manifest["spec"]["template"]["spec"]["containers"][0]
        assert container["securityContext"]["allowPrivilegeEscalation"] is False


class TestRegisterGeneratedTool:
    def test_writes_plugin_directory(self, tmp_path, monkeypatch, fake_hermes_cli):
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        status, detail = sandbox_client._register_generated_tool(
            "my_tool",
            "Does something useful.",
            "def register_tools(ctx): pass\n",
        )
        assert status == "ok"
        assert detail == ""
        plugin_dir = tmp_path / "plugins" / "my_tool"
        assert (plugin_dir / "plugin.yaml").exists()
        assert (plugin_dir / "tool.py").exists()
        assert (plugin_dir / "__init__.py").exists()
        assert "my_tool" in (plugin_dir / "plugin.yaml").read_text()
        # No prior plugin -> no backup created, and backups never live under plugins/
        assert not (tmp_path / ".plugin-backups" / "my_tool").exists()

    def test_rolls_back_on_error(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        # Pre-populate an existing plugin so rollback has something to restore
        plugin_dir = tmp_path / "plugins" / "my_tool"
        plugin_dir.mkdir(parents=True)
        original = "name: my_tool\n"
        (plugin_dir / "plugin.yaml").write_text(original)

        # Force failure during write by patching Path.write_text
        with patch.object(Path, "write_text", side_effect=OSError("disk full")):
            result = sandbox_client._register_generated_tool("my_tool", "desc", "code")
        status, detail = result
        assert status == "failed"
        assert "disk full" in detail
        # Original plugin.yaml should be restored
        assert (plugin_dir / "plugin.yaml").read_text() == original

    def test_pending_restart_when_reload_unavailable(self, tmp_path, monkeypatch):
        # Without hermes_cli installed, hot-reload fails -> the tool is on disk
        # but reported as pending_restart (not a false "live" success).
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        status, detail = sandbox_client._register_generated_tool(
            "my_tool", "desc", "def register_tools(ctx): pass\n")
        assert status == "pending_restart"
        assert (tmp_path / "plugins" / "my_tool" / "tool.py").exists()

    def test_rejects_invalid_tool_name(self):
        result = json.loads(
            sandbox_client.develop_tool(
                tool_name="bad tool name!",
                description="test",
                code="print(1)",
                test_code="def test(): pass",
            )
        )
        assert not result["success"]
        assert "snake_case" in result["error"]

    def test_returns_error_when_k8s_unavailable(self):
        with patch(
            "training.sandbox_client._k8s_client", side_effect=RuntimeError("no k8s")
        ):
            result = json.loads(
                sandbox_client.develop_tool(
                    tool_name="my_tool",
                    description="test tool",
                    code="print(1)",
                    test_code="def test(): pass",
                )
            )
            assert not result["success"]
            assert "no k8s" in result["error"]
