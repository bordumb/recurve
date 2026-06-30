#!/usr/bin/env python3
"""The interview pass (G3): walk agent-runtime.md A1-A6 from REFUSE-AND-INTERVIEW to ADMIT.

The admission gate refused A1-A6 (run examples/admit_agent_runtime.py). The interview asks, for each vague
step, "what would *wrong* look like, concretely?" — and the answer turns it into a probe-able claim (an
oracle + a counterexample). The interviewer is the LLM judgment (the answers below are hand-written, shown
transparently); `interview_step` is the deterministic stopping rule that decides CONTINUE / ESCALATE / ADMIT,
and `admit()` makes the final verdict. A3 and A4 were already probe-able.

Run it:
    cd recurve && python3 examples/interview_agent_runtime.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from recurvelib.admission import Assertion, Verdict, admit, interview_step

ALREADY_GATEABLE = {"A3", "A4"}
ALL_IDS = ["A1", "A2", "A3", "A4", "A5", "A6"]

# The interview: (id, question, the answer that makes it probe-able = oracle + counterexample).
INTERVIEW = [
    ("A1",
     "what would a finished, working minimal loop look like, and how would it fail?",
     "done: a 1-RED-claim contract + a stub actor that emits the fix -> STOP-SUCCESS in <=N cycles, gate GREEN, claim closed once",
     "wrong: STOP-SUCCESS reported while the gate is still RED, or a claim closed then silently reopened"),
    ("A2",
     "how do we observe that completeness Sense ranks real uncovered work?",
     "done: on a target with one uncovered public fn, Sense.uncovered == {that fn} and pick_next returns it",
     "wrong: Sense reports uncovered == 0 on a target with a genuinely uncovered public unit"),
    ("A5",
     "when has the adversary turn actually done its job?",
     "done: given a claim a planted wrong-but-passing impl defeats, the turn yields a trap RED on the wrong impl, GREEN on the real",
     "wrong: no new trap (or one the wrong impl still passes) for a demonstrably-defeatable claim"),
    ("A6",
     "what is the testable core of 'a swappable actor behind a stable interface'?",
     "done: an actor is reached only via propose(contract,item,evidence)->diff, and never on a non-ADMIT contract (admitted guard)",
     "wrong: the loop invokes an actor on a non-ADMIT contract, or outside the adapter interface"),
]


def assertions_with(sharpened):
    """Build the 6 assertions; A3/A4 plus everything in `sharpened` are probe-able."""
    out = []
    for aid in ALL_IDS:
        p = aid in ALREADY_GATEABLE or aid in sharpened
        out.append(Assertion(aid, "", p, p, p))
    return out


def main():
    print("=" * 72)
    print("  INTERVIEW PASS  ·  agent-runtime.md A1-A6")
    print("=" * 72)
    print(f"\n  start: {admit(assertions_with(set())).verdict.value}  "
          f"(A3, A4 already probe-able; A1/A2/A5/A6 need the interview)\n")

    history = [assertions_with(set())]   # round 0: before any answers
    print(f"  round 0  un-probe-able=4  interview_step -> {interview_step(history).value}")

    sharpened = set()
    for (aid, question, done, wrong) in INTERVIEW:
        print(f"\n  Q to human about {aid}: {question}")
        print(f"     -> {done}")
        print(f"     -> {wrong}")
        sharpened.add(aid)
        history.append(assertions_with(sharpened))
        n = sum(1 for a in history[-1] if not a.probeable)
        print(f"  {aid} now probe-able.  un-probe-able={n}  interview_step -> {interview_step(history).value}")

    final = admit(history[-1])
    print("\n" + "=" * 72)
    mark = "OK ADMIT" if final.verdict is Verdict.ADMIT else final.verdict.value
    print(f"  FINAL VERDICT:  {mark}   gateability {final.probeable}/{final.total} "
          f"({final.gateability:.2f})")
    print(f"  worklist remaining: {list(final.worklist) or 'none'}")
    print("=" * 72)


if __name__ == "__main__":
    main()
