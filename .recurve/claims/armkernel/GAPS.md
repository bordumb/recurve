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
`.../materialize.py`, `.../done_signal.py`, `.../audit.py`, and (for K3)
`recurvelib.loop.boundary`/`recurvelib.adapters.boundary`. `reads: none`.
Probes construct real `ArmSpec`s and drive the real kernel
(`make_orchestrator`/`materialize`) with mock agents — no live agent, no
spend, mirroring the `eval` suite's own convention.

## AK-1 — ArmSpec replaces the flat dict; A0/A3/A7-A10 unchanged (K1)

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
