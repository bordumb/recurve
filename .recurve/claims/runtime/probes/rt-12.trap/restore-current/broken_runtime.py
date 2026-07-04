"""RT-12 counterexample: STOP_REVERT restores the CURRENT checkpoint instead of the last green one, so the
damage is left in place. Passes RT-1 (its lying actor mutates nothing, so the two checkpoints coincide)."""

from recurvelib.analysis.admission import admitted
from recurvelib.loop.controller import Verdict, decide


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
            world.restore(world.checkpoint())                    # BUG: current state, not last_green
            return verdict, history
        if progress.open == 0 and progress.regressed == 0 and progress.broken == 0:
            last_green = world.checkpoint()
        world.apply(actor.propose(contract, None, progress))
    return Verdict.CONTINUE, history
