"""Terminal rendering — color discipline: green/red/dim, NO_COLOR honored.

The `label` parameter is what the project calls a suite in human output (set
in recurve.toml; defaults to "suite"). It is presentation only — it never
changes behavior.
"""

from __future__ import annotations

import os
import sys

from .conformance import Matrix
from .model import Gap, Ledger, Severity
from .probe import Outcome

_TTY = sys.stdout.isatty() and not os.environ.get("NO_COLOR")
C = {
    "dim": "\033[2m" if _TTY else "",
    "green": "\033[32m" if _TTY else "",
    "red": "\033[31m" if _TTY else "",
    "amber": "\033[33m" if _TTY else "",
    "bold": "\033[1m" if _TTY else "",
    "reset": "\033[0m" if _TTY else "",
}

_SEV_RANK = {Severity.HEADLINE: 0, Severity.FEATURE: 1, Severity.FRICTION: 2, Severity.COSMETIC: 3}


def dim(s: str) -> str:
    return f"{C['dim']}{s}{C['reset']}"


def ledger_table(ledger: Ledger, label: str = "suite") -> str:
    rows = sorted(ledger.gaps, key=lambda g: (g.suite, _SEV_RANK.get(g.severity, 9), g.id))
    out = [f"{C['bold']}gap         {label:<24} sev       class             status     probe{C['reset']}"]
    for g in rows:
        probe = "—" if g.probe is None else g.probe.name
        sev_color = C["red"] if g.severity is Severity.HEADLINE else C["dim"]
        out.append(
            f"{g.id:<11} {g.suite[:24]:<24} "
            f"{sev_color}{g.severity.value:<9}{C['reset']} "
            f"{g.gap_class.value:<17} {g.status.value:<10} {dim(probe)}"
        )
    out.append("")
    out.append(dim(f"{len(rows)} gaps across {len(ledger.suites)} {label}s"))
    return "\n".join(out)


def matrix_table(matrix: Matrix) -> str:
    out = [f"{C['bold']}    gap         outcome   status     Δ        detail{C['reset']}"]
    for r in matrix.results:
        color = {
            Outcome.GREEN: C["green"], Outcome.RED: C["dim"],
            Outcome.BROKEN: C["amber"], Outcome.MISSING: C["dim"],
            Outcome.STALE: C["amber"],
        }[r.outcome]
        delta = ""
        if r.is_regression:
            delta = f"{C['red']}REGRESSED{C['reset']}"
        elif r.is_ready_to_close:
            delta = f"{C['green']}READY→close{C['reset']}"
        elif r.outcome is Outcome.STALE:
            delta = f"{C['amber']}REBUILD{C['reset']}"
        out.append(
            f"  {color}{r.outcome.glyph}{C['reset']} {r.gap.id:<11} "
            f"{color}{r.outcome.value:<8}{C['reset']} {r.gap.status.value:<10} "
            f"{delta:<9} {dim(r.detail[:60])}"
        )
    c = matrix.counts()
    out.append("")
    summary = (
        f"holding {c['holding']} · "
        f"{C['green']}ready_to_close {c['ready_to_close']}{C['reset']} · "
        f"{C['red']}regressions {c['regressions']}{C['reset']} · "
        f"{C['amber']}broken {c['broken']}{C['reset']} · "
        f"{C['amber']}stale {c['stale']}{C['reset']} · "
        f"missing {c['missing']}"
    )
    out.append(summary)
    if matrix.stale_suites:
        out.append(dim("stale artifacts (rebuild before trusting the gate):"))
        for f in matrix.stale_suites:
            out.append(f"  {C['amber']}≈ {f.label}{C['reset']} — {dim(f.detail)}")
    if matrix.trap_results:
        ok = sum(1 for t in matrix.trap_results if t.ok)
        out.append(dim(f"traps: {ok}/{len(matrix.trap_results)} counterexamples still RED"))
        for t in matrix.failed_traps:
            out.append(f"  {C['red']}▲ {t.gap.id}/{t.trap} {t.outcome.value}{C['reset']} — {dim(t.detail)}")
    gate = f"{C['green']}GATE OK{C['reset']}" if matrix.gate_ok else f"{C['red']}GATE FAILED{C['reset']}"
    out.append(gate)
    return "\n".join(out)


def freshness_table(reports, label: str = "suite") -> str:
    from .freshness import Freshness
    out = [f"{C['bold']}    {label}/artifact{' ' * (26 - len(label))}freshness   detail{C['reset']}"]
    color = {Freshness.FRESH: C["green"], Freshness.STALE: C["amber"], Freshness.UNKNOWN: C["dim"]}
    glyph = {Freshness.FRESH: "●", Freshness.STALE: "≈", Freshness.UNKNOWN: "·"}
    for f in sorted(reports, key=lambda r: r.label):
        out.append(
            f"  {color[f.state]}{glyph[f.state]}{C['reset']} {f.label[:33]:<33} "
            f"{color[f.state]}{f.state.value:<11}{C['reset']} {dim(f.detail)}"
        )
    return "\n".join(out)


def gap_detail(g: Gap, label: str = "suite") -> str:
    lines = [
        f"{C['bold']}{g.id}{C['reset']}  {g.title}",
        dim(f"{label} {g.suite} · {g.gap_class.value} · {g.severity.value} · {g.status.value}"),
        "",
        f"observed:     {g.observed or '—'}",
        f"smallest_fix: {g.smallest_fix}",
        f"unlocks:      {g.unlocks or '—'}",
        f"probe:        {g.probe or '—'}",
    ]
    if g.evidence:
        lines.append("evidence:")
        lines += [f"  {e}" for e in g.evidence]
    return "\n".join(lines)
