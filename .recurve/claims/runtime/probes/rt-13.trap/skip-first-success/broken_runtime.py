"""RT-13 counterexample: STOP_SUCCESS is suppressed on the first cycle, so an already-green world has the
actor run against done code before the loop finally stops. Passes RT-1 (its world starts RED)."""

from recurvelib.admission import admitted
from recurvelib.controller import Verdict, decide


def run(world, actor, admission_report, contract, max_cycles=64):
    if not admitted(admission_report):
        return None, []
    history = []
    last_green = world.checkpoint()
    first = True
    for _ in range(max_cycles):
        progress = world.gate()
        history.append(progress)
        verdict = decide(history)
        if verdict is Verdict.STOP_SUCCESS and not first:        # BUG: first-cycle success suppressed
            return verdict, history
        if verdict is Verdict.STOP_REVERT:
            world.restore(last_green)
            return verdict, history
        if progress.open == 0 and progress.regressed == 0 and progress.broken == 0:
            last_green = world.checkpoint()
        world.apply(actor.propose(contract, None, progress))
        first = False
    return Verdict.CONTINUE, history
