"""Fast e2e for the opt-in gate verdict cache (recurvelib.core.probe_cache +
run_matrix(use_cache=True)).

The live gate cold-loads Mathlib per probe (~9 s each), so proving the cache there
costs ~9 min/run. This test proves the cache *logic* end-to-end in well under a
second: a fake project on disk (real check/source/trap files, so keys are computed
for real) + a spy ProbeRunner that counts invocations (no Lean). It asserts:

  1. populate then hit — a second run with unchanged (check, sources) invokes the
     runner ZERO times and returns the identical verdicts;
  2. source invalidation — editing a transitively-imported source re-runs the probe;
  3. check invalidation — editing the check file re-runs it;
  4. soundness — a BROKEN verdict is never cached (re-runs every time);
  5. trap batch — an all-RED trap batch is cached; a non-RED batch is not;
  6. off by default — use_cache=False always runs the probe.

Freshness is forced FRESH (monkeypatched) so the test isolates the cache key/store
logic from the Config/olean-freshness axis — which is exactly the layer the live
gate's own freshness check already governs before the cache is consulted.
"""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from recurvelib.core import conformance
from recurvelib.core.conformance import run_matrix
from recurvelib.core.freshness import Freshness, FreshnessReport
from recurvelib.core.model import Gap, GapClass, Severity, Status
from recurvelib.core.probe import Outcome, ProbeResult, TrapResult


class SpyRunner:
    """Counts run() calls and returns a scripted verdict. Thread-safe (run_matrix
    runs probes in a pool)."""

    def __init__(self, probe_outcome: Outcome = Outcome.GREEN,
                 trap_outcome: Outcome = Outcome.RED):
        self.calls = 0
        self.trap_calls = 0
        self._lock = threading.Lock()
        self.probe_outcome = probe_outcome
        self.trap_outcome = trap_outcome

    def run(self, gap: Gap, timeout_s: int = 120, trap_fixture: Path | None = None,
            iso_fixture: Path | None = None) -> ProbeResult:
        with self._lock:
            if trap_fixture is not None:
                self.trap_calls += 1
                oc = self.trap_outcome
            else:
                self.calls += 1
                oc = self.probe_outcome
        code = {Outcome.GREEN: 0, Outcome.RED: 1}.get(oc, 2)
        return ProbeResult(gap, oc, code, 0.01, "spy")


class _Cfg:
    """Minimal stand-in for Config: run_matrix touches only `.traps`, and passes
    `config` to gap_freshness (monkeypatched here)."""
    traps = "required"


@pytest.fixture
def project(tmp_path: Path, monkeypatch):
    """A fake tree: NavierStokes/Foo.lean (source) + a demo suite with one closed
    gap whose check imports NavierStokes.Foo and carries one trap fixture."""
    root = tmp_path
    (root / "NavierStokes").mkdir()
    (root / "NavierStokes" / "Foo.lean").write_text("import Mathlib\ntheorem foo : True := trivial\n")

    probes = root / ".recurve" / "claims" / "demo" / "probes"
    (probes / "checks").mkdir(parents=True)
    (probes / "foo.sh").write_text("#!/usr/bin/env bash\nexit 0\n")
    (probes / "checks" / "foo.check.lean").write_text(
        "import NavierStokes.Foo\nexample : True := foo\n")
    (probes / "foo.trap" / "sorried").mkdir(parents=True)
    (probes / "foo.trap" / "sorried" / "Module.lean").write_text("theorem foo : True := by sorry\n")

    # Force FRESH so the cache logic is what's under test (the live gate's own
    # freshness check already governs staleness before the cache is consulted).
    monkeypatch.setattr(
        conformance, "gap_freshness",
        lambda config, suite, scope, cache: FreshnessReport(suite, scope, Freshness.FRESH, "forced"))

    gap = Gap(id="DEMO-1", suite="demo", title="t", gap_class=GapClass.FRICTION,
              status=Status.CLOSED, severity=Severity.COSMETIC, evidence=(),
              observed="", smallest_fix="t", unlocks="", reads="none",
              covers=(), probe=probes / "foo.sh", source_file=root / "gaps.yaml")
    assert gap.needs_probe
    return root, gap, probes


