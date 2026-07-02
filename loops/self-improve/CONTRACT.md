# Self-Improvement Loop Contract

## Goal

Make hermes-coach 1% better per run — one PR per day, safely.

Improvements target:
1. Filling knowledge gaps in `coach-brain/` (altitude, heat, strength, female physiology, etc.)
2. Adding new tools via `develop_tool` (toolset `self-improve`)

## Workflow (every run, in order)

1. **Read** this file and the last 10 lines of `loops/worklog.md`
2. **Discover** open signals in `loops/signals/` + injected discovery script output
3. **Plan** — pick ONE high-value improvement; log intent to `worklog.md` (date + intent)
4. **Execute** — edit one `coach-brain/*.yaml` file OR develop one new tool
5. **Verify** — apply the rubric below; fail fast if it doesn't pass
6. **Commit** — branch `improve/<slug>`, push, open PR via GitHub REST API (see AGENTS.md)
7. **Deliver** — post PR link + one-line summary to the ops Discord channel
8. **Stop** — one PR per run; append completion to `worklog.md`; mark signal as `resolved`

## Stop conditions

- PR submitted → stop (done)
- 3 verify rounds fail on the same change → stop; log as a blocker signal in `loops/signals/`
- No actionable signal AND backlog is empty → stop silently (no Discord message)

## Verification rubric

### Knowledge edit (`coach-brain/*.yaml`)
- [ ] Change is evidence-based (describe physiological source in PR body)
- [ ] Does NOT contradict existing TSB thresholds or Coggan zone boundaries
- [ ] Stays within documented safe physiological ranges
- [ ] Fewer than 50 lines added per PR

### New tool (via `develop_tool`)
- [ ] Sandbox `pytest` passes with at least one meaningful assertion
- [ ] Tool has no direct network calls (uses the existing `_request()` wrapper)
- [ ] No `os`, `subprocess`, `eval`, or `exec` in tool code
- [ ] Tool name is snake_case; description is one sentence
- [ ] Returns valid JSON

## Boundaries (hard limits — do not cross)

- Only edit files under `coach-brain/` or create new tools via `develop_tool`
- Do NOT modify auth, security, deployment manifests, or test files
- Do NOT expose new tools with `toolset="training"` — use `"self-improve"` or a topic-specific set
- Do NOT make multiple PRs in one run

## Active backlog

- [ ] Add altitude acclimatization knowledge (hypoxic adaptation, ~3-week timeline, AMS warning)
- [ ] Add heat training adaptation (plasma volume, core temp tolerance, acclimatization protocol)
- [ ] Add female athlete / menstrual cycle periodization guidance
- [ ] Add cold weather training adaptations
- [ ] Add response-parser unit tests for `get_wellness` and `get_recent_activities`
- [ ] Fix SKILL.md TSB threshold cross-reference (already -20 in SKILL.md and coach-brain; verify consistency)

## Timeline

| Date | Event |
|------|-------|
| — | Loop initialized |
