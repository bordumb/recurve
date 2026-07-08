---
name: recurve-work
description: Point recurve at a goal and it drives to it under the gate — closing each piece directly if it's small, breaking it into smaller claims (and mechanically checking they add up) if it's too big, recursing until the goal is proved or it hits a genuine wall. Handles easy and hard problems with the same loop; no need to pick "burndown" vs "solver." Run /recurve-plan first if the repo isn't set up.
---

# recurve-work — point it at a goal; it drives to it under the gate

**The whole model in one paragraph.** You point recurve at a goal. It works toward
that goal one obligation at a time, and for each one it **picks its own move**:
*close it directly* if it's small enough to prove in a cycle, or *break it into
smaller claims* if it's too big — and it **mechanically checks the breakdown adds
up to the goal** before spending effort on the pieces. It recurses until the goal
is proved or it hits a genuine wall it surfaces to you. **Easy problems never
trigger the break-down — that's just burndown. Hard ones do — that's the solver.
Same loop; the difficulty decides the depth.** You never choose which; the loop does.

## 1 · Preconditions

- `recurve --help` resolves and `.recurve/` exists. If not, run **`/recurve-plan`**
  first (it installs the CLI and initializes the repo), then come back.
- Clean baseline: `recurve validate` (ledger sound — every open claim has a probe +
  trap), `recurve matrix --gate` (no regressions / broken / stale), `recurve lock
  status` (unlocked). If any fails, report it plainly and **stop** — never start on a
  broken baseline.

## 2 · Point it at something (dead simple)

Ask the user for **one** of these, or infer it if they already said:

- **A goal** — "prove X," "make Y work," "close the blowup side." If there's no claim
  for it yet, you'll author one (§3). This is the common case; the goal can be *easy
  or hard* — the loop adapts.
- **The open backlog** — "just work what's already open." Then skip to §4 and drive
  the existing claims.

If there are **no claims at all** for the goal, get approval and author the first one
from `docs/PRD.md` (or the user's goal): a precise statement, a **RED-first** probe
(passes only when the claim is genuinely true), and a **trap** (a known-bad the probe
must reject); then `recurve baseline <suite>` to arm it RED. You do **not** have to
pre-decompose a hard goal by hand — arm the top-level claim and let §4 break it down.

## 3 · The loop — one move per obligation, chosen by the loop

Repeat until the goal's claim is GREEN, the gate goes red, or a genuine wall is hit.
Each pass takes the highest-value open obligation (`recurve next`) and does **one** of:

**A · Close it** (the small case — "burndown"). Make the smallest honest change that
turns its RED probe GREEN. Rebuild → `recurve matrix --gate` (the arbiter) → promote
open→closed, update the prose → commit per policy → `recurve record append`.

**B · Break it down** (the big case — "solver") — when it *cannot* be closed honestly
in one cycle. Do **not** force it. Decompose it **RED-first**:

1. Split it into the smaller claims it genuinely needs.
2. Write the **assembly** claim — a lemma/check that derives this goal **from those
   sub-claims taken as hypotheses**. Arm it RED-first and gate it. **A GREEN here
   mechanically proves "the sub-claims imply the goal"** — the *does-my-breakdown-add-
   up?* check — *before* you prove any of them. If it won't go GREEN, the breakdown is
   wrong: revise it. *(This is the **sufficiency check**. recurve is growing built-in
   support for it — a recursive solver over these cuts. If `recurve --help` shows a
   `solve` / `sufficiency` command, prefer it over hand-driving; the behavior is the
   same, automated.)*
3. Arm the sub-claims RED-first (each a probe + trap), each pointing at this parent via
   `covers_claim:` in its ledger entry (the decomposition edge the loop walks to
   discharge the parent once every child closes).
4. Keep looping — each sub-claim gets move **A** or **B** in turn. When all children are
   GREEN, the parent closes via its assembly, and that closing propagates up.

The recursion bottoms out at claims small enough for move **A**. On an easy goal, every
obligation takes move **A** on the first try and you never see **B** — indistinguishable
from a plain burndown. On a hard one, **B** fires wherever a claim fans out, and the loop
goes as deep as the problem demands.

## 4 · How much to check in — ask once

Use **AskUserQuestion**:

- **"Endless"** — drive it hands-off to the goal. Run recurve's self-managing loop
  (fresh agent per cycle, its own stop controller, per-cycle commits):
  ```bash
  recurve run --agent 'claude -p --bare --permission-mode bypassPermissions'
  ```
  (`--bare` strips inherited session hooks so cycle agents don't stall on a "checkpoint"
  reflex.) Each cycle applies move **A** or **B** as above. Surface only when it halts —
  goal proved, gate red, cap reached, or a wall — then report the wrap-up.
- **"Per-claim"** — stop after each obligation closes (or after a break-down is armed) so
  the user reviews and approves the next. Show which claim you worked, the change, and the
  `recurve matrix --gate` output; ask to continue.

## When it hits a wall (a genuine frontier)

If an obligation can't be closed **and** can't be honestly broken down (no smaller claims
imply it, or a sub-claim is something nobody knows how to prove), **do not fake it and do
not thrash**. Surface it: state the exact open claim, park it (`recurve park`), and report
it as the precise thing a human idea — or a discovery search — has to supply. A clean
"here is exactly what's missing" is a real result, not a failure.

## Multi-repo configs (sculpts)

If `recurve.toml` has `[sculpts.<name>]` tables, `[target]` is the tree you **build** and
each sculpt is a secondary tree you may **sculpt** when a claim's honest fix lives there.
Then: **fix where the truth lives** (never fake it in the target to avoid crossing repos);
**commit per tree** (sculpt changes on the sculpt's `branch:`, in its repo); **the gate is
federated** (`recurve matrix --gate` is green only when the target's probes AND every
sculpt's `rebuild` + `gate` pass — never bypass a red sculpt gate); **vocabulary is per
tree** (respect each sculpt's `forbidden_strings`). With no `[sculpts.*]`, proceed
single-tree.

## Hard rules (every mode, every move)

- The gate is the arbiter — **believe it, not yourself.**
- **Never** fake a check, weaken a probe, or edit anything under `.recurve/claims/` to make
  the gate pass. A GREEN must mean the claim is genuinely true — the one failure the whole
  system exists to prevent.
- **Never force-close a claim that's too big — break it down instead.** A dodged or
  overreaching proof is exactly what move **B** exists to prevent.
- A break-down is not evidence of anything: only its sufficiency GREEN (the assembly) plus
  its children closing count. An unproven decomposition proves nothing.
- One unit of work per cycle; per-cycle commits, so a bad cycle costs at most one cycle.
