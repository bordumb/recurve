"""The concrete ProxyEvaluator adapters (docs/plans/fansearch.md F1)."""
from __future__ import annotations

from recurvelib.adapters.proxy.off import OffProxy
from recurvelib.adapters.registry import build_registry
from recurvelib.core.protocols import ProxyEvaluator

PROXY_ADAPTERS = build_registry({
    "off": OffProxy,
}, ProxyEvaluator, ("score",))
