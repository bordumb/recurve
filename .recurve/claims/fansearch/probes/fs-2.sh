#!/bin/bash
# FS-2: the ProxyEvaluator port resolves through the generalized registry.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../../../.." && pwd)"

if [ -n "${TRAP_FIXTURE:-}" ]; then
  REGISTRY_SRC="$TRAP_FIXTURE/registry.py"
else
  REGISTRY_SRC="$ROOT/recurvelib/adapters/registry.py"
fi

python3 - "$ROOT" "$REGISTRY_SRC" <<'PYEOF'
import sys

root, registry_src = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)

# --- the real behavior: does the ProxyEvaluator seam actually work? -------
try:
    from recurvelib.core.protocols import ProxyEvaluator, ProxyScore
    from recurvelib.adapters.proxy import PROXY_ADAPTERS
    from recurvelib.adapters.registry import build_registry, resolve, MalformedAdapterError, UnknownAdapterError
    from recurvelib.core.config import load
    from pathlib import Path
except ImportError as e:
    print(f"RED: seam not wired yet: {e}")
    sys.exit(1)

cls = resolve("off", PROXY_ADAPTERS, "proxy")
score = cls().score(object())
if not isinstance(score, ProxyScore) or not (0.0 <= score.value <= 1.0):
    print(f"RED: off proxy did not return a valid ProxyScore: {score!r}")
    sys.exit(1)

class _Malformed:
    pass

try:
    build_registry({"bad": _Malformed}, ProxyEvaluator, ("score",))
    print("RED: a class without .score was NOT refused at registration")
    sys.exit(1)
except MalformedAdapterError:
    pass

try:
    resolve("nope", PROXY_ADAPTERS, "proxy")
    print("RED: an unknown proxy name was NOT refused")
    sys.exit(1)
except UnknownAdapterError:
    pass

cfg = load(Path(root) / ".recurve" / "recurve.toml")
if cfg.fansearch_proxy != "off":
    print(f"RED: [fansearch] proxy default should be 'off', got {cfg.fansearch_proxy!r}")
    sys.exit(1)

# --- the source-shape check: no fourth hand-copy of build_X/resolve_X ----
try:
    text = open(registry_src).read()
except FileNotFoundError:
    print(f"RED: {registry_src} not found")
    sys.exit(1)

offenders = [
    line.strip() for line in text.splitlines()
    if (line.strip().startswith("def resolve_proxy(")
        or line.strip().startswith("def build_proxy_registry("))
]
if offenders:
    print("RED: a fourth hand-copy of the build/resolve pair was added instead of using "
          f"the generic build_registry/resolve: {offenders}")
    sys.exit(1)

print("GREEN: ProxyEvaluator seam resolves through the generic registry; "
      "off proxy scores validly; malformed/unknown adapters refused; "
      "no fourth hand-copy in registry.py")
sys.exit(0)
PYEOF
