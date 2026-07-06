"""core/dataset_registry.py — one dataset pin, looked up by name.

Three experiment manifests copy-paste the identical BigCodeBench pin
(`local`/`revision`/`hash`/`count`); nothing enforces they agree. This reads
`datasets/registry.toml` and resolves a manifest's `[tasks]` pin either from
an inline pin (today's shape, kept working unchanged) or from
`[tasks].dataset = "<name>"` (a lookup into the registry) -- one source of
truth for a name a manifest can opt into without any existing manifest
having to change.
"""

from __future__ import annotations

import tomllib
from pathlib import Path


class DatasetRegistryError(ValueError):
    """A manifest names a registry dataset that doesn't exist, or gives
    neither an inline pin nor a registry name."""


def load_registry(path: str | Path) -> dict[str, dict]:
    return tomllib.loads(Path(path).read_text())


def resolve_dataset_pin(manifest: dict, registry: dict[str, dict]) -> dict:
    """The `local`/`revision`/`hash`/`count` pin this manifest's `[tasks]`
    means -- inline wins if present (today's shape, unchanged); otherwise
    `[tasks].dataset` is looked up in `registry`, loud on a miss."""
    tasks = manifest.get("tasks", {})
    if tasks.get("local"):
        return {k: tasks[k] for k in ("local", "revision", "hash", "count") if k in tasks}
    name = tasks.get("dataset")
    if not name:
        raise DatasetRegistryError(
            "[tasks] has no inline pin (local/hash) and no [tasks].dataset name to look up")
    if name not in registry:
        known = ", ".join(sorted(registry))
        raise DatasetRegistryError(f"[tasks].dataset names unknown dataset {name!r}; known: {known}")
    return dict(registry[name])
