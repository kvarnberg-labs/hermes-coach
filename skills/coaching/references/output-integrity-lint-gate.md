# Output integrity — what the send-path gate does and what is still your job

Some model/provider combinations intermittently corrupt tokens (garbled Swedish,
fused words, injected CJK, stray brackets). Model self-review does not catch its
own corruption, so the check runs outside the model.

## Automatic: every reply passes a gate before delivery

Every reply — interactive chat and cron alike — is linted by the training
plugin's `transform_llm_output` hook (`plugins/training/_output_gate.py`, rules
in `scripts/brief_lint.py`) before it is sent. Structural corruption (U+FFFD,
bracket glitches, non-Latin script runs, internal error/draft-file leaks) makes
the gate replace the whole reply with:

> Mitt svar blev tekniskt skadat och stoppades innan det skickades. Skriv gärna
> igen så gör jag ett nytt försök.

You do not run the lint yourself in chat; you have no terminal there.

**If you see that notice as your previous reply:** the athlete never saw your
answer. Regenerate it from the verified tool results — shorter, with simpler
tables — and do not refer to the lost text.

## Still your job (the gate cannot check meaning)

1. **Read the whole reply once before sending.** The lint catches broken tokens,
   not broken logic: contradictory dates, a table that disagrees with the text,
   unfinished sentences (`coherence_failure` in
   `coach-brain/headless-coaching-failures.yaml`). More than one broken section →
   rebuild the reply instead of patching it.
2. **Long deliverables** (multi-week programs, plans): every day row carries
   date + weekday, and totals ("12 pass") reconcile with the rows before you ask
   for approval. An approved plan drives calendar writes.
3. **Memory writes:** never copy recalled text you cannot trace to session
   history or tool results — corrupted memory propagates into future sessions.
   Rewrite from verified data.

## Cron runs

Cron prompts keep their SLUTKONTROLL step (`python3 /opt/data/scripts/brief_lint.py`,
exit 0 required, soft findings justified or rewritten) — it lets the run
regenerate before the gate has to block. See `references/cron-prompt-templates.md`.
