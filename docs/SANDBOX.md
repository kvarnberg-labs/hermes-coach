# Sandbox — Autonomous Tool Development

The sandbox is an isolated Kubernetes environment where Hermes can develop new coaching tools at runtime without a redeploy. It implements a test-driven workflow: code is submitted with tests, validated in isolation, and registered if tests pass.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│ Hermes Pod (hermes namespace)                                    │
│                                                                  │
│  Agent identifies capability gap                                  │
│       │                                                          │
│       ▼                                                          │
│  develop_tool(name, code, test_code)                             │
│       │                                                          │
│       ├── 1. Base64-encode code + tests                          │
│       ├── 2. Create k8s Job in hermes-sandbox namespace          │
│       ├── 3. Poll Job status (90s timeout)                       │
│       └── 4. Fetch logs                                          │
│                                                                  │
└────────────────────────────┬─────────────────────────────────────┘
                             │ k8s API
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ Sandbox Pod (hermes-sandbox namespace)                           │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  python:3.13-slim + pytest                               │   │
│  │                                                           │   │
│  │  1. Decode base64 → /tmp/tool.py, /tmp/test_tool.py      │   │
│  │  2. Run pytest /tmp/test_tool.py                          │   │
│  │  3. Exit 0 (pass) or exit 1 (fail)                       │   │
│  │                                                           │   │
│  │  Network: DENIED (default-deny-all NetworkPolicy)        │   │
│  │  CPU: 250m | Memory: 2256Mi | Deadline: 60s             │   │
│  └──────────────────────────────────────────────────────────┘   │
└────────────────────────────┬─────────────────────────────────────┘
                             │
                    Tests pass?
                             │
                    ┌────────┴────────┐
                   Yes│               │No
                      ▼               ▼
             Write to PVC      Return logs to agent
             for iteration
```

## Security Model

### Network Isolation

The `hermes-sandbox` namespace has a default-deny-all NetworkPolicy:

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: sandbox-default-deny-all
  namespace: hermes-sandbox
spec:
  podSelector: {}
  policyTypes:
    - Ingress
    - Egress
```

**No network access whatsoever.** The sandbox cannot:
- Make HTTP requests
- Connect to databases
- Access external APIs
- Communicate with the hermes namespace

### Resource Limits

```yaml
resources:
  requests: {cpu: "100m", memory: "128Mi"}
  limits:   {cpu: "250m", memory: "256Mi"}
activeDeadlineSeconds: 60  # k8s hard-kills the pod
```

### Filesystem

- Read-only root filesystem (except `/tmp`)
- Code and tests written to `/tmp` by the Job entrypoint
- No persistent storage — everything is ephemeral

### RBAC

The `hermes-autonomy` service account has limited permissions in the sandbox namespace:

```yaml
rules:
  - apiGroups: ["batch"]
    resources: ["jobs"]
    verbs: ["create", "get", "list", "watch", "delete"]
  - apiGroups: [""]
    resources: ["pods", "pods/log"]
    verbs: ["get", "list", "watch"]
```

## Tool Development Workflow

### 1. Agent Identifies a Gap

During coaching, the agent realizes it needs a capability that no existing tool covers. For example: calculating training monotony from intervals.icu data.

### 2. Agent Writes Code and Tests

```python
# Tool code (submitted as a string)
tool_code = '''
import json

def calculate_monotony(discord_id: str, **kwargs) -> str:
    """Calculate training monotony from recent activities."""
    from training.intervals_icu import get_recent_activities
    activities = json.loads(get_recent_activities(discord_id=discord_id, days=28))
    loads = [a["training_load"] for a in activities["activities"] if a.get("training_load")]
    if not loads:
        return json.dumps({"monotony": None, "note": "No training load data"})
    monotony = sum(loads) / len(loads) / (max(loads) or 1)
    return json.dumps({"monotony": round(monotony, 3), "days": 28})
'''

# Test code (submitted as a string)
test_code = '''
import sys, json
sys.path.insert(0, "/tmp")
from calculate_monotony import calculate_monotony

def test_returns_json():
    # This would need mocking in the real sandbox
    result = calculate_monotony("test-user")
    data = json.loads(result)
    assert "monotony" in data
'''
```

### 3. Agent Calls develop_tool()

```python
result = develop_tool(
    tool_name="calculate_monotony",
    description="Calculate training monotony from 28-day activity history.",
    code=tool_code,
    test_code=test_code,
)
```

### 4. Sandbox Validates

