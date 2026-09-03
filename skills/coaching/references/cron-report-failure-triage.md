# Cron report failure triage

## Signal
A morning-brief cron run can be recorded as technically successful (`last_status: ok`) while its response says the report could not be generated. In the reviewed run, the output ended with an onboarding-required message because athlete identity was unavailable.

## Triage sequence

1. Inspect the actual cron output, not only scheduler metadata.
2. Classify the failure:
   - missing gateway snowflake/context;
   - missing, stale, or mismatched per-user credentials;
   - generated report routed to the wrong destination;
   - genuine upstream/tool failure.
3. For headless coaching, resolve the athlete snowflake from job origin or explicit delivery identity and run direct identity verification before any training calls.
4. Recommend `/start` only when direct verification confirms onboarding or credential identity is missing/mismatched. Do not send that instruction merely because model-visible tools lacked gateway context.
5. Check `deliver` separately: routing identifies where to send the report, but it does not prove credential ownership.
6. Report the semantic result plainly: “scheduler ran” and “usable report delivered” are separate facts.

## User-facing response pattern

- State whether the job ran.
- State whether a usable report was generated/delivered.
- Name the verified failure class.
- Give one concrete next action.
- Do not claim poor recovery, missing training data, or successful delivery when identity setup prevented analysis.

## Reproduction evidence

The reviewed output file was `cron/output/c394e2e32565/2026-08-21_06-00-40.md`. It had a normal run header and ended with: “Scheduled coaching brief could not be generated because the athlete identity was unavailable. Please rerun `/start` onboarding for this Discord identity.” The scheduler nevertheless reported `last_status: ok`; this is why output-level semantic validation is required.
