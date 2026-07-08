"""SUFF-6 counterexample: writes the scaffold probe unconditionally, with no check for
whether the target path already belongs to a DIFFERENT existing claim — the exact bug that
silently overwrote SUB-PROD-YOUNG-ENORM's real probe/check/trap files on a case-insensitive-
but-preserving filesystem before this guard existed."""

import re
from pathlib import Path


def _slug(text):
    parts = [p for p in re.split(r"[^0-9A-Za-z]+", text) if p]
    return "-".join(parts) or "cut"


def write_lean_assembly_scaffold(cut, config):
    sc = config.suite_for(cut.suite)
    slug = _slug(cut.assembly_id)
    probe_path = sc.dir / "probes" / f"{slug}.sh"
    # BUG: no collision check — just writes, clobbering whatever is already there.
    probe_path.write_text("#!/usr/bin/env bash\nexit 1\n")
