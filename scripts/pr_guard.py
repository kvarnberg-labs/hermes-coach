#!/usr/bin/env python3
"""pr_guard.py — enforce loops/self-improve/CONTRACT.md inside create-pr.sh.

The contract was prose the loop could ignore; these checks make the
self-improvement loop's PR path refuse what the contract forbids
(research P1 / loop review R2, R3, R7).

Subcommands (exit 0 = allowed, 1 = refused with a reason on stderr):
  check <file-path> <title> <body>     path allowlist, title prefix, body fields
  existing-file <file-path> <sha>      plugin files may only be NEW (Path B)
  added-lines <local-file> <base-file> fewer than MAX_ADDED_LINES added
  open-today                           JSON list of open PRs on stdin; refuse if
                                       an improve/* PR was already opened today
  base-file <out-path>                 GitHub contents-API JSON on stdin (empty =
                                       new file); writes decoded content, prints sha
"""

from __future__ import annotations

import base64
import datetime as dt
import difflib
import json
import re
import sys

MAX_ADDED_LINES = 50
BODY_FIELDS = ("Failure class:", "Anchor:", "Golden check:", "Evidence:")
KNOWLEDGE = re.compile(r"^coach-brain/[a-z0-9][a-z0-9_-]*\.ya?ml$")
NEW_TOOL = re.compile(r"^plugins/training/[a-z][a-z0-9_]*\.py$")


def check(path: str, title: str, body: str) -> list[str]:
    errors = []
    if not (KNOWLEDGE.match(path) or NEW_TOOL.match(path)):
        errors.append(f"{path}: the loop may only change coach-brain/*.yaml or add a "
                      "new plugins/training/<tool>.py — file an operator signal instead")
    if not title.startswith("improve: "):
        errors.append("title must start with 'improve: '")
    missing = [f for f in BODY_FIELDS if f not in body]
    if missing:
        errors.append(f"body is missing {', '.join(missing)} (CONTRACT.md → PR body)")
    return errors


def existing_file(path: str, sha: str) -> list[str]:
    if NEW_TOOL.match(path) and sha:
        return [f"{path} already exists on main; editing plugins is an operator signal (Path S)"]
    return []


def added_lines(local: str, base: str) -> list[str]:
    diff = difflib.unified_diff(base.splitlines(), local.splitlines(), lineterm="", n=0)
    added = sum(1 for line in diff if line.startswith("+") and not line.startswith("+++"))
    if added >= MAX_ADDED_LINES:
        return [f"{added} lines added; CONTRACT.md allows fewer than {MAX_ADDED_LINES} per PR"]
    return []


def open_today(prs: list[dict], today: dt.date) -> list[str]:
    todays = [p["html_url"] for p in prs
              if p.get("head", {}).get("ref", "").startswith("improve/")
              and p.get("created_at", "")[:10] == today.isoformat()]
    return [f"already opened an improve/ PR today: {todays[0]} (one PR per run/day)"] if todays else []


def base_file(raw: str, out_path: str) -> str:
    """Write the main-branch content of a file (empty if new); return its sha."""
    data = json.loads(raw) if raw.strip() else {}
    content = base64.b64decode(data.get("content", "")).decode("utf-8")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(content)
    return data.get("sha", "")


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


def main(argv: list[str]) -> int:
    cmd, args = (argv[0], argv[1:]) if argv else ("", [])
    if cmd == "check" and len(args) == 3:
        errors = check(*args)
    elif cmd == "existing-file" and len(args) == 2:
        errors = existing_file(*args)
    elif cmd == "added-lines" and len(args) == 2:
        errors = added_lines(_read(args[0]), _read(args[1]))
    elif cmd == "open-today" and not args:
        try:
            prs = json.loads(sys.stdin.read())
        except ValueError:
            prs = None
        errors = (open_today(prs, dt.datetime.now(dt.timezone.utc).date()) if isinstance(prs, list)
                  else ["could not list open PRs from GitHub"])
    elif cmd == "base-file" and len(args) == 1:
        print(base_file(sys.stdin.read(), args[0]))
        return 0
    else:
        print(__doc__, file=sys.stderr)
        return 2
    for e in errors:
        print(f"REFUSED: {e}", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
