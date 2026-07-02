"""Sandbox client — autonomous tool development via Kubernetes Jobs.

Hermes uses this tool to develop new capabilities at runtime without a
redeploy.  The workflow:

  1. Hermes identifies a missing capability during coaching.
  2. It calls develop_tool() with the tool name, description, code, and tests.
  3. The client creates a k8s Job in the hermes-sandbox namespace.
  4. The Job runs pytest on the provided code in a network-isolated container.
  5. If tests pass, the tool is written to $HERMES_HOME/plugins/generated/
     and Hermes reloads the plugin registry.
  6. If tests fail, the output is returned so Hermes can iterate.

Security boundaries (enforced by k8s, not this code):
  - NetworkPolicy: default-deny-all in hermes-sandbox (no internet access)
  - Resource limits: 250m CPU, 256Mi RAM per Job
  - Timeout: activeDeadlineSeconds=60 (hard kill)
  - Read-only root filesystem (except /tmp)

The generated tools directory persists on the PVC across restarts.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_SANDBOX_IMAGE = os.environ.get(
    "HERMES_SANDBOX_IMAGE", "ghcr.io/kvarnberg-labs/hermes-sandbox:main"
)
_SANDBOX_NAMESPACE = "hermes-sandbox"
_JOB_TIMEOUT_SECS = 90  # wall-clock wait before we give up
_JOB_ACTIVE_DEADLINE = 60  # k8s hard-kills the pod after this many seconds


def _plugins_dir() -> Path:
    hermes_home = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
    d = hermes_home / "plugins"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _generated_dir() -> Path:
    # ponytail: kept for sync-coach-assets.sh compatibility
    d = _plugins_dir() / "generated"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _plugin_dir(tool_name: str) -> Path:
    """Return the plugin directory for a generated tool."""
    return _plugins_dir() / tool_name


_PLUGIN_YAML_TEMPLATE = """name: {name}
version: "1.0"
author: hermes-coach (generated)
description: {description}
"""

_INIT_TEMPLATE = """# Generated plugin — do not edit header
from __future__ import annotations
from . import tool as _tool_module


def register(ctx) -> None:
    if hasattr(_tool_module, "register_tools"):
        _tool_module.register_tools(ctx)
