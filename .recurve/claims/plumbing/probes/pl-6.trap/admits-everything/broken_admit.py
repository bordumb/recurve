"""BROKEN counterexample for PL-6: an admission gate that admits every goal,
however vague — so a fuzzy PRD is claimified into a brittle proxy and its
unfalsifiable "claims" enter cycles, the exact thing admission exists to refuse."""

from types import SimpleNamespace

from recurvelib.admission import Verdict


def admit_result(result):
    return SimpleNamespace(verdict=Verdict.ADMIT)
