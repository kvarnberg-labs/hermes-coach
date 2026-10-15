# Illness — adjust the plan, don't just skip

Load when an athlete reports being ill or missing sessions through illness, or
when wellness shows an illness signal.

## Red flags first

Chest pain, breathlessness or abnormal HR response during easy exercise after a
viral illness, fainting, or fever → stop training advice and refer
(`injury_return_to_training.illness.post_viral_caution`;
`coach-brain/coaching-safety.yaml → medical_referral`). Below-the-neck symptoms
or fever = complete rest until 48 h fever-free.

## Workflow

1. **Verify the gap and the signal:** `get_recent_activities(days=14)` (the
   missed date) and `get_wellness(days=7)` — a resting-HR rise of +10–15 bpm in
   the 2–3 days before is a common early sign. Resting HR recovers slowly; do
   not trust a single normal reading.
2. **Get the return rules:** `get_coaching_knowledge("injury return to training")`
   → `illness`. Neck rule: above-the-neck only → easy activity, much lower
   intensity; below-the-neck or fever → complete rest.
   Return timeline (from the YAML): day 1–2 walking/very light only; day 3–4
   easy Z1 if feeling well; day 5–7 normal easy training; week 2 gradual return
   to intensity.
3. **Count days** from the missed session or from when the fever broke, and
   map the next planned sessions onto that timeline: a long run on day 3–4
   becomes 50–60 min low Z2; threshold moves out at least 5–7 days.
4. **Recovery week nearby?** If a deload was already planned within 7 days,
   say so — the forced rest lines up with it.
5. **Show the adjusted days as a table** (weekday + date, session, zone) and
   ask before changing the calendar. After approval use `update_planned_event`
   / `delete_planned_event` (structured sessions: delete and re-create), then
   re-read the range. Never compress the return to "catch up"; accept the lost
   session.
6. **Masters (50+):** add 1–2 extra easy days before intensity; consider a full
   extra week for 65+ (conservative coaching practice, not a fixed rule).

Short-answer athletes get it in four lines: today, tomorrow, next session
(adjusted duration + zone), and whether a recovery week absorbs it.
