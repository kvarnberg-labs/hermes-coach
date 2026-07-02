#!/bin/sh
# create-pr.sh — open a GitHub PR for one changed file in kvarnberg-labs/hermes-coach.
#
# Usage:
#   create-pr.sh <file-path> <branch-slug> <pr-title> [pr-body]
#
#   file-path   Path relative to repo root, e.g. coach-brain/heat.yaml
#               The file must exist at /opt/data/<file-path>
#   branch-slug Short identifier, e.g. add-heat-knowledge
#   pr-title    Title for the PR, e.g. "improve: heat acclimatization knowledge"
#   pr-body     Optional body text (single line). Defaults to the title.
#
# Exits 0 and prints the PR URL on success.
# Exits 1 and prints a clear error message on failure.
#
# The script reads the token from (in order):
#   1. printenv GITHUB_TOKEN
#   2. /opt/data/.github_token

set -eu

FILE_PATH="${1:-}"
SLUG="${2:-}"
PR_TITLE="${3:-}"
PR_BODY="${4:-$PR_TITLE}"

if [ -z "$FILE_PATH" ] || [ -z "$SLUG" ] || [ -z "$PR_TITLE" ]; then
    echo "Usage: create-pr.sh <file-path> <branch-slug> <pr-title> [pr-body]" >&2
    exit 1
fi

# ---------------------------------------------------------------------------
# Resolve token
# ---------------------------------------------------------------------------
TOKEN="$(printenv GITHUB_TOKEN 2>/dev/null || true)"
[ -n "$TOKEN" ] || TOKEN="$(cat /opt/data/.github_token 2>/dev/null || true)"

if [ -z "$TOKEN" ]; then
    echo "ERROR: no GitHub token found (tried GITHUB_TOKEN env and /opt/data/.github_token)" >&2
    exit 1
fi

REPO="kvarnberg-labs/hermes-coach"
API="https://api.github.com"
HERMES_HOME="${HERMES_HOME:-/opt/data}"
LOCAL_FILE="${HERMES_HOME}/${FILE_PATH}"
BRANCH="improve/${SLUG}"

if [ ! -f "$LOCAL_FILE" ]; then
    echo "ERROR: local file not found: $LOCAL_FILE" >&2
    exit 1
fi

auth() { printf 'Authorization: Bearer %s' "$TOKEN"; }

# ---------------------------------------------------------------------------
# 1. Get main SHA
# ---------------------------------------------------------------------------
MAIN_SHA=$(curl -sf "$API/repos/$REPO/git/ref/heads/main" \
    -H "$(auth)" \
    | python3 -c "import sys,json; print(json.load(sys.stdin)['object']['sha'])")

if [ -z "$MAIN_SHA" ]; then
    echo "ERROR: could not get main branch SHA" >&2
    exit 1
fi
echo "main SHA: $MAIN_SHA"

# ---------------------------------------------------------------------------
# 2. Create branch (ignore 422 = already exists)
# ---------------------------------------------------------------------------
HTTP=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$API/repos/$REPO/git/refs" \
    -H "$(auth)" -H "Content-Type: application/json" \
    -d "{\"ref\":\"refs/heads/${BRANCH}\",\"sha\":\"${MAIN_SHA}\"}")

if [ "$HTTP" != "201" ] && [ "$HTTP" != "422" ]; then
    echo "ERROR: branch creation returned HTTP $HTTP" >&2
    exit 1
fi
echo "branch: $BRANCH ($HTTP)"

# ---------------------------------------------------------------------------
# 3. Get existing file SHA on main (empty string if new file)
# ---------------------------------------------------------------------------
FILE_SHA=$(curl -sf "$API/repos/$REPO/contents/${FILE_PATH}?ref=${BRANCH}" \
    -H "$(auth)" \
    | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('sha',''))" 2>/dev/null || true)

echo "existing file SHA: ${FILE_SHA:-<new file>}"

# ---------------------------------------------------------------------------
# 4. Upload file
# ---------------------------------------------------------------------------
CONTENT_B64=$(python3 -c "
import base64, sys
print(base64.b64encode(open(sys.argv[1], 'rb').read()).decode())
" "$LOCAL_FILE")

PAYLOAD=$(python3 -c "
import json, sys
d = {
    'message': sys.argv[1],
    'content': sys.argv[2],
    'branch':  sys.argv[3],
}
sha = sys.argv[4]
if sha:
    d['sha'] = sha
print(json.dumps(d))
" "$PR_TITLE" "$CONTENT_B64" "$BRANCH" "${FILE_SHA:-}")

HTTP=$(curl -s -o /tmp/upload-resp.json -w "%{http_code}" -X PUT \
    "$API/repos/$REPO/contents/${FILE_PATH}" \
    -H "$(auth)" -H "Content-Type: application/json" \
    -d "$PAYLOAD")

if [ "$HTTP" != "200" ] && [ "$HTTP" != "201" ]; then
    echo "ERROR: file upload returned HTTP $HTTP" >&2
    cat /tmp/upload-resp.json >&2
    exit 1
fi
echo "file uploaded ($HTTP)"

# ---------------------------------------------------------------------------
# 5. Open PR (ignore 422 = already exists)
# ---------------------------------------------------------------------------
PR_PAYLOAD=$(python3 -c "
import json, sys
print(json.dumps({
    'title': sys.argv[1],
    'body':  sys.argv[2],
    'head':  sys.argv[3],
    'base':  'main',
}))
" "$PR_TITLE" "$PR_BODY" "$BRANCH")

PR_RESP=$(curl -s -X POST "$API/repos/$REPO/pulls" \
    -H "$(auth)" -H "Content-Type: application/json" \
    -d "$PR_PAYLOAD")

PR_URL=$(echo "$PR_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('html_url') or d.get('message','unknown error'))")

# A PR for an already-open branch returns the existing PR URL via the errors array
if echo "$PR_URL" | grep -q "https://github.com"; then
    echo "PR: $PR_URL"
else
    # May already exist — try to find it
    EXISTING=$(curl -sf "$API/repos/$REPO/pulls?head=kvarnberg-labs:${BRANCH}&state=open" \
        -H "$(auth)" \
        | python3 -c "import sys,json; prs=json.load(sys.stdin); print(prs[0]['html_url'] if prs else '')" 2>/dev/null || true)
    if [ -n "$EXISTING" ]; then
        echo "PR already exists: $EXISTING"
        PR_URL="$EXISTING"
    else
        echo "ERROR: could not open PR: $PR_URL" >&2
        exit 1
    fi
fi

echo "$PR_URL"
