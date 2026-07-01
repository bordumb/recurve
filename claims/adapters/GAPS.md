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

> AP-5..8 were found by an adversarial review of AP-1..4 (`docs/plans/separation-of-refereeing.md`), which
> only fed the adapters well-behaved commands and clean patches. All four were real robustness bugs in the
> shipped code — a live loop meets a messy real world (a misbehaving agent, a bad sha, a colliding patch) —
> now fixed. (The referee-matching sibling of these lives in the runtime suite as RT-15.)

## AP-5 — a misbehaving agent surfaces as AgentError

`CommandActor.propose` raises `AgentError` when the command exits non-zero or prints output that is not a
valid JSON patch — never an uncaught `JSONDecodeError`/`CalledProcessError` out of the loop, and never a
silent `{}` that hides a crashed agent; a clean run that proposed nothing still returns `{}`. Negative space:
a malformed-JSON command that crashes, or a non-zero-exit command read as `{}`, must turn the probe RED.

## AP-6 — restore fails safe on an unknown sha

`GitWorld.restore` raises `RestoreError` (not a raw `CalledProcessError`) when the checkpoint sha is
unknown/unreachable, so the safety-revert path fails in a way the driver can catch. Negative space: a restore
that lets a raw `CalledProcessError` escape on a bad sha must turn the probe RED.

## AP-7 — apply is atomic against write failures

`GitWorld.apply` is all-or-nothing not just for boundary rejections but for write failures: if a multi-key
patch fails partway (e.g. a path both a file and a directory), the earlier writes are rolled back and the
tree is left as it was. Negative space: an apply that leaves a partial write on disk after a mid-patch failure
must turn the probe RED.

## AP-8 — the evidence serializer is total

`_jsonable` returns a string for any object — even one whose `__str__` raises — so serializing the evidence
can never crash `propose` before the agent runs. Negative space: a `_jsonable` that re-raises on a
non-str-able object must turn the probe RED.

> AP-9..14 were found by a SECOND adversarial review — this time of the AP-5..8 fixes themselves (new code
> that hadn't faced a referee). All six were real bugs in the fixes; a re-pass on a bug-finding module found
> more, as loop-until-dry predicts.

## AP-9 — apply rolls back a created directory, not just files

A failed multi-key patch that created a *new directory* before failing has that directory removed on
rollback, so the tree is byte-for-byte its pre-apply self. Negative space: an apply that unlinks created
files but leaves a `mkdir`-ed directory behind must turn the probe RED.

## AP-10 — apply overwrites a binary file without a decode crash

The prior contents are snapshotted as *bytes*, so an in-bounds patch replacing an existing non-UTF-8 file
applies cleanly instead of raising a raw `UnicodeDecodeError`. Negative space: an apply that reads the prior
as text and crashes on a binary file must turn the probe RED.

## AP-11 — checkpoint works on a repo with no configured identity

`checkpoint` supplies a throwaway git identity (`-c user.name/user.email`), so it commits on a host with no
configured user instead of crashing the loop's first action. Negative space: a checkpoint that relies on
ambient git config and fails on an unconfigured repo must turn the probe RED.

## AP-12 — a missing git binary is a typed error, not a raw crash

`restore`/`_git` wrap a missing/unexecutable git (and a git timeout) into the typed `GitError`/`RestoreError`,
not a raw `FileNotFoundError`. Negative space: an `_git` catching only `CalledProcessError`, so git-missing
leaks a raw error out of the revert path, must turn the probe RED.

## AP-13 — a hanging agent times out

`CommandActor.propose` runs the command with a timeout; a command that exceeds it becomes an `AgentError`,
never an unbounded hang of the loop. Negative space: a `propose` with no timeout that lets a sleeping command
run past the budget must turn the probe RED.

## AP-14 — the evidence serializer is total for dataclasses too

`_jsonable` guards the dataclass branch, so a dataclass with a recursive/unserializable field still yields a
string rather than a `RecursionError`. Negative space: a `_jsonable` that calls `asdict` unguarded and raises
on a recursive dataclass must turn the probe RED.
