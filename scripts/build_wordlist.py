#!/usr/bin/env python3
"""build_wordlist.py — one-time generator for scripts/brief_lint_words.txt.gz.

Sources:
  * Swedish aspell dictionary (titoBouzout/Dictionaries Swedish.dic + Swedish.aff,
    fetched from GitHub) expanded with its PFX/SFX affix rules so inflected forms
    (ordentligt, återhämtningen, fredagens …) resolve.
  * pyspellchecker's bundled English dictionary (en.json.gz) for English terms.

Run from the repo root when the wordlist needs regeneration:
  uv pip install --python /opt/data/.test-venv/bin/python pyspellchecker
  curl -sL -o /tmp/sv_raw.dic  https://raw.githubusercontent.com/titoBouzout/Dictionaries/master/Swedish.dic
  curl -sL -o /tmp/sv_raw.aff  https://raw.githubusercontent.com/titoBouzout/Dictionaries/master/Swedish.aff
  python3 scripts/build_wordlist.py
"""
import gzip
import json
import os
import re
import sys

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "brief_lint_words.txt.gz")
SV_DIC = "/tmp/sv_raw.dic"
SV_AFF = "/tmp/sv_raw.aff"


def parse_aff(path):
    rules = {}
    cur = None
    with open(path, encoding="utf-8") as f:
        for line in f:
            m = re.match(r"^(PFX|SFX)\s+(\S)\s+(Y|N)\s*\d*\s*$", line)
            if m:
                cur = (m.group(1), m.group(2))
                rules[cur] = []
                continue
            m = re.match(r"^(PFX|SFX)\s+(\S)\s+(\S+)\s+(\S+)\s+(\S+)\s*$", line)
            if m and cur == (m.group(1), m.group(2)):
                rules[cur].append((m.group(3), m.group(4), m.group(5)))
    return rules


def applies(cond, word):
    if cond == ".":
        return True
    neg = cond.startswith("!")
    c = cond[1:] if neg else cond
    try:
        hit = bool(re.search(c + "$", word))
    except re.error:
        return False
    return (not hit) if neg else hit


def main():
    rules = parse_aff(SV_AFF)
    expanded = set()
    with open(SV_DIC, encoding="utf-8") as f:
        f.readline()  # entry count line
        for line in f:
            parts = line.strip().split("/")
            w = parts[0].lower()
            if not w:
                continue
            expanded.add(w)
            flags = parts[1] if len(parts) > 1 else ""
            if not flags or "!" in flags:
                continue
            for flag in flags:
                for typ in ("PFX", "SFX"):
                    for (s_, a_, c_) in rules.get((typ, flag), []):
                        if not applies(c_, w):
                            continue
                        if s_ != "0":
                            if not w.endswith(s_):
                                continue
                            stem = w[: -len(s_)]
                        else:
                            stem = w
                        if a_ == "0":
                            expanded.add(stem)
                        elif typ == "SFX":
                            expanded.add(stem + a_)
                        else:
                            expanded.add(a_ + stem)

    # English from pyspellchecker's bundled dict
    sys.path.insert(0, "/opt/data/.test-venv/lib/python3.13/site-packages")
    from spellchecker import SpellChecker  # noqa: E402
    en = SpellChecker(language="en")
    expanded |= set(en.word_frequency.dictionary.keys())

    # Curated supplement (irregular verb forms etc.)
    extra = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "brief_lint_extra_words.txt")
    if os.path.exists(extra):
        with open(extra, encoding="utf-8") as f:
            expanded |= {ln.strip().lower() for ln in f
                         if ln.strip() and not ln.startswith("#")}

    with gzip.open(OUT, "wt", encoding="utf-8") as f:
        for w in sorted(expanded):
            f.write(w + "\n")
    print(f"wrote {OUT}: {len(expanded)} words")


if __name__ == "__main__":
    main()
