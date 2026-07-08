"""SUFF-4 counterexample: parses covers_claim without checking for a self-referential
parent — silently constructs a self-loop in the decomposition DAG."""


def parse_covers_claim(raw):
    gid = str(raw["id"])
    covers_claim_raw = raw.get("covers_claim") or []
    covers_claim = tuple(str(c) for c in covers_claim_raw)
    # BUG: no check that gid not in covers_claim
    return covers_claim
