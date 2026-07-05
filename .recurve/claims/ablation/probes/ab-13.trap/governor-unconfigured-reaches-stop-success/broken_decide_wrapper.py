#!/usr/bin/env python3
"""A broken `recurve decide` wrapper: when the governor adapter cannot be
invoked at all (e.g. RECURVE_GOVERNOR_CMD unset), it treats that failure as
"cleared" instead of "pending" — silently reaching STOP-SUCCESS with a
governor that was never actually consulted. The exact bug AB-13 exists to
catch: [gate] governor= configured must not be trivially bypassable by
simply not setting up its command.
"""
import os
import sys
from pathlib import Path

ROOT = os.environ["AB13_ENGINE_ROOT"]
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from recurvelib.core.config import find_config, load as load_config
from recurvelib.loop.controller import Progress, decide


def main():
    cfg = load_config(find_config(Path.cwd()))
    progress = Progress(0, 0, 0, 0, False)
    governor_tier = getattr(cfg, "gate_governor", "off")
    if governor_tier == "off":
        print(decide([progress]).value)
        return
    try:
        from recurvelib.adapters.governor import GOVERNOR_ADAPTERS
        from recurvelib.adapters.registry import resolve_governor
        from recurvelib.adapters.snapshot import build_cycle_snapshot
        from recurvelib.core.model import load_ledger, Status
        ledger = load_ledger(cfg)
        claim_ids = sorted(g.id for g in ledger.gaps if g.status is Status.CLOSED)
        cycle = build_cycle_snapshot(cfg.tree or cfg.root, "HEAD", claim_ids, include_existing_traps=True)
        cls = resolve_governor(governor_tier, GOVERNOR_ADAPTERS)
        from recurvelib.adapters._shared.provenance import unverified
        governor = cls(unverified())
        verdict = governor.audit(cycle)
        status = "vetoed" if verdict.vetoes else "cleared"
    except Exception:
        # BUG: any failure to consult the governor (e.g. no command
        # configured) is treated as "cleared" rather than "pending".
        status = "cleared"
    print(decide([progress], governor_status=status).value)


if __name__ == "__main__":
    main()
