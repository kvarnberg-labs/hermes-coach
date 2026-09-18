#!/usr/bin/env python3
"""Regenerate tests/data/intervals_model_fields.json.

The snapshot is the field-name source of truth for
tests/test_intervals_field_contract.py. It is generated from the official
published data model:

    https://registry.npmjs.org/@intervals-icu/js-data-model
    dist/index.d.ts — "Generated from Intervals.icu source, (c) 2025
    Intervals.icu Ltd"

Run this by hand when the snapshot drifts (the contract test fails on a field
that exists upstream), then commit the regenerated JSON with this script's output
in the PR body.

    python3 scripts/gen-intervals-field-snapshot.py

Deliberately does not use npm: it fetches the registry metadata and the tarball
with urllib, so the repo needs no Node toolchain.
"""

from __future__ import annotations

import io
import json
import re
import tarfile
import urllib.request
from pathlib import Path

PACKAGE = "@intervals-icu/js-data-model"
REGISTRY = f"https://registry.npmjs.org/{PACKAGE}"
OUT = Path(__file__).resolve().parent.parent / "tests" / "data" / "intervals_model_fields.json"
INTERFACES = ("Activity", "Wellness", "SportSettings", "Athlete", "Interval")


def _fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "hermes-coach/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def main() -> None:
    meta = json.loads(_fetch(REGISTRY))
    version = meta["dist-tags"]["latest"]
    tarball = meta["versions"][version]["dist"]["tarball"]

    with tarfile.open(fileobj=io.BytesIO(_fetch(tarball)), mode="r:gz") as tar:
        dts = tar.extractfile("package/dist/index.d.ts").read().decode()

    fields = {}
    for name in INTERFACES:
        match = re.search(r"export interface " + name + r" \{(.*?)\n\}", dts, re.S)
        if match is None:
            raise SystemExit(f"interface {name} not found in the published model")
        fields[name] = sorted(set(
            re.findall(r"^\s{4}([A-Za-z_][A-Za-z0-9_]*)\??:", match.group(1), re.M
        )))

    snapshot = {
        "_source": PACKAGE,
        "_version": version,
        "_generated_from": "dist/index.d.ts (generated from the Intervals.icu source)",
        "_note": (
            "Property names per interface. Field-name contract source for "
            "tests/test_intervals_field_contract.py. The OpenAPI spec at "
            "https://intervals.icu/api/v1/docs is INCOMPLETE relative to this "
            "model: icu_intervals, icu_groups and laps appear here but not "
            "there, and they are JS-script-only (not returned by the REST "
            "activity detail endpoint)."
        ),
        "fields": fields,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n")
    print(f"wrote {OUT} ({version})")
    for name, props in fields.items():
        print(f"  {name}: {len(props)} fields")


if __name__ == "__main__":
    main()
