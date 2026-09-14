# Audit Remediation Plan — 2026-09

Source: repo-wide audit (security / performance / agent context window), this session.
Secret rotation (`super_secrets.txt`) intentionally **excluded** per Lead decision.
Every change below is reviewed and approved by the Lead before merge; this plan
proposes, applies nothing.

Tracked issues (td): td-3b2e32, td-7befd2, td-37b117, td-923922, td-7bc7c5,
td-b9533b, td-1b4091.

Test command for all items (per AGENTS.md):
`PYTHONPATH=plugins python -m pytest tests/ -q --import-mode=importlib`

Suggested order: 1 → 2 → 3 (independent; 3 is one small PR — live-verified
2026-09-14), then 4, then 5 (largest).
Item 6 is independent of 4 and 5 (it touches only the Dockerfile + the sync
script) — do it anytime. Item 7 is a decision, not code.

---

## 1. Cache hardening + weather TTL cache — td-3b2e32 (P1, bug)

**Finds:** `_cache_set` writes athlete-data JSON with default umask; cache dirs
grow unbounded (stale files are only unlinked when the *same* key is
re-requested, but date-parameterized keys roll daily and are never revisited);
`weather.py` hits Open-Meteo on every call with no cache.

**Changes:**
- `plugins/training/_http.py`
  - `_cache_set`: create the file with mode 0o600 from the start —
    `os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)` then write —
    instead of write-then-chmod, so there is no default-umask (0644) exposure
    window between write and chmod.
  - Add module-level `_last_sweep: float = 0.0`. In `_cache_set`, if
    `time.time() - _last_sweep > 3600`: iterate `_cache_dir(discord_id).glob("*.json")`,
    `unlink()` files with `mtime` older than 24 h (best-effort, swallow `OSError`),
    then set `_last_sweep`. The 24 h floor comfortably exceeds the largest TTL (6 h),
    so no live entry can be swept. `# ponytail:` hourly per-user sweep is enough
    at this user count; move to a periodic reaper job if dirs ever exceed thousands
    of files.
- `plugins/training/weather.py`
  - Module-level `_weather_cache: dict[tuple[float, float], tuple[float, dict]]`.
  - Key = `(round(latitude, 2), round(longitude, 2))`; entry valid 600 s;
    if more than 32 entries, clear the dict (crude LRU is not worth it — weather
    queries per session touch a handful of locations).
  - In-memory, not file-based: `get_weather` has no `discord_id`, and reusing the
    per-user file cache would resurrect the shared-dir pattern PR #32 removed.
  - Cache only the fetched Open-Meteo payload, not the response envelope: the
    cache key omits `location_name`, so a hit must not echo the first caller's
    display fields — regenerate the `location`/`latitude`/`longitude` labels
    from the current arguments on every call (a second caller within ~1.1 km
    of the first would otherwise get the wrong location label).

**Tests:** extend `tests/test_intervals_icu.py` (cache class): fresh-file mode is
0600; a file with old mtime (via `os.utime`) is gone after a `_cache_set` that
triggers the sweep (monkeypatch `_http._last_sweep` to force it); fresh files
survive. Extend `tests/test_weather.py`: second call within TTL does not re-fetch
(monkeypatched `urlopen` call count); entry older than TTL re-fetches.

**Risks / side effects:** none behavioral — cache hits/misses unchanged; only
orphaned files and file modes change. Weather cache returns up to 10-min-old
conditions — acceptable for training-window advice; TTL is one constant if the
Lead wants it tighter. The sweep runs only for the requesting user's cache dir
inside `_cache_set` — orphaned files of inactive/departed athletes are never
collected; acceptable at the current user count, revisit a global reaper only
if the user base grows.

**Estimate:** ~35 lines + ~50 test lines.

## 2. Mechanical static guard in `develop_tool` — td-7befd2 (P1, bug)

**Find:** CONTRACT.md bans `os`, `subprocess`, `eval`, `exec` in generated tool
code, but the only enforcement is the LLM's self-assessment. Deployed tools then
run inside the gateway process with read access to every athlete's key file and
`/opt/data/.github_token`.

