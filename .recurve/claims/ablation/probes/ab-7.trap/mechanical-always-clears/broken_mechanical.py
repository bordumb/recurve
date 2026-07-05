# A broken mechanical governor that never actually re-executes anything — it
# always clears, regardless of what the fresh checkout's probes say. This is
# the exact "works in this working directory" state-leakage bug the real
# mechanical tier exists to catch.
from recurvelib.loop.reviewers import GovernorVerdict


class BrokenMechanicalGovernor:
    def audit(self, cycle):
        return GovernorVerdict.cleared()
