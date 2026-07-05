# armkernel — the arm kernel: ports for what varies between arms

> `docs/plans/eval-arm-kernel.md`: `eval/evallib/arms.py`'s `_ARMS` dict only
> fit two of the six things an arm can vary (`recurve: bool`, `config: dict`).
> `ArmSpec` replaces it with one field per port — Workspace, Done-signal,
> Boundary, Audit, Adversary, Governor (the last two already built by
> `ablation-infra.md`). The cell-runner (`evallib.orchestrate.make_orchestrator`)
> becomes a fixed pipeline with slots, each filled by a port lookup keyed on
> the arm's `ArmSpec` — it never branches on which arm is running. Adding an
> arm is a new `ArmSpec` tuple; adding a new port VALUE is one adapter
> function (or, for `BoundaryPort`, one `recurvelib.adapters` class) plus one
> registry line. Neither ever touches the pipeline.

## Conventions

`missing-surface` claims about `eval/evallib/arms.py`, `.../orchestrate.py`,
`.../materialize.py`, `.../done_signal.py`, `.../audit.py`, and
`recurvelib.loop.boundary`/`recurvelib.adapters.boundary`. `reads: none`.
Probes construct real `ArmSpec`s and drive the real kernel
(`make_orchestrator`/`materialize`) with mock agents — no live agent, no
spend, mirroring the `eval` suite's own convention.

## AK-1 — ArmSpec replaces the flat dict; A0/A3/A7-A10 unchanged

Every arm is `ArmSpec(workspace, done_signal, boundary, audit, adversary,
governor)`. A0 = `(bare, self_report, enforced, none, off, off)`. A3 =
`(recurve_init, gate, enforced, none, off, off)`. A7-A10 extend A3 by
`adversary=`/`governor=` only, unchanged from today. Every field beyond the
two required axes (`workspace`, `done_signal`) is defaulted, so a 7th axis
added later needs no edit to any existing `ArmSpec` literal.

The regression fixture: A0/A3/A7-A10 cells, run through the new
`ArmSpec`-driven kernel with mocked agents, produce BYTE-IDENTICAL rows to
`ak-1.golden.json` — captured from the real pre-`ArmSpec` pipeline before
this claim existed (not an assertion taken on faith).

Negative space: a kernel that drops the "only non-default ports appear in
the row" discipline — leaking `boundary=`/`audit=` columns onto every row,
even A0/A3's, which never asked for them — must diverge from the golden
fixture and be caught.

## AK-2 — A0 and A6 share the self_report done-signal port

A0 (`workspace="bare"`) and A6 (`workspace="recurve_init"`) are the SAME
`done_signal="self_report"` — they differ only in `workspace`. A6's
workspace is real (`recurve init` runs for real; a real ledger is present),
but `self_report` never reads it: the gate function is called ZERO times,
and even a genuinely red verdict has zero effect on the recorded
`declared_done`. Proven both in isolation (the port function directly) and
end to end (through the real orchestrator for the A6 arm).

Negative space: a `self_report` that gives A6 its own bespoke "peek at the
gate if this looks like a recurve workspace" logic — a plausible bug where
someone "helpfully" makes the port smarter for a recurve-initialized
workspace — must be caught; A0 and A6 share one function object, not two
that merely behave alike.

## AK-3 — BoundaryPort["open"] is real, and hard to reach by accident

A config-driven bypass of `within_boundary()` exists in `recurvelib`
(`recurvelib.loop.boundary`, `recurvelib.adapters.boundary`, and a new,
defaulted `boundary=` argument on `GitWorld`) — off by default, and reachable
ONLY through the literal `[gate] boundary = "open"` key. A sweep of
realistic `recurve.toml` blocks (case/whitespace/suffix typos, a TOML
boolean instead of a string, the wrong key entirely, another arm's whole
`[gate]` config, no `[gate]` section at all) shows none of them resolve to
`open` by coincidence — every one is either the real, strict default
(`enforced`) or a hard `ConfigError`. When
`open` genuinely is used, it is LOUD: a fixed warning to stderr on every
single boundary check (`GitWorld.apply`), plus an explicit `boundary` field
in the row's own provenance when run through the real orchestrator — never
silently. A5 = A3 + `boundary="open"`, the one arm that uses it.

Negative space: a `[gate] boundary` resolver that fuzzy-matches anything
LOOKING like "open" (case-insensitive, trimmed, prefix-matched) instead of
requiring the exact literal — a plausible "helpful" typo-tolerance bug — must
be caught; the sweep proves only the exact string ever resolves to the
dangerous capability.
