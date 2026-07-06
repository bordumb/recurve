"""swebench_majority.py — grading aggregates independent verification runs
into one majority-vote verdict, never a single run.

SWE-bench's own test suites are not perfectly deterministic — timing-
sensitive tests, container-startup jitter, and non-deterministic test
ordering can flip a genuinely-unchanged patch's verdict between runs. A
SINGLE grading run cannot distinguish "the fix is wrong" from "this run
happened to hit a flaky test." `grade_with_majority_vote` runs the
underlying grader `num_runs` times (default 3) and takes whichever verdict a
STRICT MAJORITY of runs agree on — never trusting run #1 alone.

Every individual run's result is preserved in the returned dict (`runs`),
never discarded — a 2-1 split is real information (this instance's tests
are flaky) and must stay visible in provenance, not be silently smoothed
away into one boolean.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from evallib.swebench_quarantine import grade_fresh


class NoMajorityError(RuntimeError):
    """`num_runs` verdicts split with no strict majority (only reachable
    with an even `num_runs`) — refuse to guess rather than pick arbitrarily."""


def grade_with_majority_vote(instance: dict, diff_text: str,
                              environment_image_digest: str, *,
                              agent_container_id: str | None = None,
                              num_runs: int = 3, grader=None,
                              model_name: str = "agent", timeout: int = 1800,
                              client=None, log_dir=None) -> dict:  # pragma: no cover - needs docker via grade_fresh
    """Run `grader` (defaults to `swebench_quarantine.grade_fresh`) `num_runs`
    times against the SAME diff/instance/environment and return the
    majority-vote verdict. `agent_container_id` is forwarded to EVERY run —
    the fresh-container reuse guard must fire on any run that would collide
    with the agent's own container, not just the first. Returns `{"resolved": bool
    (the majority verdict), "runs": [each run's full result dict, in order],
    "agreement": "<majority>/<num_runs>", "unanimous": bool}` — the
    individual runs are never dropped, so a split verdict stays visible in
    provenance instead of being silently smoothed into one boolean."""
    grader = grader or grade_fresh
    runs = []
    for i in range(num_runs):
        run_log_dir = (Path(log_dir) / f"run-{i}") if log_dir else None
        runs.append(grader(instance, diff_text, environment_image_digest,
                            agent_container_id=agent_container_id,
                            model_name=model_name, timeout=timeout,
                            client=client, log_dir=run_log_dir))
    votes = Counter(bool(r.get("resolved")) for r in runs)
    (majority_verdict, majority_count), = votes.most_common(1)
    if majority_count * 2 <= num_runs:
        raise NoMajorityError(
            f"{num_runs} verification runs split with no strict majority: "
            f"{dict(votes)}")
    return {
        "resolved": majority_verdict,
        "runs": runs,
        "agreement": f"{majority_count}/{num_runs}",
        "unanimous": majority_count == num_runs,
    }
