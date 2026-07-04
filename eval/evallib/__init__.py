"""evallib — the recurve evaluation pipeline.

Three verbs with an inspectable file between each (plan → matrix.jsonl → run →
results.jsonl → analyze → summary.md). The matrix is data, not code: an
experiment is a small manifest, and everything downstream is a pure function of
it. Core logic is stdlib-only so the gated claims run without the heavy
fetch/oracle dependencies.
"""

__version__ = "0.1.0"
