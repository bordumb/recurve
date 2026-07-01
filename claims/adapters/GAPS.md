# adapters — wiring the loop to a real repo + a live actor, probed

> The real-world adapters for the runtime loop (`recurvelib.adapters`): a git-backed `World` and a BYO-agent
> `CommandActor`. These claims gate the deterministic plumbing; the agent behind the command stays external
> and pluggable. Each probe drives a real temporary git repository.

## Conventions

`missing-surface` claims about `recurvelib.adapters`, `reads: none` — each probe stands up a real temp git
tree (or a real subprocess) and a kept counterexample.

## AP-1 — the write boundary is enforced when a patch is applied to a real tree

`GitWorld.apply` refuses a patch that touches the referee surface (raising, writing nothing) and writes a
patch confined to the target tree. Negative space: an apply that skips the boundary check and writes a probe
edit to disk must turn the probe RED.

## AP-2 — checkpoint then restore rolls a real tree back

`GitWorld.checkpoint` commits the tree and `restore` hard-resets to it, so a later STOP-REVERT actually
undoes the actor's changes. Negative space: a restore that is a no-op (leaving the mutation on disk) must
turn the probe RED.

## AP-3 — the actor is driven by the external command

`CommandActor.propose` runs the agent command, passes it the evidence, and returns the patch it prints
(empty stdout → no change). Negative space: an actor that ignores the command and returns a canned patch must
turn the probe RED.

## AP-4 — the loop burns a real repo down and stops

`run` over a `GitWorld` + a `CommandActor` drives a RED file to GREEN on disk, returns STOP-SUCCESS, and never
touches the referee surface. Negative space: a world whose apply drops the patch (so the tree is never fixed)
must turn the probe RED.
