# Deployment Guide

## Infrastructure

Hermes Coach runs on a Hetzner CS23 VPS (Helsinki) with k3s single-node Kubernetes.

| Component | Specification |
|-----------|---------------|
| VPS | Hetzner CS23 (4 vCPU, 8GB RAM, 160GB NVMe) |
| OS | Ubuntu 24.04 LTS |
| K8s | k3s v1.31+ |
| GitOps | Flux CD |
| Registry | GitHub Container Registry (ghcr.io) |
| Storage | local-path provisioner (PVC on host) |

> **No ingress needed.** Hermes is a Discord bot that connects outbound to Discord's gateway. There is no inbound HTTP traffic to route, so no ingress controller or Cloudflare tunnel is required.

## One-Time VPS Setup

### 1. Provision Hetzner VPS

```bash
# Via Hetzner Cloud Console or hcloud CLI
hcloud server create \
  --type cs23 \
  --image ubuntu-24.04 \
  --location hel1 \
  --name hermes-coach \
  --ssh-key <your-key>
```

### 2. Install k3s

```bash
curl -sfL https://get.k3s.io | sh -
sudo cp /etc/rancher/k3s/k3s.yaml ~/.kube/config
sudo chmod 600 ~/.kube/config
```

### 3. Install local-path Provisioner

Already included with k3s by default. Verify:
```bash
kubectl get sc
# Should show "local-path" as default
```

### 4. Create GHCR Pull Secret

The deployment pulls images from `ghcr.io/kvarnberg-labs/hermes-coach`. Create the pull secret before Flux bootstraps:

```bash
# Generate a GitHub PAT with read:packages scope, then:
kubectl create namespace hermes
kubectl create secret docker-registry ghcr-registry-secret \
  --namespace hermes \
  --docker-server=ghcr.io \
  --docker-username=<your-github-username> \
  --docker-password=<your-github-pat>

# Also create it in hermes-sandbox — needed to pull the sandbox runner image
kubectl create namespace hermes-sandbox
kubectl create secret docker-registry ghcr-registry-secret \
  --namespace hermes-sandbox \
  --docker-server=ghcr.io \
  --docker-username=<your-github-username> \
  --docker-password=<your-github-pat>
```

This secret is referenced in `deployment.yaml` and in dynamically-created sandbox Jobs. It cannot be committed to git because it contains your PAT. Recreate it in both namespaces after any cluster rebuild.

### 5. Install SealedSecrets Controller

```bash
# Get the latest controller manifest
kubectl apply -f https://github.com/bitnami-labs/sealed-secrets/releases/download/v0.28.0/controller.yaml

# Wait for the controller to be ready
kubectl wait --namespace sealed-secrets \
  --for=condition=ready pod \
  --selector=app.kubernetes.io/name=sealed-secrets \
  --timeout=90s
```

### 6. Generate Sealing Certificate

```bash
kubectl get secret -n sealed-secrets \
  -o jsonpath="{.items[0].data.tls\.crt}" | base64 -d > ~/.hermes/coach-cluster-cert.pem
```

This certificate is used to seal secrets for GitOps. **Do not commit it.**

### 7. Install Flux CD

```bash
# Install flux CLI
brew install fluxcd/tap/flux

# Bootstrap Flux to watch this repo
flux bootstrap github \
  --owner=kvarnberg-labs \
  --repository=hermes-coach \
  --branch=main \
  --path=clusters/coach \
  --personal
```

This generates `clusters/coach/flux-system/gotk-components.yaml` with the actual Flux controllers.

## Secrets Management

### Sealing Secrets

```bash
# Seal Discord bot token + allowed user IDs (space-separated Discord user IDs)
kubectl create secret generic hermes-discord-secret \
  --namespace hermes \
  --from-literal=DISCORD_BOT_TOKEN=<token> \
  --from-literal=DISCORD_ALLOWED_USERS="<user-id-1> <user-id-2>" \
  --dry-run=client -o yaml | \
  kubeseal --cert ~/.hermes/coach-cluster-cert.pem --format yaml \
  > apps/hermes/hermes-discord-sealed-secret.yaml

# Seal model API key
kubectl create secret generic hermes-model-secret \
  --namespace hermes \
  --from-literal=OPENCODE_GO_API_KEY=<key> \
  --dry-run=client -o yaml | \
  kubeseal --cert ~/.hermes/coach-cluster-cert.pem --format yaml \
  > apps/hermes/hermes-model-sealed-secret.yaml
```

