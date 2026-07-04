---
name: recurve-work
description: Run recurve's burndown loop on the current repo — turn the highest-value RED claim GREEN under the gate. Asks whether to run endless-until-complete or stop-for-approval after each claim, and authors claims from the PRD first if the ledger is empty. Run /recurve-plan first.
---

# recurve-work — burn down claims under the gate

## 1 · Preconditions

- `recurve --help` resolves. If not, run **`/recurve-plan`** first (it installs
  the CLI), then come back.
- `.recurve/` exists. If not, tell the user to run **`/recurve-plan`** first and
  **stop** — there is nothing to burn down yet.
- The baseline is clean:
  - `recurve validate` — ledger is sound (every open claim has a probe + trap),
  - `recurve matrix --gate` — no regressions / broken / stale,
  - `recurve lock status` — unlocked (no other driver).
  If any fails, report it plainly and stop. Do not start on a broken baseline.

## 2 · If the ledger is empty, author the first claims

Run `recurve ledger`. If there are **no claims yet**, you cannot burn down an
empty backlog. Tell the user and get approval before authoring:

> "No claims yet. I'll author the first wave from `docs/PRD.md`: precise
> statements, each with a **RED-first** probe (passes only when the claim is
> genuinely true) and a **trap** (a known-bad input the probe must reject), then
> baseline them RED. Proceed?"

On approval: author the claims + probes + traps, run `recurve baseline <suite>`,
and show the resulting RED ledger. Then continue.

## 3 · Ask how to run

Use **AskUserQuestion**:

- **"Endless"** — run cycle after cycle until the gate is complete, goes red, or
  hits a dead-end; do **not** stop for approval between claims.
- **"Per-claim"** — stop after each claim closes so the user reviews and approves
  the next.

## 4a · Endless mode

Drive recurve's self-managing burndown — it uses a fresh agent per cycle, its own
stop controller, and per-cycle commits:

```bash
recurve run --agent 'claude -p --bare --permission-mode bypassPermissions'
```

(`--bare` strips inherited session hooks so cycle agents don't stall on a
"checkpoint" reflex.) Relay progress; surface only when it halts — complete, gate
red, cap reached, or a dead-end — then report the wrap-up (what closed, what got
parked and why, what needs the human).

## 4b · Per-claim mode

Repeat until the backlog is empty, the gate goes red, or the user stops:

1. Run **exactly one** cycle following `.recurve/RUN.md`: `recurve next` (triage
   the highest-value RED claim) → make the smallest honest change → rebuild →
   `recurve matrix --gate` (the arbiter) → promote open→closed and update the
   prose → snapshot/commit per policy → `recurve record append`.
2. **Stop** and show the user: which claim you worked, what changed (a short diff
   summary), and the `recurve matrix --gate` output.
3. Ask the user to approve continuing. On "next", run the following cycle;
   otherwise stop.

## Multi-repo configs (sculpts)

Check `recurve.toml` for `[sculpts.<name>]` tables. If present, this is a
multi-repo config: `[target]` is the tree you **build**; each sculpt is a
secondary tree (usually another repo) you may **sculpt** when a claim's honest
fix lives there. Rules that change:

- **Fix where the truth lives.** If the honest fix for a claim is in a sculpt
  tree, make it there — never fake it in the target to avoid crossing repos.
- **Commit per tree.** Sculpt changes are committed in the *sculpt's* repo, on
  its declared `branch:` — target commits and sculpt commits stay separate.
- **The gate is federated.** `recurve matrix --gate` is green only when the
  target's probes pass AND every sculpt's `rebuild` and own `gate` command exit
  zero. Never bypass a red sculpt gate by hardening the target around it.
- **Vocabulary is per tree.** Each sculpt declares its own `forbidden_strings`;
  do not leak the target's loop vocabulary into a sculpt tree (or vice versa).

With no `[sculpts.*]` tables, none of this applies — proceed single-tree.

## Hard rules (both modes)

- The gate is the arbiter — **believe it, not yourself.**
- **Never** fake a check, weaken a probe, or edit anything under
  `.recurve/claims/` to make the gate pass. A GREEN must mean the claim is
  genuinely true — this is the one failure the whole system exists to prevent.
- One unit of work per cycle; per-cycle commits, so a bad cycle costs at most one
  cycle.
