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

def cmd_receipts(args):
    from recurvelib.io import render
    from recurvelib.io.receipts import ReceiptChain, verify_signatures
    C = render.C
    cfg = _config(args)
    suites = [args.suite] if args.suite else list(cfg.suites)
    problems = []
    for s in suites:
        chain = ReceiptChain(cfg, s)
        rs = chain.receipts()
        if args.action == "list":
            for r in rs:
                sig = " ✎signed" if r.get("signature") else ""
                print(f"{r['observed_at']}  {r['gap']:<12} {r['verdict']:<8} "
                      f"tree={r['tree']['kind']}:{r['tree']['value'][:12]} "
                      f"{r['self_sha256'][:12]}{sig}")
        else:
            chain_probs = chain.verify()
            sig_probs = verify_signatures(cfg, rs)
            probs = chain_probs + sig_probs
            problems += probs
            status = "chain holds" if not chain_probs else f"{len(chain_probs)} chain problem(s)"
            if cfg.receipts_verifier:
                status += (", signatures verify" if not sig_probs
                           else f", {len(sig_probs)} signature problem(s)")
            print(f"  {'●' if not probs else '▲'} {s}: {len(rs)} receipt(s), {status}")
            for p in probs:
                print(f"    {C['red']}{p}{C['reset']}")
    if args.action == "verify":
        if problems:
            print(f"{C['red']}✗ evidence failed verification — the chain was edited or a "
                  f"signature does not hold.{C['reset']}")
            raise SystemExit(1)
        print(f"{C['green']}✓ every chain holds"
              f"{' and every signature verifies' if cfg.receipts_verifier else ''} — "
              f"the evidence is what it was when written.{C['reset']}")
