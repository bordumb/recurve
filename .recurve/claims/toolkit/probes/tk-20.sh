#!/usr/bin/env bash
# TK-20: `recurve status` summarizes health without ever greenwashing a failed
# gate. summarize(ledger, matrix_result) must take its gate verdict from the
# matrix result, so a matrix whose gate FAILED yields gate_ok=False — and it
# must report the open/closed claim counts. RED-first: a summarize that returns
# gate_ok=True over a failed gate is RED.
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
python3 - "$ROOT" "${TRAP_FIXTURE:-}" <<'PYEOF'
import importlib.util
import sys
from pathlib import Path

root, fixture = sys.argv[1], sys.argv[2]
sys.path.insert(0, root)
try:
    from recurvelib.model import Status
    if fixture:
        spec = importlib.util.spec_from_file_location(
            "strap", Path(fixture) / "broken_status.py")
        mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        summarize = mod.summarize
    else:
        from recurvelib.status import summarize
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)


# A minimal stand-in ledger: three closed gaps, two open. summarize reads only
# each gap's `.status` (a real Status enum with .value), so a tiny fake built
# from the real enum stays faithful to the object shape.
class FakeGap:
    def __init__(self, status): self.status = status


class FakeLedger:
    def __init__(self, statuses):
        self.gaps = [FakeGap(s) for s in statuses]


# A matrix result whose gate FAILED (one regression, so gate_ok is False).
class FailedMatrix:
    regressions = ["a-closed-gap-went-red"]
    broken = []
    stale = []
    skipped = []
    failed_traps = []
    gate_ok = False


ledger = FakeLedger([Status.CLOSED, Status.CLOSED, Status.CLOSED,
                     Status.OPEN, Status.OPEN])
try:
    s = summarize(ledger, FailedMatrix())
except Exception as e:
    print(f"selfcheck could not run: {e}")
    sys.exit(2)

green = s.get("gate_ok") is False and s.get("open") == 2 and s.get("closed") == 3
if green:
    print(f"ours=gate_ok={s['gate_ok']},open={s['open']},closed={s['closed']} "
          f"oracle=gate_ok=False,open=2,closed=3 — the summary never greenwashes a failed gate")
    sys.exit(0)
print(f"ours=gate_ok={s.get('gate_ok')!r},open={s.get('open')!r},closed={s.get('closed')!r} "
      f"oracle=gate_ok=False,open=2,closed=3")
sys.exit(1)
PYEOF
