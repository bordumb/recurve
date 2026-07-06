"""A deliberately-wrong `[gate] boundary` resolver: it fuzzy-matches
anything that LOOKS like "open" (case, whitespace, suffixes) instead of
requiring the exact literal value — precisely the "some other config path
resolves to open by coincidence" bug the real config loader must never have.
"""
from __future__ import annotations


def broken_gate_boundary(gate: dict) -> str:
    raw = str(gate.get("boundary", "enforced")).strip().lower()
    if raw.startswith("open"):
        return "open"
    return "enforced"