**Changes:** `plugins/training/sandbox_client.py`
- Module constant `_FORBIDDEN = re.compile(r"(?:^|\W)(?:import\s+os\b|from\s+os\b|import\s+subprocess\b|from\s+subprocess\b|__import__\s*\(|\beval\s*\(|\bexec\s*\()")` (compile once).
- In `develop_tool`, right after the `tool_name` validation: scan `code` (the
  deployed artifact) only — `test_code` runs inside the network-isolated sandbox
  and never reaches the gateway. On match: return `success: false` naming the
  offending fragment and pointing at CONTRACT.md.
- This is a denylist, not a sandbox — it closes the self-certification gap cheaply,
  it is not a substitute for the k8s isolation that already exists. `# ponytail:`
  regex denylist catches the CONTRACT.md classes only; a real capability boundary
  would need a subprocess-per-tool or an import hook — build only if the loop ever
  gains broader write privileges.

**Tests:** `tests/test_sandbox_client.py`: one reject case per pattern class
(`import os`, `from os import path`, `import subprocess`, `__import__("os")`,
`eval(`, `exec(`), one accept case (clean tool), and a case where `test_code`
contains `import os` but is accepted (documenting the intentional asymmetry).

**Risks / side effects:** a generated tool that legitimately needs `os.path`
would be rejected — per CONTRACT.md that is already the rule; the error message
should say what to do instead (pure-Python, no env/file access). No change to
the k8s Job manifest or RBAC.

**Estimate:** ~15 lines + ~35 test lines.

## 3. Manifest hardening — td-37b117 (P1, bug)

**Finds:** the `hermes` container has no `securityContext` at all (the sandbox
Job has the full block — its spec is built in code at
`plugins/training/sandbox_client.py:139–172`, not a YAML manifest under
`apps/hermes-sandbox/`); the egress NetworkPolicy pins the Hetzner node's public
IP, which breaks silently if the node is ever re-IPed.

**Changes:**
- `apps/hermes/deployment.yaml` — add to the `hermes` container:
  ```yaml
  securityContext:
    runAsNonRoot: true
    runAsUser: 10000
    runAsGroup: 10000
    allowPrivilegeEscalation: false
    capabilities: { drop: ["ALL"] }
    seccompProfile: { type: RuntimeDefault }
  ```
  (Live gate passed 2026-09-14: `id -u` in the running container = 10000.)
  InitContainers stay as-is: `fix-data-permissions` (busybox) is the one that
  needs root for `chown`; `configure-hermes` has no securityContext and runs as
  the image user (10000) — its `chown -R 10000:10000` succeeds without root
  (chown-to-self).
  Deliberately **not** setting `readOnlyRootFilesystem`: the runtime writes
  `__pycache__` under `/opt/hermes/plugins/` and possibly venv state; enabling it
  needs a `emptyDir` + `PYTHONDONTWRITEBYTECODE` audit first — separate follow-up
  if wanted.
- `apps/hermes/networkpolicy.yaml` — **live-verified outcome (2026-09-14,
  all gates run against the production node via SSH): keep the ipBlock pin
  permanently; ship no selector rule.** Single change: extend the
  `10.43.0.1/32` ClusterIP rule to TCP 443 as well as 6443 (clients dial the
  Service on 443; hygiene in case enforcement ever matches pre-DNAT), and add
  a YAML comment on the `167.233.152.107/32` rule documenting the node-IP pin
  as an accepted ops constraint.
  Evidence from the live cluster (k3s v1.36.2, single node `ubuntu-4gb-nbg1-1`,
  no `--disable-network-policy` flag ⇒ embedded kube-router NP enforcement ON):
  - `kubectl get pods -n kube-system -l component=kube-apiserver` → **No
    resources found** — the control plane runs in-process; a
    namespaceSelector+podSelector rule would match nothing. The selector
    migration is dead; the fallback branch (keep the pin) is the design.
  - The node has no private IP (`INTERNAL-IP` = `167.233.152.107`), so the pin
    is simply “this node” — it breaks only if Hetzner re-IPs the server, which
    is the documented constraint.
  - In-pod: `KUBERNETES_SERVICE_HOST=10.43.0.1`, `PORT=443`; Service
    `kubernetes` maps 443→6443. Empirically the pod reaches
    `https://10.43.0.1:443/healthz` (apiserver answers 401 to anonymous)
    **despite no 443 rule on that CIDR** — enforcement matches post-DNAT at
    node `167.233.152.107:6443`, which the ipBlock rule allows. The pin is the
    operative rule; deleting it would break in-cluster API access.
  - Server-side dry-run of both final manifests (securityContext + 443
    extension): **pass**.

