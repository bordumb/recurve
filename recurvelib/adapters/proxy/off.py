"""off: the identity proxy — a fixed, neutral score regardless of the
candidate. Exists so the `ProxyEvaluator` seam is real (config, registry,
resolution) before any domain adapter is registered against it."""
from __future__ import annotations

from recurvelib.core.protocols import ProxyScore


class OffProxy:
    def score(self, candidate) -> ProxyScore:
        return ProxyScore(value=1.0, signal=None)
