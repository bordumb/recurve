"""BROKEN counterexample for SR-2: a policy that honors ANY skip, even one on a
claim that declared no oracle_waiver. That is a silent hole — any probe could
exit 3 to dodge the gate without declaring anything."""


def is_waived_skip(result):
    from recurvelib.probe import Outcome
    return result.outcome is Outcome.SKIP
