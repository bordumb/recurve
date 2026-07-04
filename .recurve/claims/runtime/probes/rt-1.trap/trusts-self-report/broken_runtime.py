"""RT-1 counterexample: the loop trusts the actor's self-reported 'done', so a lying actor stops it with
success while the gate is still RED."""

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
            world.restore(last_green)
            return verdict, history
        diff = actor.propose(contract, None, progress)
        if getattr(diff, "done", False):           # BUG: the actor's word ends the loop
            return Verdict.STOP_SUCCESS, history
        world.apply(diff)
    return Verdict.CONTINUE, history
