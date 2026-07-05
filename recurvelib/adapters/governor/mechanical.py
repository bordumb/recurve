"""mechanical: fresh-checkout re-execution of the cycle's probes+traps —
near-free, no LLM in the loop, the default candidate (R5's mechanical tier,
`docs/plans/ablation-infra.md` AI2/AI10).

Re-executes every probe AND every trap for the cycle's claim_ids against the
isolated `CycleSnapshot`'s own tree — not the working directory the burndown
loop used. This catches a different bug class than correlated authorship:
state leakage ("works in this working directory"), accidental
trap-weakening mid-run. It deliberately does NOT catch correlated
authorship (a same-model blind spot re-derives the identical wrong answer in
the snapshot too) — that is `mechanical_review`'s job, not this tier's.
"""
from __future__ import annotations

from recurvelib.loop.reviewers import GovernorVerdict
from recurvelib.core.config import find_config, load as load_config
from recurvelib.core.model import load_ledger
from recurvelib.core.probe import ShellProbeRunner, Outcome, run_traps


class MechanicalGovernor:
    def audit(self, cycle) -> GovernorVerdict:
        cfg_path = find_config(cycle.root)
        if cfg_path is None:
            return GovernorVerdict.veto({
                cid: "mechanical governor: no recurve.toml found in the cycle snapshot "
                     "— cannot re-execute"
                for cid in cycle.claim_ids
            })
        cfg = load_config(cfg_path)
        ledger = load_ledger(cfg)
        runner = ShellProbeRunner()
        vetoes: dict[str, str] = {}
        for cid in cycle.claim_ids:
            gap = ledger.by_id(cid)
            if gap is None:
                vetoes[cid] = "mechanical governor: claim not found in the snapshot's ledger"
                continue
            result = runner.run(gap, timeout_s=120)
            if result.outcome is not Outcome.GREEN:
                vetoes[cid] = (
                    f"mechanical governor: re-execution in a fresh, isolated checkout came "
                    f"back {result.outcome.value}, not GREEN — {result.detail[:150]}")
                continue
            bad_traps = [t for t in run_traps(gap, runner, timeout_s=120) if not t.ok]
            if bad_traps:
                t = bad_traps[0]
                vetoes[cid] = (
                    f"mechanical governor: trap {t.trap} came back {t.outcome.value} on "
                    f"re-execution, not RED — {t.detail[:150]}")
        if vetoes:
            return GovernorVerdict.veto(vetoes)
        return GovernorVerdict.cleared()
