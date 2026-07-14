"""Explore mode — the falsifier engine and its load-bearing calibration invariant.

End-to-end: real `run.sh` falsifiers in a tmp dir, driven through the real
`ShellFalsifierRunner`, so the exit-code contract and the §2 invariant are
exercised for real (not mocked).
"""

from __future__ import annotations

from pathlib import Path

from recurvelib.core.conjecture import (
    Attack,
    ConjectureVerdict,
    FalsifierKind,
    run_falsifiers,
)

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
