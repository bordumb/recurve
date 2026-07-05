"""Oracle tier — what actually backed a claim's GREEN, derived, never hand-set.

Every claim's GREEN carries a tier reflecting which passes actually ran
against it: `self_probe < trap_hardened < fuzz_measured < adversary_reviewed
< adversary_cross_model < differential_checked_llm <
differential_checked_mechanical < kernel_verified`. Mechanical checks (no
model in the loop) are a categorically different kind of evidence than
LLM-backed checks (risk-reduced, never risk-free) — the vocabulary's ordering
makes that split explicit, not just a stronger point on one ladder.

Tier is derived from two sources, never asserted: the gap's static shape
(does it have a trap? a `reference`?) and a **tier-evidence log**
(`.recurve/state/tier_evidence/<suite>.jsonl`) recording whether a check
actually *ran* against this gap — `drill --diff`/`--fuzz` and (once
`recurvelib.adapters` exists) an adversary pass append here. This is a third,
narrow log, distinct from the ledger (`gaps.yaml`, verified observations) and
from the run-record dataset (`drill`'s own docstring: "leaves no trace in the
ledger or run records" — that promise is about the cost/reward training set,
not about tier provenance, which has nowhere else to live).

`Gap.parse` (`recurvelib.core.model`) refuses a literal `tier:` key outright
— this module is the ONLY place a tier is ever computed.
"""
from __future__ import annotations

import fnmatch
import json
from enum import Enum
from pathlib import Path

from recurvelib.core.config import Config
from recurvelib.core.model import Gap, Status


class OracleTier(str, Enum):
    """Declared in increasing strength order — enum iteration order IS the
    rank order (`_RANK` below), so adding a new tier is one line, in place."""

    SELF_PROBE = "self_probe"
    TRAP_HARDENED = "trap_hardened"
    FUZZ_MEASURED = "fuzz_measured"
    ADVERSARY_REVIEWED = "adversary_reviewed"
    ADVERSARY_CROSS_MODEL = "adversary_cross_model"
    DIFFERENTIAL_CHECKED_LLM = "differential_checked_llm"
    DIFFERENTIAL_CHECKED_MECHANICAL = "differential_checked_mechanical"
    KERNEL_VERIFIED = "kernel_verified"


_RANK = {t: i for i, t in enumerate(OracleTier)}

# A reference whose own source shells out to one of these is presumed to
# invoke a model in its own construction — never mechanical, however a config
# author labels it. Declaration (the allowlist) is necessary but not
# sufficient; this scan is what makes "mechanical" verifiable rather than
# asserted (R1's anti-gaming trap).
_LLM_MARKERS = (
    "AGENT_CMD", "claude -p", "anthropic", "openai", "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY", "chat.completions", "messages.create",
)


def _evidence_path(cfg: Config, suite: str) -> Path:
    return cfg.state_dir / "tier_evidence" / f"{suite}.jsonl"


def record_evidence(cfg: Config, suite: str, gap_id: str, check: str, **fields) -> None:
    """Append one tier-evidence record: `check` names what ran (`fuzz`,
    `diff`, `adversary`, ...); `fields` carries the check-specific detail
    (`ran`, `disagreement`, `mode`, `verified_cross_model`, ...). Append-only,
    never mutated — the same discipline receipts use, one level narrower in
    scope."""
    path = _evidence_path(cfg, suite)
    path.parent.mkdir(parents=True, exist_ok=True)
    rec = {"gap": gap_id, "check": check, **fields}
    with path.open("a") as f:
        f.write(json.dumps(rec, sort_keys=True) + "\n")


def load_evidence(cfg: Config, suite: str, gap_id: str) -> list[dict]:
    """Every recorded evidence line for one gap, in append order. Empty when
    the log doesn't exist yet — that's the honest default: no check has ever
    run beyond the trap itself."""
    path = _evidence_path(cfg, suite)
    if not path.exists():
        return []
    out = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        if rec.get("gap") == gap_id:
            out.append(rec)
    return out


def is_mechanical_reference(gap: Gap, cfg: Config) -> bool:
    """A reference is mechanical ground truth iff it matches a `[gate]
    mechanical_references` allowlist glob AND its own source contains no
    LLM/agent-invocation marker. Both conditions are required: the allowlist
    alone would be a bare declaration (asserted, not verified); the content
    scan alone would have no config-driven default. Missing/unreadable
    references are never mechanical (fail closed)."""
    if gap.reference is None or not gap.reference.exists():
        return False
    allow = getattr(cfg, "mechanical_references", ())
    if not allow:
        return False
    try:
        rel = str(gap.reference.relative_to(gap.suite_dir))
    except ValueError:
        rel = gap.reference.name
    if not any(fnmatch.fnmatch(rel, pat) for pat in allow):
        return False
    try:
        text = gap.reference.read_text()
    except OSError:
        return False
    return not any(marker in text for marker in _LLM_MARKERS)


def _max_tier(a: OracleTier, b: OracleTier) -> OracleTier:
    return a if _RANK[a] >= _RANK[b] else b


def derive_tier(gap: Gap, cfg: Config, evidence: list[dict] | None = None) -> OracleTier:
    """Derive the oracle tier from the gap's static shape plus its recorded
    tier-evidence. Never reads a `tier` field — there isn't one; `Gap.parse`
    refuses it outright."""
    if evidence is None:
        evidence = load_evidence(cfg, gap.suite, gap.id)

    tier = OracleTier.TRAP_HARDENED if gap.traps else OracleTier.SELF_PROBE

    if any(e.get("check") == "fuzz" and e.get("ran") for e in evidence):
        tier = _max_tier(tier, OracleTier.FUZZ_MEASURED)

    adversary_runs = [e for e in evidence if e.get("check") == "adversary" and e.get("ran")]
    if any(e.get("mode") in ("same_model", "cross_model") for e in adversary_runs):
        tier = _max_tier(tier, OracleTier.ADVERSARY_REVIEWED)
    if any(e.get("mode") == "cross_model" and e.get("verified_cross_model") for e in adversary_runs):
        tier = _max_tier(tier, OracleTier.ADVERSARY_CROSS_MODEL)

    diff_ran = any(e.get("check") == "diff" and e.get("ran") for e in evidence)
    if gap.reference is not None and diff_ran:
        if is_mechanical_reference(gap, cfg):
            tier = _max_tier(tier, OracleTier.DIFFERENTIAL_CHECKED_MECHANICAL)
        else:
            tier = _max_tier(tier, OracleTier.DIFFERENTIAL_CHECKED_LLM)

    return tier


def needs_oracle_advisory(gap: Gap, cfg: Config, evidence: list[dict] | None = None) -> bool:
    """R3: a claim closing on `self_probe`/`trap_hardened` alone — no
    reference, no adversary evidence, no declared `oracle_waiver` — surfaces
    an advisory. Advisory only; never blocks GREEN (`§2.8`: legible, not
    refused)."""
    if gap.status is not Status.CLOSED:
        return False
    if gap.oracle_waiver:
        return False
    tier = derive_tier(gap, cfg, evidence)
    return tier in (OracleTier.SELF_PROBE, OracleTier.TRAP_HARDENED)
