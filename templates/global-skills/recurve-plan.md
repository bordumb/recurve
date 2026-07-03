---
name: recurve-plan
description: Set up recurve in the current repo and produce a gate-ready PRD. Verifies the recurve CLI, runs recurve init, then interviews the user toward a PRD that passes recurve's admission gate (recurve admit). Run this before /recurve-work.
---

# recurve-plan — get to a gate-ready plan

Goal of this skill: leave the current repo initialized for recurve, with a
**PRD that passes the admission gate**, so claims can be built from it. Work
*with* the user and stop at the checkpoints — do not invent scope they didn't
sanction.

## 1 · Verify the recurve CLI

Run `recurve --help`. If it is missing, install recurve from its checkout (it is
a Python package with a console script) and stop until `recurve` resolves:

```bash
# from a clone of the recurve repo:
pip install -e .        # or: pipx install .
recurve install         # links the entrypoint onto PATH (~/.local/bin)
```

Confirm `command -v recurve` before continuing.

## 2 · Initialize the repo

If there is no `.recurve/` directory, run `recurve init` — it stamps
`recurve.toml`, `.recurve/RUN.md`, the claims scaffold, and the per-repo
cycle/loop/burndown skills. Then confirm a sound baseline with `recurve validate`.

## 3 · Ensure a PRD exists

Look for `docs/PRD.md` (or ask the user which file is the PRD). If none exists,
**interview the user** to draft one. Keep it decomposition-oriented — claims get
carved from it, so vague prose is worthless here:

- What is the goal, in one sentence?
- What does "done" / "better" mean **concretely and observably**?
- What are the top-level sub-goals, and the named intermediate pieces each needs?
- What must **never** happen (behaviors to forbid)?

Propose the shape before writing it out, then draft `docs/PRD.md` from the answers.

## 4 · Pass the admission gate — the "great PRD" check

Run `recurve admit docs/PRD.md`. This is recurve's front-door gate: it judges
whether the goal is concrete enough to become falsifiable claims and prints an
**interview worklist** of what is still too vague. Work through that worklist
*with the user*, tightening the PRD, and re-run `recurve admit` until it passes.

A goal that can't be admitted can't be gated — do not skip this or hand-wave it
GREEN.

## 5 · Stop and hand off

Report: repo initialized, `recurve validate` clean, PRD **admitted** (gate-ready).
Tell the user the next step is **`/recurve-work`**, which will author the first
claims from this PRD and start the burndown loop.

## Hard rules

- Interview, propose, confirm — never write a PRD the user didn't sanction.
- The admission gate is the arbiter of "good enough to build on," not your
  judgment. If `recurve admit` won't pass, the PRD isn't ready — keep refining.
