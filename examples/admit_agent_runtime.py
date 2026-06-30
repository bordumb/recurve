#!/usr/bin/env python3
"""Run the admission gate (Layer 0) on docs/plans/agent-runtime.md's build steps A1-A6.

This is a worked example of `recurvelib.admission`. The admission gate decides whether a goal is *gateable*
— whether it can become a faithful contract at all. The natural-language judgment "is this step probe-able?"
is the pluggable rater part (here, hand-rated below, with the reasoning shown); `admit()` makes the
deterministic verdict over those ratings.

Run it:
    cd recurve && python3 examples/admit_agent_runtime.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from recurvelib.admission import Assertion, Verdict, admit

# The rater's reading of agent-runtime.md §5. Each tuple:
#   (id, text, falsifiable?, has_counterexample?, bounded?, reasoning)
RATED = [
    ("A1", "the minimal closed loop: Sense -> decide -> Act -> revert-to-last-green, the honest MVP",
     False, False, True,
     "names an architecture; states no observable done-condition and no counterexample"),
    ("A2", "completeness Sense: wire surface/coverage/frontier so pick_next ranks uncovered work",
     False, False, True,
     "'wire X into Y' has no pass/fail; when is it done? unstated"),
    ("A3", "fidelity Sense: feed divergent so the loop refuses a success-stop on a goal-counterexample",
     True, True, True,
     "embeds a testable behavior: a divergent cycle must not STOP-SUCCESS (already gated as ST-7/CL-13)"),
    ("A4", "the write boundary: actor diffs touch only the target tree; reject otherwise",
     True, True, True,
     "a crisp enforcement rule: a diff that edits a probe must be rejected -> clear oracle + counterexample"),
    ("A5", "the adversary turn: a periodic separate agent red-teams new claims; capture rule -> traps",
     False, False, True,
     "'periodic' / 'red-teams' has no done-condition; a process description, not a check"),
    ("A6", "human gate + actor adapter: approval, escalations, a stable interface so the actor is swappable",
     False, False, False,
     "bundles three vague aims; 'a swappable actor behind a stable interface' is open scope"),
]

BAR = "=" * 70


def main():
    assertions = [Assertion(i, t, f, c, b) for (i, t, f, c, b, _why) in RATED]
    report = admit(assertions)

    print(BAR)
    print("  ADMISSION GATE  ·  docs/plans/agent-runtime.md  (build steps A1-A6)")
    print(BAR)
    mark = "OK ADMIT" if report.verdict is Verdict.ADMIT else f"REFUSED -> {report.verdict.value}"
    print(f"\n  VERDICT:  {mark}")
    print(f"  gateability: {report.probeable}/{report.total} assertions are probe-able "
          f"({report.gateability:.2f})")
    if report.verdict is not Verdict.ADMIT:
        print("  => NOT yet a contract; the steps below must be sharpened before burndown.\n")

    print("  --- the rater's reading (the pluggable judgment) ---")
    for (i, t, f, c, b, why) in RATED:
        tag = "probe-able    " if (f and c and b) else "NOT probe-able"
        print(f"  {i} [{tag}] oracle={int(f)} counterexample={int(c)} bounded={int(b)}")
        print(f"       {why}")

    if report.probeable:
        print(f"\n  --- already a gateable spine (let through) ---")
        print(f"  {', '.join(a.id for a in assertions if a.probeable)}")

    if report.worklist:
        print(f"\n  --- interview worklist (what to sharpen, and exactly why) ---")
        for aid, gaps in report.worklist:
            print(f"  {aid}:")
            for g in gaps:
                print(f"       - {g}")
    print()


if __name__ == "__main__":
    main()
