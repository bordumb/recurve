# A broken cross_model adversary that trusts a caller-supplied
# "requested_model" string instead of the reviewer's ACTUAL served_model —
# exactly the config-drift bug: the flag says one thing, the server did
# another.
from recurvelib.adapters.adversary.same_model import _cmd, _parse
from recurvelib.adapters._shared.provenance import metadata_verified, verified_different_identity


class BrokenCrossModel:
    def __init__(self, actor_provenance, *, cmd=None, timeout=300, requested_model=None):
        self.actor_provenance = actor_provenance
        self.cmd = cmd
        self.timeout = timeout
        self.requested_model = requested_model

    def review(self, claim):
        from recurvelib.adapters._shared.reviewer_base import run_isolated_review
        inv = run_isolated_review(claim, _cmd(self.cmd), timeout=self.timeout)
        verdict, _served_prov = _parse(inv)
        # BUG: verifies against the REQUESTED model (self-reported), not the
        # reviewer's actual served_model.
        claimed_prov = metadata_verified(self.requested_model)
        if not verified_different_identity(self.actor_provenance, claimed_prov):
            from recurvelib.adapters.adversary.cross_model import CrossModelIdentityViolation
            raise CrossModelIdentityViolation("refused")
        return verdict
