"""Counterexample: an engine variant whose verdict map defaults crashes to
RED — a fourth state in disguise. The totality check MUST catch it (exit 1)."""

LENIENT = {0: "GREEN", 1: "RED"}


def outcome(rc: int) -> str:
    return LENIENT.get(rc, "RED")   # the bug under test: crash → verdict


import sys

sys.exit(0 if outcome(139) == "BROKEN" else 1)
