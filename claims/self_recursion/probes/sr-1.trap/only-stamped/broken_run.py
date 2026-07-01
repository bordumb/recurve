"""BROKEN counterexample for SR-1: a resolver that only ever returns the stamped
target's workflow. On the self-host repo there is no `.recurve/workflows/`, so
this returns a path that does not exist — `recurve run` could never run on the
recurve repo itself."""

from pathlib import Path  # noqa: F401  (kept for parity with the real module)


def resolve_workflow(cfg, parallel=False):
    name = "burndown-parallel.sh" if parallel else "burndown.sh"
    return cfg.assets_dir / "workflows" / name
