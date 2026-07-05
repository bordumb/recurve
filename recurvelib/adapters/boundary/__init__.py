"""The concrete Boundary adapters (docs/plans/eval-arm-kernel.md K3)."""
from __future__ import annotations

from recurvelib.loop.boundary import EnforcedBoundary, OpenBoundary
from recurvelib.adapters.registry import build_boundary_registry

BOUNDARY_ADAPTERS = build_boundary_registry({
    "enforced": EnforcedBoundary,
    "open": OpenBoundary,
})
