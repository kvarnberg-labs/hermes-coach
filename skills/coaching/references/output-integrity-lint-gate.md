# Output integrity — pre-send lint gate for ALL coaching deliverables

## Why this exists

Two interactive coaching answers arrived garbled. A **4-week post-illness rebuild
program** was delivered to Aldrin (2026-10-06, session 20260829_172300_6bb3ad9b,
msg 20986) with malformed tables and injected tokens (`| hosta |` table fragment,
`DUPLICATE-HAZARD`, `pre-V154303`, `Mån 12/1 0`, `Lör 17/40 min Z2`,
`@"@Local first:`), and a Wilma analysis (2026-10-04, message 20623: "jag bore inte
kalender", "mitt ansvatertjänst", "uppgeflytta baseline", "CrossFit-känslanitics",
"veilåda", "sätts tillmax"). **A third instance (2026-10-14 05:31 CEST, session
20260831_043233_5e644b44, msg 21936 to Wilma) proved the gate is skipped for SHORT
interactive messages that don't look like "deliverables":** a short chat
confirmation ("calendern är städad") plus a mini weekly-plan table went out with
broken Swedish and garbled fragments untouched — "Det var min fél — fartleken
(även lätt) inte en lågintensiv pass enligt din önskan", "din HR-värde & pulströ
som vi evaluate doodaa **söndag**", "Normen kommer troligen då". The corruption
class is **identity-confirmed**:
Aug–mid-Sep sessions rendered on `gpt-5.6-luna` are clean Swedish; the corrupted
onsets (2026-09-12/13 Millberg briefs, Oct 4 Wilma, Oct 6 Aldrin) all track the
`glm-5.3-flash` pin (provider-side intermittent token corruption; vLLM #54150,
opencode #16903).

The mechanical lint `scripts/brief_lint.py` (HARD = structural corruption,
SOFT = unknown-token review) was added for **headless** briefs (PRs #95+, prompt
SLUTKONTROLL). It demonstrably catches this class in production briefs. But
**interactive** coaching messages and long deliverables (programs, weekly plans,
post-workout analyses) get NO mechanical gate — they rely on the model
self-reviewing its own output, which the headless history proved unreliable
(model self-review does not catch its own corruption; the check must be
external and mechanical).

## Rule (applies to EVERY coaching deliverable — interactive included)

Before sending any athlete-facing coaching message or deliverable:

1. **"Deliverable" means EVERY athlete-facing outgoing message — interactive chat
   replies included, however short.** A one-line confirmation ("kalendern är
   städad"), a mini plan table inside a casual reply, an emoji answer — all are
   deliverables. Skipping the gate because a message is "too short to lint" is
   the confirmed Oct-14 failure mode (short Wilma reply delivered broken Swedish
   + garbled fragments). Length is not a trigger; the fact that the text will be
   read by the athlete is.
2. **Draft to a file** under `$HERMES_HOME` (e.g. `/opt/data/brief_draft.md`),
   never `/tmp` (write_file is locked to `$HERMES_HOME`).
3. **Run the mechanical lint:** `python3 /opt/data/scripts/brief_lint.py
   <draft-file>` (or `cat draft.md | python3 brief_lint.py`).
   Exit 0 required. Hard findings → regenerate the offending row/section and
   re-run until clean. Soft findings (unknown tokens) → either justify each
   token in context or rewrite the line, then re-run.
4. **Then read the whole draft as text** — mechanical lint cannot catch broken
   sentence logic or semantics (e.g. a table mislabeled "Vecka 2 continued"
   that actually contradicts the program). More than one broken section →
   abort delivery and rebuild the artifact; tell the athlete the redo is in
   progress instead of sending junk.
5. **Send the linted draft verbatim — never compose live into the chat box.**
   Paste the linted file as your outgoing message text. Live-composing means the
   provider corrupts text AFTER the lint passed, which reintroduces exactly the
   class the gate exists to block.
6. **Memory writes follow the same discipline** — corrupted text posing as a
   stored memory entry (e.g. Aldrin's memory entry claiming its own previous
   version contained "völlig/Institivitet/vedertaget") propagates into future
   sessions as fake context. When re-writing a memory entry and you cannot
   trace the old/new text to a verifiable source, rewrite from verified data
   (session history, tool results) instead of trusting the recalled text.

For **longer deliverables** (multi-week programs, plans): additionally
tabulate dates/loads in-line with the plan — day-by-day rows must each carry
date + weekday, and the total counts (e.g. "12 sessions") must reconcile with
the enumerated rows before you ask for approval.

Interactive deliverables are higher stakes, not lower: an interactive program
seeks approval and then drives calendar writes — garbage in, garbage to Garmin.

## Scope and quantities (2026-10-07 audit)

- Interactive corrupt deliveries confirmed: Aldrin program (Oct 6), Wilma
  analysis (Oct 4), **and a SHORT Wilma chat confirmation + mini weekly-plan
  table (Oct 14, session 20260831_043233_5e644b44 msg 21936)** — all on
  `glm-5.3-flash`; older gpt-5.6-luna sessions clean. The Oct-14 case shows the
  real-world trigger is not deliverable size but agent self-classification:
  short interactive messages get treated as "not worth linting" and walk past
  the gate, so the rule above defines ANY athlete-facing outgoing message as a
  deliverable and requires the linted text to be sent verbatim.
- Headless SLUTKONTROLL gate: validated clean in both Oct 7 production briefs
  (Wilma + Millberg), gate wording present in all 3 live cron prompts
  (`/opt/data/cron/jobs.json` — verified this date).

See also: `references/cron-prompt-templates.md` (STEG 0 + SLUTKONTROLL blocks),
`coach-brain/headless-coaching-failures.yaml` (output_corruption class),
`scripts/brief_lint.py`.
