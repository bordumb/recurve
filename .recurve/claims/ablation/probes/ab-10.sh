#!/usr/bin/env bash
# AB-10: one registry, two consumers, no duplication (docs/plans/ablation-infra.md
# AI5) — eval/evallib's arm composer resolves adversary=/governor= through
# recurvelib's registry, unblocking eval-full.md's A7-A10.
# RED-first: until eval/evallib/arms.py has A7-A10 wired to the real
# registry the probe is RED.
#
# With $TRAP_FIXTURE: a candidate arms.py that defines its own local
# ADVERSARY_ADAPTERS/GOVERNOR_ADAPTERS mapping instead of importing
# recurvelib's — a lint-shaped drift fixture (RED = caught).
set -u
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
python3 - "$ROOT" "${TRAP_FIXTURE:-}" <<'PYEOF'
import sys
from pathlib import Path

root, fixture = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)
sys.path.insert(0, str(Path(root) / "eval"))

try:
    from recurvelib.adapters.adversary import ADVERSARY_ADAPTERS
    from recurvelib.adapters.governor import GOVERNOR_ADAPTERS
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)


def check(label, cond):
    if not cond:
        print(f"FAIL: {label}")
        sys.exit(1)


ARMS_PY = Path(root) / "eval" / "evallib" / "arms.py"


def defines_own_registry(text: str) -> bool:
    """The AI5 lint check: does this source define its OWN
    ADVERSARY_ADAPTERS/GOVERNOR_ADAPTERS mapping (a dict literal assignment)
    rather than importing recurvelib's?"""
    return ("ADVERSARY_ADAPTERS = {" in text or "ADVERSARY_ADAPTERS: dict" in text
            or "GOVERNOR_ADAPTERS = {" in text or "GOVERNOR_ADAPTERS: dict" in text)


def imports_from_recurvelib(text: str) -> bool:
    return ("from recurvelib.adapters.adversary import" in text
            and "from recurvelib.adapters.governor import" in text)


if fixture:
    candidate = (Path(fixture) / "arms.py").read_text()
    if defines_own_registry(candidate) and not (
        "# THIS IS THE REAL, ALLOWED IMPORT" in candidate and imports_from_recurvelib(candidate)
    ):
        print("ours=candidate defines its own ADVERSARY_ADAPTERS/GOVERNOR_ADAPTERS mapping "
              "oracle=must import recurvelib's — correctly caught the drift")
        sys.exit(1)
    print("ours=candidate does not reimplement oracle=expected a local reimplementation "
          "(this fixture did not exercise the intended bug)")
    sys.exit(0)

# --- no TRAP_FIXTURE: the real positive assertions -------------------------

# 1. arms.py imports the registries from recurvelib — never a local mapping.
text = ARMS_PY.read_text()
check("arms.py does NOT define its own ADVERSARY_ADAPTERS/GOVERNOR_ADAPTERS mapping",
      not defines_own_registry(text))
check("arms.py imports both registries from recurvelib.adapters",
      imports_from_recurvelib(text))

# 2. A7-A10 are real arm entries whose config resolves through the SAME
# recurvelib objects imported above (identity check, not just "looks similar").
from evallib import arms
check("A7 configures adversary=cross_model", arms.arm_spec("A7")["config"]["adversary"] == "cross_model")
check("A8 configures governor=mechanical", arms.arm_spec("A8")["config"]["governor"] == "mechanical")
check("A9 configures governor=mechanical_review",
      arms.arm_spec("A9")["config"]["governor"] == "mechanical_review")
check("A10 configures both switches", arms.arm_spec("A10")["config"]["adversary"] == "cross_model"
      and arms.arm_spec("A10")["config"]["governor"] == "mechanical_review")

check("arms.resolve_adversary_adapter resolves through the SAME registry object",
      arms.resolve_adversary_adapter("cross_model") is ADVERSARY_ADAPTERS["cross_model"])
check("arms.resolve_governor_adapter resolves through the SAME registry object",
      arms.resolve_governor_adapter("mechanical_review") is GOVERNOR_ADAPTERS["mechanical_review"])

# 3. an unknown arm still fails loud, before any run.
try:
    arms.arm_spec("not-a-real-arm")
    check("unknown arm refused", False)
except KeyError:
    pass

print("eval/evallib's arm composer resolves adversary=/governor= through recurvelib's own "
      "registry (imported, never reimplemented); A7-A10 are real, resolvable arm entries")
sys.exit(0)
PYEOF
