"""Score coaching-decision cases with scripts/decision_predicates.py.

Phase 1 of docs/plans/2026-11-implementation-plan.md. NEVER in CI: a live run
costs one model call per case, twice that with `--twice`.

Two modes:
  default   re-score saved transcripts (`--transcripts DIR`, one
            <case_id>.json or <case_id>.correct.json per case; defaults to
            tests/golden/decisions/transcripts). Free, deterministic, offline.
  --live    drive a model through the driver command in $HERMES_EVAL_DRIVER
            (or --driver): it reads one case JSON on stdin and must print a
            transcript JSON (see decision_predicates for the shape). This
            runner never imports hermes and never holds an API key — the
            driver owns the model call. The driver is spawned with
            shell=True and inherits this process's environment, so anything
            exported here (API keys included) reaches the driver: never run
            --live in CI, and keep secrets out of the calling shell.

Output JSON is the Phase 1 exit gate: pass rate and per-predicate variance.

stdout is a short table; the full report goes to --out.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import decision_predicates as dp  # noqa: E402

import yaml  # noqa: E402

DEFAULT_CASES = Path(__file__).resolve().parent.parent / "tests" / "golden" / "decisions"
# Default transcript dir: one synthetic <case_id>.correct.json per case.
DEFAULT_TRANSCRIPTS = DEFAULT_CASES / "transcripts"


def load_cases(cases_dir: Path) -> list[dict]:
    cases = []
    for path in sorted(cases_dir.glob("*.yaml")):
        with path.open(encoding="utf-8") as handle:
            cases.append(yaml.safe_load(handle))
    return cases


def load_fixtures(case: dict, cases_dir: Path) -> dict[str, dict]:
    """Frozen tool results the driver may replay instead of calling intervals.icu."""
    fixtures = {}
    for name in case.get("fixtures") or []:
        with (cases_dir / "fixtures" / name).open(encoding="utf-8") as handle:
            fixtures[name] = json.load(handle)
    return fixtures


def require_chat_type(case: dict, transcript: dict) -> dict:
    """Score only a transcript that was produced under the case's chat_type.

    no_coding_tools_in_dm disables itself on any other chat_type, so a silent
    mismatch would score the case green for the wrong reason.
    """
    if transcript.get("chat_type") != case.get("chat_type"):
        raise SystemExit(
            f"{case['id']}: transcript chat_type {transcript.get('chat_type')!r} "
            f"!= case chat_type {case.get('chat_type')!r}"
        )
    return transcript


def saved_transcript(case: dict, transcripts_dir: Path | None) -> dict | None:
    """Saved transcript for a case: <id>.json (a live run) first, then the
    committed synthetic <id>.correct.json."""
    if transcripts_dir is None:
        return None
    for name in (f"{case['id']}.json", f"{case['id']}.correct.json"):
        path = transcripts_dir / name
        if path.exists():
            with path.open(encoding="utf-8") as handle:
                return require_chat_type(case, json.load(handle))
    return None


def drive_live(case: dict, cases_dir: Path, driver: str) -> dict:
    """One model run. The driver contract is case JSON in, transcript JSON out."""
    request = json.dumps({**case, "_fixtures": load_fixtures(case, cases_dir)})
    result = subprocess.run(
        driver, shell=True, input=request, capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        raise SystemExit(f"driver failed for {case['id']}: {result.stderr.strip()[:400]}")
    transcript = json.loads(result.stdout)
    transcript.setdefault("case_id", case["id"])
    return require_chat_type(case, transcript)


def score(cases: list[dict], runs: list[dict], out: Path) -> dict:
    """Evaluate one transcript per case, plus predicate flips across repeats."""
    rows, flips = [], {}
    for case, transcript in zip(cases, runs):
        report = dp.evaluate(case, transcript)
        rows.append({"case_id": case["id"], "expect": case["expect"], **report})
        for row in report["results"]:
            flips.setdefault(row["predicate"], set()).add(row["passed"])
    passed = sum(1 for row in rows if row["passed"])
    per_predicate = {
        name: {
            "cases": sum(1 for row in rows for r in row["results"] if r["predicate"] == name),
            "failures": sum(
                1 for row in rows
                for r in row["results"] if r["predicate"] == name and not r["passed"]
            ),
        }
        for name in dp.PREDICATES
    }
    report = {
        "cases": len(rows),
        "passed": passed,
        "pass_rate": round(passed / len(rows), 3) if rows else 0.0,
        "per_predicate": per_predicate,
        "variance": sorted(name for name, seen in flips.items() if len(seen) > 1),
        "results": rows,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--cases", default=str(DEFAULT_CASES), help="case directory")
    parser.add_argument("--transcripts", default=str(DEFAULT_TRANSCRIPTS),
                        help="directory of saved <case_id>.json transcripts")
    parser.add_argument("--out", default="decisions-report.json", help="report path")
    parser.add_argument("--twice", action="store_true", help="run each case twice, report flips")
    parser.add_argument("--live", action="store_true", help="drive a model via the driver command")
    parser.add_argument("--driver", default=os.environ.get("HERMES_EVAL_DRIVER"),
                        help="command: case JSON on stdin, transcript JSON on stdout")
    args = parser.parse_args(argv)

    cases_dir = Path(args.cases)
    cases = load_cases(cases_dir)
    if not cases:
        raise SystemExit(f"no cases in {cases_dir}")
    rounds = 2 if args.twice else 1

    if args.live and os.environ.get("CI"):
        raise SystemExit("--live is a paid model run: never in CI")
    if args.live and not args.driver:
        raise SystemExit("--live needs --driver or $HERMES_EVAL_DRIVER")
    if not args.live and not args.transcripts:
        raise SystemExit("without --live, pass --transcripts DIR (nothing is scored from fixtures alone)")
    if args.twice and not args.live:
        print("note: --twice without --live re-scores the same saved files; flips stay empty",
              file=sys.stderr)

    runs: list[dict] = []
    for _round in range(rounds):  # runs stays round-major: variance slices by round
        for case in cases:
            if args.live:
                runs.append(drive_live(case, cases_dir, args.driver))
                continue
            transcript = saved_transcript(case, Path(args.transcripts))
            if transcript is None:
                raise SystemExit(f"missing transcript for {case['id']} in {args.transcripts}")
            runs.append(transcript)

    if rounds > 1:
        return variance_report(cases, runs, Path(args.out))
    report = score(cases, runs, Path(args.out))
    print(f"{report['passed']}/{report['cases']} cases passed (pass_rate {report['pass_rate']})")
    for row in report["results"]:
        if not row["passed"]:
            for failure in row["failures"]:
                print(f"  FAIL {row['case_id']}: {failure['predicate']} — {failure['reason']}")
    print(f"report: {args.out}")
    return 0 if report["passed"] == report["cases"] else 1


def variance_report(cases: list[dict], runs: list[dict], out: Path) -> int:
    """Score each repeat separately and list the predicates that flip."""
    rounds = len(runs) // len(cases)
    reports = [
        score(cases, runs[i * len(cases):(i + 1) * len(cases)], out.with_suffix(f".run{i + 1}.json"))
        for i in range(rounds)
    ]
    flips = sorted({
        name for a, b in zip(reports, reports[1:])
        for name in a["per_predicate"]
        if (a["per_predicate"][name]["failures"] > 0) != (b["per_predicate"][name]["failures"] > 0)
    })
    merged = {
        "cases": reports[0]["cases"],
        "runs": rounds,
        "pass_rate": [r["pass_rate"] for r in reports],
        "per_predicate": reports[0]["per_predicate"],
        "variance": flips,
    }
    out.write_text(json.dumps(merged, indent=1) + "\n", encoding="utf-8")
    print(f"pass_rate per run: {merged['pass_rate']}")
    print(f"flipping predicates: {flips or 'none'}")
    print(f"report: {out}")
    return 0 if not flips else 1


if __name__ == "__main__":
    sys.exit(main())
