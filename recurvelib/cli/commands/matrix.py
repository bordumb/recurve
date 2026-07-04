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

def cmd_matrix(args):
    from recurvelib.io import render
    cfg = _config(args)
    # Refresh each sculpt's artifacts before probing. A sculpt's rebuild turns
    # its source into what the target's probes and the sculpt's own gate consume,
    # so it runs before the target matrix — a probe must never read a stale
    # artifact. A failing rebuild fails the gate. This runs only in gate mode and
    # is a no-op when no sculpts are configured, so single-tree behavior is
    # unchanged.
    rebuild_ok = True
    failed_rebuilds = set()
    if args.gate and cfg.sculpts:
        import subprocess
        for sname, sc in cfg.sculpts.items():
            if not sc.rebuild:
                continue
            cwd = sc.tree if sc.tree.is_dir() else cfg.root
            try:
                rb = subprocess.run(sc.rebuild, shell=True, cwd=str(cwd),
                                    capture_output=True, text=True, timeout=args.timeout)
                rrc = rb.returncode
            except subprocess.TimeoutExpired:
                rrc = 124
            ok = rrc == 0
            print(f"sculpt {sname}: rebuild {'OK' if ok else 'FAILED'} (exit {rrc})")
            rebuild_ok = rebuild_ok and ok
            if not ok:
                failed_rebuilds.add(sname)
    matrix = run_matrix(list(_load(cfg).gaps), cfg, timeout_s=args.timeout)
    print(render.matrix_table(matrix))
    gate_ok = matrix.gate_ok and rebuild_ok
    if getattr(args, "receipts", False):
        from recurvelib.io.receipts import emit_for_matrix
        n = emit_for_matrix(cfg, matrix)
        print(render.dim(f"receipts: {n} verdict(s) chained under .recurve/receipts/"))
    for fed in getattr(args, "federate", None) or []:
        try:
            fcfg = load(Path(fed).resolve())
        except ConfigError as e:
            _fail(f"\033[31m✗ federated config error:\033[0m {e}")
        try:
            fledger = load_ledger(fcfg)
        except GapParseError as e:
            _fail(f"\033[31m✗ federated ledger parse error:\033[0m {e}")
        fmatrix = run_matrix(list(fledger.gaps), fcfg, timeout_s=args.timeout)
        print(f"\n── federated: {fcfg.name} ({fed}) ──")
        print(render.matrix_table(fmatrix))
        gate_ok = gate_ok and fmatrix.gate_ok
        if getattr(args, "receipts", False):
            from recurvelib.io.receipts import emit_for_matrix
            emit_for_matrix(fcfg, fmatrix)
    # FR-C3: federate each sculpt's OWN gate into the verdict. A sculpt is a
    # secondary tree (frontend, platform) the loop may sculpt; its gate is run
    # in its own tree and AND-ed in — `matrix --gate` is green only when the
    # target probes AND every sculpt's gate pass. With no [sculpts.*] this loop
    # has no iterations, so behavior and output are byte-identical to today.
    if args.gate:
        import subprocess
        for sname, sc in cfg.sculpts.items():
            # A failed rebuild has already failed the gate; skip its gate.
            if sname in failed_rebuilds:
                continue
            if not sc.gate:
                continue
            cwd = sc.tree if sc.tree.is_dir() else cfg.root
            try:
                r = subprocess.run(sc.gate, shell=True, cwd=str(cwd),
                                   capture_output=True, text=True, timeout=args.timeout)
                rc = r.returncode
            except subprocess.TimeoutExpired:
                rc = 124
            ok = rc == 0
            mark = "OK" if ok else "FAILED"
            print(f"sculpt {sname}: gate {mark} (exit {rc})")
            gate_ok = gate_ok and ok
    if args.gate and not gate_ok:
        raise SystemExit(1)
