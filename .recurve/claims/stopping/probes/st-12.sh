#!/usr/bin/env bash
# ST-12: the governor supersedes STOP_SUCCESS (R5,
# docs/plans/oracle-strength-and-decorrelation.md). RED-first: until
# decide() accepts governor_status (or gets the resolution wrong) the probe
# is RED.
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
python3 - "$ROOT" "${TRAP_FIXTURE:-}" <<'PYEOF'
import importlib.util
import sys
from pathlib import Path

root, fixture = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)
try:
    from recurvelib.loop.controller import Progress, Verdict
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

try:
    if fixture:
        spec = importlib.util.spec_from_file_location("ctrap", Path(fixture) / "broken_controller.py")
        mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        decide = mod.decide
    else:
        from recurvelib.loop.controller import decide
except (ImportError, TypeError) as e:
    print(f"ours=decide() does not yet accept governor_status ({e}) "
          f"oracle=a governor status parameter supersedes STOP_SUCCESS")
    sys.exit(1)  # RED-first


def check(label, cond):
    if not cond:
        print(f"FAIL: {label}")
        sys.exit(1)


green = Progress(open=0, regressed=0, broken=0, uncovered=0, divergent=False)

# 1. governor_status="off" (the default) means no governor is configured at
# all, so a green cycle proceeds straight to STOP-SUCCESS.
check("governor off (default) -> STOP-SUCCESS on a green cycle",
      decide([green]) == Verdict.STOP_SUCCESS)
check("governor_status='off' explicit -> STOP-SUCCESS", decide([green], governor_status="off") == Verdict.STOP_SUCCESS)

# 2. governor_status="cleared" also proceeds to STOP-SUCCESS.
check("governor cleared -> STOP-SUCCESS", decide([green], governor_status="cleared") == Verdict.STOP_SUCCESS)

# 3. governor_status="pending" on an otherwise-green cycle -> PENDING_GOVERNOR,
# NEVER STOP-SUCCESS. governor_cleared cannot default to true.
v_pending = decide([green], governor_status="pending")
check("governor pending -> PENDING_GOVERNOR, not STOP-SUCCESS",
      v_pending == Verdict.PENDING_GOVERNOR and v_pending != Verdict.STOP_SUCCESS)

# 4. governor_status="vetoed" -> CONTINUE (the veto becomes a captured trap;
# the cycle keeps working), never STOP-SUCCESS.
v_vetoed = decide([green], governor_status="vetoed")
check("governor vetoed -> CONTINUE, not STOP-SUCCESS",
      v_vetoed == Verdict.CONTINUE and v_vetoed != Verdict.STOP_SUCCESS)

# 5. a non-green cycle is unaffected by governor_status (the gate itself has
# work left; the governor question doesn't even arise yet).
red = Progress(open=1, regressed=0, broken=0, uncovered=0, divergent=False)
check("a non-green cycle ignores governor_status",
      decide([red], governor_status="pending") == Verdict.CONTINUE)

# 6. an unrecognized governor_status raises rather than resolving silently.
try:
    decide([green], governor_status="not-a-real-status")
    check("unknown governor_status refused", False)
except (ValueError, Exception):
    pass

print("decide() supersedes STOP-SUCCESS with the governor's status: off/cleared proceed "
      "unchanged, pending yields PENDING_GOVERNOR, vetoed yields CONTINUE — "
      "governor_cleared never defaults to true")
sys.exit(0)
PYEOF
