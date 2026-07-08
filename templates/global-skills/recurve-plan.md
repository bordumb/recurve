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

**Single-tree or multi-repo?** Ask one scoping question: *will reaching this
goal require changing another repository* (a platform this repo feeds, a
sibling library, a shared toolchain)? The default — one repo — needs nothing.
If the answer is yes, declare each secondary tree as a `[sculpts.<name>]`
table in `recurve.toml` **with the user** (they own these values):

```toml
[sculpts.platform]
tree = "../platform"              # resolved against this config
branch = "dev-platform"           # sculpt commits land on THIS branch, in THAT repo
rebuild = "cargo build --release" # how fresh artifacts reach its checks
gate = "cargo test"               # its OWN gate — folded into the federated gate
forbidden_strings = ["GAP-"]      # this tree's leak vocabulary
```

`recurve matrix --gate` then federates: green only when the target's probes
AND every sculpt's rebuild + gate pass. /recurve-work knows the per-tree
commit rules from there. Do not invent sculpts speculatively — declare one
only when the goal genuinely requires cross-repo work.

## 3 · Ensure a PRD exists

Look for `docs/PRD.md` (or ask the user which file is the PRD). If none exists,
**interview the user** to draft one. Keep it goal-and-observable-oriented — claims get
carved from it, so vague prose is worthless here:

- What is the goal, in one sentence? (It can be *easy or hard* — that's fine.)
- What does "done" / "better" mean **concretely and observably**?
- What are the top-level sub-goals, and the shape of the approach?
- If multi-repo: which sub-goals live in the target, and which in a sculpt tree?
- What must **never** happen (behaviors to forbid)?

You do **not** need to enumerate every leaf of a hard goal here — `/recurve-work` breaks
big claims down itself (and mechanically checks the breakdown adds up). Capture the goal,
what "done" observably means, and the top-level shape; let the loop find the rest.
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
Tell the user the next step is **`/recurve-work`**: point it at the goal (easy or hard)
and it authors the first claim, then drives to the goal under the gate — closing each
piece directly when it's small, or breaking it into smaller claims (with a mechanical
check that they add up) wherever a piece is too big. They don't pre-decompose a hard goal
by hand; the loop does that.

## Hard rules

- Interview, propose, confirm — never write a PRD the user didn't sanction.
- The admission gate is the arbiter of "good enough to build on," not your
  judgment. If `recurve admit` won't pass, the PRD isn't ready — keep refining.
