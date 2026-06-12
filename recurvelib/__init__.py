"""recurvelib — the engine for claims-driven recursive software improvement.

A *claim* is a falsifiable statement about a target, recorded in three
synchronized layers: prose (GAPS.md), ledger (gaps.yaml), and an executable
probe. The engine burns down the gap between claimed and proven: probes emit
GREEN/RED/BROKEN verdicts, a fleet-wide matrix gates promotion, freshness
checks refuse to trust stale artifacts, and coverage keeps prose and ledger
from drifting apart.

Everything that varies between targets lives in `recurve.toml` (see config).
Everything else — the gap schema, the probe exit-code contract, status
semantics, the gate conjunction — is frozen core. Do not make it configurable.
"""

ENGINE_VERSION = "0.1.0"

# The gap-schema version this engine ships and enforces. Targets may pin a
# major version in recurve.toml ([project] schema = "1"); a mismatch is a
# validation failure, never a silent reinterpretation.
SCHEMA_VERSION = "1.0.0"

from pathlib import Path as _Path


def resource_dir(name: str) -> _Path:
    """Locate a shipped resource tree (templates/, schema/, packs/).

    Source checkout: a sibling of recurvelib/. Installed wheel: bundled
    under recurvelib/_assets/ (see pyproject force-include). Missing both
    is a broken install — fail loud, never guess.
    """
    here = _Path(__file__).resolve().parent
    for candidate in (here.parent / name, here / "_assets" / name):
        if candidate.is_dir():
            return candidate
    raise FileNotFoundError(
        f"recurve resource {name!r} found neither beside recurvelib/ nor in "
        f"recurvelib/_assets/ — the install is broken"
    )
