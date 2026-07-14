"""Explore mode — the falsifier engine (invert the trap).

A *trap* is a known-bad a probe must **reject**: seeing it come back RED proves
the probe can fail, and that is what licenses trusting its GREEN. A trap guards a
claim we believe TRUE.

A *falsifier* is the mirror image, pointed at a **conjecture** we do not yet know:
a genuine attempt to construct a counterexample. If it lands, the conjecture is
FALSIFIED and pruned; if a battery of *potent* falsifiers all miss, the conjecture
SURVIVES — a trustworthy lead, because it withstood real attempts to destroy it.

The load-bearing invariant (`docs/plans/explore-mode.md` §2): **a survival counts
only from falsifiers that have demonstrably killed a seeded "decoy"** — a known-false
variant the falsifier MUST refute to prove it has teeth. This is the exact mirror of
"a probe is only trusted once its trap has been seen RED." Without it, "survived N
falsifiers" is vacuous (nobody tried), and explore mode is a guess-amplifier. So a
battery with no calibrated falsifier is BROKEN, never SURVIVING.

This module is deliberately decoupled from the `Gap`/ledger model — it operates on a
`falsifiers/` directory (the structural inverse of a probe's `.trap/` dir). How a
conjecture is *declared* in the ledger and *surfaced* in the matrix is a later
milestone (§9); the calibration engine here is Milestone 2, built first and provably
un-bypassable.

Falsifier exit-code convention (a falsifier is a `run.sh`, cwd = the suite dir, handed
the target-to-attack via env `RECURVE_FALSIFY_TARGET` — set to the decoy for
calibration, unset to attack the real conjecture):

    0  KILLED    — a counterexample was found (the conjecture/decoy is refuted)
    1  SURVIVED  — no counterexample found
    other/timeout — BROKEN (a crash is never read as a verdict)
"""

from __future__ import annotations

import os
import subprocess
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Protocol


class FalsifierKind(str, Enum):
    """Graded by how sound the oracle underneath it is — a survival against a
    numeric proxy is a hint; against a kernel-checked partial proof it is strong
    (mirrors the framework paper's graded-guarantee spectrum)."""

    NUMERIC = "numeric"              # simulate + measure — unsound proxy
    FUZZ = "fuzz"                    # random-instance counterexample search
    SYMBOLIC = "symbolic"           # symbolic sign / monotonicity check
    ADVERSARY = "adversary"         # an agent constructing a counterexample
    PARTIAL_PROOF = "partial-proof" # kernel-checked restricted-case refutation attempt

    @property
    def strength(self) -> int:
        return {
            FalsifierKind.NUMERIC: 1,
            FalsifierKind.FUZZ: 2,
            FalsifierKind.SYMBOLIC: 2,
            FalsifierKind.ADVERSARY: 3,
            FalsifierKind.PARTIAL_PROOF: 4,
        }[self]


class Attack(str, Enum):
    """The outcome of running one falsifier against one target."""

    KILLED = "KILLED"      # exit 0 — a counterexample was found
    SURVIVED = "SURVIVED"  # exit 1 — none found
    BROKEN = "BROKEN"      # anything else — could not decide

    icon = property(lambda self: {"KILLED": "✗", "SURVIVED": "○", "BROKEN": "▲"}[self.value])


class ConjectureVerdict(str, Enum):
    SURVIVING = "SURVIVING"  # >=1 calibrated falsifier, and every calibrated one SURVIVED
    FALSIFIED = "FALSIFIED"  # a calibrated falsifier KILLED it (a dead lead — real information)
    BROKEN = "BROKEN"        # the battery has no teeth: no falsifier killed its decoy (or empty)
    # PROMOTED is not produced here — it is the closure loop's job: a conjecture whose
    # *probe* goes kernel-clean GREEN leaves this axis and becomes an ordinary closed claim.


