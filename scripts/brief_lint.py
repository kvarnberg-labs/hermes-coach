#!/usr/bin/env python3
"""brief_lint.py — mechanical output-corruption lint for headless coaching briefs.

Why: GLM-5.3-flash-class models have a documented intermittent token-corruption
mode (vLLM #54150, opencode #16903). Two delivered morning briefs (2026-09-12 and
2026-09-13, Millberg) contained garbled tokens ("(133}.sget48-185 W", "RegnarPlan B",
"vid Livri TSB +11 bilh", "bakom pentalk på lax") even though the model was instructed
to self-review. Model self-review (SLUTKONTROLL) demonstrably does not catch its own
corruption — the check must be EXTERNAL and MECHANICAL, run in the terminal.

Checks — [HARD] = structural corruption, always regenerate:
  1. U+FFFD replacement characters
  2. Close-bracket directly followed by a letter ("}s", "]g")
  3. Mismatched bracket pairs within a 40-char span ("( ... }")
  4. Digit directly followed by } or | then a letter ("133}.s")
  5. CamelCase fused words ("RegnarPlan") minus allowlist
Check — [SOFT] = unknown token, REVIEW and justify or regenerate:
  6. Tokens >= 4 letters not in the bundled Swedish+English wordlist
     (scripts/brief_lint_words.txt.gz), not decomposable into known Swedish
     compounds with clitic suffixes, and not in the allowlist. Dictionary checks
     can never be exact — a flagged token is cleared only when the agent can
     justify it in context (e.g. "sömmtimmar" = sömn + timmar); glitched tokens
     like "livri" or "bilh" cannot be justified and force regeneration.

Usage:
  python3 brief_lint.py <brief-file>
  cat draft.md | python3 brief_lint.py        # stdin mode — use in cron SLUTKONTROLL

Exit codes: 0 = clean, 1 = findings (fix/regenerate before delivery), 2 = usage/IO error.
"""
import gzip
import os
import re
import sys

WORDLIST = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "brief_lint_words.txt.gz")

# Tokens that are legitimately not in a Swedish/English dictionary.
ALLOWLIST = {
    # brands / platforms / equipment
    "zwift", "echelon", "garmin", "zoezi", "wahoo", "healthfit", "intervals",
    "icu", "zwo", "erg", "erghrs", "di2", "etube", "bmc", "lesmills", "trainerroad",
    # acronyms / metrics / abbreviations used in briefs
    "tsb", "ctl", "atl", "ftp", "eftp", "np", "if", "hrv", "sdnn", "lthr", "rpe",
    "vo2max", "vo2", "hr", "bpm", "kj", "kcal", "tss", "fit", "gpx", "uppv",
    # zone / training shorthand
    "z1", "z2", "z3", "z4", "z5", "styrka", "vilodag",
    # athlete-local place & route names
    "ljungskile", "stenungsund", "uddevalla", "bohuslän", "bohusbanan", "ekerö",
    "grevgatan", "bokenäset", "kustvägen", "mellerud", "klarälvsloppet",
    # misc recurring terms
    "morgonbrief", "veckoplan", "hemkomstbacke", "öppningar", "lax",
}

# Legit mixed-case tokens the CamelCase check must not flag.
CAMELCASE_ALLOW = {"vo2max", "di2", "s2", "etube"}

# Swedish clitic/inflectional suffixes allowed when stripping before re-splitting.
CLITICS = ("s", "ts", "en", "et", "na", "rna", "arn", "arnas", "ns", "ens", "ets")


def load_words():
    words = set()
    with gzip.open(WORDLIST, "rt", encoding="utf-8") as f:
        for line in f:
            w = line.strip().lower()
            if w:
                words.add(w)
    return words


def known(part, words):
    return part in ALLOWLIST or part in words


def split_ok(token, words, depth=0):
    """True if token is known or decomposes into known parts (Swedish compounds
    freely concatenate words: vilopuls, återhämtningsveckan). Recursive split plus
    clitic-suffix stripping; bounded depth keeps it fast."""
    if known(token, words):
        return True
    if depth > 4 or len(token) < 4:
        return False
    for suf in CLITICS:
        if token.endswith(suf) and len(token) - len(suf) >= 4 \
                and split_ok(token[:-len(suf)], words, depth + 1):
            return True
    for i in range(3, len(token) - 2):
        if known(token[:i], words) and split_ok(token[i:], words, depth + 1):
            return True
    return False


def lint(text, words):
    findings = []  # (severity, message)

    def hard(msg):
        findings.append(("HARD", msg))

    def soft(msg):
        findings.append(("SOFT", msg))

    if "\ufffd" in text:
        hard("U+FFFD replacement character present")

    for m in re.finditer(r"[}\]][A-Za-zÅÄÖåäö]", text):
        s = max(0, m.start() - 15)
        hard(f"close-bracket+letter: ...{text[s:m.end() + 15]}...")

    for m in re.finditer(r"\([^()\n]{0,40}[}\]]|\[[^\[\]\n]{0,40}[})]", text):
        s = max(0, m.start() - 15)
        hard(f"mismatched brackets: ...{text[s:m.end() + 15]}...")

    for m in re.finditer(r"\d[}\|][A-Za-zÅÄÖåäö]", text):
        s = max(0, m.start() - 15)
        hard(f"digit+glitch-punct+letter: ...{text[s:m.end() + 15]}...")

    for m in re.finditer(r"[a-zåäö]{3,}[A-ZÄÖÅ][a-zåäö]{2,}", text):
        tok = m.group(0)
        if tok.lower() not in CAMELCASE_ALLOW:
            hard(f"CamelCase fused word: {tok}")

    word_re = re.compile(r"[A-Za-zÅÄÖåäöÉÈéèÜü][A-Za-zÅÄÖåäöéèüÉÈéèÜü\-']+")
    unknown = []
    seen = set()
    for raw in word_re.findall(text):
        for part in raw.lower().split("-"):
            part = part.strip("'")
            if len(part) < 4 or part in seen:
                continue
            seen.add(part)
            if split_ok(part, words):
                continue
            unknown.append(part)
    if unknown:
        soft("unknown words (justify each in context, else regenerate): "
             + ", ".join(unknown[:25]))

    return findings


def main():
    if len(sys.argv) > 2:
        print("usage: brief_lint.py [<file>]  (or pipe text on stdin)", file=sys.stderr)
        return 2
    if len(sys.argv) == 2:
        try:
            with open(sys.argv[1], encoding="utf-8") as f:
                text = f.read()
        except OSError as e:
            print(f"brief_lint: cannot read {sys.argv[1]}: {e}", file=sys.stderr)
            return 2
    else:
        text = sys.stdin.read()

    if not text.strip():
        print("brief_lint: empty input — treat as failure", file=sys.stderr)
        return 1

    findings = lint(text, load_words())
    if findings:
        n_hard = sum(1 for sev, _ in findings if sev == "HARD")
        print(f"CORRUPTION-LINT: {len(findings)} finding(s) "
              f"({n_hard} HARD) — fix/regenerate before delivery:")
        for sev, msg in findings:
            print(f"  [{sev}] {msg}")
        return 1
    print("CORRUPTION-LINT: clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
