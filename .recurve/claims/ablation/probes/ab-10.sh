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
check("A7 configures adversary=cross_model", arms.arm_spec("A7").adversary == "cross_model")
check("A8 configures governor=mechanical", arms.arm_spec("A8").governor == "mechanical")
check("A9 configures governor=mechanical_review",
      arms.arm_spec("A9").governor == "mechanical_review")
check("A10 configures both switches", arms.arm_spec("A10").adversary == "cross_model"
      and arms.arm_spec("A10").governor == "mechanical_review")

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

# 4. `eval plan` itself (evallib.plan.expand — what cmd_plan actually calls)
# resolves adversary=/governor= through the registry, on a REAL manifest
# naming A7-A10 — the literal §8 acceptance criterion, not just the
# isolated resolve_*_adapter functions.
from evallib.plan import expand, resolved_gate_config
manifest = {"matrix": {"models": ["m"], "arms": ["A3", "A7", "A9"], "budgets": [1000], "seeds": [0]}}
tasks = [{"task_id": "T-1", "instruct_prompt": "x"}]
cells = expand(manifest, tasks)
by_arm = {c["arm"]: c for c in cells}
check("A3's planned cell carries an empty gate_config (no adversary/governor)",
      by_arm["A3"]["gate_config"] == {})
check("A7's planned cell carries the REAL resolved adversary=cross_model config",
      by_arm["A7"]["gate_config"] == {"adversary": "cross_model"})
check("A9's planned cell carries the REAL resolved governor=mechanical_review config",
      by_arm["A9"]["gate_config"] == {"governor": "mechanical_review"})

# 5. an unknown arm in the manifest fails the WHOLE plan loud (before any
# cell is written), not just when resolved in isolation.
bad_manifest = {"matrix": {"models": ["m"], "arms": ["A99-does-not-exist"],
                          "budgets": [1000], "seeds": [0]}}
try:
    expand(bad_manifest, tasks)
    check("an unknown arm named in a manifest is refused by expand()", False)
except KeyError:
    pass

# 6. a KNOWN arm whose config names an adversary/governor NOT in the
# registry (simulating drift between arms.py's table and the registry) is
# refused by resolved_gate_config, not silently accepted — inject a
# temporary bad entry into the real _ARMS table rather than a copy, so this
# proves the ACTUAL function used by expand() checks it.
from evallib import arms as arms_mod
arms_mod._ARMS["_AB10_BOGUS"] = arms_mod.ArmSpec(
    workspace="recurve_init", done_signal="gate", adversary="not-a-real-adapter",
    label="test-only bogus arm")
try:
    resolved_gate_config("_AB10_BOGUS")
    check("an unknown adversary value inside a known arm's config is refused", False)
except Exception:
    pass
finally:
    del arms_mod._ARMS["_AB10_BOGUS"]

print("eval/evallib's arm composer resolves adversary=/governor= through recurvelib's own "
      "registry (imported, never reimplemented); A7-A10 are real, resolvable arm entries; "
      "`eval plan` itself (expand()) resolves and records the config on every cell, and "
      "refuses loud on an unknown arm or an unknown adversary/governor value")
sys.exit(0)
PYEOF