@dataclass(frozen=True)
class Falsifier:
    """One kill-attempt: an executable, its declared kind, and the calibration
    decoy it must KILL to be admissible."""

    name: str
    exe: Path
    kind: FalsifierKind
    decoy: Path | None   # the known-false variant this falsifier must refute


@dataclass(frozen=True)
class FalsifierResult:
    name: str
    kind: FalsifierKind
    calibrated: bool          # did it KILL its decoy? (uncalibrated ⟹ contributes nothing)
    against_target: Attack    # its verdict on the *real* conjecture
    detail: str = ""

    @property
    def is_survival(self) -> bool:
        return self.calibrated and self.against_target is Attack.SURVIVED


@dataclass(frozen=True)
class SurvivalProfile:
    """The graded evidence a conjecture has accrued — a profile, never a single
    'safe' bit. Only calibrated survivors are counted."""

    survivors: tuple[FalsifierResult, ...]

    @property
    def count(self) -> int:
        return len(self.survivors)

    @property
    def by_kind(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for r in self.survivors:
            out[r.kind.value] = out.get(r.kind.value, 0) + 1
        return out

    @property
    def strength(self) -> int:
        """The strongest oracle the conjecture has survived (0 = nothing)."""
        return max((r.kind.strength for r in self.survivors), default=0)

    def render(self) -> str:
        if not self.survivors:
            return "no calibrated survivors"
        parts = ", ".join(f"{n}×{k}" for k, n in sorted(self.by_kind.items()))
        weak = " (unsound-proxy only)" if self.strength <= FalsifierKind.NUMERIC.strength else ""
        return f"survived {self.count} calibrated · strength {self.strength} · {parts}{weak}"


@dataclass(frozen=True)
class ConjectureResult:
    verdict: ConjectureVerdict
    results: tuple[FalsifierResult, ...]
    profile: SurvivalProfile
    detail: str = ""


class FalsifierRunner(Protocol):
    def run(self, exe: Path, target: Path | None, suite_dir: Path,
            timeout_s: int) -> tuple[Attack, str]: ...


class ShellFalsifierRunner:
    """Runs a `run.sh` falsifier, mapping exit codes to an `Attack`. The target to
    attack (a decoy, for calibration) is handed over via `RECURVE_FALSIFY_TARGET`;
    unset means 'attack the real conjecture'."""

    def run(self, exe: Path, target: Path | None, suite_dir: Path,
            timeout_s: int = 120) -> tuple[Attack, str]:
        if not exe.exists():
            return Attack.BROKEN, f"falsifier executable absent: {exe}"
        env = {**os.environ, "NO_COLOR": "1"}
        if target is not None:
            env["RECURVE_FALSIFY_TARGET"] = str(target)
        else:
            env.pop("RECURVE_FALSIFY_TARGET", None)
        try:
            proc = subprocess.run(
                ["bash", str(exe)],
                cwd=suite_dir,
                capture_output=True,
                text=True,
                timeout=timeout_s,
                env=env,
            )
        except subprocess.TimeoutExpired:
            return Attack.BROKEN, f"timed out after {timeout_s}s"
        attack = {0: Attack.KILLED, 1: Attack.SURVIVED}.get(proc.returncode, Attack.BROKEN)
        return attack, _tail(proc.stdout, proc.stderr)


def _tail(stdout: str, stderr: str, lines: int = 4) -> str:
    blob = (stdout + stderr).strip().splitlines()
    return " ⏎ ".join(blob[-lines:]) if blob else ""


def falsifier_dir_for(probe: Path) -> Path:
    """`probes/<name>.sh` pairs with `probes/<name>.falsifiers/` — the structural
    inverse of `<name>.trap/`."""
    return probe.parent / (probe.stem + ".falsifiers")


def discover_falsifiers(falsifier_dir: Path) -> tuple[Falsifier, ...]:
    """One subdirectory per falsifier: `run.sh`, a one-line `kind`, and a `decoy/`
    (the calibration target it must KILL). An unreadable `kind` defaults to the
    weakest (`numeric`) so a mislabelled falsifier can never over-claim strength."""
    if not falsifier_dir.is_dir():
        return ()
    out: list[Falsifier] = []
    for sub in sorted(p for p in falsifier_dir.iterdir() if p.is_dir()):
        kind_file = sub / "kind"
        try:
            kind = FalsifierKind(kind_file.read_text().strip()) if kind_file.exists() else FalsifierKind.NUMERIC
        except ValueError:
            kind = FalsifierKind.NUMERIC
        decoy = sub / "decoy"
        out.append(Falsifier(
            name=sub.name,
            exe=sub / "run.sh",
            kind=kind,
            decoy=decoy if decoy.is_dir() else None,
        ))
    return tuple(out)


def run_falsifiers(falsifier_dir: Path, suite_dir: Path,
                   runner: FalsifierRunner | None = None,
                   timeout_s: int = 120) -> ConjectureResult:
    """Score a conjecture on the second gradient. Enforces the §2 calibration
    invariant: every falsifier must first KILL its decoy; only calibrated
    falsifiers count toward FALSIFIED or SURVIVING. A battery with no calibrated
    falsifier — nobody with demonstrated teeth tried — is BROKEN, never SURVIVING."""
    runner = runner or ShellFalsifierRunner()
    falsifiers = discover_falsifiers(falsifier_dir)
    if not falsifiers:
        return ConjectureResult(
            ConjectureVerdict.BROKEN, (), SurvivalProfile(()),
            "no falsifier battery — a lead no one tried to kill is not a lead",
        )

    results: list[FalsifierResult] = []
    for f in falsifiers:
        # Calibration first: a falsifier with no decoy, or one that fails to KILL its
        # decoy, has not demonstrated it can fail-the-right-way and is not admissible.
        if f.decoy is None:
            results.append(FalsifierResult(f.name, f.kind, False, Attack.BROKEN,
                                           "no calibration decoy — cannot demonstrate teeth"))
            continue
        decoy_attack, decoy_detail = runner.run(f.exe, f.decoy, suite_dir, timeout_s)
        if decoy_attack is not Attack.KILLED:
            results.append(FalsifierResult(
                f.name, f.kind, False, Attack.BROKEN,
                f"failed calibration: did not KILL its decoy (got {decoy_attack.value}) — {decoy_detail}",
            ))
            continue
        # Admissible — now let it fire at the real conjecture.
        attack, detail = runner.run(f.exe, None, suite_dir, timeout_s)
        results.append(FalsifierResult(f.name, f.kind, True, attack, detail))

    return _verdict(tuple(results))


def _verdict(results: tuple[FalsifierResult, ...]) -> ConjectureResult:
    calibrated = [r for r in results if r.calibrated]
    if not calibrated:
        return ConjectureResult(
            ConjectureVerdict.BROKEN, results, SurvivalProfile(()),
            "battery has no teeth: no falsifier KILLED its calibration decoy",
        )
    killed = [r for r in calibrated if r.against_target is Attack.KILLED]
    if killed:
        return ConjectureResult(
            ConjectureVerdict.FALSIFIED, results, SurvivalProfile(()),
            f"falsified by {killed[0].name} ({killed[0].kind.value})",
        )
    survivors = tuple(r for r in calibrated if r.against_target is Attack.SURVIVED)
    if not survivors:
        # calibrated, none killed, but none cleanly survived either (all BROKEN on the
        # real target) — no evidence was actually gathered.
        return ConjectureResult(
            ConjectureVerdict.BROKEN, results, SurvivalProfile(()),
            "calibrated falsifiers could not decide against the conjecture (all BROKEN)",
        )
    profile = SurvivalProfile(survivors)
    return ConjectureResult(ConjectureVerdict.SURVIVING, results, profile, profile.render())
