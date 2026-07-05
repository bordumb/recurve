# A broken cross_model adversary that never checks identity at all — it
# always returns the reviewer's verdict, regardless of whether the served
# model matches the actor's. This is the exact O6 bug class: a same-model
# actor and prober agreeing, unchallenged.
import sys
from pathlib import Path

_REPO_ADAPTERS = Path(__file__)
import importlib.util
_spec = importlib.util.spec_from_file_location(
    "same_model_real",
    Path(sys.argv[0]).resolve().parents[0] if False else None,
)

from recurvelib.adapters.adversary.same_model import _cmd, _parse


class BrokenCrossModel:
    def __init__(self, actor_provenance, *, cmd=None, timeout=300, requested_model=None):
        self.actor_provenance = actor_provenance
        self.cmd = cmd
        self.timeout = timeout

    def review(self, claim):
        from recurvelib.adapters._shared.reviewer_base import run_isolated_review
        inv = run_isolated_review(claim, _cmd(self.cmd), timeout=self.timeout)
        verdict, prov = _parse(inv)
        # BUG: no identity check at all.
        return verdict
