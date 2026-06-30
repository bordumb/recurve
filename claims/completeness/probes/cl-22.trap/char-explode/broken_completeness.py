"""CL-22 counterexample: passes a string `covers` straight to set.update, exploding "verify_chain" into
character-ids and losing the intended coverage."""


def covered_ids(claims):
    ids = set()
    for claim in claims:
        ids.update(claim.get("covers") or [])  # BUG: a str is iterated into single characters
    return ids
