"""Writes one archived candidate into the target repo's own ledger for
good: appends its theorem to the target source, writes a check/trap/probe
triple matching that repo's own shell-probe convention, adds a draft
ledger entry, rebuilds, and baselines there. This is the one step in this
package that mutates another repo's history -- never automatic, always a
single explicit call naming one archived candidate.
"""
from __future__ import annotations

import json
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from recurvelib.fansearch.campaign import archive_path, domain_module, read_archive

_DEFINITION_PINS = """-- definition pins (defeq): the bound model cannot be quietly redefined
example : lam = (2 : ℝ) := rfl
example : wavenumber = fun n : ℕ => lam ^ (n : ℝ) := rfl
example : dissipationFactor = fun (α : ℝ) (n : ℕ) => lam ^ (2 * α * (n : ℝ)) := rfl
example : shellRHS = fun (ν α : ℝ) (u : ℕ → ℝ) (n : ℕ) =>
    -(ν * dissipationFactor α n * u n) + wavenumber n * u (n - 1) ^ 2
      - wavenumber (n + 1) * (u n * u (n + 1)) := rfl
"""

_TRAP_MODEL_HEADER = """import Mathlib

namespace NavierStokes.Shells

def lam : ℝ := 2

noncomputable def wavenumber (n : ℕ) : ℝ := lam ^ (n : ℝ)

noncomputable def dissipationFactor (α : ℝ) (n : ℕ) : ℝ := lam ^ (2 * α * (n : ℝ))

noncomputable def shellRHS (ν α : ℝ) (u : ℕ → ℝ) (n : ℕ) : ℝ :=
  -(ν * dissipationFactor α n * u n) + wavenumber n * u (n - 1) ^ 2
    - wavenumber (n + 1) * (u n * u (n + 1))
"""


class PromoteError(ValueError):
    pass


@dataclass(frozen=True)
class PromoteResult:
    claim_id: str
    ok: bool
    detail: str


def _sanitize_ident(claim_id: str) -> str:
    return re.sub(r"[^a-z0-9_]", "_", claim_id.lower())


def promote_candidate(cfg, domain: str, ns_repo: str, round_index: int,
                      claim_id: str, timeout_s: int = 300) -> PromoteResult:
    _, mod = domain_module(domain)
    compile_fn = getattr(mod, "compile_to_claim", None)
    if compile_fn is None:
        raise PromoteError(f"domain {domain!r} has no compile_to_claim")
    candidate_cls = getattr(mod, "Candidate")

    archive = read_archive(archive_path(cfg, domain))
    entries = [e for e in archive if e["round"] == round_index]
    if not entries:
        raise PromoteError(f"no archived candidate at round {round_index} for domain {domain!r}")
    entry = entries[-1]
    candidate = candidate_cls(N=entry["N"], b=tuple(entry["b"]), d=tuple(entry["d"]))

    ident = _sanitize_ident(claim_id)
    theorem_name = f"dyadic_candidate_{ident}_dissipative"
    draft = compile_fn(candidate, theorem_name=theorem_name)

    ns = Path(ns_repo)
    basic = ns / "NavierStokes" / "Shells" / "Basic.lean"
    marker = "\nend NavierStokes.Shells\n"
    text = basic.read_text()
    if marker not in text:
        raise PromoteError(f"expected marker {marker!r} not found in {basic}")
    basic.write_text(text.replace(marker, f"\n{draft.theorem_lean}\n{marker}", 1))

    probe_id = ident
    checks_dir = ns / ".recurve" / "claims" / "shells" / "probes" / "checks"
    trap_dir = ns / ".recurve" / "claims" / "shells" / "probes" / f"{probe_id}.trap" / "mangled"
    probes_dir = ns / ".recurve" / "claims" / "shells" / "probes"
    checks_dir.mkdir(parents=True, exist_ok=True)
    trap_dir.mkdir(parents=True, exist_ok=True)

    (checks_dir / f"{probe_id}.check.lean").write_text(
        f"import NavierStokes.Shells.Basic\n\nopen NavierStokes.Shells\n\n"
        f"{_DEFINITION_PINS}\n{draft.statement_lean}"
    )
    (trap_dir / "Module.lean").write_text(
        f"{_TRAP_MODEL_HEADER}\n{draft.trap_lean}\nend NavierStokes.Shells\n"
    )
    (probes_dir / f"{probe_id}.sh").write_text(
        f'#!/usr/bin/env bash\nexec "$(dirname "${{BASH_SOURCE[0]}}")/_lean_probe.sh" {probe_id}\n'
    )
    (probes_dir / f"{probe_id}.sh").chmod(0o755)

    draft_path = ns / ".recurve" / "claims" / "shells" / "gaps.draft.yaml"
    draft_entry = (
        f"- id: {claim_id}\n"
        f"  title: single-active-shell dissipation, a fansearch-discovered candidate "
        f"(N={candidate.N})\n"
        f"  class: missing-surface\n"
        f"  severity: friction\n"
        f"  covers:\n  - {claim_id}\n"
        f"  smallest_fix: '{draft.smallest_fix_note}'\n"
        f"  probe: probes/{probe_id}.sh\n"
    )
    if draft_path.exists():
        draft_path.write_text(draft_path.read_text().rstrip("\n") + "\n\n" + draft_entry)
    else:
        draft_path.write_text(
            "# gaps.draft.yaml -- schema-shaped intentions awaiting the baseline ceremony.\n"
            + draft_entry
        )

    build = subprocess.run(["lake", "build", "NavierStokes"], cwd=ns_repo,
                           capture_output=True, text=True, timeout=timeout_s)
    if build.returncode != 0:
        return PromoteResult(claim_id, False, f"lake build failed: {(build.stdout + build.stderr)[-300:]}")

    baseline = subprocess.run(["recurve", "baseline", "shells"], cwd=ns_repo,
                              capture_output=True, text=True, timeout=timeout_s)
    detail = (baseline.stdout + baseline.stderr).strip()
    if baseline.returncode != 0 or "promoted-closed" not in detail:
        return PromoteResult(claim_id, False, f"baseline did not close: {detail[-300:]}")

    promotions = Path(ns_repo) / ".recurve" / "state" / "fansearch" / "promotions.jsonl"
    promotions.parent.mkdir(parents=True, exist_ok=True)
    with promotions.open("a") as f:
        f.write(json.dumps({
            "gap": claim_id, "domain": domain, "proxy_score": entry["proxy_score"],
            "round": round_index, "promoted_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        }, sort_keys=True) + "\n")

    return PromoteResult(claim_id, True, detail[-200:])
