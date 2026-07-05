"""calibration.py — the structural defense against a harness that flatters itself.

Every defect in this pipeline's design fails in one direction: a correct real
solution turned into an error, read as an oracle failure, inflating
shipped-bad-work — the paper's own headline. Inspection alone can't catch the
next one. Calibration can: grade all 148 canonical solutions through the finished
oracle path, and since canonical solutions cannot be wrong, any bug in that class
drops the pass rate. So no paid cell runs while the calibration for the current
oracle env is RED.

The teeth are two:
  - `derive_calibration` REFUSES to produce a calibration when too many canonical
    solutions fail — a broken harness must not be able to "pass" by excluding
    everything. The residual few genuinely-flaky tasks become REGISTERED,
    content-hashed exclusions, and the per-task timeout is derived from the
    canonical p99 (measured under the real runtime, not guessed).
  - `calibration_admits_spend` refuses at every boundary: no calibration, a
    calibration for a different oracle env (stale key), a different dataset, an
    edited exclusion list, or a pass rate below the bar.

Keyed by (oracle_env_hash, dataset_hash), so a changed oracle or dataset
auto-invalidates a stale calibration instead of being silently reused.
"""

from __future__ import annotations

import hashlib
import json
import math

# A run with more than this fraction of canonical solutions failing is a harness
# bug, not a set of exclusions — refuse to calibrate rather than launder it.
DEFAULT_MAX_EXCLUSION_FRAC = 0.10
# Multiplier on the canonical p99 latency → the per-task oracle timeout. Under
# emulation a fixed guess turns slow passes into errors; derive it instead.
DEFAULT_TIMEOUT_K = 3.0


class CalibrationError(RuntimeError):
    """Calibration cannot be produced, or does not admit spending — refused."""


def exclusion_content_hash(exclusions) -> str:
    """Order-invariant content hash of the registered exclusion list, so editing
    it after calibration is detectable."""
    canon = json.dumps(sorted(exclusions), separators=(",", ":"))
    return "exh:" + hashlib.sha256(canon.encode()).hexdigest()[:16]


def _p99(values) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    idx = max(0, min(len(s) - 1, math.ceil(0.99 * len(s)) - 1))
    return s[idx]


def derive_calibration(oracle_env_hash: str, dataset_hash: str, results: dict, *,
                       timeout_k: float = DEFAULT_TIMEOUT_K,
                       max_exclusion_frac: float = DEFAULT_MAX_EXCLUSION_FRAC) -> dict:
    """Derive a calibration from canonical-solution grading results.

    `results`: {task_id: {"verdict": pass|fail|error|timeout, "seconds": float}}.
    A canonical solution that does not pass is either genuinely environment-flaky
    (a registered exclusion) or evidence of a harness bug. If the non-pass
    fraction exceeds `max_exclusion_frac`, refuse — a broken harness must not pass
    by excluding everything. The timeout is the canonical p99 × k (ceil)."""
    tids = sorted(results)
    n = len(tids)
    if n == 0:
        raise CalibrationError("no calibration results — nothing to calibrate")
    passing = [t for t in tids if results[t].get("verdict") == "pass"]
    exclusions = [t for t in tids if results[t].get("verdict") != "pass"]
    if len(exclusions) / n > max_exclusion_frac:
        raise CalibrationError(
            f"{len(exclusions)}/{n} canonical solutions did not pass "
            f"(> {max_exclusion_frac:.0%}) — canonical solutions cannot be wrong, "
            f"so this is a harness bug, not a set of exclusions; refusing to "
            f"calibrate (fix the oracle, do not launder it into exclusions)")
    timeout = int(math.ceil(_p99([results[t]["seconds"] for t in passing]) * timeout_k))
    return {
        "oracle_env_hash": oracle_env_hash,
        "dataset_hash": dataset_hash,
        "n_tasks": n,
        "raw_pass_rate": len(passing) / n,
        "exclusions": sorted(exclusions),
        "exclusion_hash": exclusion_content_hash(exclusions),
        "resolved_timeout": max(1, timeout),
        "verdicts": {t: results[t].get("verdict") for t in tids},
    }


def calibration_admits_spend(cal: dict | None, *, oracle_env_hash: str,
                             dataset_hash: str, exclusions_content,
                             min_pass_rate: float = 1.0 - DEFAULT_MAX_EXCLUSION_FRAC) -> dict:
    """Return the calibration if it admits spending on this (oracle, dataset), or
    raise CalibrationError. This is the gate with teeth: no paid cell runs unless
    a calibration measured THIS oracle env against THIS dataset, its exclusion
    list is untouched, and its pass rate clears the bar."""
    if not cal:
        raise CalibrationError(
            "no calibration for this oracle env — refusing to spend before the "
            "oracle is calibrated on the canonical solutions")
    if cal.get("oracle_env_hash") != oracle_env_hash:
        raise CalibrationError(
            f"calibration is for oracle {cal.get('oracle_env_hash')!r}, current is "
            f"{oracle_env_hash!r} — stale; re-calibrate before spending")
    if cal.get("dataset_hash") != dataset_hash:
        raise CalibrationError(
            f"calibration measured dataset {cal.get('dataset_hash')!r}, current is "
            f"{dataset_hash!r} — refusing")
    if exclusion_content_hash(exclusions_content) != cal.get("exclusion_hash"):
        raise CalibrationError(
            "the registered exclusion list was edited after calibration (content "
            "hash mismatch) — refusing to spend against tampered exclusions")
    if cal.get("raw_pass_rate", 0.0) < min_pass_rate:
        raise CalibrationError(
            f"calibration pass rate {cal.get('raw_pass_rate')} < {min_pass_rate} — "
            f"a latent harness bug; refusing to spend")
    return cal
