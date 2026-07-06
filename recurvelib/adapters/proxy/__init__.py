"""The concrete ProxyEvaluator adapters."""
from __future__ import annotations

from recurvelib.adapters.proxy.dyadic_lyapunov import DyadicLyapunovProxy
from recurvelib.adapters.proxy.off import OffProxy
from recurvelib.adapters.registry import build_registry
from recurvelib.core.protocols import ProxyEvaluator

PROXY_ADAPTERS = build_registry({
    "off": OffProxy,
    "dyadic_lyapunov": DyadicLyapunovProxy,
}, ProxyEvaluator, ("score",))
