"""audit.py — AuditPort: a post-hoc hardening pass that can only ADD columns,
never change the outcome.

`AuditResult` structurally cannot carry `declared_done`/`oracle_verdict` —
the type itself has no such fields, so there is nothing for a caller to
mistake for the outcome. `has_forbidden_field` is the same KIND of
structural guard `recurvelib.loop.reviewers.has_bypass_field` already
applies to Adversary/Governor verdicts, applied here to the eval-only Audit
port: a type-level impossibility, not a runtime check that a future edit
could quietly bypass.

`drill_hardened` wraps the existing `drill --fuzz --iso --diff` CLI (already
a real contract) against the cell's workspace; A4 = A3 + this port, nothing
else new.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, fields
from pathlib import Path

_FORBIDDEN_AUDIT_FIELDS = frozenset({"declared_done", "oracle_verdict"})


@dataclass(frozen=True)
class AuditResult:
    """Additive-only. No field here may ever decide a cell's outcome —
    `declared_done` (DoneSignalPort) and `oracle_verdict` (the held-out
    oracle) are computed independently of this type; AuditResult has no way
    to touch them, by construction, not by convention."""

    audit_ran: bool
    fuzz_fpr: float | None = None
    iso_flip_rate: float | None = None
    diff_disagreements: int | None = None
    raw_output: str = ""


def has_forbidden_field(result_type: type) -> str | None:
    """Structural check: does this dataclass type carry a field name that
    could let an audit result masquerade as (or silently overwrite) the
    outcome fields? Returns the offending name, or None if clean. Applies to
    the real `AuditResult` above, or any candidate replacement — a reusable
    guard, not a one-off assertion about today's one type."""
    try:
        names = {f.name for f in fields(result_type)}
    except TypeError:
        return None  # not a dataclass — nothing to check
    hit = names & _FORBIDDEN_AUDIT_FIELDS
    return sorted(hit)[0] if hit else None


def none_audit(workspace) -> AuditResult:
    """AuditPort["none"] — no hardening pass; the default for every arm that
    doesn't ask for one (A0/A3/A6/A7-A10 today)."""
    return AuditResult(audit_ran=False)


# These match `recurvelib.cli.commands.drill.cmd_drill`'s own summary lines
# verbatim (e.g. "fuzz: 3 fuzz-capable probe(s) measured, 1 false
# positive(s)") — the real, already-shipped CLI output, not a guess at one.
_FUZZ_RE = re.compile(r"^fuzz:\s*(\d+)\s+fuzz-capable probe\(s\) measured,\s*(\d+)\s+false positive\(s\)",
                      re.MULTILINE)
_ISO_RE = re.compile(r"^iso:\s*(\d+)\s+iso-capable probe\(s\) measured,\s*(\d+)\s+flip\(s\)",
                     re.MULTILINE)
_DIFF_RE = re.compile(r"^diff:\s*(\d+)\s+reference-bearing claim\(s\) checked,\s*(\d+)\s+disagreement\(s\)",
                     re.MULTILINE)


def drill_hardened_audit(workspace) -> AuditResult:
    """AuditPort["drill_hardened"] — literally invokes the existing `recurve
    drill --fuzz --iso --diff` CLI against the cell's workspace (A4). Additive
    only: returns an AuditResult, never touches declared_done/oracle_verdict —
    those were already decided by the DoneSignalPort and the held-out oracle
    before this port ever runs."""
    r = subprocess.run(["recurve", "drill", "--fuzz", "--iso", "--diff"],
                       cwd=str(workspace), capture_output=True, text=True)
    out = r.stdout + r.stderr

    fuzz_fpr = None
    m = _FUZZ_RE.search(out)
    if m:
        probes, fps = int(m.group(1)), int(m.group(2))
        fuzz_fpr = (fps / probes) if probes else None

    iso_flip_rate = None
    m = _ISO_RE.search(out)
    if m:
        probes, flips = int(m.group(1)), int(m.group(2))
        iso_flip_rate = (flips / probes) if probes else None

    diff_disagreements = None
    m = _DIFF_RE.search(out)
    if m:
        diff_disagreements = int(m.group(2))

    return AuditResult(
        audit_ran=True,
        fuzz_fpr=fuzz_fpr,
        iso_flip_rate=iso_flip_rate,
        diff_disagreements=diff_disagreements,
        raw_output=out,
    )


AUDIT_PORTS = {"none": none_audit, "drill_hardened": drill_hardened_audit}


def resolve_audit_port(name: str):
    if name not in AUDIT_PORTS:
        raise KeyError(f"unknown audit {name!r}; known: {', '.join(AUDIT_PORTS)}")
    return AUDIT_PORTS[name]
