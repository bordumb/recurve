#!/usr/bin/env bash
# RT-6: the actor is reached only on an admitted contract (A6).
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
python3 - "$ROOT" "${TRAP_FIXTURE:-}" <<'PYEOF'
import importlib.util
import sys
from pathlib import Path

root, fixture = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)
try:
    from recurvelib.admission import Assertion, admit
    if fixture:
        spec = importlib.util.spec_from_file_location("rtrap", Path(fixture) / "broken_runtime.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        guarded_propose = mod.guarded_propose
    else:
        from recurvelib.runtime import guarded_propose

    admit_rep = admit([Assertion("a", "", True, True, True), Assertion("b", "", True, True, True)])
    refuse_rep = admit([Assertion("a", "", False, True, True), Assertion("b", "", False, True, True)])

    class Spy:
        def __init__(self):
            self.called = False
        def propose(self, c, i, e):
            self.called = True
            return "diff"

    s1 = Spy()
    r1 = guarded_propose(s1, admit_rep, None, None, None)
    s2 = Spy()
    r2 = guarded_propose(s2, refuse_rep, None, None, None)
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

if r1 == "diff" and s1.called and r2 is None and not s2.called:
    print("ADMIT -> actor invoked; non-ADMIT -> actor never called, returns None")
    sys.exit(0)
print(f"ours=(admit: r={r1!r} called={s1.called}; refuse: r={r2!r} called={s2.called}) "
      f"oracle=(admit invokes; refuse never calls) (reaching an actor on a non-ADMIT contract burns a non-contract)")
sys.exit(1)
PYEOF
