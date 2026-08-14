# ADR 0001 — Coach-brain corpus conventions

## Context

`coach-brain/*.yaml` is a flat-merged knowledge store (19 files, 27 top-level
keys) loaded by `_brain.py._load_all()` and consumed by two modules:
`coaching.get_coaching_knowledge` (keyword search) and `strength_coach.*`
(direct `brain.get` lookups). The self-improvement loop edits these YAML files
daily via PRs but, per `loops/self-improve/CONTRACT.md`, cannot edit plugin
source or tests. An architecture review surfaced several conventions that were
implicit and had begun to drift (strength knowledge reachable through two
uncoordinated paths, a duplicated Coggan zone model, an omnibus policy hardcoded
in the consumer). This ADR records the decisions so the loop and future
developers don't re-litigate them.

## Decisions

**D1 — Dual-access to strength knowledge is intentional.**
`get_coaching_knowledge` is the *knowledge* path (returns raw YAML sections the
agent reads to coach well); the four dedicated `strength_coach` tools are the
*action* path (return structured workout/program/assessment output). The
endurance `skills/coaching/SKILL.md` defers strength topics to the
`strength-coaching` skill and must not call `get_coaching_knowledge` for
strength. To stop the endurance skill from fuzzy-matching strength sections via
content-fallback, `strength_standards`, `strength_principles`, and
`strength_training` join `_OMNIBUS_SECTIONS` — omnibus blocks content-fallback
but not explicit key-match, so the strength skill's
`get_coaching_knowledge("strength principles")` still works.

**D2 — Cross-file key collisions: warn + keep last at runtime; fail in CI.**
`_brain.py` logs a warning and keeps the last definition (preserving the
historical `dict.update` semantics) so a duplicate-key typo doesn't take down
all knowledge tools at runtime. `test_no_cross_file_top_level_key_collisions`
asserts the real corpus has zero collisions, catching the error in CI before
deploy.

**D3 — Omnibus set stays hardcoded in `coaching.py`; guarded by a CI test.**
`_OMNIBUS_SECTIONS` describes corpus structure but lives in the consumer, not
the corpus. Keeping it hardcoded (rather than in YAML metadata) is deliberate:
the loop rarely creates *large* sections, and the real cost (stale/unmarked
entries going unnoticed) is covered by
`test_every_omnibus_section_exists_in_corpus`, which fails CI if an omnibus
entry is renamed or removed from the corpus.

**D4 — Coggan 7-zone power model: `power-zones.yaml` is canonical.**
The rich version (`coggan_power_7_zone` with per-zone `range` + `purpose`) is
the single source. The simpler duplicate that lived under
`training-philosophies.yaml`'s `intensity_zones` was removed — its
`coaching_note` was already conveyed by the rich version's per-zone purposes.
The two HR zone models (5-zone LTHR in `power-zones.yaml`, 3-zone VT in
`training-philosophies.yaml`) are *different models*, not duplicates, and both
stay.

## Considered and rejected

- **Omnibus as YAML metadata (`_meta` blocks / a `_manifest.yaml`).** Solves a
  low-frequency problem (the loop rarely adds large sections) with a new parsing
  convention + search-exclusion logic. The CI guardrail (D3) covers the real
  cost without the convention overhead.
- **Restructure multi-key files to one-key-per-file.** The granular sub-keys
  (e.g. `zone_distribution`) aid keyword-search precision; merging them under a
  single key would degrade matching to content-fallback. The
  `overview`/`coaching_notes` noise in `available_topics` is cosmetic and only
  appears on a no-match fallback.
- **Typed access layer for `strength_coach`.** After D1, the keys `strength_coach`
  reads (`strength_standards`, `exercise_database`, `strength_programming`) are
  all omnibus entries, so D3's guardrail already catches top-level renames in CI.
  Sub-key renames degrade gracefully (empty field, not silent total failure) and
  a typed adapter would couple to evolving YAML.
- **Hard runtime error on key collision.** `_load_all` is called by every
  knowledge tool; a hard error would take them all down for one typo.
  Warn + CI guard (D2) gives the same safety without the blast radius.
- **mtime-aware cache in `_brain.py`.** This is a deploy-restart architecture
  (edits → PR → Flux → pod restart → cold cache); mid-session hot edits don't
  occur in production. The 60s TTL only avoids re-reading disk within a session,
  which is its job.
