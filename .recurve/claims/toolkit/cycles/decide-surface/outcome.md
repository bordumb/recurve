# Outcome: decide-surface

Closed PL-1. Sculpt: `recurvelib/decide_cli.py` exposes `verdict_for(open,
regressed, broken, uncovered, divergent)` — a thin faithful mirror of
`controller.decide` that wraps the vector in a one-cycle history and returns the
verdict string, adding no policy of its own. `cmd_decide` in `cli.py` reads the
vector from `--open/--regressed/--broken/--uncovered/--divergent` and prints the
verdict; the `decide` subparser is registered and listed in the module docstring.

Gate: `probe --gap PL-1` GREEN (verdict_for mirrors controller.decide across all
four vectors); `matrix --gate` green fleet-wide — holding 117, zero
regressions/broken/stale, 118/118 traps still RED (the always-STOP-SUCCESS
counterexample stays rejected); `coverage --gate` green, plumbing matched 1/1.
Prose in `GAPS.md` rewritten to describe the shipped surface. No new gaps
discovered.
