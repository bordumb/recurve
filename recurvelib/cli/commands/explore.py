"""`recurve explore` — the exploration matrix (the second gradient beside `matrix`).

`matrix` scores the closure gradient: is each claim proven (GREEN)? `explore`
scores the survival gradient: for every **conjecture** (an open claim carrying a
`probes/<name>.falsifiers/` battery), is the lead still alive? It reports:

    PROMOTED   — the probe is kernel-clean GREEN: proven. Hand it to the closure
                 loop; it stops being a conjecture (the jackpot).
    SURVIVING  — a live lead: every calibrated falsifier missed. Ranked by the
                 strength of what it survived (the reward gradient).
    FALSIFIED  — a dead lead: a calibrated falsifier found a counterexample. Real
                 information — prune it.
    BROKEN     — the battery has no demonstrated teeth (no falsifier KILLed its
                 decoy). An uncalibrated lead is not a lead — fix it before trusting
                 any survival.

Believe the battery, not the proposer: a survival is only ever a graded,
honestly-labeled lead, never a proof.
"""

from __future__ import annotations

from ..base import *  # shared recurvelib imports  # noqa: F401,F403
from ..base import _config, _fail, _load


def cmd_explore(args):
    from recurvelib.core.conjecture import (
        ConjectureVerdict,
        frontier_rank,
        run_falsifiers,
    )
    from recurvelib.core.probe import Outcome, ShellProbeRunner

    cfg = _config(args)
    conjectures = [g for g in _load(cfg).gaps if g.is_conjecture]
    if not conjectures:
        print("no conjectures armed — no claim carries a probes/<name>.falsifiers/ battery.")
        print("explore mode scores the survival gradient; arm a falsifier battery to add a lead.")
        return

    probe_runner = ShellProbeRunner()
    surviving: list = []
    falsified: list = []
    broken: list = []
    promoted: list = []
    for g in conjectures:
        # Promotion first: a proven conjecture leaves the survival axis entirely.
        pr = probe_runner.run(g, timeout_s=args.timeout)
        if pr.outcome is Outcome.GREEN:
            promoted.append((g, None))
            continue
        res = run_falsifiers(g.falsifier_dir, g.suite_dir, timeout_s=args.timeout)
        {
            ConjectureVerdict.SURVIVING: surviving,
            ConjectureVerdict.FALSIFIED: falsified,
            ConjectureVerdict.BROKEN: broken,
        }[res.verdict].append((g, res))

    # The reward gradient: strongest, most-survived leads at the top of the frontier.
    surviving.sort(key=lambda gr: frontier_rank(gr[1]), reverse=True)

    def _line(icon: str, gid: str, detail: str) -> None:
        print(f"  {icon} {gid:<30} {detail}")

    if promoted:
        print("\nPROMOTED — proven (probe kernel-clean GREEN); hand to the closure loop:")
        for g, _ in promoted:
            _line("★", g.id, "probe GREEN — no longer a conjecture")
    if surviving:
        print("\nSURVIVING — live leads, ranked by strength (the exploration frontier):")
        for g, res in surviving:
            _line("○", g.id, res.profile.render())
    if falsified:
        print("\nFALSIFIED — dead leads (a counterexample was found); prune:")
        for g, res in falsified:
            _line("✗", g.id, res.detail)
    if broken:
        print("\nBROKEN — batteries with no demonstrated teeth; fix before trusting a survival:")
        for g, res in broken:
            _line("▲", g.id, res.detail)

    print(
        f"\nfrontier: surviving {len(surviving)} · falsified {len(falsified)} · "
        f"broken {len(broken)} · promoted {len(promoted)}"
    )

    # --strict: an uncalibrated battery is a real defect (a lead nobody can trust),
    # exactly as a probe without a trap is — exit nonzero so CI can gate on it.
    if getattr(args, "strict", False) and broken:
        _fail(f"{len(broken)} conjecture(s) have BROKEN (uncalibrated) batteries", code=1)
