"""adapters/runtime.py — the agent runtime as ONE indirection point.

There is exactly one agent runtime today (`claude -p`) -- a full port +
registry for it would be speculative generality, the exact trap this
codebase's own kernel discipline otherwise avoids. This is the cheap,
non-speculative slice instead: `evallib.adapters.claude`'s real,
already-proven invocation/parsing logic (reused completely unchanged, not
copied) is wrapped behind ONE name, `resolve_runtime`, so callers ask for
"the runtime" rather than importing `evallib.adapters.claude` by name
directly. Build the full `AgentRuntime` protocol + a second real runtime
the day a genuinely cross-runtime result is wanted -- not speculatively now.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class Runtime:
    name: str
    make_adapter: Callable          # (prompt_for) -> agent(cell, workspace)
    make_gated_adapter: Callable    # (cycle_prompt_for, cap) -> agent(cell, workspace)


def _claude_runtime() -> Runtime:
    from evallib.adapters.claude import make_adapter, make_gated_adapter
    return Runtime(name="claude", make_adapter=make_adapter, make_gated_adapter=make_gated_adapter)


_RUNTIMES = {"claude": _claude_runtime}


def resolve_runtime(name: str = "claude") -> Runtime:
    """KeyError-with-known-names on an unregistered runtime -- lazy
    (constructs on first resolve, not at import time), so importing this
    module never has to import the real paid-path Claude adapter unless a
    caller actually asks for it."""
    if name not in _RUNTIMES:
        known = ", ".join(sorted(_RUNTIMES))
        raise KeyError(f"unknown agent runtime {name!r}; known: {known}")
    return _RUNTIMES[name]()
