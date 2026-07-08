---
name: cycle
description: Run exactly ONE improvement cycle for {{PROJECT}} — triage the highest-value RED claim, then either close it or (if it's too big) break it down RED-first, gate, commit, stop
---

# Single cycle

You were invoked to run one sculpting cycle by hand (no orchestrator).

Read `.recurve/RUN.md` and follow it exactly — it is your entrypoint and your stop
condition. The short form: `{{PROG}} validate && {{PROG}} matrix` (clean baseline),
`{{PROG}} next` (triage the highest-value RED claim), then make **one move**:

- **Close it** — when it's small enough to prove honestly this cycle. Sculpt the smallest
  honest change, rebuild, `{{PROG}} matrix --gate` (the arbiter), promote open→closed +
  rewrite the prose, snapshot, commit per policy, `{{PROG}} record append`.
- **Break it down** — when it's *too big to close honestly this cycle*. **Do not force
  it.** Decompose it RED-first: the smaller claims it genuinely needs, plus an **assembly**
  claim that derives this goal **from those sub-claims as hypotheses**. Arm + gate the
  assembly — a GREEN assembly mechanically certifies the breakdown *adds up to the goal*
  before you prove any piece; if it won't go GREEN, the breakdown is wrong, so fix it. Then
  arm the sub-claims RED-first (each a probe + trap), each with `covers_claim:` pointing at
  this parent. Commit, `{{PROG}} record append`. The next cycle picks up a child; when all
  children close, the parent closes via its assembly.

Then **STOP**. One cycle = one agent — do not start a second cycle because the first went
well.

**Never** fake a check, weaken a probe, or force an overreaching proof to close a too-big
claim — the break-down move is exactly what prevents that. Believe the gate.
