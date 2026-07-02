"""Tests for the training plugin — sandbox client."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "plugins"))

from training import sandbox_client


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


class TestDevelopTool:
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
