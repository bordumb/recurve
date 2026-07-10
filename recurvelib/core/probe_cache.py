"""Verdict cache for the conformance matrix — sound by construction.

A probe's verdict (GREEN/RED) is a deterministic function of two things: the
bytes of its check file, and the built oleans that check imports. If neither
changed since the last run, the verdict cannot have changed and the probe need
not re-run. That is the single biggest lever on gate wall-clock, because every
probe cold-loads Mathlib (~9 s, ~5.5 GB RSS measured), so the fleet re-pays that
load ~N times per gate even when nothing it depends on moved.

Soundness (the whole point of the gate is that it cannot be fooled):

  * The cache key hashes the check-file bytes, the trap-fixture bytes (for trap
    runs), AND the content-hash of every PROJECT module the check transitively
    imports. A changed dependency changes the key, so a stale cache can never
    mask a regression. Mathlib/Init/Std modules are pinned by the toolchain and
    excluded from the key (they do not change within a run).
  * Only trustworthy verdicts are cached — GREEN and RED. BROKEN / STALE / SKIP
    are never stored, so a transient failure never sticks.
  * Opt-in: callers pass ``use_cache=True``. With it off (the default) the gate
    behaves exactly as before — a full, uncached re-run — so the arbiter's
    guarantee is unchanged unless a caller deliberately trades a little latency
    margin for speed. Run the full uncached gate at merge / report / baseline.

The key is computed against the same oleans the probe's own staleness guard
checks, so a hit means "same check, same artifacts" — the exact condition under
which re-running would reproduce the verdict.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from recurvelib.core.model import Gap

_IMPORT_RE = re.compile(r"^\s*import\s+([A-Za-z0-9_.]+)", re.M)
# Project-local module root; everything else (Mathlib, Init, Std, Lean) is
# toolchain-pinned and cannot change within a run, so it is excluded from the key.
_PROJECT_ROOT = "NavierStokes"


def _check_path(gap: Gap) -> Path | None:
    """probes/<slug>.sh pairs with probes/checks/<slug>.check.lean."""
    if gap.probe is None:
        return None
    return gap.probe.parent / "checks" / (gap.probe.stem + ".check.lean")


def target_root(gap: Gap) -> Path | None:
    """The tree root (holds NavierStokes/ and .lake/), derived from the probe's
    known layout <root>/.recurve/claims/<suite>/probes/<slug>.sh."""
    if gap.probe is None:
        return None
    parents = gap.probe.parents
    return parents[4] if len(parents) > 4 else None


def _project_imports(text: str) -> list[str]:
    return [m for m in _IMPORT_RE.findall(text) if m.split(".")[0] == _PROJECT_ROOT]


def _module_lean(root: Path, mod: str) -> Path:
    return root / (mod.replace(".", "/") + ".lean")


def transitive_project_modules(check_path: Path, root: Path) -> set[str]:
    """BFS the project import graph from a check file. Mathlib imports terminate
    the walk (excluded). Returns every reachable NavierStokes.* module."""
    seen: set[str] = set()
    try:
        queue = _project_imports(check_path.read_text())
    except OSError:
        return seen
    while queue:
        mod = queue.pop()
        if mod in seen:
            continue
        seen.add(mod)
        try:
            queue.extend(_project_imports(_module_lean(root, mod).read_text()))
        except OSError:
            pass
    return seen


def build_source_shas(root: Path) -> dict[str, str]:
    """Content-hash every project SOURCE .lean once (shared across all probes so
    the fleet costs one hashing pass, not one per probe).

    We key on sources, NOT oleans: the gate's ``rebuild = "lake build"`` step can
    rewrite an olean byte-differently between runs (oleans are not guaranteed
    reproducible), which would break every cache hit. A source file is stable
    unless someone edits it. Soundness of a hit then rests on the freshness check
    the matrix already runs BEFORE consulting the cache: a hit is honoured only
    when the gap's suite is FRESH (its oleans are current with its sources), so an
    unchanged source + a FRESH suite + a pinned toolchain ⇒ an unchanged verdict.
    A source edit is caught either by a key mismatch (olean rebuilt) or by STALE
    freshness (olean not yet rebuilt) — never silently."""
    base = root / _PROJECT_ROOT
    out: dict[str, str] = {}
    if not base.is_dir():
        return out
    for lean in base.rglob("*.lean"):
        rel = lean.relative_to(base).with_suffix("")
        mod = _PROJECT_ROOT + "." + str(rel).replace("/", ".")
        try:
            out[mod] = hashlib.sha256(lean.read_bytes()).hexdigest()
        except OSError:
            pass
    return out


def probe_key(gap: Gap, root: Path, source_shas: dict[str, str],
              trap_fixture: Path | None = None) -> str | None:
    """SHA256 of (check bytes ⊕ trap-fixture bytes ⊕ the source hashes of every
    project module the check transitively imports). None if the check is absent."""
    check = _check_path(gap)
    if check is None or not check.exists():
        return None
    h = hashlib.sha256()
    h.update(check.read_bytes())
    if trap_fixture is not None:
        try:
            h.update((trap_fixture / "Module.lean").read_bytes())
        except OSError:
            h.update(b"NO_FIXTURE")
    for mod in sorted(transitive_project_modules(check, root)):
        h.update(mod.encode())
        h.update(b"=")
        h.update(source_shas.get(mod, "MISSING").encode())
        h.update(b"\0")
    return h.hexdigest()


def trap_batch_key(gap: Gap, root: Path, source_shas: dict[str, str]) -> str | None:
    """Key for a gap's whole trap batch: check bytes ⊕ every fixture's Module.lean
    bytes ⊕ the transitive project source hashes. Same fixtures + same sources ⇒
    same RED verdicts (under the FRESH-suite guard the matrix applies)."""
    check = _check_path(gap)
    if check is None or not check.exists():
        return None
    h = hashlib.sha256()
    h.update(b"TRAPS\0")
    h.update(check.read_bytes())
    for fx in sorted(gap.traps, key=lambda p: p.name):
        h.update(fx.name.encode())
        h.update(b"\0")
        try:
            h.update((fx / "Module.lean").read_bytes())
        except OSError:
            h.update(b"NO_FIXTURE")
    for mod in sorted(transitive_project_modules(check, root)):
        h.update(mod.encode())
        h.update(b"=")
        h.update(source_shas.get(mod, "MISSING").encode())
        h.update(b"\0")
    return h.hexdigest()


class VerdictCache:
    """A JSON store mapping entry-id → {key, outcome, exit_code, detail}. Only
    GREEN/RED verdicts (and all-RED trap batches) are ever written; anything else
    re-runs every time."""

    def __init__(self, path: Path):
        self.path = path
        self.data: dict[str, dict] = {}
        try:
            loaded = json.loads(path.read_text())
            if isinstance(loaded, dict):
                self.data = loaded
        except (OSError, json.JSONDecodeError):
            pass

    def get(self, entry_id: str, key: str) -> dict | None:
        e = self.data.get(entry_id)
        return e if (e and e.get("key") == key and
                     e.get("outcome") in ("GREEN", "RED")) else None

    def put(self, entry_id: str, key: str, outcome: str,
            exit_code: int | None, detail: str) -> None:
        if outcome not in ("GREEN", "RED"):
            return
        self.data[entry_id] = {"key": key, "outcome": outcome,
                               "exit_code": exit_code, "detail": detail}

    def get_traps(self, entry_id: str, key: str) -> list[dict] | None:
        e = self.data.get(entry_id)
        if e and e.get("key") == key and isinstance(e.get("traps"), list):
            return e["traps"]
        return None

    def put_traps(self, entry_id: str, key: str, traps: list[dict]) -> None:
        # Cache a trap batch ONLY if every fixture came back RED — the guarantee
        # the trap pass exists to hold. A non-RED trap is a gate failure and must
        # never be cached away.
        if traps and all(t.get("outcome") == "RED" for t in traps):
            self.data[entry_id] = {"key": key, "traps": traps}

    def save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self.data, indent=1, sort_keys=True))
        except OSError:
            pass
