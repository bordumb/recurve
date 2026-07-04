"""The parked store — run state, never claim truth.

Parking marks a gap un-greenable-this-run so the loop continues past it
(never halts on it). It lives in a sidecar file (`.recurve/parked.yaml`), not
the ledger: the schema's status enum is epistemics, parking is workflow.

Each parked gap carries an **attempt journal**: what was tried and why it
failed, as observations — commands run, output seen, the RED line at stop —
never conclusions. When a parked gap is re-picked, the orchestrator injects
prior attempts into that cycle's prompt framed as "prior attempts, possibly
mistaken: verify before trusting." This is deliberately the only memory
besides the ledger that crosses agents: bounded, gap-scoped, loaded only when
relevant.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass(frozen=True)
class ParkedGap:
    gap: str
    reason: str
    parked_at: str
    attempts: tuple[dict, ...] = field(default_factory=tuple)  # {at, tried, observed}


class ParkedStore:
    def __init__(self, project_root: Path):
        self.path = project_root / ".recurve" / "parked.yaml"

    def _load_raw(self) -> list[dict]:
        if not self.path.exists():
            return []
        doc = yaml.safe_load(self.path.read_text()) or []
        return doc if isinstance(doc, list) else []

    def list(self) -> list[ParkedGap]:
        return [
            ParkedGap(gap=str(e.get("gap", "")), reason=str(e.get("reason", "")),
                      parked_at=str(e.get("parked_at", "")),
                      attempts=tuple(e.get("attempts") or []))
            for e in self._load_raw()
        ]

    def ids(self) -> set[str]:
        return {p.gap for p in self.list()}

    def park(self, gap: str, reason: str, parked_at: str,
             attempt: dict | None = None) -> None:
        entries = self._load_raw()
        for e in entries:
            if e.get("gap") == gap:
                e["reason"] = reason
                e["parked_at"] = parked_at
                if attempt:
                    e.setdefault("attempts", []).append(attempt)
                break
        else:
            e = {"gap": gap, "reason": reason, "parked_at": parked_at}
            if attempt:
                e["attempts"] = [attempt]
            entries.append(e)
        self._write(entries)

    def add_attempt(self, gap: str, attempt: dict) -> bool:
        entries = self._load_raw()
        for e in entries:
            if e.get("gap") == gap:
                e.setdefault("attempts", []).append(attempt)
                self._write(entries)
                return True
        return False

    def unpark(self, gap: str) -> bool:
        entries = self._load_raw()
        kept = [e for e in entries if e.get("gap") != gap]
        if len(kept) == len(entries):
            return False
        self._write(kept)
        return True

    def _write(self, entries: list[dict]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        header = ("# Parked gaps — run state, not claim truth (the ledger never records\n"
                  "# parking). Attempt journals are observations, never conclusions.\n")
        self.path.write_text(header + yaml.safe_dump(entries, sort_keys=False,
                                                     allow_unicode=True))