def _cache_file(root: Path) -> Path:
    return root / ".recurve" / "cache" / "gate-verdicts.json"


def test_populate_then_hit_runs_zero_probes(project):
    root, gap, _ = project
    cfg = _Cfg()

    spy1 = SpyRunner()
    m1 = run_matrix([gap], cfg, runner=spy1, workers=2, use_cache=True)
    assert spy1.calls == 1, "first run must actually run the probe"
    assert spy1.trap_calls == 1, "first run must run the trap"
    assert _cache_file(root).exists(), "cache file should be written"
    v1 = m1.results[0].outcome

    spy2 = SpyRunner()
    m2 = run_matrix([gap], cfg, runner=spy2, workers=2, use_cache=True)
    assert spy2.calls == 0, "second run must be an all-hit: probe not re-run"
    assert spy2.trap_calls == 0, "second run must be an all-hit: trap not re-run"
    assert m2.results[0].outcome is v1, "cached verdict must match"
    assert m2.gate_ok == m1.gate_ok


def test_source_edit_invalidates(project):
    root, gap, _ = project
    cfg = _Cfg()
    run_matrix([gap], cfg, runner=SpyRunner(), workers=2, use_cache=True)  # populate

    # Edit a transitively-imported source -> key changes -> probe re-runs.
    (root / "NavierStokes" / "Foo.lean").write_text("import Mathlib\ntheorem foo : True := by trivial\n")
    spy = SpyRunner()
    run_matrix([gap], cfg, runner=spy, workers=2, use_cache=True)
    assert spy.calls == 1, "a changed transitive source must invalidate the cache"


def test_check_edit_invalidates(project):
    root, gap, probes = project
    cfg = _Cfg()
    run_matrix([gap], cfg, runner=SpyRunner(), workers=2, use_cache=True)  # populate

    (probes / "checks" / "foo.check.lean").write_text(
        "import NavierStokes.Foo\nexample : True := foo  -- edited\n")
    spy = SpyRunner()
    run_matrix([gap], cfg, runner=spy, workers=2, use_cache=True)
    assert spy.calls == 1, "a changed check file must invalidate the cache"


def test_broken_never_cached(project):
    root, gap, _ = project
    cfg = _Cfg()
    run_matrix([gap], cfg, runner=SpyRunner(probe_outcome=Outcome.BROKEN),
               workers=2, use_cache=True)  # populate with BROKEN
    spy = SpyRunner(probe_outcome=Outcome.BROKEN)
    run_matrix([gap], cfg, runner=spy, workers=2, use_cache=True)
    assert spy.calls == 1, "BROKEN must never be cached — always re-run"


def test_non_red_trap_batch_not_cached(project):
    root, gap, _ = project
    cfg = _Cfg()
    # A trap that comes back GREEN (a gate failure) must not be cached away.
    run_matrix([gap], cfg, runner=SpyRunner(trap_outcome=Outcome.GREEN),
               workers=2, use_cache=True)
    spy = SpyRunner(trap_outcome=Outcome.GREEN)
    run_matrix([gap], cfg, runner=spy, workers=2, use_cache=True)
    assert spy.trap_calls == 1, "a non-RED trap batch must never be cached"


def test_off_by_default_always_runs(project):
    root, gap, _ = project
    cfg = _Cfg()
    run_matrix([gap], cfg, runner=SpyRunner(), workers=2, use_cache=True)  # populate
    spy = SpyRunner()
    run_matrix([gap], cfg, runner=spy, workers=2, use_cache=False)
    assert spy.calls == 1, "use_cache=False must ignore the cache and run"
