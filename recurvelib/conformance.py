"""The conformance matrix — the loop's heartbeat.

Runs every gap probe (optionally in parallel) and classifies the fleet:

  - regressions    : closed gaps that went RED  → STOP. The target lost ground.
  - ready_to_close : open/sculpting gaps now GREEN → the sculpt landed; promote.
  - broken         : probes that couldn't decide → fix the probe before trusting.
  - stale          : the suite's artifacts predate the tree source → rebuild it;
                     the probe was NOT run because its verdict would be a lie.
  - holding        : status matches probe color → as expected.

Staleness is checked BEFORE a probe runs: a probe reads the suite's copied
artifact, so if that predates the tree source the verdict is meaningless. A
stale suite blocks the gate exactly like a broken probe — a false green is the
one thing the regression guard exists to prevent.

A cycle is "green-ward" when it produces ready_to_close transitions and zero
regressions, broken, or stale. `matrix --gate` exits non-zero otherwise.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from .config import Config
from .freshness import Freshness, FreshnessReport, gap_freshness
from .model import Gap, Status
from .probe import Outcome, ProbeResult, ProbeRunner, ShellProbeRunner, TrapResult, run_traps


@dataclass(frozen=True)
class Matrix:
    results: tuple[ProbeResult, ...]
    freshness: tuple[FreshnessReport, ...] = ()
    trap_results: tuple[TrapResult, ...] = ()

    @property
    def regressions(self) -> list[ProbeResult]:
        return [r for r in self.results if r.is_regression]

    @property
    def ready_to_close(self) -> list[ProbeResult]:
        return [r for r in self.results if r.is_ready_to_close]

    @property
    def broken(self) -> list[ProbeResult]:
        return [r for r in self.results if r.outcome is Outcome.BROKEN]

    @property
    def missing(self) -> list[ProbeResult]:
        return [r for r in self.results if r.outcome is Outcome.MISSING]

    @property
    def stale(self) -> list[ProbeResult]:
        return [r for r in self.results if r.outcome is Outcome.STALE]

    @property
    def stale_suites(self) -> list[FreshnessReport]:
        return [f for f in self.freshness if f.state is Freshness.STALE]

    @property
    def unknown_freshness(self) -> list[FreshnessReport]:
        return [f for f in self.freshness if f.state is Freshness.UNKNOWN]

    @property
    def holding(self) -> list[ProbeResult]:
        return [r for r in self.results if r.matches_status]

    @property
    def failed_traps(self) -> list[TrapResult]:
        return [t for t in self.trap_results if not t.ok]

    @property
    def gate_ok(self) -> bool:
        """The hard gate: no regressions, no broken probes, no stale suites,
        and no closed gap's probe blessing its own counterexample."""
        return (not self.regressions and not self.broken and not self.stale
                and not self.failed_traps)

    def counts(self) -> dict[str, int]:
        return {
            "total": len(self.results),
            "holding": len(self.holding),
            "ready_to_close": len(self.ready_to_close),
            "regressions": len(self.regressions),
            "broken": len(self.broken),
            "stale": len(self.stale),
            "missing": len(self.missing),
        }


def run_matrix(
    gaps: list[Gap],
    config: Config,
    runner: ProbeRunner | None = None,
    timeout_s: int = 120,
    workers: int = 4,
) -> Matrix:
    runner = runner or ShellProbeRunner()
    measurable = [g for g in gaps if g.needs_probe]

    # Freshness per (suite, artifact-class). Source scans and artifact hashes
    # are cached across gaps so the whole fleet costs one scan per class.
    cache: dict = {}
    fresh: dict[tuple[str, str], FreshnessReport] = {}
    for g in measurable:
        key = (g.suite, g.reads)
        if key not in fresh:
            fresh[key] = gap_freshness(config, g.suite, g.reads, cache)

    def measure(g: Gap) -> ProbeResult:
        report = fresh[(g.suite, g.reads)]
        if report.state is Freshness.STALE:
            # Do not run the probe — its verdict would be untrustworthy.
            return ProbeResult(g, Outcome.STALE, None, 0.0, report.detail)
        return runner.run(g, timeout_s)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(measure, measurable))

    # The trap pass (§ probe contract): closed gaps' probes are regression
    # guards forever — re-prove each can still FAIL by running its kept
    # counterexamples. Skipped entirely for instances predating the
    # discipline ([gate] traps = "off").
    trap_results: list[TrapResult] = []
    if config.traps == "required":
        guards = [g for g in measurable
                  if g.status is Status.CLOSED
                  and fresh[(g.suite, g.reads)].state is not Freshness.STALE]
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for batch in pool.map(lambda g: run_traps(g, runner, timeout_s), guards):
                trap_results.extend(batch)

    results.sort(key=lambda r: (not r.is_regression, r.outcome is not Outcome.STALE,
                                not r.is_ready_to_close, r.gap.id))
    trap_results.sort(key=lambda t: (t.ok, t.gap.id, t.trap))
    return Matrix(results=tuple(results), freshness=tuple(fresh.values()),
                  trap_results=tuple(trap_results))
