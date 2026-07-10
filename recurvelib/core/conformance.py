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

from recurvelib.core.config import Config
from recurvelib.core.freshness import Freshness, FreshnessReport, gap_freshness
from recurvelib.core.model import Gap, Status
from recurvelib.core.probe import Outcome, ProbeResult, ProbeRunner, ShellProbeRunner, TrapResult, run_traps


def is_waived_skip(result: ProbeResult) -> bool:
    """A probe that reported its external oracle absent (SKIP, exit 3) on a claim
    that DECLARED an `oracle_waiver` — a visible, non-blocking "not applicable
    here". A SKIP without a declared waiver is NOT honored: it blocks the gate
    like a broken probe, so a probe can never silently dodge the gate."""
    return result.outcome is Outcome.SKIP and bool(result.gap.oracle_waiver)


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
        # BROKEN, plus an UNdeclared skip: a probe cannot dodge the gate by
        # reporting its oracle absent unless the claim declared an oracle_waiver.
        return [r for r in self.results
                if r.outcome is Outcome.BROKEN
                or (r.outcome is Outcome.SKIP and not r.gap.oracle_waiver)]

    @property
    def skipped(self) -> list[ProbeResult]:
        """Probes whose external oracle was absent AND whose claim declared an
        oracle_waiver — non-blocking, but surfaced as visible debt."""
        return [r for r in self.results if is_waived_skip(r)]

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
            "skipped": len(self.skipped),
        }


def run_matrix(
    gaps: list[Gap],
    config: Config,
    runner: ProbeRunner | None = None,
    timeout_s: int = 120,
    workers: int = 4,
    use_cache: bool = False,
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

    # Opt-in verdict cache. A probe's GREEN/RED is a deterministic function of
    # its check file and the oleans it imports; an unchanged (check, oleans) pair
    # cannot change verdict, so it need not re-run — the biggest lever on gate
    # wall-clock, since every probe cold-loads Mathlib. Keys are precomputed
    # single-threaded and verdicts stored AFTER the pools (never inside a worker),
    # so there is no write race. Off by default: with use_cache=False the gate is
    # the old full, uncached re-run, byte for byte. See core/probe_cache.py.
    vcache = None
    pkeys: dict[str, str | None] = {}
    tkeys: dict[str, str | None] = {}
    _root = _shas = None
    if use_cache and measurable:
        from recurvelib.core.probe_cache import (
            VerdictCache, build_source_shas, probe_key, target_root)
        _root = next((target_root(g) for g in measurable if target_root(g) is not None), None)
        if _root is not None:
            _shas = build_source_shas(_root)
            vcache = VerdictCache(_root / ".recurve" / "cache" / "gate-verdicts.json")
            for g in measurable:
                pkeys[g.id] = probe_key(g, _root, _shas)

    def measure(g: Gap) -> ProbeResult:
        report = fresh[(g.suite, g.reads)]
        if report.state is Freshness.STALE:
            # Do not run the probe — its verdict would be untrustworthy.
            return ProbeResult(g, Outcome.STALE, None, 0.0, report.detail)
        # Cache hit is honoured ONLY when the suite is FRESH — the source-keyed
        # verdict is trustworthy exactly when the oleans are current with the
        # sources (UNKNOWN freshness could hide a stale/missing olean).
        if vcache is not None and report.state is Freshness.FRESH:
            k = pkeys.get(g.id)
            if k is not None:
                hit = vcache.get(g.id, k)
                if hit is not None:
                    return ProbeResult(g, Outcome(hit["outcome"]), hit.get("exit_code"),
                                       0.0, "cached ⏎ " + hit.get("detail", ""))
        return runner.run(g, timeout_s)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(measure, measurable))

    if vcache is not None:
        for r in results:
            k = pkeys.get(r.gap.id)
            if k is not None and r.outcome in (Outcome.GREEN, Outcome.RED):
                vcache.put(r.gap.id, k, r.outcome.value, r.exit_code, r.detail)

    # The trap pass (§ probe contract): closed gaps' probes are regression
    # guards forever — re-prove each can still FAIL by running its kept
    # counterexamples. Skipped entirely for instances predating the
    # discipline ([gate] traps = "off").
    trap_results: list[TrapResult] = []
    if config.traps == "required":
        # A probe whose external oracle was absent (SKIP) can't run its traps
        # either — exclude it so a not-applicable claim doesn't fail the trap pass.
        skipped_ids = {r.gap.id for r in results if r.outcome is Outcome.SKIP}
        guards = [g for g in measurable
                  if g.status is Status.CLOSED
                  and fresh[(g.suite, g.reads)].state is not Freshness.STALE
                  and g.id not in skipped_ids]
        if vcache is not None:
            from recurvelib.core.probe_cache import trap_batch_key
            for g in guards:
                tkeys[g.id] = trap_batch_key(g, _root, _shas)

        def guarded(g: Gap) -> list[TrapResult]:
            if vcache is not None and fresh[(g.suite, g.reads)].state is Freshness.FRESH:
                k = tkeys.get(g.id)
                if k is not None:
                    # Distinct entry-id from the probe verdict (same gap.id) so the
                    # two never overwrite each other in the store.
                    cached = vcache.get_traps(g.id + "::traps", k)
                    if cached is not None:
                        return [TrapResult(g, t["trap"], Outcome(t["outcome"]),
                                           "cached ⏎ " + t.get("detail", "")) for t in cached]
            return run_traps(g, runner, timeout_s)

        with ThreadPoolExecutor(max_workers=workers) as pool:
            for batch in pool.map(guarded, guards):
                trap_results.extend(batch)

        if vcache is not None:
            for g in guards:
                k = tkeys.get(g.id)
                if k is None:
                    continue
                batch = [{"trap": t.trap, "outcome": t.outcome.value, "detail": t.detail}
                         for t in trap_results if t.gap.id == g.id]
                vcache.put_traps(g.id + "::traps", k, batch)

    if vcache is not None:
        vcache.save()

    results.sort(key=lambda r: (not r.is_regression, r.outcome is not Outcome.STALE,
                                not r.is_ready_to_close, r.gap.id))
    trap_results.sort(key=lambda t: (t.ok, t.gap.id, t.trap))
    return Matrix(results=tuple(results), freshness=tuple(fresh.values()),
                  trap_results=tuple(trap_results))
