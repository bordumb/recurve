"""RT-6 counterexample: the guard invokes the actor regardless of the admission verdict, so a non-ADMIT
contract is burned down."""


def guarded_propose(actor, admission_report, contract, item, evidence):
    return actor.propose(contract, item, evidence)   # BUG: no admitted() precondition
