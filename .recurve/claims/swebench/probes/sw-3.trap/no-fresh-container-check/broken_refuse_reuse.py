"""The plausible bug: skipping the reuse check entirely (a grading path that
just trusts whatever container id it was handed, agent's own included) —
the exact state-leakage-into-its-own-grade failure quarantine exists to
prevent.
"""

from __future__ import annotations


class OracleContainerReuseError(RuntimeError):
    pass


def refuse_reuse_of_agent_container(agent_container_id, grading_container_id) -> None:
    return None  # never refuses anything