**Remaining checkpoints:** none pre-merge — all gates were run 2026-09-14
against the live cluster (evidence above). Post-merge only: confirm the pod
becomes Ready after the Flux-synced restart. Note: `develop_tool`'s Job
submission has **never been exercised in production** (zero Jobs ever created
in `hermes-sandbox`); API-server reachability from the pod is proven, but the
first real `develop_tool` run is still untested end-to-end — watch it when it
happens.

**Risks / side effects:** any manifest merge triggers Flux sync; deployment.yaml
change = pod restart, and strategy is `Recreate` (single replica) → a short
outage window — merge when no athlete session is active. The NetworkPolicy
change is now additive-only (one extra port on an existing rule + a comment);
the previously feared “wrong selector silently blocks API-server egress”
failure mode is eliminated because no selector rule ships at all.

**Estimate:** ~14 YAML lines, one PR, zero code.

## 4. Fitness-chart downsample + docstring truth + description trim — td-923922 (P2, feature)

**Finds:** `intervals_icu.py` header claims keys are stored "(age-encrypted)"
(they are plaintext chmod-600 — false assurance); `get_fitness_chart(days=365)`
returns ~365 daily records (~70 KB JSON) into model context; tool descriptions
enumerate every response field (~600–800 always-on words across the toolset).

**Changes:**
- Fix the header docstring: `intervals_key   (plaintext, chmod 0600, PVC-local)`.
  Do **not** add encryption in this PR: keys arrive via DM conversation anyway
  (see item 7), the PVC is single-tenant, and age would add a key-management
  dependency for no boundary it actually moves. Revisit only if the threat model
  changes.
- `get_fitness_chart`: when `days > 60`, keep one record per ISO week (the last
  daily record of each week — CTL/ATL/TSB are level metrics, so the weekly close
  is representative; no averaging that would smear ramps), add
  `"resolution": "weekly"` to the response; `days <= 60` stays daily with
  `"resolution": "daily"`. Update the tool description and the SKILL.md
  quick-reference row.
