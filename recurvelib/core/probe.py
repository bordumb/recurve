"""Probe execution — the port, and a shell adapter.

A *probe* is an executable that asserts a claim's DESIRED behavior. It is
written RED (the target doesn't do it yet) and turns GREEN when the target is
sculpted to support it. That inversion is what makes the loop TDD: the probe
is the failing test you make pass by changing the target tree.

Probe exit-code contract (frozen):
    0  GREEN   — the desired behavior is present
    1  RED     — the desired behavior is absent (expected while the gap is open)
    2  BROKEN  — the probe could not decide (setup failed, artifact missing)
    3  SKIP    — the probe's EXTERNAL oracle is absent (not-applicable here). It
               is non-blocking ONLY when the claim declares an `oracle_waiver`;
               an undeclared skip is treated as BROKEN, so nothing dodges the gate.
  any other exit — crash, signal, 127, timeout (124) — coerces to BROKEN,
  never to a verdict. The map is total; there is no verdict beyond these.

A probe must be hermetic: build nothing, mutate no sacred space, and finish in
seconds against already-built artifacts. Slow setup belongs in the suite's own
rebuild step, not the probe.
"""

from __future__ import annotations

import os
import subprocess
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Protocol

from recurvelib.core.model import Gap


class Outcome(str, Enum):
    GREEN = "GREEN"      # exit 0 — behavior present
    RED = "RED"          # exit 1 — behavior absent
    BROKEN = "BROKEN"    # exit 2 / timeout / crash — undecidable
    MISSING = "MISSING"  # no probe file on disk
    STALE = "STALE"      # suite artifacts older than the tree — verdict untrustworthy
    SKIP = "SKIP"        # exit 3 — external oracle absent; non-blocking only with an oracle_waiver

    @property
    def glyph(self) -> str:
        return {"GREEN": "●", "RED": "○", "BROKEN": "▲", "MISSING": "·",
                "STALE": "≈", "SKIP": "⊘"}[self.value]


@dataclass(frozen=True)
class ProbeResult:
    gap: Gap
    outcome: Outcome
    exit_code: int | None
    duration_s: float
    detail: str

    @property
    def is_regression(self) -> bool:
        """A closed gap whose probe went red — the target lost ground.
        A STALE result is never a regression (it's untrustworthy, not red)."""
        from recurvelib.core.model import Status
        return self.gap.status is Status.CLOSED and self.outcome is Outcome.RED

    @property
    def is_ready_to_close(self) -> bool:
        """An open/sculpting gap whose probe is green — the fix landed; promote it.
        Only a TRUSTWORTHY green counts — a stale suite can't promote a gap."""
        return self.gap.expects_red and self.outcome is Outcome.GREEN

    @property
    def matches_status(self) -> bool:
        if self.outcome in (Outcome.BROKEN, Outcome.MISSING, Outcome.STALE, Outcome.SKIP):
            return False
        if self.gap.expects_red:
            return self.outcome is Outcome.RED
        return self.outcome is Outcome.GREEN  # closed


@dataclass(frozen=True)
class TrapResult:
    """One counterexample run: the probe invoked with TRAP_FIXTURE set MUST
    come back RED. GREEN means the probe blessed its own counterexample — a
    gate failure of the highest order. Anything else is BROKEN (an empty or
    crashing trap is not a pass)."""

    gap: Gap
    trap: str            # fixture directory name
    outcome: Outcome
    detail: str

    @property
    def ok(self) -> bool:
        return self.outcome is Outcome.RED


class ProbeRunner(Protocol):
    def run(self, gap: Gap, timeout_s: int) -> ProbeResult: ...


class ShellProbeRunner:
    """Adapter: runs an executable probe file, mapping exit codes to outcomes."""

    def run(self, gap: Gap, timeout_s: int = 120, trap_fixture: Path | None = None,
            iso_fixture: Path | None = None) -> ProbeResult:
        if gap.probe is None:
            return ProbeResult(gap, Outcome.MISSING, None, 0.0, "no probe declared")
        if not gap.probe.exists():
            return ProbeResult(gap, Outcome.MISSING, None, 0.0, f"probe file absent: {gap.probe}")

        env = {**os.environ, "NO_COLOR": "1", "RECURVE_PROBE": gap.id}
        if trap_fixture is not None:
            env["TRAP_FIXTURE"] = str(trap_fixture)
        if iso_fixture is not None:
            env["ISO_FIXTURE"] = str(iso_fixture)
        start = time.monotonic()
        try:
            proc = subprocess.run(
                ["bash", str(gap.probe)],
                cwd=gap.suite_dir,  # probes/ live under the suite dir
                capture_output=True,
                text=True,
                timeout=timeout_s,
                env=env,
            )
        except subprocess.TimeoutExpired:
            return ProbeResult(gap, Outcome.BROKEN, 124, float(timeout_s),
                               f"timed out after {timeout_s}s")
        dur = time.monotonic() - start
        tail = _tail(proc.stdout, proc.stderr)
        # The total map: 0 GREEN, 1 RED, 3 SKIP (external oracle absent), anything
        # else BROKEN. A segfault must never read as a verdict.
        outcome = {0: Outcome.GREEN, 1: Outcome.RED, 3: Outcome.SKIP}.get(
            proc.returncode, Outcome.BROKEN)
        return ProbeResult(gap, outcome, proc.returncode, dur, tail)


def _tail(stdout: str, stderr: str, lines: int = 4) -> str:
    blob = (stdout + stderr).strip().splitlines()
    return " ⏎ ".join(blob[-lines:]) if blob else ""


def run_traps(gap: Gap, runner: ShellProbeRunner | None = None,
              timeout_s: int = 120) -> list[TrapResult]:
    """Run every counterexample fixture for one gap's probe. A trap dir with
    no fixtures is itself a BROKEN result — absence of a counterexample never
    reads as a pass."""
    runner = runner or ShellProbeRunner()
    if gap.probe is None:
        return []
    if gap.trap_dir is not None and gap.trap_dir.is_dir() and not gap.traps:
        return [TrapResult(gap, "(empty)", Outcome.BROKEN,
                           "trap dir exists but holds no fixture subdirectories")]
    results = []
    for fixture in gap.traps:
        r = runner.run(gap, timeout_s=timeout_s, trap_fixture=fixture)
        detail = r.detail if r.outcome is not Outcome.GREEN else \
            f"probe exited GREEN on counterexample {fixture.name} — it can no longer fail"
        results.append(TrapResult(gap, fixture.name, r.outcome, detail))
    return results
