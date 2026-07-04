#!/usr/bin/env bash
# SR-2: the self-host gate is greenable — a probe whose EXTERNAL oracle is absent
# (SKIP, exit 3) is honored as non-blocking ONLY when the claim declares an
# oracle_waiver; an UNdeclared skip is not honored (it still blocks the gate). So
# a claim like TK-2 (equivalence to absent ancestor instances) can skip visibly
# without letting any probe dodge the gate by exiting 3. RED-first: a policy that
# honors an undeclared skip is RED.
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
python3 - "$ROOT" "${TRAP_FIXTURE:-}" <<'PYEOF'
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

root, fixture = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)
try:
    from recurvelib.probe import Outcome
    if fixture:
        spec = importlib.util.spec_from_file_location(
            "ctrap", Path(fixture) / "broken_conformance.py")
        mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        is_waived_skip = mod.is_waived_skip
    else:
        from recurvelib.conformance import is_waived_skip
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)


def R(outcome, waiver):
    return SimpleNamespace(outcome=outcome, gap=SimpleNamespace(oracle_waiver=waiver))


waived = is_waived_skip(R(Outcome.SKIP, "ancestors absent"))    # -> True
undecl = is_waived_skip(R(Outcome.SKIP, ""))                    # -> False (must still block)
non_skip = is_waived_skip(R(Outcome.GREEN, "ancestors absent"))  # -> False (only SKIP)

if waived is True and undecl is False and non_skip is False:
    print("a declared oracle_waiver honors a skip (non-blocking); an undeclared skip still blocks")
    sys.exit(0)
print(f"ours=(waived={waived}, undeclared={undecl}, non_skip={non_skip}) "
      f"oracle=(True, False, False) — only a DECLARED oracle_waiver may skip the gate")
sys.exit(1)
PYEOF