- Trim descriptions of `get_activity_detail`, `get_activity_streams`,
  `get_wellness`, `get_recent_activities`, `get_planned_events` (and
  `create_planned_event`'s schema text): keep purpose + "use when" + the
  `activity_id` provenance note; drop field enumerations (responses are
  self-describing JSON). Verified no test asserts description text.

**⚠ Response-shape change — needs explicit Lead sign-off:** consumers of
`get_fitness_chart` are (a) the model (reads `resolution` fine), and (b) the
embedded recipes in `skills/coaching/references/` — the real consumers,
located by review: `cron-coaching.md:68` (runtime recipe
`show('FITNESS', intervals_icu.get_fitness_chart, 365)`) and `:82`
(output-format table), `training-summary-workflow.md:20`,
`training-plan-creation.md:12`, and `hr-pace-drift-analysis.md:57`.
(`cron-prompt-templates.md` contains **zero** `get_fitness_chart` references.)
Grep the references tree for `get_fitness_chart` before merge and update every
embedded example or recipe. **Behavior change to disclose:**
`hr-pace-drift-analysis.md` uses `days=90`, which crosses the `> 60` weekly
threshold — that documented workflow's CTL ramp-rate guidance must be reviewed
under weekly resolution, or the workflow updated to request daily data within
a ≤ 60-day window. `training-summary-workflow.md:20` also uses `days=90`; its
daily-cadence needs are served by `get_wellness(days=42)` (stays daily) and its
fitness-chart call targets long-range trends, which weekly resolution still
serves — confirm that reading during sign-off rather than assuming breakage.

**Tests:** downsample unit test (mocked 365-record response → 52 weekly records,
resolution=weekly; 30-day response → 30 records, resolution=daily). Update
`tests/test_streams_and_fitness.py::test_fitness_chart_returns_long_range_data`:
it feeds 3 same-ISO-week records at `days=365` and asserts `record_count == 3` —
under weekly downsample this collapses to 1 record (assertion failure +
IndexError). Spread the mock dates across ISO weeks, or switch the test to
`days=30`.

**Estimate:** ~60 lines + ~40 test lines.

## 5. SKILL.md de-weaponize + restructure — td-7bc7c5 (P1, task, largest item)

**Finds:** `skills/coaching/SKILL.md` is 98 KB (~24 K tokens) loaded into every
coaching session; it carries (a) a **live-pod mutation recipe** and a
**raw-API-key echo recipe** that contradict AGENTS.md ("Never mutate live pod
plugins directly"), (b) inline essays duplicating `references/` (46 files,
190 KB) and `coach-brain/` YAML, (c) per-athlete incident logs with names/dates,
(d) mechanical defects: 4 literal `\n` artifacts (lines 399, 423–424, 434), a
broken `| Zwift…` table row, two half-marathon paragraphs sharing a verbatim
duplicated opening sentence (lines 623/627).

**Changes (one PR, editorial):**
1. Move "Credential recovery (live-pod fix)" and the live-pod `cp`-sync workflow
   out of the athlete-facing skill into a new `docs/OPS-BREAKGLASS.md`.
   `docs/` is **not** copied into the image (Dockerfile copies plugins,
   coach-brain, skills, sandbox, scripts, AGENTS.md, loops only), so athlete
   sessions and the coaching skill never see it; humans and dev sessions still
   can. Keep in SKILL.md the safe guidance: PR workflow via `create-pr.sh`,
   `develop_tool` usage patterns, "never curl for training data".
2. Mechanical fixes: repair the 4 `\n` artifacts and the table row. For the
   half-marathon duplication, **merge the two paragraphs** — only their opening
   sentence is duplicated verbatim (lines 623/627 diverge after it; the second
   paragraph carries unique guidance: phase model, 3-runs template, deload
   cadence). Deleting the paragraph would lose live guidance.
3. Deduplicate against existing sources — keep a 2–5 line summary + link:
   Norwegian Singles → **move the section into a reference file** (only the
   core principles overlap `coach-brain/training-philosophies.yaml`; the
   threshold format library and progression warnings at SKILL.md:171–188 have
   no counterpart in `training-philosophies.yaml` or
   `references/norwegian-singles-paces.md` — moving, not deleting, preserves
   them); HR zone table → `references/hr-based-training.md` (full duplicate);
   post-ride quality spec → `references/post-ride-review-quality.md`; HR-lag /
   Z2-conversational-test paragraphs likewise.
4. Pitfalls section: convert each multi-paragraph pitfall to a bolded 1–2 line
   rule + `See references/…` link; move the full text into
   `references/pitfalls-<topic>.md` (or the existing reference file when one
   covers it — 46 already exist, prefer folding over new files). Move incident
   specifics (dates, "Found 2026-09-06…", athlete names) into the reference
   files.
5. Add `tests/test_skill_links.py` (stdlib `re`): every `references/<file>.md`
   mentioned in `SKILL.md` resolves to an existing file — prevents link rot as
   content keeps moving. One test, no framework beyond pytest.

**Acceptance:** `wc -c skills/coaching/SKILL.md` ≤ 40 000; link test green; full
suite green; spot-check that no guidance is *lost* (only moved) — diff review by
Lead on the moved sections.

**Risks / side effects:** the coaching model will need one extra `skill_view`
 hop for deep pitfall text — that is the intended trade (load 24 K tokens always
vs. ~10 K + on-demand reads). Transient risk of a broken reference during the
move — mitigated by the link test. Do item 4 before this PR or accept a small
quick-reference conflict (both touch SKILL.md lines).

**Estimate:** large editorial diff (mostly moves, little new prose) + ~25-line
test. Suggest a fresh focused session; optionally delegate the
essay→reference extraction to a subagent with a strict move-don't-rewrite brief.

## 6. Ship only bot-facing skills — td-b9533b (P2, chore)

**Find:** Dockerfile copies `skills/` wholesale → all 22 skills (19 of them dev
workflow skills from `mattpocock/skills`) are synced to the pod and indexed in
every athlete session's `<available_skills>` (~1–2 K tokens/session of pure
noise + prompt surface). **Live check (2026-09-14):** `/opt/data/skills/` on
the PVC holds **38** dirs — the image-shipped set plus **~16 runtime-installed
skills** (via the skills hub: apple, autonomous-ai-agents, creative,
data-science, devops, email, github, media, mlops, note-taking, productivity,
smart-home, social-media, software-development, web, yuanbao). The per-session
index cost is correspondingly larger than estimated.

