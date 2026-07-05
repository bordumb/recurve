# A broken decide() that ignores governor_status entirely — a fully-green
# cycle always reaches STOP-SUCCESS, even when the governor has not yet run
# (pending) or vetoed. This is the exact bug R5/ST-12 exists to prevent:
# governor_cleared defaulting to true.
import sys
from pathlib import Path

ROOT = str(Path(__file__).resolve().parents[5])
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from recurvelib.loop.controller import Verdict


def decide(history, k=3, governor_status="off"):
    if not history:
        return Verdict.CONTINUE
    cur = history[-1]
    if cur.open == 0 and cur.regressed == 0 and cur.broken == 0 and cur.uncovered == 0 and not cur.divergent:
        return Verdict.STOP_SUCCESS  # BUG: ignores governor_status entirely
    return Verdict.CONTINUE
