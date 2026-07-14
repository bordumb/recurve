"""Explore mode — the falsifier engine and its load-bearing calibration invariant.

End-to-end: real `run.sh` falsifiers in a tmp dir, driven through the real
`ShellFalsifierRunner`, so the exit-code contract and the §2 invariant are
exercised for real (not mocked).
"""

from __future__ import annotations

from pathlib import Path

from recurvelib.core.conjecture import (
    Attack,
    ConjectureResult,
    ConjectureVerdict,
    FalsifierKind,
    FalsifierResult,
    SurvivalProfile,
    frontier_rank,
    promotion_status,
    run_falsifiers,
)
from recurvelib.core.model import Gap, GapClass, Severity, Status

# run.sh templates (falsifier exit contract: 0 KILLED, 1 SURVIVED, other BROKEN).
# RECURVE_FALSIFY_TARGET is set only during calibration (attack the decoy).
_KILLS_DECOY_SURVIVES_REAL = (
    "#!/usr/bin/env bash\n"
    'if [ -n "${RECURVE_FALSIFY_TARGET:-}" ]; then exit 0; fi\n'  # KILLED the decoy
    "exit 1\n"                                                    # SURVIVED the conjecture
)
_SURVIVES_EVERYTHING = "#!/usr/bin/env bash\nexit 1\n"   # can't even kill its decoy → uncalibrated
_KILLS_EVERYTHING = "#!/usr/bin/env bash\nexit 0\n"      # kills decoy AND the real conjecture
_CRASHES = "#!/usr/bin/env bash\nexit 7\n"               # BROKEN


def _mk_falsifier(battery: Path, name: str, script: str,
                  kind: FalsifierKind = FalsifierKind.NUMERIC,
                  with_decoy: bool = True) -> None:
    d = battery / name
    d.mkdir(parents=True)
    (d / "run.sh").write_text(script)
    (d / "kind").write_text(kind.value + "\n")
    if with_decoy:
        (d / "decoy").mkdir()


def _battery(tmp_path: Path) -> Path:
    b = tmp_path / "the-conjecture.falsifiers"
    b.mkdir()
    return b


# --- the load-bearing invariant (§2): no survival without a demonstrated kill ---

def test_uncalibrated_battery_is_broken(tmp_path: Path):
    """A falsifier that cannot KILL its own decoy has not shown it can fail-right.
    A battery of only such falsifiers is BROKEN — never SURVIVING. This is the
    line between exploration and a guess-amplifier."""
    b = _battery(tmp_path)
    _mk_falsifier(b, "toothless", _SURVIVES_EVERYTHING)  # "survives" its decoy too
    res = run_falsifiers(b, tmp_path)
    assert res.verdict is ConjectureVerdict.BROKEN
    assert res.profile.count == 0
    only = res.results[0]
    assert only.calibrated is False
    assert "calibration" in only.detail.lower()


def test_no_decoy_is_uncalibrated(tmp_path: Path):
    """A falsifier with no calibration decoy cannot demonstrate teeth → not admissible."""
    b = _battery(tmp_path)
    _mk_falsifier(b, "no-decoy", _KILLS_EVERYTHING, with_decoy=False)
    res = run_falsifiers(b, tmp_path)
    assert res.verdict is ConjectureVerdict.BROKEN
    assert res.results[0].calibrated is False


def test_uncalibrated_does_not_inflate_a_real_survival(tmp_path: Path):
    """An uncalibrated falsifier is inert: it can neither falsify nor pad the
    survival profile. One genuine calibrated survivor still carries the verdict."""
    b = _battery(tmp_path)
    _mk_falsifier(b, "toothless", _SURVIVES_EVERYTHING)
    _mk_falsifier(b, "real-numeric", _KILLS_DECOY_SURVIVES_REAL, FalsifierKind.NUMERIC)
    res = run_falsifiers(b, tmp_path)
    assert res.verdict is ConjectureVerdict.SURVIVING
    assert res.profile.count == 1  # the toothless one contributes nothing
    assert res.profile.by_kind == {"numeric": 1}


# --- the happy paths ---

def test_calibrated_survivor_is_surviving(tmp_path: Path):
    b = _battery(tmp_path)
    _mk_falsifier(b, "numeric-search", _KILLS_DECOY_SURVIVES_REAL, FalsifierKind.NUMERIC)
    res = run_falsifiers(b, tmp_path)
    assert res.verdict is ConjectureVerdict.SURVIVING
    assert res.results[0].calibrated is True
    assert res.results[0].against_target is Attack.SURVIVED
    assert res.profile.count == 1


def test_calibrated_killer_falsifies(tmp_path: Path):
    """A calibrated falsifier that also kills the real conjecture → FALSIFIED
    (a dead lead is real information, not a failure)."""
    b = _battery(tmp_path)
    _mk_falsifier(b, "finds-counterexample", _KILLS_EVERYTHING, FalsifierKind.FUZZ)
    res = run_falsifiers(b, tmp_path)
    assert res.verdict is ConjectureVerdict.FALSIFIED
    assert res.results[0].calibrated is True
    assert res.results[0].against_target is Attack.KILLED


def test_empty_battery_is_broken(tmp_path: Path):
    b = _battery(tmp_path)  # exists but holds no falsifiers
    res = run_falsifiers(b, tmp_path)
    assert res.verdict is ConjectureVerdict.BROKEN
    assert "no one tried to kill" in res.detail

    missing = tmp_path / "absent.falsifiers"  # not even a dir
    assert run_falsifiers(missing, tmp_path).verdict is ConjectureVerdict.BROKEN


