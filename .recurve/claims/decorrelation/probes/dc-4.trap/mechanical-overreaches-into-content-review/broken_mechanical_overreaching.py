# A broken mechanical governor that over-reaches: on top of the real
# re-execution check, it ALSO runs a stricter content-level probe (the
# failure-inclusion case) directly, itself, with no isolated model pass —
# conflating the mechanical and review tiers R5 deliberately keeps separate.
# It would WRONGLY veto the O6 replay through the "free" tier alone.
import subprocess
from pathlib import Path

from recurvelib.loop.reviewers import GovernorVerdict
from recurvelib.core.config import find_config, load as load_config
from recurvelib.core.model import load_ledger
from recurvelib.core.probe import ShellProbeRunner, Outcome, run_traps


class OverreachingMechanicalGovernor:
    def audit(self, cycle):
        cfg_path = find_config(cycle.root)
        cfg = load_config(cfg_path)
        ledger = load_ledger(cfg)
        runner = ShellProbeRunner()
        vetoes = {}
        for cid in cycle.claim_ids:
            gap = ledger.by_id(cid)
            result = runner.run(gap, timeout_s=120)
            if result.outcome is not Outcome.GREEN:
                vetoes[cid] = "re-execution failed"
                continue
            bad_traps = [t for t in run_traps(gap, runner, timeout_s=120) if not t.ok]
            if bad_traps:
                vetoes[cid] = "trap regression"
                continue
            # BUG: over-reaches into content-level review, mechanically,
            # with no decorrelated model pass at all.
            suite_dir = gap.suite_dir
            r = subprocess.run(
                ["python3", "-c",
                 "import sys; sys.path.insert(0, '.'); from solution import task_func; "
                 "r = task_func(['a','b','c'], should_fail=['b']); "
                 "sys.exit(0 if r == ['a','b','c'] else 1)"],
                cwd=suite_dir, capture_output=True, text=True)
            if r.returncode != 0:
                vetoes[cid] = "mechanical tier over-reached into content review"
        if vetoes:
            return GovernorVerdict.veto(vetoes)
        return GovernorVerdict.cleared()
