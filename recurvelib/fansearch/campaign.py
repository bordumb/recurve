"""Runs proposal/scoring rounds for a registered domain, archiving every
candidate tried. A new best-scoring candidate is verified against the real
target repo (does its compiled claim actually elaborate, kernel-clean) via
a scratch file -- nothing is written to that repo here. Writing a verified
candidate into the target repo's own ledger for good is a separate,
explicit step (`promote`), never automatic.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from recurvelib.adapters.proxy import PROXY_ADAPTERS


class CampaignError(ValueError):
    pass


@dataclass(frozen=True)
class CampaignSummary:
    domain: str
    rounds: int
    records: int
    gate_confirmed: int
    stopped_reason: str


def archive_path(cfg, domain: str) -> Path:
    p = cfg.state_dir / "fansearch" / domain / "archive.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def read_archive(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _append_archive(path: Path, entry: dict) -> None:
    with path.open("a") as f:
        f.write(json.dumps(entry, sort_keys=True) + "\n")


def domain_module(domain: str):
    if domain not in PROXY_ADAPTERS or domain == "off":
        raise CampaignError(f"unknown or non-searchable domain {domain!r}; "
                            f"known: {', '.join(sorted(k for k in PROXY_ADAPTERS if k != 'off'))}")
    cls = PROXY_ADAPTERS[domain]
    return cls, sys.modules[cls.__module__]


def verify_compiled_claim(ns_repo: str, draft, timeout_s: int = 120) -> tuple[bool, str]:
    """Read-only: does `draft.theorem_lean` elaborate, kernel-clean, against
    the real target repo, without writing anything there."""
    full = (
        "import NavierStokes.Shells.Basic\n\n"
        "namespace NavierStokes.Shells\n\n"
        f"{draft.theorem_lean}\n"
        "end NavierStokes.Shells\n\n"
        "open NavierStokes.Shells\n\n"
        f"{draft.statement_lean}\n"
    )
    with tempfile.TemporaryDirectory() as tmp:
        lean_file = Path(tmp) / "Check.lean"
        lean_file.write_text(full)
        try:
            r = subprocess.run(["lake", "env", "lean", str(lean_file)], cwd=ns_repo,
                               capture_output=True, text=True, timeout=timeout_s)
        except Exception as e:
            return False, str(e)
        if r.returncode != 0:
            for line in (r.stdout + r.stderr).splitlines():
                if "error" in line.lower():
                    return False, line.strip()[:200]
            return False, "elaboration failed (no error line found)"
        if "sorryAx" in r.stdout or "sorryAx" in r.stderr:
            return False, "proof depends on sorryAx"
        return True, "kernel-clean"


def run_campaign(cfg, domain: str, ns_repo: str | None, budget_seconds: float = 60.0,
                 dry_generations: int = 3, seed0: int = 0,
                 n_choices: tuple = (4, 5, 6, 7, 8),
                 promotion_threshold: float = 0.6) -> CampaignSummary:
    cls, mod = domain_module(domain)
    propose = getattr(mod, "propose_candidate", None)
    compile_fn = getattr(mod, "compile_to_claim", None)
    if propose is None:
        raise CampaignError(f"domain {domain!r} has no propose_candidate -- not searchable")

    path = archive_path(cfg, domain)
    existing = read_archive(path)
    best_score = max((e["proxy_score"] for e in existing), default=-1.0)

    proxy = cls()
    round_n = len(existing)
    dry, records, gate_confirmed = 0, 0, 0
    start = time.time()
    stopped_reason = "dry_generations"

    while True:
        if time.time() - start >= budget_seconds:
            stopped_reason = "budget"
            break
        if dry >= dry_generations:
            stopped_reason = "dry_generations"
            break

        seed = seed0 + round_n
        N = n_choices[round_n % len(n_choices)]
        candidate = propose(seed=seed, N=N)
        score = proxy.score(candidate)
        entry = {
            "round": round_n, "seed": seed, "N": candidate.N,
            "b": list(candidate.b), "d": list(candidate.d),
            "proxy_score": score.value, "signal": score.signal,
            "is_record": False, "gate_status": "untested", "claim_id": None,
            "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        }

        is_record = score.value > best_score and score.value >= promotion_threshold
        if is_record and compile_fn is not None and ns_repo:
            best_score = score.value
            records += 1
            entry["is_record"] = True
            draft = compile_fn(candidate)
            ok, detail = verify_compiled_claim(ns_repo, draft)
            entry["gate_detail"] = detail
            if ok:
                entry["gate_status"] = "gate_confirmed"
                gate_confirmed += 1
                dry = 0
            else:
                entry["gate_status"] = "gate_rejected"
                dry += 1
        else:
            dry += 1

        _append_archive(path, entry)
        round_n += 1

    return CampaignSummary(domain=domain, rounds=round_n - len(existing), records=records,
                           gate_confirmed=gate_confirmed, stopped_reason=stopped_reason)