# --- grading (§3): the profile reports strength, never a single bit ---

def test_survival_profile_is_graded(tmp_path: Path):
    b = _battery(tmp_path)
    _mk_falsifier(b, "a-numeric", _KILLS_DECOY_SURVIVES_REAL, FalsifierKind.NUMERIC)
    _mk_falsifier(b, "b-adversary", _KILLS_DECOY_SURVIVES_REAL, FalsifierKind.ADVERSARY)
    res = run_falsifiers(b, tmp_path)
    assert res.verdict is ConjectureVerdict.SURVIVING
    assert res.profile.count == 2
    assert res.profile.strength == FalsifierKind.ADVERSARY.strength  # max, not sum
    assert res.profile.by_kind == {"numeric": 1, "adversary": 1}


def test_one_kill_among_survivors_still_falsifies(tmp_path: Path):
    """A single calibrated counterexample kills the lead regardless of how many
    other falsifiers it survived — falsification dominates survival."""
    b = _battery(tmp_path)
    _mk_falsifier(b, "survives", _KILLS_DECOY_SURVIVES_REAL, FalsifierKind.NUMERIC)
    _mk_falsifier(b, "kills", _KILLS_EVERYTHING, FalsifierKind.SYMBOLIC)
    res = run_falsifiers(b, tmp_path)
    assert res.verdict is ConjectureVerdict.FALSIFIED


def test_calibrated_but_broken_on_real_is_broken(tmp_path: Path):
    """Kills its decoy (calibrated) but crashes on the real conjecture → no evidence
    gathered → BROKEN, not a vacuous survival."""
    b = _battery(tmp_path)
    script = (
        "#!/usr/bin/env bash\n"
        'if [ -n "${RECURVE_FALSIFY_TARGET:-}" ]; then exit 0; fi\n'  # KILLED the decoy
        "exit 7\n"                                                    # BROKEN on the real conjecture
    )
    _mk_falsifier(b, "flaky", script)
    res = run_falsifiers(b, tmp_path)
    assert res.verdict is ConjectureVerdict.BROKEN
    assert res.results[0].calibrated is True
    assert res.results[0].against_target is Attack.BROKEN


# --- model hook: a claim carrying a falsifier battery IS a conjecture (M3) ---

def _gap(tmp_path: Path, with_battery: bool) -> Gap:
    probes = tmp_path / "probes"
    probes.mkdir(exist_ok=True, parents=True)
    probe = probes / "c-1.sh"
    probe.write_text("#!/usr/bin/env bash\nexit 1\n")
    if with_battery:
        f = probes / "c-1.falsifiers" / "num"
        f.mkdir(parents=True)
        (f / "run.sh").write_text(_KILLS_DECOY_SURVIVES_REAL)
        (f / "kind").write_text("numeric\n")
        (f / "decoy").mkdir()
    return Gap(
        id="C-1", suite="s", title="a conjecture", gap_class=GapClass.FRICTION,
        status=Status.OPEN, severity=Severity.FEATURE, evidence=(), observed="",
        smallest_fix="", unlocks="", reads="ledger", covers=(), probe=probe,
        source_file=tmp_path / "gaps.yaml",
    )


def test_gap_is_conjecture_iff_it_has_a_battery(tmp_path: Path):
    plain = _gap(tmp_path / "a", with_battery=False)
    assert plain.is_conjecture is False
    assert plain.falsifier_dir is not None  # the path exists as a property
    assert not plain.falsifier_dir.exists()

    conj = _gap(tmp_path / "b", with_battery=True)
    assert conj.is_conjecture is True
    assert conj.falsifier_dir.name == "c-1.falsifiers"


def test_empty_battery_dir_is_not_a_conjecture(tmp_path: Path):
    """A .falsifiers/ dir that holds no falsifier subdirs doesn't make a conjecture."""
    conj = _gap(tmp_path, with_battery=True)
    for sub in list(conj.falsifier_dir.iterdir()):
        (sub / "run.sh").unlink()
        (sub / "kind").unlink()
        (sub / "decoy").rmdir()
        sub.rmdir()
    assert not conj.is_conjecture


# --- frontier helpers (M4): promotion + the reward ranking ---

def _surviving(*kinds: FalsifierKind) -> ConjectureResult:
    survivors = tuple(
        FalsifierResult(f"f{i}", k, True, Attack.SURVIVED) for i, k in enumerate(kinds)
    )
    prof = SurvivalProfile(survivors)
    return ConjectureResult(ConjectureVerdict.SURVIVING, survivors, prof, prof.render())


def test_promotion_status():
    surv = _surviving(FalsifierKind.NUMERIC)
    assert promotion_status(True, surv) == "PROMOTED"        # probe proven → jackpot
    assert promotion_status(False, surv) == "SURVIVING"
    assert promotion_status(False, None) == "BROKEN"


def test_frontier_rank_prefers_strength_then_count():
    strong = _surviving(FalsifierKind.PARTIAL_PROOF)             # strength 4, count 1
    many_weak = _surviving(FalsifierKind.NUMERIC, FalsifierKind.NUMERIC)  # strength 1, count 2
    # strongest oracle wins over sheer count — a partial-proof survival outranks two numeric ones
    assert frontier_rank(strong) > frontier_rank(many_weak)
    # among equal strength, more survivals ranks higher
    a = _surviving(FalsifierKind.ADVERSARY)
    b = _surviving(FalsifierKind.ADVERSARY, FalsifierKind.ADVERSARY)
    assert frontier_rank(b) > frontier_rank(a)
