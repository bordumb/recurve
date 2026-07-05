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


def _record_diff_challenge(cfg, gap, probe_r, ref_r) -> None:
    """R4/AI8: `drill --diff` finding a real disagreement on a CLOSED
    claim's CURRENT state is exactly "a later differential pass" showing a
    published GREEN wrong — record it as a `challenge_event`
    (`phase="post_publication"`), not a printed line nobody remembers.
    Failure to record is never fatal to the drill itself (observability,
    not control flow — matching the report-posting convention elsewhere in
    the loop)."""
    try:
        from recurvelib.adapters.challenge_event import make_challenge_event, ChallengeLog
        from recurvelib.analysis.oracle_tier import derive_tier
        tier = derive_tier(gap, cfg)
        event = make_challenge_event(
            claim_id=gap.id,
            phase="post_publication",
            tier_at_challenge=tier.value,
            reason=(f"drill --diff disagreement: probe={probe_r.outcome.value} "
                   f"reference={ref_r.outcome.value} against reference {gap.reference}"),
        )
        ChallengeLog(cfg, gap.suite).append(event)
    except Exception:
        pass


def cmd_drill(args):
    """The sabotage audit: re-prove the guards can still catch their defects.
    Trap audit (every closed gap's probe must turn RED on its kept
    counterexamples) plus the per-suite end-to-end hook (harness/drill.sh on
    a scratch tree copy, --deep). The trap-audit and fuzz/iso passes leave NO
    trace in the ledger or run records — re-running a KNOWN fixture is
    drill's own self-test, and polluting the cost/reward dataset with it
    would poison the very evidence it exists to validate.

    `--diff` is different in kind, not just in name: it checks the probe
    against its reference on the SAME, CURRENT, real state — a genuine
    finding about whether a CLOSED claim is still actually true, not a
    self-test replay of a known fixture. R4/AI8
    (docs/plans/oracle-strength-and-decorrelation.md,
    docs/plans/ablation-infra.md) name exactly this case — "a later
    differential pass" showing a published GREEN wrong — as a
    challenge_event trigger, so a real `--diff` disagreement on a closed
    claim IS recorded there (recurvelib.adapters.challenge_event), never
    silently printed and forgotten. This is a third, narrow log distinct
    from both the ledger and the run-record dataset the paragraph above
    protects."""
    import os
    import shutil
    import tempfile
    from dataclasses import replace
    from recurvelib.io import render
    from recurvelib.loop.lock import LockHeld, TreeLock
    from recurvelib.core.probe import Outcome, ShellProbeRunner, run_traps
    C = render.C
    cfg = _config(args)
    ledger = _load(cfg)
    guards = [g for g in ledger.gaps
              if g.status is Status.CLOSED and (not args.suite or g.suite == args.suite)]
    if not guards:
        print("nothing to drill: no closed gaps guard anything yet.")
        return
    failures, waived, audited = [], 0, 0
    oracle_waived = 0
    fuzz_probes, fuzz_fps = 0, 0
    iso_probes, iso_flips = 0, 0
    diff_checked, diff_disagreements = 0, 0
    try:
        with TreeLock(cfg.tree or cfg.root):
            for g in guards:
                if g.trap_waiver:
                    waived += 1
                    continue
                for t in run_traps(g, timeout_s=args.timeout):
                    audited += 1
                    # A trap whose external oracle is absent (SKIP) on a claim
                    # that DECLARED oracle_waiver mirrors the gate's
                    # is_waived_skip — visible, non-blocking debt, never a
                    # drill failure. Without a declared waiver the SKIP is not
                    # excused — it falls through to the failure path below
                    # like any other non-RED outcome.
                    if t.outcome is Outcome.SKIP and g.oracle_waiver:
                        oracle_waived += 1
                        print(f"  {C['amber']}⊘{C['reset']} {g.id}/{t.trap} "
                              f"oracle-waived (external oracle absent, declared) — {t.detail[:60]}")
                        continue
                    mark = C["green"] + "●" if t.ok else C["red"] + "▲"
                    print(f"  {mark}{C['reset']} {g.id}/{t.trap} "
                          f"{'RED (still catches it)' if t.ok else t.outcome.value + ' — ' + t.detail[:60]}")
                    if not t.ok:
                        failures.append(t)
            if args.fuzz:
                # The fuzz pass: a probe can pass its curated traps and still be
                # leaky. Each guard may ship a generator (<probe-stem>.fuzz.sh)
                # that emits GENERATED known-bads; the probe must reject every
                # one, and the measured false-positive rate is reported beside
                # the trap audit. Generated state lives only in a temp dir.
                import subprocess
                runner = ShellProbeRunner()
                for g in guards:
                    if g.probe is None:
                        continue
                    gen = g.probe.with_name(g.probe.name[:-3] + ".fuzz.sh") \
                        if g.probe.name.endswith(".sh") else \
                        g.probe.with_name(g.probe.name + ".fuzz.sh")
                    if not gen.is_file():
                        continue
                    fuzz_probes += 1
                    with tempfile.TemporaryDirectory(prefix="recurve-fuzz-") as fo:
                        r = subprocess.run(
                            ["bash", str(gen)], cwd=gen.parent,
                            env={**os.environ, "FUZZ_OUT": fo,
                                 "FUZZ_N": str(cfg.drill_fuzz_n)},
                            capture_output=True, text=True, timeout=args.timeout * 5)
                        if r.returncode != 0:
                            print(f"  {C['red']}▲{C['reset']} {g.id} fuzz generator "
                                  f"failed (rc={r.returncode})")
                            failures.append(f"{g.id} fuzz generator")
                            continue
                        variants = sorted(p for p in Path(fo).iterdir()
                                          if p.is_dir())[: cfg.drill_fuzz_n]
                        if not variants:
                            print(f"  {C['amber']}·{C['reset']} {g.id} fuzz: "
                                  f"generator produced no variants")
                            continue
                        fp = sum(
                            1 for v in variants
                            if runner.run(g, timeout_s=args.timeout,
                                          trap_fixture=v).outcome is Outcome.GREEN)
                        fuzz_fps += fp
                        rate = fp / len(variants)
                        leaky = rate > cfg.drill_fuzz_fpr_max
                        mark = C["red"] + "▲" if leaky else (
                            C["amber"] + "●" if fp else C["green"] + "●")
                        print(f"  {mark}{C['reset']} {g.id} fuzz fpr {fp}/{len(variants)}"
                              + (f" — exceeds fuzz_fpr_max {cfg.drill_fuzz_fpr_max:g}"
                                 if leaky else ""))
                        if leaky:
                            failures.append(f"{g.id} fuzz fpr {fp}/{len(variants)}")
            if args.iso:
                # The isomorphic pass (fuzz's dual): a probe can reject every
                # broken variant and still have latched onto surface form. Each
                # guard may ship a generator (<probe-stem>.iso.sh) that emits
                # semantics-preserving restatements of the true state; the
                # probe's verdict on each must still be GREEN (a closed gap's
                # true verdict) — a differing verdict is a flip. Generated
                # state lives only in a temp dir.
                import subprocess
                runner = ShellProbeRunner()
                for g in guards:
                    if g.probe is None:
                        continue
                    gen = g.probe.with_name(g.probe.name[:-3] + ".iso.sh") \
                        if g.probe.name.endswith(".sh") else \
                        g.probe.with_name(g.probe.name + ".iso.sh")
                    if not gen.is_file():
                        continue
                    iso_probes += 1
                    with tempfile.TemporaryDirectory(prefix="recurve-iso-") as io:
                        r = subprocess.run(
                            ["bash", str(gen)], cwd=gen.parent,
                            env={**os.environ, "ISO_OUT": io,
                                 "ISO_N": str(cfg.drill_iso_n)},
                            capture_output=True, text=True, timeout=args.timeout * 5)
                        if r.returncode != 0:
                            print(f"  {C['red']}▲{C['reset']} {g.id} iso generator "
                                  f"failed (rc={r.returncode})")
                            failures.append(f"{g.id} iso generator")
                            continue
                        variants = sorted(p for p in Path(io).iterdir()
                                          if p.is_dir())[: cfg.drill_iso_n]
                        if not variants:
                            print(f"  {C['amber']}·{C['reset']} {g.id} iso: "
                                  f"generator produced no variants")
                            continue
                        flips = sum(
                            1 for v in variants
                            if runner.run(g, timeout_s=args.timeout,
                                          iso_fixture=v).outcome is not Outcome.GREEN)
                        iso_flips += flips
                        rate = flips / len(variants)
                        flipping = rate > cfg.drill_iso_flip_max
                        mark = C["red"] + "▲" if flipping else (
                            C["amber"] + "●" if flips else C["green"] + "●")
                        print(f"  {mark}{C['reset']} {g.id} iso flips {flips}/{len(variants)}"
                              + (f" — exceeds iso_flip_max {cfg.drill_iso_flip_max:g}"
                                 if flipping else ""))
                        if flipping:
                            failures.append(f"{g.id} iso flips {flips}/{len(variants)}")
            if args.diff:
                # Differential probes: a claim may declare a stricter/slower
                # reference oracle. Disagreement between the probe and its
                # reference on the SAME true state is an alarm — a coincidence
                # nobody checks, made loud.
                for g in guards:
                    if g.reference is None:
                        continue
                    if not g.reference.exists():
                        print(f"  {C['red']}▲{C['reset']} {g.id} reference oracle "
                              f"missing: {g.reference}")
                        failures.append(f"{g.id} reference missing")
                        continue
                    runner = ShellProbeRunner()
                    diff_checked += 1
                    probe_r = runner.run(g, timeout_s=args.timeout)
                    ref_r = runner.run(replace(g, probe=g.reference), timeout_s=args.timeout)
                    disagree = {probe_r.outcome, ref_r.outcome} == {Outcome.GREEN, Outcome.RED}
                    mark = C["red"] + "▲" if disagree else C["green"] + "●"
                    print(f"  {mark}{C['reset']} {g.id} diff probe={probe_r.outcome.value} "
                          f"reference={ref_r.outcome.value}"
                          + (" — DISAGREEMENT" if disagree else ""))
                    if disagree:
                        diff_disagreements += 1
                        failures.append(f"{g.id} diff disagreement "
                                        f"probe={probe_r.outcome.value} reference={ref_r.outcome.value}")
                        _record_diff_challenge(cfg, g, probe_r, ref_r)
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
          f"{waived} waived (debt — the drill cannot repay what no fixture exercises), "
          f"{oracle_waived} oracle-waived (external oracle absent, declared)")
    if args.fuzz:
        print(f"fuzz: {fuzz_probes} fuzz-capable probe(s) measured, "
              f"{fuzz_fps} false positive(s)")
    if args.iso:
        print(f"iso: {iso_probes} iso-capable probe(s) measured, "
              f"{iso_flips} flip(s)")
    if args.diff:
        print(f"diff: {diff_checked} reference-bearing claim(s) checked, "
              f"{diff_disagreements} disagreement(s)")
    if failures:
        print(f"{C['red']}✗ DRILL FAILED — a guard would bless its own defect; "
              f"fix the probe, never the trap.{C['reset']}")
        raise SystemExit(1)
    print(f"{C['green']}✓ drill clean — every audited guard still catches its defect.{C['reset']}")
