# Gap Discovery Through Cross-Athlete Conversation Analysis

Self-improvement loop only. Cross-athlete session reading must never happen in
an athlete's coaching session (moved out of the coaching skill 2026-10-15).

A systematic technique for finding coaching tool gaps, deployment issues, and
silent failures by reading conversations across multiple athletes in one session.

## Why this works

Coaching sessions with individual athletes look successful in isolation but
patterns emerge when you read 3-4 athletes' sessions side by side:

- **Agent silently using raw curl** — the agent works around missing tools
  without reporting errors. Only visible across multiple sessions.
- **Agent fabricating data** — cron prompts tell agents to call tools that
  fail silently. The agent produces values that look correct but were never
  pulled from intervals.icu.
- **Deployment gaps logged but never escalated** — the self-improvement
  worklog identifies gaps correctly but never acts on them.

## Technique

1. Pick 2-3 athletes who have recent activity. Rotate daily.
2. Scroll into their most recent coaching session.
3. Look for: agents using terminal/curl for API data (missing tool), agents
   fabricating wellness values (broken cron prompt), agents spending 3+
   messages on simple explanations (missing documentation).
4. Cross-reference against the coaching skill's routing table, the
   self-improvement worklog, active cron prompts, and plugin deployment state.
5. Act on the highest-impact gap within CONTRACT.md: Path A/B if it is a
   knowledge or new-tool gap, otherwise a Path S signal — don't just log it.

## Case study: July 28, 2026

Reading 4 athletes' conversations uncovered 5 tool gaps the self-improvement
cron had missed for 10+ days. All five issues produced successful-looking
responses — no athlete complained, no errors appeared. Only cross-session
reading caught them.