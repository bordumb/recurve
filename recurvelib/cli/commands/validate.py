from __future__ import annotations

from ..base import *  # shared recurvelib imports
from ..base import (
    _fail,
    _config,
    _load,
    _filter,
    _parse_point,
    _parse_goal,
    _draft_backlog,
)

def cmd_validate(args):
    cfg = _config(args)
    ledger = _load(cfg)  # parsing already enforced the hard invariants
    problems: list[str] = []
    waived: list = []
    greps: list = []
    for g in ledger.gaps:
        if g.status is Status.PERMANENT:
            continue
        if g.probe is None:
            problems.append(f"{g.id}: no probe (a gap without a probe is an opinion)")
        elif not g.probe.exists():
            problems.append(f"{g.id}: probe file missing on disk: {g.probe}")
        elif cfg.traps == "required":
            # The trap discipline: a probe never seen RED is not yet evidence.
            if g.trap_waiver:
                waived.append(g)
            elif not g.traps:
                problems.append(
                    f"{g.id}: probe has no trap (probes/{g.probe.stem}.trap/<fixture>/) "
                    f"and no trap_waiver — a probe that has never been seen RED is not "
                    f"yet evidence")
        if "UNBASELINED" in g.observed:
            problems.append(f"{g.id}: observed contains UNBASELINED — drafts live in "
                            f"gaps.draft.yaml until the baseline ceremony promotes them")
        if cfg.traps == "required" and g.reads in ("none",) and g.probe is not None:
            greps.append(g)
    if problems:
        print("\033[31m✗ validation failed:\033[0m")
        for p in problems:
            print(f"  - {p}")
        raise SystemExit(1)
    n = sum(1 for g in ledger.gaps if g.needs_probe)
    print(f"\033[32m✓ ledger valid:\033[0m {len(ledger.gaps)} gaps parsed, {n} probes declared and present")
    if waived:
        print(f"\033[33m  trap waivers — visible debt, {len(waived)} probe(s) never proven able to fail:\033[0m")
        for g in waived:
            print(f"  - {g.id}: {g.trap_waiver}")
    if greps:
        print(f"\033[33m  grep-style probes (reads: none) — permitted only when the claim is about source:\033[0m")
        for g in greps:
            print(f"  - {g.id}")
    drafts = [s for s in cfg.suites.values() if (s.dir / "gaps.draft.yaml").exists()]
    if drafts:
        print("\033[33m  drafts pending authoring (not in the strict ledger):\033[0m")
        for s in drafts:
            print(f"  - {s.name}/gaps.draft.yaml")
