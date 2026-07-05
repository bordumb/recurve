# ablation — ports, adapters, and isolation for adversary/governor, probed

> `docs/plans/ablation-infra.md`: the *how* to `oracle-strength-and-decorrelation.md`'s
> R2 (cross-model adversary) and R5 (the governor). Ports (`Adversary`/
> `Governor`) live beside `World`/`Actor` in `recurvelib.loop`; concrete
> adapters live in a new `recurvelib.adapters` package so adding switch N+1 is
> a new file plus one registry line, never a change to the loop/controller.

## Conventions

`missing-surface` claims about `recurvelib.loop.reviewers` and
`recurvelib.adapters`, `reads: none`. Probes build real temp git repos for
snapshot/isolation claims (mirroring the `adapters` suite's own convention for
`recurvelib.loop.adapters`) and construct real dataclasses/registries
directly for the pure-Python pieces.

## AB-1 — the two ports exist; nothing existing changes

`Adversary`/`Governor` protocols (`recurvelib.loop.reviewers`) are added;
`World`, `Actor`, `capture()`, `within_boundary()`, `guarded_propose()`
(`recurvelib.loop.runtime`) are untouched. Neither verdict type
(`AdversaryVerdict`/`GovernorVerdict`) can certify a claim GREEN directly —
both are structurally checked (`has_bypass_field`) to carry no
certification-shaped field; proposing is the only power either port has, and
`capture()` still independently judges any proposed trap.

Negative space: a capture-rule regression (any of the four canonical
`capture(bool, bool)` truth-table cells disagreeing with the spec) must turn
the probe RED. A verdict type carrying a bypass-shaped field (`certified`,
`closed`, `green`, ...) must be flagged by `has_bypass_field`, not silently
accepted.