The k8s Job:
1. Decodes base64 strings to `/tmp/tool.py` and `/tmp/test_tool.py`
2. Runs `pytest /tmp/test_tool.py -v --tb=short --import-mode=importlib`
3. Returns exit code and logs

### 5. Registration (if tests pass)

```python
# sandbox_client.py writes to PVC:
dest = "$HERMES_HOME/plugins/generated/calculate_monotony.py"
dest.write_text(code)

# Hot-load to catch import errors
spec = importlib.util.spec_from_file_location("generated.calculate_monotony", dest)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
```

The tool is now available in the current session and persists across restarts (stored on PVC).

### 6. Iteration (if tests fail)

The test output is returned to the agent, which can fix the code and retry:

```python
result = develop_tool(
    tool_name="calculate_monotony",
    description="...",
    code=fixed_code,  # Updated code
    test_code=fixed_tests,  # Updated tests
)
```

## Sandbox Image

### Building Locally

```bash
cd sandbox
docker build -t ghcr.io/kvarnberg-labs/hermes-sandbox:main .
docker push ghcr.io/kvarnberg-labs/hermes-sandbox:main
```

### Dockerfile

```dockerfile
FROM python:3.13-slim

RUN pip install --no-cache-dir pytest && rm -rf /root/.cache

RUN groupadd -g 1000 runner && useradd -u 1000 -g runner -m runner
USER runner

WORKDIR /tmp
ENTRYPOINT ["python", "-m", "pytest", "-v", "--tb=short", "--import-mode=importlib"]
```

### Image Configuration

The sandbox image is configured in `plugins/training/sandbox_client.py`:

```python
_SANDBOX_IMAGE = os.environ.get(
    "HERMES_SANDBOX_IMAGE", "ghcr.io/kvarnberg-labs/hermes-sandbox:main"
)
```

Override via environment variable in the ConfigMap:
```yaml
HERMES_SANDBOX_IMAGE: "ghcr.io/kvarnberg-labs/hermes-sandbox:custom"
```

## Job Lifecycle

1. **Created** by `sandbox_client.py` with a unique name: `sandbox-{tool_name}-{6-char-hash}`
2. **Running** — k8s schedules the pod, pytest executes
3. **Completed** (success or failure) — logs are fetched
4. **Deleted** — `sandbox_client.py` deletes the Job after fetching results
5. **TTL** — k8s also cleans up finished Jobs after 120 seconds (`ttlSecondsAfterFinished`)

## Generated Tools Directory

```
$HERMES_HOME/plugins/generated/
├── calculate_monotony.py
├── calculate_monotony.py.bak  # backup for rollback
└── ...
```

- Tools are written as plain Python files
- A `.bak` file is kept for rollback if a new version fails to import
- Tools persist on the PVC across pod restarts
- Tools are discovered by the Hermes plugin system at runtime

## Limitations

1. **No network access.** Generated tools cannot make HTTP requests or connect to external services.
2. **No persistent state.** Each Job run starts from scratch. Tools must be self-contained.
3. **60-second deadline.** Complex tests or slow imports will be killed.
4. **256Mi memory limit.** Memory-intensive operations will OOM.
5. **Standard library only.** Only `pytest` is pre-installed. Tools must use stdlib or dependencies already in the Hermes image.

## Troubleshooting

### Job Fails to Start

```bash
# Check if the sandbox namespace exists
kubectl get ns hermes-sandbox

# Check NetworkPolicy
kubectl get networkpolicy -n hermes-sandbox

# Check RBAC
kubectl auth can-i create jobs --as=system:serviceaccount:hermes:hermes-autonomy -n hermes-sandbox
```

### Tests Fail with Import Error

The sandbox only has pytest pre-installed. Tool code must use stdlib or import from the Hermes image's Python environment (which is not available in the sandbox — it's a separate image).

**Solution:** Keep tool code self-contained. If external dependencies are needed, they must be installed in the sandbox image.

### Job Times Out

```bash
# Check Job status
kubectl get jobs -n hermes-sandbox

# View logs
kubectl logs job/<job-name> -n hermes-sandbox

# Check if the image is pullable
docker pull ghcr.io/kvarnberg-labs/hermes-sandbox:main
```

### Generated Tool Not Loading

```bash
# Check if the file exists on PVC
kubectl exec -it deployment/hermes -n hermes -- ls -la /opt/data/plugins/generated/

# Check file permissions
kubectl exec -it deployment/hermes -n hermes -- stat /opt/data/plugins/generated/<tool>.py

# Restart the pod to reload plugins
kubectl rollout restart deployment/hermes -n hermes
```
