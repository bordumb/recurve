"""recurve — claims-driven recursive improvement control.

Point it at a project (recurve.toml) and it turns documented claims into
probed, gated, burn-downable gaps.

    recurve ledger                 every gap across every suite (the red backlog)
    recurve show <gap-id>          one gap in full
    recurve validate               schema + invariants: every open gap has a probe
    recurve next                   value-first triage; flags review-gated gaps
    recurve run [--agent CMD]      run the burndown loop; the agent defaults to a
                                   bypass-permissions Claude (--dry-run to preview)
    recurve decide [--open N …]    ask the stopping controller for its stop verdict
                                   from a measured progress vector (never blind)
    recurve frontier [--point ID:W …]    surface the ranked uncovered ids — what
                                   no claim covers (the completeness frontier)
    recurve sense [--point …] [--goal …]    assemble the FULL measured progress
                                   vector — gate counts + uncovered + divergent —
                                   exactly as the loop senses it for the controller
    recurve probe [--suite S|--gap ID]   run gap probes, report RED/GREEN/BROKEN
    recurve matrix [--gate]        the conformance matrix; --gate exits nonzero on
                                   any regression, broken probe, or stale suite
    recurve status [--gate]        one-glance health: open/closed counts, the true
                                   gate verdict, broken/stale counts, pending drafts
    recurve report [--narrate]     the run report: progress, durations, ETA,
                                   diff honesty — deterministic; --narrate adds prose
    recurve freshness [--gate]     are suite artifacts current with the tree?
    recurve coverage [--gate]      does the ledger mirror every GAPS.md gap?
    recurve review <gap-id>        adversarial-review brief for review-gated gaps
    recurve import <suite>         seed a draft ledger from a suite's GAPS.md
    recurve cycle new <name> --gaps ID,ID    scaffold a sculpting-cycle plan
    recurve demo                   zero-setup sign-of-life: watch one claim go
                                   RED → GREEN behind the gate (temp dir, no config)

Exit codes: 0 ok · 1 gate/validation failure · 2 usage/parse error.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from . import SCHEMA_VERSION
from .config import Config, ConfigError, find_config, load
from .conformance import run_matrix
from .coverage import coverage
from .cycle import write_cycle_plan
from .freshness import gap_freshness
from .importer import parse_gaps_md, to_yaml_skeleton
from .model import GapParseError, Ledger, Status, load_ledger
from .triage import review_gated, triage

_STUBS: dict[str, str] = {}


def _fail(msg: str, code: int = 2):
    print(msg, file=sys.stderr)
    raise SystemExit(code)


def _config(args) -> Config:
    path = Path(args.config) if getattr(args, "config", None) else find_config(Path.cwd())
    if path is None:
        _fail("no recurve.toml found from the current directory upward — pass --config")
    try:
        cfg = load(Path(path))
    except ConfigError as e:
        _fail(f"\033[31m✗ config error:\033[0m {e}")
    if cfg.schema_pin and cfg.schema_pin != SCHEMA_VERSION.split(".")[0]:
        _fail(f"\033[31m✗ schema pin mismatch:\033[0m project pins schema {cfg.schema_pin!r}, "
              f"engine ships {SCHEMA_VERSION} — migrate the ledger or the engine, never reinterpret")
    return cfg


def _load(cfg: Config) -> Ledger:
    try:
        return load_ledger(cfg)
    except GapParseError as e:
        print(f"\033[31m✗ ledger parse error:\033[0m {e}", file=sys.stderr)
        raise SystemExit(2)


def _filter(ledger: Ledger, suite: str | None, gap: str | None):
    gaps = list(ledger.gaps)
    if suite:
        gaps = [g for g in gaps if g.suite == suite]
    if gap:
        sel = ledger.by_id(gap)
        if not sel:
            print(f"unknown gap id: {gap}", file=sys.stderr)
            raise SystemExit(2)
        gaps = [sel]
    return gaps


def cmd_ledger(args):
    from . import render
    cfg = _config(args)
    print(render.ledger_table(_load(cfg), cfg.label))


def cmd_show(args):
    from . import render
    cfg = _config(args)
    g = _load(cfg).by_id(args.gap_id)
    if not g:
        print(f"unknown gap id: {args.gap_id}", file=sys.stderr)
        raise SystemExit(2)
    print(render.gap_detail(g, cfg.label))


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


def cmd_probe(args):
    from . import render
    cfg = _config(args)
    gaps = _filter(_load(cfg), args.suite, args.gap)
    matrix = run_matrix(gaps, cfg, timeout_s=args.timeout)
    print(render.matrix_table(matrix))


def cmd_decide(args):
    from .decide_cli import verdict_for
    print(verdict_for(args.open, args.regressed, args.broken, args.uncovered, args.divergent))


def _parse_point(spec: str):
    """Parse one `ID[:WEIGHT]` surface point from the command line."""
    from .frontier import SurfacePoint
    id_part, _, w_part = spec.partition(":")
    id_part = id_part.strip()
    if not id_part:
        _fail(f"empty surface point id in {spec!r} — use ID or ID:WEIGHT")
    try:
        weight = int(w_part) if w_part else 0
    except ValueError:
        _fail(f"non-integer weight in {spec!r} — use ID or ID:WEIGHT")
    return SurfacePoint(id_part, weight)


def cmd_frontier(args):
    """Print the ranked uncovered ids for a surface given on flags — what no
    claim covers, highest-risk first. A thin honest report over
    `frontier_cli.frontier_ids`, which mirrors `compute_frontier`."""
    from .frontier_cli import frontier_ids
    surface = [_parse_point(s) for s in (args.point or [])]
    covered = set(args.covered or [])
    deferred = set(args.deferred or [])
    ids = frontier_ids(surface, covered, deferred)
    if not ids:
        print("frontier empty — every surface point is covered or deferred.")
        return
    for i in ids:
        print(i)


def _parse_goal(spec: str):
    """Parse one `ID[:WEIGHT]` accepted goal-counterexample from the command line.

    A goal named on `--goal` is one that was observed *accepted* this cycle — a
    divergence signal — so it is always constructed with ``accepted=True``."""
    from .fidelity import GoalCounterexample
    id_part, _, w_part = spec.partition(":")
    id_part = id_part.strip()
    if not id_part:
        _fail(f"empty goal-counterexample id in {spec!r} — use ID or ID:WEIGHT")
    try:
        weight = int(w_part) if w_part else 0
    except ValueError:
        _fail(f"non-integer weight in {spec!r} — use ID or ID:WEIGHT")
    return GoalCounterexample(id_part, accepted=True, weight=weight)


def cmd_sense(args):
    """Print the full measured progress vector for a surface given on flags —
    gate counts plus the uncovered (completeness) and divergent (fidelity)
    signals, exactly as the loop senses it for the controller. A thin honest
    report over `sense_cli.sense_vector`, which mirrors `runtime.sense`."""
    from .sense_cli import sense_vector
    gate = {"open": args.open, "regressed": args.regressed, "broken": args.broken}
    surface = [_parse_point(s) for s in (args.point or [])]
    covered = set(args.covered or [])
    deferred = set(args.deferred or [])
    goals = [_parse_goal(s) for s in (args.goal or [])]
    v = sense_vector(gate, surface, covered, goals, deferred)
    print(f"open       {v['open']}")
    print(f"regressed  {v['regressed']}")
    print(f"broken     {v['broken']}")
    print(f"uncovered  {v['uncovered']}")
    print(f"divergent  {v['divergent']}")


def cmd_matrix(args):
    from . import render
    cfg = _config(args)
    matrix = run_matrix(list(_load(cfg).gaps), cfg, timeout_s=args.timeout)
    print(render.matrix_table(matrix))
    gate_ok = matrix.gate_ok
    if getattr(args, "receipts", False):
        from .receipts import emit_for_matrix
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
            from .receipts import emit_for_matrix
            emit_for_matrix(fcfg, fmatrix)
    # FR-C3: federate each sculpt's OWN gate into the verdict. A sculpt is a
    # secondary tree (frontend, platform) the loop may sculpt; its gate is run
    # in its own tree and AND-ed in — `matrix --gate` is green only when the
    # target probes AND every sculpt's gate pass. With no [sculpts.*] this loop
    # has no iterations, so behavior and output are byte-identical to today.
    if args.gate:
        import subprocess
        for sname, sc in cfg.sculpts.items():
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


def cmd_coverage(args):
    from . import render
    C = render.C
    cfg = _config(args)
    reports = coverage(cfg, _load(cfg))
    total_orphans = 0
    print(f"{C['bold']}    {cfg.label:<30}covered  orphan  closed  ledger?{C['reset']}")
    for r in reports:
        total_orphans += len(r.orphans)
        mark = C["green"] if r.complete and r.has_ledger else C["amber"]
        print(f"  {mark}{'●' if r.complete else '≈'}{C['reset']} {r.suite[:29]:<29} "
              f"{len(r.covered):>7}  {len(r.orphans):>6}  {len(r.closed):>6}  "
              f"{'yes' if r.has_ledger else C['amber'] + 'NONE' + C['reset']}")
    orphan_suites = [r for r in reports if r.orphans]
    if orphan_suites:
        print(f"\n{C['amber']}prose gaps with no ledger entry (import + author a probe, then add `covers:`):{C['reset']}")
        for r in orphan_suites:
            for anchor, title in r.orphans:
                print(f"  {C['dim']}· {r.suite} §{anchor}  {title[:60]}{C['reset']}")
    print(f"\n{total_orphans} orphan prose gap(s) across {len(reports)} {cfg.label}s")
    if args.gate and total_orphans:
        raise SystemExit(1)


def cmd_freshness(args):
    from . import render
    cfg = _config(args)
    ledger = _load(cfg)
    cache, seen, reports = {}, set(), []
    for g in ledger.gaps:
        if not g.needs_probe:
            continue
        key = (g.suite, g.reads)
        if key in seen:
            continue
        seen.add(key)
        reports.append(gap_freshness(cfg, g.suite, g.reads, cache))
    print(render.freshness_table(reports, cfg.label))
    if args.gate and any(r.blocks_gate for r in reports):
        raise SystemExit(1)


def _draft_backlog(cfg) -> tuple[list[dict], int]:
    """What the strict ledger cannot see: per-suite pending draft counts and
    unresolved adjudication forks. Orchestrators consult this to decide
    whether an empty backlog means 'done' or 'the next wave is unarmed'."""
    import yaml
    drafts = []
    for s in cfg.suites.values():
        p = s.dir / "gaps.draft.yaml"
        if not p.exists():
            continue
        try:
            doc = yaml.safe_load(p.read_text()) or []
        except yaml.YAMLError:
            doc = []
        if isinstance(doc, list) and doc:
            drafts.append({"suite": s.name, "pending": len(doc)})
    adj = cfg.assets_dir / "ADJUDICATE.md"
    forks = adj.read_text().count("DECIDED: (pending") if adj.exists() else 0
    return drafts, forks


def cmd_next(args):
    import json as _json
    from . import render
    from .parked import ParkedStore
    C = render.C
    cfg = _config(args)
    prog = args.prog
    ledger = _load(cfg)
    auto, gated = triage(ledger, cfg)
    parked = ParkedStore(cfg.root).list()
    parked_ids = {p.gap for p in parked}
    auto = [g for g in auto if g.id not in parked_ids]
    gated = [g for g in gated if g.id not in parked_ids]
    open_gaps = auto + gated
    drafts, forks_pending = _draft_backlog(cfg)

    if getattr(args, "lanes", None):
        from .triage import lanes as deal_lanes
        dealt = deal_lanes(ledger, cfg, args.lanes, exclude=parked_ids)
        if getattr(args, "json", False):
            print(_json.dumps({"lanes": [
                {"gap": g.id, "suite": g.suite, "title": g.title,
                 "class": g.gap_class.value, "severity": g.severity.value,
                 "dir": str(cfg.suites[g.suite].dir)}
                for g in dealt]}))
        else:
            for g in dealt:
                print(f"  lane {g.suite:<24} ▸ {g.id}  {g.title}")
            if not dealt:
                print("no lanes to deal — no workable open gaps.")
        return

    if getattr(args, "json", False):
        rec = auto[0] if auto else None
        print(_json.dumps({
            "recommended": ({"gap": rec.id, "suite": rec.suite, "title": rec.title,
                             "class": rec.gap_class.value, "severity": rec.severity.value}
                            if rec else None),
            "then": [g.id for g in auto[1:]],
            "review_gated": [g.id for g in gated],
            "parked": [{"gap": p.gap, "reason": p.reason} for p in parked],
            "drafts": drafts,
            "adjudications_pending": forks_pending,
        }))
        return

    if auto:
        top = auto[0]
        slug = "".join(c if c.isalnum() else "-" for c in top.title.lower())[:24].strip("-")
        print(f"{C['bold']}recommended next (highest value first; green gate is sufficient):{C['reset']}")
        print(f"  {C['green']}▸ {top.id}{C['reset']}  {top.title}")
        print(f"    {render.dim(top.suite + ' · ' + top.gap_class.value + ' · ' + top.severity.value)}")
        if top.unlocks:
            print(f"    {render.dim('unlocks: ' + top.unlocks.splitlines()[0])}")
        print(f"    scaffold: ./{prog} cycle new {slug or top.id.lower()} --gaps {top.id}")
        if len(auto) > 1:
            print(render.dim("  then: " + ", ".join(f"{g.id}({g.severity.value})" for g in auto[1:])))
    else:
        print(f"{C['amber']}no green-gate-sufficient open gaps remain.{C['reset']}")

    if gated:
        print(f"\n{C['amber']}review-gated — security-tradeoff (a green gate is NOT enough; "
              f"loosening a check can pass every probe and still open a hole):{C['reset']}")
        for g in gated:
            print(f"  {C['dim']}· {g.id}  {g.title}{C['reset']}")
        print(render.dim(f"  workable via the adversarial protocol: ./{prog} review {gated[0].id}  (then RUN.md §review-gated)"))

    if parked:
        print(f"\n{C['amber']}parked — run state awaiting human triage (the loop continues past these):{C['reset']}")
        for p in parked:
            print(f"  {C['dim']}· {p.gap}  {p.reason[:70]}{C['reset']}")

    if not open_gaps:
        print(f"{C['green']}✓ no open gaps — the backlog is clear for this ledger.{C['reset']}")
    if drafts:
        total = sum(d["pending"] for d in drafts)
        where = ", ".join(f"{d['suite']} ({d['pending']})" for d in drafts)
        print(f"\n{C['amber']}{total} draft claim(s) await the next wave:{C['reset']} {where}")
        if forks_pending:
            print(f"  {C['amber']}⚠ {forks_pending} fork(s) pending in ADJUDICATE.md — "
                  f"one human sentence each, before any baseline.{C['reset']}")
        print(render.dim(f"  arm them: author probes + traps, then ./{prog} baseline <suite> "
                         f"(the burndown loop arms waves itself)"))


def cmd_review(args):
    """Print the adversarial-review brief for a review-gated gap — the brief you
    hand to an INDEPENDENT reviewer (an agent/human prompted to REFUTE the
    change's safety), not to the implementer."""
    from . import render
    C = render.C
    cfg = _config(args)
    prog = args.prog
    g = _load(cfg).by_id(args.gap_id)
    if not g:
        print(f"unknown gap id: {args.gap_id}", file=sys.stderr)
        raise SystemExit(2)
    if not review_gated(g):
        print(f"{C['green']}{g.id} is not review-gated (class={g.gap_class.value}).{C['reset']} "
              f"It fails loud — a green `{prog} matrix --gate` is sufficient to promote it.")
        return
    print(f"{C['bold']}ADVERSARIAL REVIEW BRIEF — {g.id}{C['reset']}  ({g.gap_class.value})")
    print(f"  {g.title}\n")
    print(f"  change under review: {g.smallest_fix}")
    print(f"  was observed today:  {g.observed or '—'}\n")
    print(f"{C['amber']}  The reviewer's job is to BREAK it, not confirm it.{C['reset']} A green gate")
    print( "  proves the INTENDED case works; it does not prove the change is safe.")
    print( "  Find an input the loosened check now WRONGLY accepts. Specifically:")
    print( "    1. Enumerate what the new check accepts that the old one rejected.")
    print( "       For each, ask: is that acceptance always legitimate?")
    print( "    2. The suite's own adversarial probes are a FLOOR, not a ceiling —")
    print( "       invent NEW attacks (replay, reorder, forge, substitute identity).")
    print( "    3. If the fix relies on a corroboration source (witness / log / receipt),")
    print( "       attack THAT source's trust assumption, not just the happy path.")
    print( "    4. Re-read the upstream comment that made this fail-closed — it named")
    print( "       the threat. Confirm the loosening doesn't re-open exactly that.\n")
    print(f"{C['amber']}  Promote open→closed ONLY IF all hold:{C['reset']}")
    print( "    · the reviewer could not break it, and said so explicitly;")
    print( "    · the reviewer is INDEPENDENT of the implementer (different agent/pass);")
    print(f"    · `{prog} matrix --gate` is green fleet-wide;")
    print( "    · a new RED probe was added for any attack the reviewer tried (so the")
    print( "      next cycle guards it). Otherwise: leave open, record the finding.")


def cmd_import(args):
    cfg = _config(args)
    sc = cfg.suites.get(args.suite)
    if sc is None:
        _fail(f"unknown {cfg.label} {args.suite!r}; configured: {', '.join(cfg.suites)}")
    gaps_md = sc.dir / "GAPS.md"
    if not gaps_md.exists():
        _fail(f"no GAPS.md in {sc.dir}")
    prefix = args.prefix or "".join(w[0] for w in args.suite.split("-")).upper()
    imported = parse_gaps_md(gaps_md.read_text())
    skeleton = to_yaml_skeleton(args.suite, prefix, imported, prog=args.prog)
    # Drafts live in gaps.draft.yaml — the strict ledger (gaps.yaml) only ever
    # holds AUTHORED gaps with real class/severity/probe. Entries graduate via
    # the baseline ceremony.
    out = sc.dir / "gaps.draft.yaml"
    if out.exists() and not args.force:
        _fail(f"{out} exists — pass --force to overwrite (it merges nothing)")
    out.write_text(skeleton)
    print(f"wrote {out} ({len(imported)} gaps, prefix {prefix}) — "
          f"author probes, then graduate each entry into {sc.name}/gaps.yaml")


def cmd_cycle_new(args):
    from . import render
    cfg = _config(args)
    ids = [s.strip() for s in args.gaps.split(",") if s.strip()]
    try:
        gaps = _load(cfg).select(ids)
    except GapParseError as e:
        _fail(str(e))
    matrix = run_matrix(gaps, cfg, timeout_s=args.timeout)
    baseline = re.sub(r"\033\[[0-9;]*m", "", render.matrix_table(matrix))
    plan = write_cycle_plan(cfg.cycles_dir, args.name, gaps, baseline,
                            prog=args.prog, label=cfg.label)
    print(f"wrote {plan}\nseed your cycle's work plan from it (spike-first when the fix needs design)")


def cmd_baseline(args):
    import time
    from . import render
    from .baseline import run_baseline
    from .lock import LockHeld
    C = render.C
    cfg = _config(args)
    adj = cfg.assets_dir / "ADJUDICATE.md"
    if adj.exists() and "DECIDED: (pending" in adj.read_text():
        pending = adj.read_text().count("DECIDED: (pending")
        print(f"\033[33m⚠ {pending} unresolved fork(s) in ADJUDICATE.md — claims touching "
              f"them will encode a guess, not a decision. One human sentence each.\033[0m")
    today = time.strftime("%Y-%m-%d")
    try:
        outcomes, ok = run_baseline(cfg, args.suite, today, timeout_s=args.timeout)
    except (GapParseError, ConfigError) as e:
        _fail(f"\033[31m✗ baseline failed:\033[0m {e}")
    except LockHeld as e:
        _fail(f"\033[31m✗ {e}\033[0m", 1)
    color = {"promoted-open": C["red"], "promoted-closed": C["green"],
             "kept-draft": C["amber"], "skipped": C["dim"]}
    for o in outcomes:
        print(f"  {color[o.action]}{o.action:<15}{C['reset']} {o.gap_id:<12} {render.dim(o.detail)}")
    if not ok:
        print(f"{C['red']}✗ baseline incomplete — fix the harness/traps above; "
              f"do not start a cycle on a broken baseline.{C['reset']}")
        raise SystemExit(1)
    print(f"{C['green']}✓ baseline complete{C['reset']} — promoted entries are now "
          f"measurements; the ledger stays a record of observations.")


def cmd_park(args):
    import time
    from . import render
    from .parked import ParkedStore
    C = render.C
    cfg = _config(args)
    store = ParkedStore(cfg.root)
    if not args.gap_id:
        parked = store.list()
        if not parked:
            print("nothing parked.")
            return
        for p in parked:
            print(f"{C['amber']}{p.gap}{C['reset']}  parked {p.parked_at} — {p.reason}")
            for a in p.attempts:
                print(render.dim(f"    attempt {a.get('at', '?')}: {a.get('tried', '')} "
                                 f"→ {a.get('observed', '')}"))
        return
    if args.unpark:
        if store.unpark(args.gap_id):
            print(f"unparked {args.gap_id} — it is triage-eligible again.")
        else:
            _fail(f"{args.gap_id} is not parked")
        return
    if _load(cfg).by_id(args.gap_id) is None:
        _fail(f"unknown gap id: {args.gap_id}")
    now = time.strftime("%Y-%m-%d")
    attempt = None
    if args.attempt:
        attempt = {"at": now, "tried": args.attempt, "observed": args.observed or ""}
    if args.reason:
        store.park(args.gap_id, args.reason, now, attempt)
        print(f"parked {args.gap_id} — the loop continues past it; humans triage parked gaps.")
    elif attempt:
        if not store.add_attempt(args.gap_id, attempt):
            _fail(f"{args.gap_id} is not parked — pass --reason to park it")
        print(f"recorded attempt on parked {args.gap_id} (observations, never conclusions).")
    else:
        _fail("pass --reason to park, --attempt to journal, or --unpark to release")


def cmd_init(args):
    from .init import infer_init_mode, run_init

    # An explicit mode flag always wins over the positional; --target likewise
    # wins over an inferred directory. The positional is a convenience that
    # resolves to one of the three explicit modes, and we ALWAYS say which.
    explicit_mode = args.from_prd or args.from_repo
    from_repo = args.from_repo
    from_prd = args.from_prd
    target = Path(args.target).resolve()

    if args.path is not None:
        pos = Path(args.path)
        mode, reason = infer_init_mode(pos)
        if explicit_mode:
            chose = "from-prd" if args.from_prd else "from-repo"
            print(f"inferred: {mode} ({reason}) — overridden: --{chose} was given explicitly, "
                  f"the flag wins")
        else:
            print(f"inferred: {mode} ({reason}) — use --from-repo/--from-prd/blank to override")
            if mode == "from-prd":
                from_prd = str(pos)
            elif mode == "from-repo":
                from_repo = True
                target = pos.resolve()
            else:  # blank
                target = pos.resolve()

    name = args.name or target.name
    suite = args.suite or ("claims" if from_prd else "core")
    try:
        notes = run_init(target, name=name, suite=suite, tree=args.tree,
                         label=args.label, quality=args.quality, prog=args.prog,
                         from_repo=from_repo)
    except FileExistsError as e:
        _fail(str(e))
    if from_prd:
        from .claimify import run_claimify
        notes += run_claimify(target, Path(from_prd), suite=suite,
                              prog=args.prog, skip_review=args.no_review)
    print(f"initialized {name} at {target}")
    for n in notes:
        print(f"  - {n}")
    print(f"next: edit recurve.toml ([target] tree, [reads.*], rebuild), write claims, "
          f"author probes + traps, then `{args.prog} baseline {suite}`.")


def cmd_install(args):
    """Symlink the recurve entrypoint onto PATH — one idempotent step, no
    package install. The entrypoint resolves recurvelib relative to its own
    real path, so a symlink anywhere runs the engine from this clone."""
    import os
    entry = (Path(__file__).resolve().parent.parent / "recurve")
    if not entry.exists():
        _fail(f"recurve entrypoint not found at {entry} — run install from a recurve checkout")
    bin_dir = Path(args.bin_dir).expanduser().resolve()
    bin_dir.mkdir(parents=True, exist_ok=True)
    link = bin_dir / "recurve"
    # Idempotent: replace an existing symlink (to recurve or anything) but never
    # clobber a real file we did not place.
    if link.is_symlink():
        link.unlink()
    elif link.exists():
        _fail(f"{link} exists and is not a symlink — refusing to overwrite a real file", 1)
    link.symlink_to(entry)
    print(f"linked {link} → {entry}")
    path_dirs = (os.environ.get("PATH", "")).split(os.pathsep)
    if str(bin_dir) not in path_dirs:
        print(f"\033[33m⚠ {bin_dir} is not on $PATH — add it, e.g. "
              f"export PATH=\"{bin_dir}:$PATH\"\033[0m")


def cmd_run(args):
    """Run the burndown loop with sensible defaults — the friendly wrapper over
    the stamped workflow (`recurvelib.run`). Resolves the agent (defaulting to a
    bypass-permissions Claude so an unattended cycle never stalls on a prompt),
    the cap, and the script, then execs it. `--dry-run` prints the resolution
    and exits."""
    import os
    import subprocess

    from .run import build_run, bypasses_permissions, materialize_workflow, resolve_agent

    cfg = _config(args)
    agent, source = resolve_agent(args.agent, os.environ.get("AGENT_CMD"))
    cap = args.cap if args.cap is not None else cfg.burndown_cap
    argv, overrides = build_run(cfg, agent, cap, args.lanes, args.parked,
                                caffeinate=not args.no_caffeinate)
    if argv is None:
        _fail(f"no burndown workflow found (no stamped .recurve/workflows/, no shipped "
              f"template) — run `{args.prog} init` in the target first", 1)
    script = Path(argv[-1])

    warn = "  \033[33m⚠ permissions bypassed\033[0m" if bypasses_permissions(agent) else ""
    lanes = f"   lanes: {args.lanes}" if args.lanes and args.lanes > 1 else ""
    print(f"agent: {agent}   [{source}]{warn}")
    print(f"cap: {cap}   script: {script.name}{lanes}")
    if args.dry_run:
        print(" ".join(argv))
        return

    # Interpolate the shipped template (if un-stamped) into a runnable script.
    runnable = materialize_workflow(cfg, script)
    argv = [str(runnable) if a == str(script) else a for a in argv]
    env = dict(os.environ)
    env.update(overrides)
    raise SystemExit(subprocess.run(argv, env=env).returncode)


def cmd_record(args):
    import json as _json
    from .records import RecordError, validate_run_record
    cfg = _config(args)
    path = cfg.state_dir / "records.jsonl"
    if args.action == "append":
        try:
            record = _json.loads(Path(args.file).read_text() if args.file else sys.stdin.read())
        except (OSError, _json.JSONDecodeError) as e:
            _fail(f"unreadable record: {e}")
        if args.run_id:
            record.setdefault("run_id", args.run_id)
        record.setdefault("project", cfg.name)
        try:
            validate_run_record(record)
        except RecordError as e:
            _fail(f"record rejected (the dataset stays clean or it is worthless): {e}", 1)
        path.parent.mkdir(parents=True, exist_ok=True)
        line = _json.dumps(record, sort_keys=True)
        # Idempotent: both the agent (per RUN.md) and the loop (per burndown)
        # may append the same record — one observation lands once.
        if path.exists() and line in set(path.read_text().splitlines()):
            print(f"cycle {record.get('cycle', '?')} already recorded — skipped "
                  f"(append is idempotent)")
            return
        with path.open("a") as f:
            f.write(line + "\n")
        print(f"recorded cycle {record.get('cycle', '?')} status={record.get('status')}")
    else:  # list
        if not path.exists():
            print("no run records yet.")
            return
        for line in path.read_text().splitlines():
            r = _json.loads(line)
            print(f"{r.get('finished_at', r.get('started_at', '?')):<22} "
                  f"{r.get('run_id', ''):<16} {r.get('cycle', ''):<18} "
                  f"{r.get('status', ''):<13} gap={r.get('gap', '')} "
                  f"attempts={r.get('attempts')} net_new={r.get('net_new_gaps', 0)}")


def cmd_lock(args):
    from .lock import LockHeld, TreeLock, read_lock
    cfg = _config(args)
    tree = cfg.tree or cfg.root
    if args.action == "status":
        holder = read_lock(tree)
        if holder is None:
            print(f"unlocked — no loop holds {cfg.tree_display}")
        else:
            print(f"LOCKED by {holder.describe()}")
            raise SystemExit(1)
    elif args.action == "acquire":
        # For orchestrators that span many CLI invocations: the lock file
        # outlives this process; pair every acquire with a release.
        try:
            TreeLock(tree).acquire()
        except LockHeld as e:
            _fail(f"\033[31m✗ {e}\033[0m", 1)
        print(f"acquired — this run is the single loop on {cfg.tree_display}; "
              f"release when the run ends")
    elif args.action == "release":
        holder = read_lock(tree)
        if holder is None:
            print("nothing to release — the tree was not locked.")
        else:
            TreeLock(tree).steal()
            print(f"released {cfg.tree_display}")
    elif args.action == "steal":
        holder = TreeLock(tree).steal()
        if holder is None:
            print("nothing to steal — the tree was not locked.")
        else:
            print(f"stole the lock from {holder.describe()} — only do this when the "
                  f"holder is confirmed dead; two loops on one tree corrupt both.")


def cmd_receipts(args):
    from . import render
    from .receipts import ReceiptChain
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
            probs = chain.verify()
            problems += probs
            print(f"  {'●' if not probs else '▲'} {s}: {len(rs)} receipt(s), "
                  f"{'chain holds' if not probs else f'{len(probs)} problem(s)'}")
            for p in probs:
                print(f"    {C['red']}{p}{C['reset']}")
    if args.action == "verify":
        if problems:
            print(f"{C['red']}✗ evidence chain broken — someone edited it after the fact.{C['reset']}")
            raise SystemExit(1)
        print(f"{C['green']}✓ every chain holds — the evidence is what it was when written.{C['reset']}")


def cmd_stats(args):
    import json as _json
    from . import render
    C = render.C
    cfg = _config(args)
    path = cfg.state_dir / "records.jsonl"
    if not path.exists():
        print("no run records yet — the dataset starts with the first cycle.")
        return
    records = [_json.loads(l) for l in path.read_text().splitlines() if l.strip()]
    by_class: dict[str, list] = {}
    for r in records:
        by_class.setdefault(r.get("class") or "(unclassed)", []).append(r)
    print(f"{C['bold']}class               cycles  closed  parked  failed  close%  avg-attempts  avg-clock{C['reset']}")
    for cls, rs in sorted(by_class.items()):
        closed = sum(1 for r in rs if r.get("status") == "closed")
        parked = sum(1 for r in rs if r.get("status") == "parked")
        failed = sum(1 for r in rs if r.get("status") == "failed")
        rate = 100 * closed / len(rs) if rs else 0
        att = sum(r.get("attempts", 0) for r in rs) / len(rs)
        clk = sum(r.get("wall_clock_s", 0) for r in rs) / len(rs)
        print(f"{cls:<19} {len(rs):>6}  {closed:>6}  {parked:>6}  {failed:>6}  "
              f"{rate:>5.0f}%  {att:>12.1f}  {clk:>8.0f}s")
    total_closed = sum(1 for r in records if r.get("status") == "closed")
    regressions = sum(r.get("regressions_caught", 0) for r in records)
    print(render.dim(
        f"\n{len(records)} cycle records · {total_closed} self-grading tasks accumulated "
        f"(snapshot + RED probe + gate-as-oracle) · {regressions} regression(s) caught at the gate"))
    print(render.dim("close-rate by class is triage prior material; the dataset is the product."))


def cmd_status(args):
    """One-glance health: open/closed claim counts, the TRUE gate verdict
    (computed from a full matrix run, never hardcoded), any broken/stale
    counts, and the pending draft backlog."""
    from . import render
    from .status import summarize
    C = render.C
    cfg = _config(args)
    ledger = _load(cfg)
    matrix = run_matrix(list(ledger.gaps), cfg, timeout_s=args.timeout)
    s = summarize(ledger, matrix)
    drafts, _forks = _draft_backlog(cfg)
    pending = sum(d["pending"] for d in drafts)

    verdict = (f"{C['green']}PASS{C['reset']}" if s["gate_ok"]
               else f"{C['red']}FAIL{C['reset']}")
    print(f"{C['bold']}{cfg.name} — health{C['reset']}")
    print(f"  claims     {C['red']}{s['open']} open{C['reset']} · "
          f"{C['green']}{s['closed']} closed{C['reset']}")
    print(f"  gate       {verdict}")
    trouble = []
    if s["regressions"]:
        trouble.append(f"{s['regressions']} regression")
    if s["broken"]:
        trouble.append(f"{s['broken']} broken")
    if s["stale"]:
        trouble.append(f"{s['stale']} stale")
    if s["failed_traps"]:
        trouble.append(f"{s['failed_traps']} failed-trap")
    if trouble:
        print(f"  trouble    {C['amber']}{', '.join(trouble)}{C['reset']}")
    if pending:
        print(f"  drafts     {C['amber']}{pending} pending{C['reset']}")
    if args.gate and not s["gate_ok"]:
        raise SystemExit(1)


def cmd_report(args):
    import json as _json
    from .report import NarratorError, gather, load_records, run_narrator, to_markdown
    cfg = _config(args)
    if args.suite and args.suite not in cfg.suites:
        _fail(f"unknown {cfg.label} {args.suite!r}; configured: {', '.join(cfg.suites)}")
    if args.narrate and not cfg.report_narrator:
        _fail(f"--narrate needs [report] narrator in {cfg.source_file.name} — none is configured")
    gaps = [g for g in _load(cfg).gaps if not args.suite or g.suite == args.suite]
    records = load_records(cfg, args.suite)
    data = gather(cfg, gaps, records, suite=args.suite)
    md = to_markdown(data)
    narrator_err = ""
    if args.narrate:
        try:
            prose = run_narrator(cfg.report_narrator, cfg.report_narrator_timeout,
                                 md, records)
            md += f"\n\n## Narrative\n\n{prose}"
            data["narrative"] = prose
        except NarratorError as e:
            narrator_err = str(e)
    text = _json.dumps(data, indent=2, sort_keys=True) if args.format == "json" else md
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("a") as f:
            f.write(text + "\n")
        print(f"appended report to {out}")
    else:
        print(text)
    # A narrator failure costs the prose, never the report: the deterministic
    # output above was already emitted in full before we say so.
    if narrator_err:
        print(f"\033[31m✗ narrator failed:\033[0m {narrator_err} — "
              f"the deterministic report stands", file=sys.stderr)
        raise SystemExit(1)


def cmd_pack(args):
    from .pack import PackError, export_pack, install_pack
    cfg = _config(args)
    try:
        if args.action == "export":
            dest = export_pack(cfg, args.suite, Path(args.out), version=args.version)
            print(f"exported pack to {dest} — drafts only; receivers measure for themselves.")
        else:
            for n in install_pack(cfg, Path(args.path), args.suite):
                print(f"  - {n}")
    except PackError as e:
        _fail(str(e))


def cmd_adjudicate(args):
    import time
    from . import render
    from .adjudicate import adjudicate, retire
    C = render.C
    cfg = _config(args)
    g = _load(cfg).by_id(args.gap_id)
    if not g:
        _fail(f"unknown gap id: {args.gap_id}")
    decision = args.decision
    if not decision and sys.stdin.isatty():
        print(f"{C['bold']}{g.id}{C['reset']}  {g.title}")
        print(f"  current smallest_fix: {g.smallest_fix[:120]}")
        decision = input("one sentence — the decision (empty aborts): ").strip()
    if not decision:
        _fail("no decision given — adjudication records a human sentence, never a guess")
    date = time.strftime("%Y-%m-%d")
    try:
        notes = (retire(cfg, g, decision, date) if args.retire
                 else adjudicate(cfg, g, decision, date))
    except GapParseError as e:
        _fail(str(e))
    for n in notes:
        print(f"  - {n}")
    verb = "retired" if args.retire else "adjudicated"
    print(f"{C['green']}✓ {g.id} {verb}{C['reset']} — three places, one decision; "
          f"run `{args.prog} validate && {args.prog} coverage` to confirm nothing drifted.")


def cmd_drill(args):
    """The sabotage audit: re-prove the guards can still catch their defects.
    Trap audit (every closed gap's probe must turn RED on its kept
    counterexamples) plus the per-suite end-to-end hook (harness/drill.sh on
    a scratch tree copy, --deep). Leaves NO trace in the ledger or run
    records — a drill that pollutes the dataset would poison the very
    evidence it exists to validate."""
    import shutil
    import tempfile
    from . import render
    from .lock import LockHeld, TreeLock
    from .probe import run_traps
    C = render.C
    cfg = _config(args)
    ledger = _load(cfg)
    guards = [g for g in ledger.gaps
              if g.status is Status.CLOSED and (not args.suite or g.suite == args.suite)]
    if not guards:
        print("nothing to drill: no closed gaps guard anything yet.")
        return
    failures, waived, audited = [], 0, 0
    try:
        with TreeLock(cfg.tree or cfg.root):
            for g in guards:
                if g.trap_waiver:
                    waived += 1
                    continue
                for t in run_traps(g, timeout_s=args.timeout):
                    audited += 1
                    mark = C["green"] + "●" if t.ok else C["red"] + "▲"
                    print(f"  {mark}{C['reset']} {g.id}/{t.trap} "
                          f"{'RED (still catches it)' if t.ok else t.outcome.value + ' — ' + t.detail[:60]}")
                    if not t.ok:
                        failures.append(t)
            if args.deep and cfg.tree is not None:
                for name, sc in cfg.suites.items():
                    hook = sc.dir / "harness" / "drill.sh"
                    if not hook.exists():
                        continue
                    with tempfile.TemporaryDirectory(prefix="recurve-drill-") as scratch:
                        scratch_tree = Path(scratch) / "tree"
                        shutil.copytree(cfg.tree, scratch_tree, symlinks=True,
                                        ignore=shutil.ignore_patterns(".git"))
                        import subprocess
                        r = subprocess.run(["bash", str(hook)], cwd=sc.dir,
                                           env={**__import__("os").environ,
                                                "SCRATCH_TREE": str(scratch_tree),
                                                "RECURVE_DRILL": "1"},
                                           capture_output=True, text=True,
                                           timeout=args.timeout * 5)
                        okd = r.returncode == 0
                        print(f"  {'●' if okd else '▲'} {name}/harness/drill.sh "
                              f"{'sabotage caught' if okd else 'FAILED: ' + (r.stdout + r.stderr)[-100:]}")
                        if not okd:
                            failures.append(name)
    except LockHeld as e:
        _fail(f"\033[31m✗ {e}\033[0m", 1)
    print(f"drill: {audited} counterexample(s) audited across {len(guards)} guard(s), "
          f"{waived} waived (debt — the drill cannot repay what no fixture exercises)")
    if failures:
        print(f"{C['red']}✗ DRILL FAILED — a guard would bless its own defect; "
              f"fix the probe, never the trap.{C['reset']}")
        raise SystemExit(1)
    print(f"{C['green']}✓ drill clean — every audited guard still catches its defect.{C['reset']}")


def cmd_demo(args):
    """Zero-setup sign-of-life. Runs one claim from RED to GREEN inside a fresh
    temp dir — no config, no network, no agent, no cwd pollution — and prints a
    compact narrative of the loop's shape (claim → probe → gate → green). The
    temp dir is removed before returning."""
    import tempfile
    from . import render
    from .demo import run_demo
    C = render.C
    with tempfile.TemporaryDirectory(prefix="recurve-demo-") as tmp:
        trace = run_demo(Path(tmp))
    steps = trace["steps"]
    before = next((s for s in steps if s["probe"] == "RED"), None)
    after = next((s for s in steps if s["probe"] == "GREEN"), None)

    def mark(probe: str) -> str:
        return (f"{C['red']}RED{C['reset']}" if probe == "RED"
                else f"{C['green']}GREEN{C['reset']}")

    print(f"{C['bold']}recurve demo{C['reset']} — one claim, RED → GREEN, behind the gate")
    print(render.dim("  (ran in a throwaway temp dir; nothing written to your cwd)"))
    print(f"  claim   the target says 'ready'")
    print(f"  probe   reads the tree and returns RED or GREEN")
    if before:
        print(f"  {mark(before['probe'])}     probe fails — the claim is unmet")
    print(render.dim("  fix     write 'ready' to the target (the trivial change)"))
    if after:
        print(f"  {mark(after['probe'])}   same probe passes — the claim now holds")
    verdict = (f"{C['green']}open{C['reset']}" if trace["gate_ok"]
               else f"{C['red']}shut{C['reset']}")
    print(f"  gate    {verdict} — a claim promotes only when its probe is GREEN")
    if before and after:
        print(f"\n{C['green']}✓ watched a failing probe go green.{C['reset']} "
              f"That RED → GREEN transition, gated, is the whole loop.")
    else:
        print(f"\n{C['red']}✗ demo did not show a real RED → GREEN transition.{C['reset']}")
        raise SystemExit(1)


def _stub(args):
    _fail(f"{args.prog} {args.cmd}: not yet implemented — {_STUBS[args.cmd]} (plan.md §14)")


def main(argv=None, prog: str | None = None, config_path: str | None = None):
    prog = prog or "recurve"
    p = argparse.ArgumentParser(prog=prog, description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--config", default=config_path, help="path to recurve.toml (default: search upward)")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("ledger", help="every gap across every suite").set_defaults(fn=cmd_ledger)

    s = sub.add_parser("show", help="one gap in full"); s.add_argument("gap_id"); s.set_defaults(fn=cmd_show)

    sub.add_parser("validate", help="schema + invariants").set_defaults(fn=cmd_validate)

    s = sub.add_parser("next", help="recommend the next gap (value-first; flags review-gated ones)")
    s.add_argument("--json", action="store_true", help="machine-readable triage (for orchestrators)")
    s.add_argument("--lanes", type=int, metavar="N",
                   help="deal up to N parallel lanes from pairwise-disjoint suites")
    s.set_defaults(fn=cmd_next)

    s = sub.add_parser("init", help="stamp the loop into a target (blank, --from-repo archaeology, --from-prd claimify)")
    s.add_argument("path", nargs="?",
                   help="optional target: infers the mode — a spec FILE → --from-prd, a "
                        "repo/docs DIR → --from-repo, an empty DIR → blank (always announced; "
                        "an explicit mode flag overrides)")
    s.add_argument("--target", default=".")
    s.add_argument("--name"); s.add_argument("--suite")
    s.add_argument("--tree", default=".")
    s.add_argument("--label", default="suite")
    s.add_argument("--quality", default="pre-launch", help="pre-launch | stable | <path>")
    s.add_argument("--from-repo", action="store_true", help="mine the repo's documented promises into drafts")
    s.add_argument("--from-prd", metavar="FILE", help="decompose a PRD/spec into draft claims")
    s.add_argument("--no-review", action="store_true",
                   help="skip the human draft review (NOT recommended — the skim is a security boundary)")
    s.set_defaults(fn=cmd_init)

    s = sub.add_parser("install", help="symlink the recurve entrypoint onto PATH (idempotent)")
    s.add_argument("--bin-dir", default="~/.local/bin",
                   help="directory to link recurve into (default: ~/.local/bin)")
    s.set_defaults(fn=cmd_install)

    s = sub.add_parser("run", help="run the burndown loop with sensible defaults (agent defaults to a bypass-permissions Claude)")
    s.add_argument("--agent", help="agent invocation (reads a cycle prompt on stdin); overrides $AGENT_CMD and the default")
    s.add_argument("--cap", type=int, help="max sculpting cycles (default: [burndown] cap)")
    s.add_argument("--lanes", type=int, help="run N parallel lanes (uses burndown-parallel.sh)")
    s.add_argument("--parked", help="comma-separated parked gap ids to seed this run")
    s.add_argument("--no-caffeinate", action="store_true", help="do not keep the machine awake (macOS)")
    s.add_argument("--dry-run", action="store_true", help="print the resolved agent + cap + script and exit, without running")
    s.set_defaults(fn=cmd_run)

    s = sub.add_parser("record", help="run records: append (schema-validated) / list")
    s.add_argument("action", choices=["append", "list"])
    s.add_argument("--file"); s.add_argument("--run-id")
    s.set_defaults(fn=cmd_record)

    s = sub.add_parser("review", help="print the adversarial-review brief for a review-gated gap")
    s.add_argument("gap_id")
    s.set_defaults(fn=cmd_review)

    s = sub.add_parser("probe", help="run gap probes")
    s.add_argument("--suite")
    s.add_argument("--gap"); s.add_argument("--timeout", type=int, default=120)
    s.set_defaults(fn=cmd_probe)

    s = sub.add_parser("matrix", help="the conformance matrix")
    s.add_argument("--gate", action="store_true", help="exit nonzero on regression/broken/stale/failed-trap")
    s.add_argument("--timeout", type=int, default=120)
    s.add_argument("--receipts", action="store_true", help="chain an evidence receipt per verdict")
    s.add_argument("--federate", action="append", metavar="RECURVE_TOML",
                   help="also gate another project's suites (shared-tree federation); repeatable")
    s.set_defaults(fn=cmd_matrix)

    s = sub.add_parser("decide", help="run the stopping controller on a measured progress vector and print its verdict")
    s.add_argument("--open", type=int, default=0, help="claims still RED (work remaining)")
    s.add_argument("--regressed", type=int, default=0, help="claims that went GREEN → RED this cycle")
    s.add_argument("--broken", type=int, default=0, help="claims that could not be measured")
    s.add_argument("--uncovered", type=int, default=0, help="frontier size (completeness signal)")
    s.add_argument("--divergent", action="store_true", help="a goal-counterexample passed (built the wrong thing)")
    s.set_defaults(fn=cmd_decide)

    s = sub.add_parser("frontier", help="surface the ranked uncovered ids — what no claim covers")
    s.add_argument("--point", action="append", metavar="ID[:WEIGHT]",
                   help="a surface point (repeatable); WEIGHT ranks it (higher first, default 0)")
    s.add_argument("--covered", action="append", metavar="ID", help="an id a claim covers (repeatable)")
    s.add_argument("--deferred", action="append", metavar="ID", help="an id explicitly deferred (repeatable)")
    s.set_defaults(fn=cmd_frontier)

    s = sub.add_parser("sense", help="assemble the full measured progress vector — gate counts + uncovered + divergent")
    s.add_argument("--open", type=int, default=0, help="claims still RED (work remaining)")
    s.add_argument("--regressed", type=int, default=0, help="claims that went GREEN → RED this cycle")
    s.add_argument("--broken", type=int, default=0, help="claims that could not be measured")
    s.add_argument("--point", action="append", metavar="ID[:WEIGHT]",
                   help="a surface point (repeatable); WEIGHT ranks it (higher first, default 0)")
    s.add_argument("--covered", action="append", metavar="ID", help="an id a claim covers (repeatable)")
    s.add_argument("--deferred", action="append", metavar="ID", help="an id explicitly deferred (repeatable)")
    s.add_argument("--goal", action="append", metavar="ID[:WEIGHT]",
                   help="an accepted goal-counterexample (repeatable) — a divergence signal")
    s.set_defaults(fn=cmd_sense)

    s = sub.add_parser("receipts", help="evidence chains: verify / list")
    s.add_argument("action", choices=["verify", "list"])
    s.add_argument("--suite")
    s.set_defaults(fn=cmd_receipts)

    sub.add_parser("stats", help="the run-record dataset: close rates, attempts, cost by class").set_defaults(fn=cmd_stats)

    s = sub.add_parser("status", help="one-glance health: open/closed counts, the true gate verdict, broken/stale/drafts")
    s.add_argument("--gate", action="store_true", help="exit nonzero if the gate does not pass")
    s.add_argument("--timeout", type=int, default=120)
    s.set_defaults(fn=cmd_status)

    s = sub.add_parser("report", help="the run report: progress, durations, ETA, diff honesty (deterministic; --narrate adds prose)")
    s.add_argument("--suite")
    s.add_argument("--format", choices=["md", "json"], default="md")
    s.add_argument("--out", metavar="FILE", help="append the report to FILE (parents created) instead of stdout")
    s.add_argument("--narrate", action="store_true",
                   help="pipe the report + cycle records to [report] narrator and append its prose")
    s.set_defaults(fn=cmd_report)

    s = sub.add_parser("pack", help="claim packs: export a suite / install one (drafts only)")
    psub = s.add_subparsers(dest="action", required=True)
    pe = psub.add_parser("export"); pe.add_argument("suite"); pe.add_argument("--out", required=True)
    pe.add_argument("--version", default="0.1.0"); pe.set_defaults(fn=cmd_pack)
    pi = psub.add_parser("install"); pi.add_argument("path"); pi.add_argument("--suite", required=True)
    pi.set_defaults(fn=cmd_pack)

    s = sub.add_parser("freshness", help="are suite artifacts current with the target tree?")
    s.add_argument("--gate", action="store_true", help="exit nonzero if any suite is stale")
    s.set_defaults(fn=cmd_freshness)

    s = sub.add_parser("coverage", help="does the ledger mirror every GAPS.md gap? (orphans = invisible to the loop)")
    s.add_argument("--gate", action="store_true", help="exit nonzero if any prose gap has no ledger entry")
    s.set_defaults(fn=cmd_coverage)

    s = sub.add_parser("import", help="seed a draft ledger from GAPS.md")
    s.add_argument("suite"); s.add_argument("--prefix"); s.add_argument("--force", action="store_true")
    s.set_defaults(fn=cmd_import)

    c = sub.add_parser("cycle", help="sculpting cycles")
    csub = c.add_subparsers(dest="cyclecmd", required=True)
    cn = csub.add_parser("new", help="scaffold a cycle plan")
    cn.add_argument("name"); cn.add_argument("--gaps", required=True, help="comma-separated gap ids")
    cn.add_argument("--timeout", type=int, default=120)
    cn.set_defaults(fn=cmd_cycle_new)

    s = sub.add_parser("baseline", help="the promotion ceremony: drafts → measured ledger entries")
    s.add_argument("suite"); s.add_argument("--timeout", type=int, default=120)
    s.set_defaults(fn=cmd_baseline)

    sub.add_parser("demo", help="zero-setup sign-of-life: watch one claim go RED → GREEN behind the gate (temp dir, no config)").set_defaults(fn=cmd_demo)

    s = sub.add_parser("park", help="park a gap (run state, not claim truth) / list parked")
    s.add_argument("gap_id", nargs="?")
    s.add_argument("--reason"); s.add_argument("--attempt"); s.add_argument("--observed")
    s.add_argument("--unpark", action="store_true")
    s.set_defaults(fn=cmd_park)

    s = sub.add_parser("lock", help="tree lock: status / acquire / release (orchestrators) / steal (human-confirmed only)")
    s.add_argument("action", choices=["status", "acquire", "release", "steal"])
    s.set_defaults(fn=cmd_lock)

    s = sub.add_parser("adjudicate", help="record a human decision in three synchronized places / amend / retire")
    s.add_argument("gap_id")
    s.add_argument("--decision", help="the one human sentence (omit for interactive prompt)")
    s.add_argument("--retire", action="store_true",
                   help="retire the claim: prose tombstone + probe deleted + entry removed, one change")
    s.set_defaults(fn=cmd_adjudicate)

    s = sub.add_parser("drill", help="sabotage audit: re-prove the guards can still fail (scratch-only, traceless)")
    s.add_argument("--suite"); s.add_argument("--timeout", type=int, default=120)
    s.add_argument("--deep", action="store_true", help="also run per-suite harness/drill.sh hooks on a scratch tree copy")
    s.set_defaults(fn=cmd_drill)

    for name in _STUBS:
        s = sub.add_parser(name, help=_STUBS[name])
        s.add_argument("rest", nargs="*")
        s.set_defaults(fn=_stub)

    args = p.parse_args(argv)
    args.prog = prog
    args.fn(args)


if __name__ == "__main__":
    main()
