"""ST-1 counterexample: a controller missing the STOP-SUCCESS branch — it never stops on a green cycle
(the core "LLM cannot stop" failure). Still reverts on flat and continues on progress, so it passes ST-2/3."""

from recurvelib.loop.controller import Verdict


def decide(history, k=3):
    if not history:
        return Verdict.CONTINUE
    # BUG: no STOP-SUCCESS branch
    if len(history) >= k:
        window = history[-k:]
        if all(p.divergent for p in window):
            return Verdict.STOP_REVERT
        if all(p.regressed > 0 for p in window):
            return Verdict.STOP_REVERT
        remaining = [p.open + p.uncovered for p in window]
        if remaining[0] > 0 and remaining[-1] >= remaining[0]:
            return Verdict.STOP_REVERT
    return Verdict.CONTINUE
