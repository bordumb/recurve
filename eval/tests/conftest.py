"""Shared pytest setup for the eval suite.

Puts `eval/` on `sys.path` (so `import src.*` / `import evallib.*` resolve),
registers every benchmark once (so `resolve`/`known_names` see them), and
provides fixtures that skip a test when its out-of-tree inputs — the gitignored
benchmark datasets, or a docker daemon — are not present in this checkout.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

EVAL = Path(__file__).resolve().parents[1]
if str(EVAL) not in sys.path:
    sys.path.insert(0, str(EVAL))

# Importing a benchmark module registers it in the benchmark registry.
import src.benchmarks.bigcodebench  # noqa: E402,F401
import src.benchmarks.humaneval_plus  # noqa: E402,F401
import src.benchmarks.swebench  # noqa: E402,F401

_BCB = EVAL / "datasets" / "bigcodebench-hard@298d2cc7b96612e15e47313c3603ee124cee0c1f.jsonl"
_SWE = EVAL / "datasets" / "swebench-verified@c104f840cc67f8b6eec6f759ebc8b2693d585d4a.jsonl"


@pytest.fixture
def eval_root() -> Path:
    return EVAL


@pytest.fixture
def require_datasets():
    """Skip when the gitignored benchmark JSONLs are not in this checkout."""
    if not (_BCB.exists() and _SWE.exists()):
        pytest.skip("gitignored benchmark datasets absent in this checkout")


@pytest.fixture
def require_docker():
    """Skip when no docker daemon is reachable (real-grading replay tests)."""
    if shutil.which("docker") is None:
        pytest.skip("docker not available in this environment")
