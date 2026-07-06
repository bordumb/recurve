"""core/schema.py — the manifest as a validated, versioned declaration.

A manifest is supposed to be a complete, honest declaration of an experiment:
read it and know exactly what will run. Left unvalidated it can name a
benchmark nothing dispatches on, omit the hash that lets a dataset refuse
drift, or leave a `budgets` list ambiguous between dollars and tokens --
each a real, silent gap found in the manifests already on disk. This module
raises `ManifestError` at plan time -- before any resolution, any dataset
fetch, any oracle-env lock -- so a bad manifest fails loud and precisely
instead of surfacing as a mystery mid-run.
"""

from __future__ import annotations

SCHEMA_VERSION = 1

# A per-cell budget above this, under budget_unit="usd", is far more likely a
# token count left mislabeled as dollars than a genuine five-figure spend.
_USD_SANITY_MAX = 100.0


class ManifestError(ValueError):
    """A manifest fails validation -- required key missing, an unknown
    benchmark name, or an ambiguous/out-of-range budget unit."""


def _require(manifest: dict, table: str, key: str):
    section = manifest.get(table)
    if not isinstance(section, dict) or key not in section:
        raise ManifestError(f"manifest missing required key: [{table}].{key}")
    return section[key]


def resolve_budget_unit(manifest: dict) -> str:
    """`[matrix].budget_unit`, defaulting to `"usd"` (the spend gate's own
    unit) -- the ONE discriminator between a dollar-budget and a
    token-budget experiment. No manifest may be silent about which it
    means; an explicit value outside the two known units fails loud."""
    unit = manifest.get("matrix", {}).get("budget_unit", "usd")
    if unit not in ("usd", "tokens"):
        raise ManifestError(f'[matrix].budget_unit must be "usd" or "tokens", got {unit!r}')
    return unit


def validate_manifest(manifest: dict, *, known_benchmarks) -> None:
    """Required tables/keys, an enumerated `benchmark`, a dataset reference
    that can actually refuse drift, and a budget list that cannot be
    ambiguous about its own unit. `known_benchmarks` is the live
    `core.benchmark.known_names()` set -- an unknown name fails here, not
    three calls deep into `resolve()`."""
    _require(manifest, "experiment", "name")
    models = _require(manifest, "matrix", "models")
    arms = _require(manifest, "matrix", "arms")
    budgets = _require(manifest, "matrix", "budgets")
    _require(manifest, "matrix", "seeds")
    for table, key, value in (("matrix", "models", models), ("matrix", "arms", arms),
                              ("matrix", "budgets", budgets)):
        if not isinstance(value, list) or not value:
            raise ManifestError(f"[{table}].{key} must be a non-empty list")

    benchmark = _require(manifest, "tasks", "benchmark")
    if benchmark not in known_benchmarks:
        known = ", ".join(sorted(known_benchmarks))
        raise ManifestError(f"[tasks].benchmark names unknown benchmark {benchmark!r}; known: {known}")

    tasks = manifest["tasks"]
    if tasks.get("local"):
        if not tasks.get("hash"):
            raise ManifestError(
                "[tasks].local is set but [tasks].hash is missing -- "
                "an inline pin without a hash cannot refuse on drift")
    elif not tasks.get("dataset") and not tasks.get("revision"):
        raise ManifestError(
            "[tasks] must set one of: local+hash (inline pin), "
            "dataset (a datasets/registry.toml name), or revision (live fetch)")

    unit = resolve_budget_unit(manifest)
    if unit == "usd":
        for b in budgets:
            if b > _USD_SANITY_MAX:
                raise ManifestError(
                    f"[matrix].budgets contains {b}, over the ${_USD_SANITY_MAX:.0f} sanity "
                    f'bound for budget_unit="usd" -- this looks like a token count; set '
                    f'[matrix].budget_unit = "tokens" if that\'s what\'s intended, or fix '
                    f"the value if it's a mistyped dollar amount")
