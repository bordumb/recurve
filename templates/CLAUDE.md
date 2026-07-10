# {{PROJECT}}

Managed by **recurve** — a claims-gated improvement loop. Every promise this
project makes lives in three synchronized places: prose
(`.recurve/claims/<suite>/GAPS.md`), a ledger entry (`gaps.yaml`), and an
**executable probe** that answers GREEN (proven), RED (not yet true), or
BROKEN (couldn't measure). A probe only goes GREEN when the claim is
genuinely true — the whole system exists to make that statement trustworthy
without anyone having to take an agent's word for it.

## How to work in this repo

- Read `.recurve/RUN.md` (the per-cycle contract), or invoke the **`cycle`**
  skill (`.claude/skills/cycle/`) to run one improvement cycle by hand. For an
  unattended run, see `.recurve/RUN-AUTO.md` or the **`loop`** / **`burndown`**
  skills.
- The arbiter is `{{PROG}} matrix --gate`. **Believe the gate — not yourself,
  not an agent's summary.** A claim is closed when its probe is GREEN and the
  fleet-wide gate holds, never because someone believes it is. (`--cache` runs the
  same gate faster by skipping probes whose inputs are unchanged — sound; use it
  freely, but run one uncached gate before a PR/report/`baseline`. See RUN.md.)
- **Never fake a check:** no weakened probes, no skipped traps, no editing
  anything under `.recurve/claims/` to make the gate pass. A GREEN must mean
  the claim is genuinely true.
- **Every claim carries a trap** — a counterexample its probe must turn RED —
  so a probe that quietly stopped working gets caught, not trusted. A probe
  never seen RED is not yet evidence (`.recurve/quality.md`).
- **One writer per tree.** Don't run a second driver against `{{TREE}}` while
  a cycle is in flight — a shared build/lock races and corrupts the fleet
  gate (`{{PROG}} lock status`).
- Report without inflation: a closed claim is exactly what its probe checked,
  nothing more.

## An open claim is a target, not a verdict

This is a hard rule, not a style preference:

- **Never write "this can't be done" or "still open" as if that settles the
  question.** Say what the actual blocker is and what clearing it would need.
  A claim stays RED because the right fix hasn't landed yet — not because
  it's unfixable.
- **RED means "not yet, and worth another attempt"** — never "give up here."
  Parking a claim after a few honest attempts (see `.recurve/RUN.md`) records
  what was tried so the next cycle doesn't repeat it; it does not close the
  door.
- **A claim too big for one cycle isn't a verdict either.** Break it down
  RED-first — sub-claims plus a mechanically-checked assembly proving they
  add up to the goal (`.recurve/RUN.md` §DECOMPOSE) — rather than forcing an
  overreaching proof, weakening a probe, or parking it as merely stuck.
- **The fix for language that reads as defeatist is more concrete work, not
  less honesty.** Never manufacture a false sense of "basically done," and
  never fake a probe to feel better about progress — that is exactly the
  dishonesty this harness exists to prevent. Instead, go find the next real,
  smaller step.
- If something is genuinely beyond this project's reach right now (an
  external dependency, a decision only a human can make, a result nobody has
  found yet), say so plainly — but frame it as *here's the specific blocker,
  here's what resolving it would look like*, not as a dead end.

## The pieces

| File | What it is |
| --- | --- |
| `.recurve/recurve.toml` | all project variability: suites, tree, freshness, gate |
| `.recurve/claims/<{{LABEL}}>/` | prose + ledger + probes + traps + harness for one domain |
| `.recurve/RUN.md` | the per-cycle agent contract (one cycle, proven, stop) |
| `.recurve/RUN-AUTO.md` | unattended operation runbook |
| `.recurve/REVIEW.md` | the adversarial protocol for review-gated claims |
| `.recurve/TROUBLESHOOTING.md` | symptom → which rule fired → what to do |
| `.recurve/README.md` | the 60-second overview and the three starter commands |

_(This file is a starting point, stamped once by `{{PROG}} init` — edit it
freely as this project's own conventions grow past the defaults.)_
