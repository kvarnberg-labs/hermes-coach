#!/bin/bash
# sync-plugin.sh — sync a plugin file between sandbox and runtime.
#
# Usage: sync-plugin.sh <filename.py>
#
# Copies the file from sandbox ($HERMES_HOME/plugins/training/) to
# runtime (/opt/hermes/plugins/training/).  Also clears bytecode so
# the gateway picks up the change on next tool invocation.
#
# The self-improve agent calls this after every plugin edit to
# eliminate the recurring sandbox/runtime drift (Candidate 3 of the
# 2026-08-04 architecture review).

set -euo pipefail

HERMES_HOME="${HERMES_HOME:-/opt/data}"
SANDBOX="${HERMES_HOME}/plugins/training"
RUNTIME="/opt/hermes/plugins/training"

if [ $# -ne 1 ]; then
    echo "Usage: sync-plugin.sh <filename.py>" >&2
    exit 1
fi

FILE="$1"

SRC="${SANDBOX}/${FILE}"
DST="${RUNTIME}/${FILE}"

if [ ! -f "$SRC" ]; then
    echo "ERROR: $SRC does not exist" >&2
    exit 1
fi

cp "$SRC" "$DST"
rm -rf "${SANDBOX}/__pycache__" "${RUNTIME}/__pycache__"
python3 -m py_compile "$DST" && echo "SYNCED: $FILE → runtime" || {
    echo "ERROR: py_compile failed for $DST" >&2
    exit 1
}
