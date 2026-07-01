"""RT-10 counterexample: the guard keys on the probe-able COUNT instead of the ADMIT verdict, so a
REFUSE-AND-INTERVIEW contract (probeable >= 1) still reaches the actor. Passes RT-6 (ADMIT vs
NOT_GATEABLE only)."""


def guarded_propose(actor, admission_report, contract, item, evidence):
    if admission_report.probeable < 1:                           # BUG: count, not admitted() verdict
        return None
    return actor.propose(contract, item, evidence)