**Change:** `Dockerfile` — replace
`COPY --chown=hermes:hermes skills/ /opt/hermes/coach-skills/` with explicit
copies of `skills/coaching`, `skills/strength-coaching`,
`skills/self-improvement`. **The Dockerfile change alone does not achieve the
goal:** the sync script installs each skill only if absent
(`sync-coach-assets.sh:33–41`, guard at line 38) and never deletes — all 22 skills are already
on the PVC from prior rollouts, so the 19 dev skills would remain installed and
indexed. Therefore also extend `docker/sync-coach-assets.sh` to prune skill
dirs under `${HERMES_HOME}/skills/` that the image no longer ships (compare
against `/opt/hermes/coach-skills/` contents, remove the extras) — or, if the
Lead prefers no deletion logic in the sync script, perform a documented
one-time PVC cleanup after rollout. Dev skills remain in the repo for local
dev use — just not on the pod.

**⚠ Note for the Lead:** the prune adds deletion logic to a runtime script
that mutates the PVC (removes previously-installed dev-skill dirs). No athlete
data is touched; the removed dirs are exactly the dev-workflow skills the
image stops shipping. **Decision needed (live finding):** the prune policy is
either (a) prune to exactly the shipped allowlist — this also deletes the
~16 runtime-installed skills (re-installable via the skills hub if an athlete
session wants them; the “exactly three skills” verification holds) — or
(b) prune only the 19 repo-shipped dev skills and leave runtime installs
alone (smaller context win; verification becomes “no repo dev skills
remain”).

**Accepted limitation:** the self-improve cron loop cannot load dev skills
on-pod. Per CONTRACT.md it only edits `coach-brain/` and uses `develop_tool` —
it never loads them today. If that ever changes, extend the allowlist then.

**Sequencing:** independent of items 4 and 5 — this item touches only the
Dockerfile and the sync script; item 5 touches only `skills/coaching/`. Do it
anytime.

**Verification:** image builds in CI; after rollout `ls /opt/data/skills/` on the
pod shows exactly three skills.

**Estimate:** ~10 lines (Dockerfile + sync-script prune).

## 7. ADR — API keys transit model context — td-1b4091 (P3, decision)

**Find:** `coach_onboard` receives `api_key` as a model-supplied tool argument:
the key is in the prompt to the model provider (opencode.ai) and is persisted
in the transcript (`state.db`) as part of the tool-call arguments. The tool's
*response* never echoes the key (`onboarding.py:86–101`), and the exact
storage format of tool-call args is gateway-owned and unverifiable from this
repo — `scan-signals.sh` reads tool rows from that same DB, so any key-bearing
argument storage is within its reach, but no specific query here is claimed
to surface the key.

**Why this is a decision, not a diff:** redaction-at-persistence belongs to the
hermes-agent gateway (base image, not this repo). Within this repo the only
"fix" is moving key collection out of model-visible args (e.g. a DM attachment
or slash-command flow), which changes the onboarding UX.

**Proposed ADR content (docs/adr/0002):** data-flow diagram (athlete DM →
model → tool arg → file), threat statement, the two options with trade-offs,
and the Lead's ruling. Optionally file an upstream request for tool-arg
redaction in hermes-agent.

**Estimate:** ADR writing only, once the Lead rules.

---

## Explicitly not in scope

- Secret rotation — excluded by Lead instruction.
- Implementing age encryption for key files — docstring fix only (item 4);
  adds a dependency and key-management surface without moving a boundary.
- `readOnlyRootFilesystem` on the main container — needs a writable-path audit;
  follow-up if wanted after item 3.
- Any change to the hermes-agent gateway itself (base image).