### Adding a New Athlete

Re-seal `hermes-discord-secret` with the new user ID appended to `DISCORD_ALLOWED_USERS`, then push. Flux reconciles within 1 minute.

### Updating Secrets

Re-seal with the same command whenever a secret value changes. The sealed secret is encrypted for this specific cluster — it cannot be reused on another cluster.

## Discord Configuration

### 1. Create Discord Bot

1. Go to Discord Developer Portal → Applications → New Application
2. Create a Bot, copy the token
3. Enable `MESSAGE_CONTENT` intent
4. Under OAuth2, invite the bot to your server with scope `bot` and permission `Send Messages`

> **DM-only model.** Athletes interact with Hermes via Discord DMs, not a shared channel.
> No channel IDs or role IDs are needed. Access is controlled entirely by
> `DISCORD_ALLOWED_USERS` in the sealed secret — add a Discord user ID to grant access.

## Deploying

### Via GitOps (recommended)

```bash
# Make changes, commit, and push
git add .
git commit -m "feat: update coaching knowledge"
git push origin main

# Flux reconciles within 1 minute
flux get kustomizations -n flux-system
```

### Via kubectl (manual)

```bash
# Apply all resources
kubectl apply -k apps/

# Check deployment status
kubectl get pods -n hermes
kubectl get pods -n hermes-sandbox

# View logs
kubectl logs -f deployment/hermes -n hermes
```

### Force Restart

Update the config-generation annotation in `deployment.yaml`:
```yaml
annotations:
  hermes.kvarnberg.io/config-generation: "coach-v2"  # bump this string
```

## Monitoring

### Health Probes

The deployment configures three probes on `/health` (port 8642):
- **Startup**: 30 failures × 10s = 5 minutes max startup time
- **Readiness**: 3 failures × 10s = 30 seconds before traffic stops
- **Liveness**: 3 failures × 30s = 90 seconds before restart

### Logs

```bash
# Agent logs
kubectl logs deployment/hermes -n hermes --tail=100

# Init container logs (config setup)
kubectl logs deployment/hermes -n hermes -c configure-hermes

# Sandbox job logs
kubectl get jobs -n hermes-sandbox
kubectl logs job/<job-name> -n hermes-sandbox
```

### PVC Data

```bash
# Inspect PVC contents
kubectl exec -it deployment/hermes -n hermes -- ls -la /opt/data/

# Check coach-brain sync
kubectl exec -it deployment/hermes -n hermes -- ls -la /opt/data/coach-brain/

# Check user credentials
kubectl exec -it deployment/hermes -n hermes -- ls -la /opt/data/users/
```

## Scaling

The deployment uses `strategy.type: Recreate` to prevent two gateway instances from fighting over Discord events. This is intentional — Hermes Coach is designed to run as a single replica.

If you need high availability:
1. Use a shared PVC (NFS, not local-path)
2. Implement leader election via k8s Leases (RBAC already configured)
3. Change strategy to `RollingUpdate` with `maxUnavailable: 1`

## Rollback

```bash
# Rollback to previous deployment
kubectl rollout undo deployment/hermes -n hermes

# Rollback to specific revision
kubectl rollout undo deployment/hermes -n hermes --to-revision=3
```

## Disaster Recovery

### PVC Backup

```bash
# Create a backup pod
kubectl run backup-pod \
  --image=busybox \
  --rm -it --restart=Never \
  -n hermes \
  -- sh -c "tar czf /tmp/hermes-data.tar.gz -C /opt/data ."

# Copy backup to local machine
kubectl cp hermes/backup-pod:/tmp/hermes-data.tar.gz ./hermes-data-backup.tar.gz
```

### PVC Restore

```bash
# Delete existing PVC (warning: this destroys current data)
kubectl delete pvc hermes-data -n hermes

# Create restore pod with backup
kubectl run restore-pod \
  --image=busybox \
  --rm -it --restart=Never \
  -n hermes \
  -- sh -c "tar xzf /opt/data/hermes-data.tar.gz -C /opt/data/"
```
