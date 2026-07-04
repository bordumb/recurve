# self_recursion — recurve runs its own loop, on its own repo

> The plumbing that lets recurve drive its improvement loop on the recurve repo
> *itself* (the self-host layout), not only on stamped targets. This is the first
> step of #4 (complete the plumbing): you cannot burn down the plumbing WITH the
> loop until the loop can run on this repo.

## Conventions

`missing-surface` claims about `recurvelib.run`, `reads: none` — each probe
executes the resolution against the real self-host config and a kept
counterexample.

## SR-1 — recurve run resolves a runnable workflow on the self-host repo

`recurve run` finds a runnable burndown workflow on the recurve repo itself —
falling back to the engine's shipped `templates/workflows/burndown.sh` when no
stamped `.recurve/workflows/` exists — instead of erroring "no workflow, run
init first". This is what makes the loop runnable on its own repo. Negative
space: a resolver that only looks for a stamped `.recurve/workflows/` workflow
finds nothing on the self-host layout and must turn the probe RED.
