"""A grading function that LOOKS like majority-vote aggregation (same
return shape: resolved/runs/agreement/unanimous) but calls the underlying
grader only ONCE and reports that single result as if it were an agreed
verdict — the exact bug this claim exists to catch. A flaky second run
that would have disagreed never gets a chance to vote."""


def broken_grade_with_majority_vote(instance, diff_text, digest, *,
                                     agent_container_id=None, num_runs=3,
                                     grader=None, **kw):
    grader = grader or (lambda *a, **k: {"resolved": True})
    result = grader(instance, diff_text, digest,
                     agent_container_id=agent_container_id, **kw)
    return {
        "resolved": result["resolved"],
        "runs": [result],
        "agreement": f"{num_runs}/{num_runs}",
        "unanimous": True,
    }