"""


def _job_name(tool_name: str) -> str:
    slug = tool_name.lower().replace("_", "-")[:40]
    suffix = hashlib.sha256(f"{tool_name}{time.time()}".encode()).hexdigest()[:6]
    return f"sandbox-{slug}-{suffix}"


def _k8s_client():
    """Return a configured kubernetes BatchV1Api + CoreV1Api pair."""
    try:
        from kubernetes import client as k8s
        from kubernetes import config as k8s_config
    except ImportError:
        raise RuntimeError(
            "kubernetes Python package not installed. "
            "Run: uv pip install 'kubernetes>=29.0.0,<32'"
        )
    try:
        k8s_config.load_incluster_config()
    except Exception:
        try:
            k8s_config.load_kube_config()
        except Exception as exc:
            raise RuntimeError(
                f"Could not load k8s config (in-cluster or kubeconfig): {exc}"
            ) from exc
    return k8s.BatchV1Api(), k8s.CoreV1Api()


def _build_job_manifest(job_name: str, code_b64: str, test_b64: str) -> dict:
    """Build the k8s Job spec that runs pytest on the provided code."""
    return {
        "apiVersion": "batch/v1",
        "kind": "Job",
        "metadata": {
            "name": job_name,
            "namespace": _SANDBOX_NAMESPACE,
            "labels": {"app": "hermes-sandbox", "managed-by": "hermes"},
        },
        "spec": {
            "ttlSecondsAfterFinished": 120,
            "backoffLimit": 0,
            "activeDeadlineSeconds": _JOB_ACTIVE_DEADLINE,
            "template": {
                "metadata": {"labels": {"app": "hermes-sandbox"}},
                "spec": {
                    "restartPolicy": "Never",
                    "automountServiceAccountToken": False,
                    "securityContext": {
                        "runAsNonRoot": True,
                        "runAsUser": 1000,
                        "runAsGroup": 1000,
                        "seccompProfile": {"type": "RuntimeDefault"},
                    },
                    "imagePullSecrets": [{"name": "ghcr-registry-secret"}],
                    "containers": [
                        {
                            "name": "runner",
                            "image": _SANDBOX_IMAGE,
                            "imagePullPolicy": "IfNotPresent",
                            "command": ["/bin/sh", "-c"],
                            "args": [
                                # Decode the base64-encoded files, write them to /tmp,
                                # then run pytest with strict exit codes.
                                f"echo '{code_b64}' | base64 -d > /tmp/tool.py && "
                                f"echo '{test_b64}' | base64 -d > /tmp/test_tool.py && "
                                "python -m pytest /tmp/test_tool.py -v --tb=short "
                                "--import-mode=importlib 2>&1"
                            ],
                            "resources": {
                                "requests": {"cpu": "100m", "memory": "128Mi"},
                                "limits": {"cpu": "250m", "memory": "256Mi"},
                            },
                            "securityContext": {
                                "readOnlyRootFilesystem": False,  # /tmp must be writable
                                "allowPrivilegeEscalation": False,
                                "capabilities": {"drop": ["ALL"]},
                            },
                        }
                    ],
                },
            },
        },
    }


def _wait_for_job(
    batch_api,
    core_api,
    job_name: str,
    timeout: int = _JOB_TIMEOUT_SECS,
) -> tuple[bool, str]:
    """Poll until the Job completes; return (succeeded, logs)."""
    from kubernetes.client.rest import ApiException

    deadline = time.time() + timeout
    pod_name = None

    while time.time() < deadline:
        time.sleep(3)

        # Find the pod
        if pod_name is None:
            try:
                pods = core_api.list_namespaced_pod(
                    _SANDBOX_NAMESPACE,
                    label_selector=f"job-name={job_name}",
                )
                if pods.items:
                    pod_name = pods.items[0].metadata.name
            except ApiException:
                pass

        # Check Job status
        try:
            job = batch_api.read_namespaced_job(job_name, _SANDBOX_NAMESPACE)
        except ApiException:
            return False, "Job disappeared unexpectedly."

        if job.status.succeeded:
            logs = _fetch_logs(core_api, pod_name) if pod_name else "(no logs)"
            return True, logs

        if job.status.failed:
            logs = _fetch_logs(core_api, pod_name) if pod_name else "(no logs)"
            return False, logs

    return False, f"Job timed out after {timeout}s."


def _fetch_logs(core_api, pod_name: str) -> str:
    from kubernetes.client.rest import ApiException

    try:
        return core_api.read_namespaced_pod_log(
            pod_name, _SANDBOX_NAMESPACE, tail_lines=200
        )
    except ApiException as exc:
        return f"(could not fetch logs: {exc})"


def _register_generated_tool(tool_name: str, description: str, code: str) -> str:
    """Write a proper Hermes plugin directory and hot-reload it."""
    plugin_dir = _plugin_dir(tool_name)
    backup_dir = _plugins_dir() / f"{tool_name}.bak"

    # Back up existing plugin for rollback
    if plugin_dir.exists():
        import shutil

        if backup_dir.exists():
            shutil.rmtree(backup_dir)
        shutil.copytree(plugin_dir, backup_dir)

    try:
        plugin_dir.mkdir(parents=True, exist_ok=True)
        (plugin_dir / "plugin.yaml").write_text(
            _PLUGIN_YAML_TEMPLATE.format(name=tool_name, description=description),
            encoding="utf-8",
        )
        (plugin_dir / "tool.py").write_text(code, encoding="utf-8")
        (plugin_dir / "__init__.py").write_text(_INIT_TEMPLATE, encoding="utf-8")

        # Hot-reload via Hermes plugin discovery
        try:
            from hermes_cli.plugins import discover_plugins

            discover_plugins(force=True)
        except Exception as exc:
            logger.warning("discover_plugins failed (may need restart): %s", exc)

        return "ok"
    except Exception as exc:
        # Roll back
        import shutil

        shutil.rmtree(plugin_dir, ignore_errors=True)
        if backup_dir.exists():
            shutil.copytree(backup_dir, plugin_dir)
        return f"Failed to write plugin — rolled back: {exc}"


def develop_tool(
    tool_name: str,
    description: str,
    code: str,
    test_code: str,
    **_: Any,
) -> str:
    """Develop and deploy a new Hermes tool via the sandbox.

    Submits the provided code and tests to an isolated k8s Job, waits for
    results, and registers the tool if tests pass.

    Args:
        tool_name:   Snake_case name for the new tool (e.g. 'calculate_monotony').
        description: One-sentence description of what the tool does.
        code:        Complete Python source of the tool module.
                     Must define a function named tool_name() and call
                     ctx.register_tool() or use the registry pattern.
        test_code:   Complete pytest test file that imports from /tmp/tool.py.
                     Must contain at least one test function.

    Returns JSON with keys: success (bool), output (test output), message.
    """
    if not tool_name.replace("_", "").isalnum():
        return json.dumps(
            {
                "success": False,
                "error": "tool_name must be snake_case alphanumeric.",
            }
        )

    # Try to submit the k8s Job
    try:
        batch_api, core_api = _k8s_client()
    except RuntimeError as exc:
        return json.dumps(
            {
                "success": False,
                "error": str(exc),
                "hint": "The sandbox requires a running k8s cluster with the hermes-sandbox namespace.",
            }
        )

    job_name = _job_name(tool_name)
    code_b64 = base64.b64encode(code.encode()).decode()
    test_b64 = base64.b64encode(test_code.encode()).decode()

    manifest = _build_job_manifest(job_name, code_b64, test_b64)

    try:
        from kubernetes import client as k8s

        batch_api.create_namespaced_job(_SANDBOX_NAMESPACE, manifest)
    except Exception as exc:
        return json.dumps({"success": False, "error": f"Failed to create Job: {exc}"})

    logger.info("Sandbox Job %s created for tool %s", job_name, tool_name)
    succeeded, logs = _wait_for_job(batch_api, core_api, job_name)

    # Clean up the Job regardless of outcome
    try:
        from kubernetes import client as k8s

        batch_api.delete_namespaced_job(
            job_name,
            _SANDBOX_NAMESPACE,
            body=k8s.V1DeleteOptions(propagation_policy="Foreground"),
        )
    except Exception:
        pass  # TTL controller will handle it

    if not succeeded:
        return json.dumps(
            {
                "success": False,
                "output": logs,
                "message": (
                    "Tests failed. Review the output above, fix the code or tests, "
                    "and call develop_tool() again."
                ),
            }
        )

    # Tests passed — register the tool
    result = _register_generated_tool(tool_name, description, code)
    if result != "ok":
        return json.dumps(
            {
                "success": False,
                "output": logs,
                "message": f"Tests passed but tool registration failed: {result}",
            }
        )

    logger.info("Tool %s deployed to generated plugins", tool_name)
    return json.dumps(
        {
            "success": True,
            "output": logs,
            "message": (
                f"Tool '{tool_name}' deployed successfully. "
                "It is now available in this session and will persist across restarts."
            ),
            "tool_path": str(_plugin_dir(tool_name)),
        }
    )


def register_tools(ctx) -> None:
    ctx.register_tool(
        name="develop_tool",
        toolset="self-improve",  # intentionally NOT "training" — Discord users cannot call this
        schema={
            "name": "develop_tool",
            "description": (
                "Develop and deploy a new coaching tool at runtime. "
                "Write the tool code and a pytest test file, submit them to an "
                "isolated sandbox, and if tests pass the tool is registered immediately. "
                "Use this when you identify a capability gap — a calculation, "
                "data transformation, or analysis that no existing tool covers."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "tool_name": {
                        "type": "string",
                        "description": "Snake_case name, e.g. 'calculate_training_monotony'.",
                    },
                    "description": {
                        "type": "string",
                        "description": "One sentence describing what the tool does.",
                    },
                    "code": {
                        "type": "string",
                        "description": (
                            "Complete Python source of the tool. "
                            "Must be importable from /tmp/tool.py in the test file."
                        ),
                    },
                    "test_code": {
                        "type": "string",
                        "description": (
                            "Complete pytest test file. Import the tool with: "
                            "import sys; sys.path.insert(0, '/tmp'); from tool import <fn>. "
                            "Must include at least one test_* function."
                        ),
                    },
                },
                "required": ["tool_name", "description", "code", "test_code"],
            },
        },
        handler=lambda args, **kw: develop_tool(
            tool_name=args["tool_name"],
            description=args["description"],
            code=args["code"],
            test_code=args["test_code"],
        ),
    )
