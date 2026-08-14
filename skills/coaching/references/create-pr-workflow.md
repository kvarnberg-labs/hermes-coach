# create-pr.sh Multi-File PR Workflow

The `create-pr.sh` script in the hermes-coach repo uploads **one file per call**
to a GitHub branch and opens a PR. To push multiple files to the same PR, use
the **same branch-slug** on subsequent calls:

```bash
# First file (plugin source) — creates branch + PR
/opt/data/scripts/create-pr.sh \
  plugins/training/intervals_icu.py \
  add-streams-and-fitness-tools \
  "improve: add get_activity_streams and get_fitness_chart tools"

# Second file (tests) — same branch-slug, adds to existing PR
/opt/data/scripts/create-pr.sh \
  tests/test_streams_and_fitness.py \
  add-streams-and-fitness-tools \
  "improve: add get_activity_streams and get_fitness_chart tools"
```

The script handles branch-already-exists (422 → falls through to existing PR),
new-file (no SHA) vs update (needs SHA), and PR-already-exists (finds existing
PR URL). Do not change the branch-slug between calls.

## Full workflow

1. **Copy plugin to sandbox**: `cp /opt/hermes/plugins/training/<file>.py /opt/data/plugins/training/<file>.py`
2. **Edit with `patch`**: use `patch(mode='replace', path='/opt/data/plugins/training/<file>.py', ...)`
3. **Test end-to-end on real data** from the sandbox path (has credential access)
4. **Write tests** directly to `/opt/data/tests/`
5. **Run full suite**: `PYTHONPATH=plugins /opt/data/.test-venv/bin/python -m pytest tests/ -v --import-mode=importlib`
6. **Push plugin + tests** via `create-pr.sh` with shared branch-slug
7. **Verify from fresh clone**:
   ```bash
   cd /tmp && git clone -b improve/<slug> https://github.com/kvarnberg-labs/hermes-coach.git
   cd hermes-coach && PYTHONPATH=plugins /opt/data/.test-venv/bin/python -m pytest tests/ -v --import-mode=importlib
   ```

## Pitfalls

- **Multiline PR bodies break the JSON parser in create-pr.sh.** The script passes
  `pr-body` as an argument that gets embedded in a curl JSON body. Control characters
  (newlines, quotes) in the body break JSON parsing. **Always use a short, single-line
  description as the PR body.** If you need a detailed description, push with a
  one-liner first, then update via `curl PATCH`:

  ```bash
  # Push file with short body
  /opt/data/scripts/create-pr.sh plugins/training/intervals_icu.py \
    my-branch-slug "improve: short title" "One line summary only."

  # Then update PR description with full details
  curl -s -X PATCH \
    -H "Authorization: Bearer $GITHUB_TOKEN" \
    -H "Accept: application/vnd.github+json" \
    https://api.github.com/repos/kvarnberg-labs/hermes-coach/pulls/<PR_NUMBER> \
    -d "{\"body\": $(python3 -c "import sys,json; print(json.dumps(sys.stdin.read()))" <<'EOF'
  Full multi-line PR body here.
  With all the detail you want.
  EOF
  )}"
  ```

- **Pre-existing repo tests you don't have locally.** The local `/opt/data/tests/`
  directory may be a subset of the full repo test suite. When changing shared
  library behavior (e.g. modifying `_require_user_id`, adding/removing constants,
  changing function signatures), the repo's `tests/test_intervals_icu.py` may have
  tests that reference the old behavior and aren't in your local directory.
  **Before pushing, pull the full test file from the branch and grep for the
  function/constant you're changing:**

  ```bash
  curl -s "https://raw.githubusercontent.com/kvarnberg-labs/hermes-coach/main/tests/test_intervals_icu.py" \
    | grep -n "function_name\|CONSTANT_NAME"
  ```

  If matches exist, download the file, update those tests, and push it along
  with your other changes.

- **Stale test files on the branch**: the first `create-pr.sh` call uploads the plugin file.
  If you edit tests locally but forget to push them, the PR branch's tests reference
  old response formats and fail. Always push ALL changed files.

- **conftest.py for cache isolation**: when adding module-level caches to plugins,
  add a `conftest.py` fixture that clears them between tests so stale cache state
  doesn't poison subsequent tests in the same run.

- **Missing test dependencies**: CI installs `pyyaml` from the workflow file, but
  local test venvs may not have it. Install with `uv pip install pyyaml --python
  /opt/data/.test-venv/bin/python` if coaching tests fail with "pyyaml not installed."
