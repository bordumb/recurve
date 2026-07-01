"""RT-11 counterexample: the last-green floor is recorded on open==0 alone, so a regressed cycle becomes the
revert target. Passes RT-1 (its world always has regressed==0, broken==0)."""

from recurvelib.admission import admitted
from recurvelib.controller import Verdict, decide


def run(world, actor, admission_report, contract, max_cycles=64):
    if not admitted(admission_report):
        return None, []
    history = []
    last_green = world.checkpoint()
    for _ in range(max_cycles):
        progress = world.gate()
        history.append(progress)
        verdict = decide(history)
        if verdict is Verdict.STOP_SUCCESS:
            return verdict, history
        if verdict is Verdict.STOP_REVERT:
            world.restore(last_green)
            return verdict, history
        if progress.open == 0:                                   # BUG: drops the regressed/broken guard
            last_green = world.checkpoint()
        world.apply(actor.propose(contract, None, progress))
    return Verdict.CONTINUE, history
