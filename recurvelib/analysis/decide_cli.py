"""`decide` — surface the stopping controller as a callable verb.

An orchestrator (or a human) needs to ask for a stop verdict from a *measured*
progress vector rather than let a mechanical cap decide blind. :func:`verdict_for`
runs :func:`recurvelib.controller.decide` on a single measured cycle and returns
its verdict string. The surface adds no policy of its own beyond what R5 adds to
the controller itself, so the verb can never disagree with the referee it exposes.

When `cfg` names a configured (`!= "off"`) `[gate] governor=` and the
gate/mechanical vector is green, `verdict_for` resolves it through the SAME
registry `AB-6`/`AB-7` built, invokes the real adapter against the ledger's
currently-closed claims, and feeds its verdict into `decide()` — the exact call
`templates/workflows/burndown.sh`'s `stop_verdict()` already makes (`$PROG
decide --open ... --regressed ...`), unchanged. A configured governor is
invokable via config alone; no other part of the loop needs to change
(`docs/plans/oracle-strength-and-decorrelation.md` R5,
`docs/plans/ablation-infra.md` AI2).
"""
from __future__ import annotations

from recurvelib.loop.controller import Progress, decide


def _resolve_governor_status(cfg, governor_tier: str) -> str:
    """Resolve the CONFIGURED governor tier into a `decide()` governor_status
    by actually invoking it — the live R5 wiring. Any failure to build a
    snapshot or invoke the adapter resolves to "pending", never "cleared":
    a governor that cannot be consulted must not silently clear the run."""
    import os

    from recurvelib.adapters.governor import GOVERNOR_ADAPTERS
    from recurvelib.adapters.registry import resolve_governor
    from recurvelib.adapters.snapshot import build_cycle_snapshot, SnapshotError
    from recurvelib.adapters._shared.provenance import metadata_verified, unverified
    from recurvelib.core.model import load_ledger, Status

    try:
        ledger = load_ledger(cfg)
    except Exception:
        return "pending"
    claim_ids = sorted(g.id for g in ledger.gaps if g.status is Status.CLOSED)
    tree = cfg.tree or cfg.root
    try:
        cycle = build_cycle_snapshot(tree, "HEAD", claim_ids, include_existing_traps=True)
    except SnapshotError:
        return "pending"

    try:
        cls = resolve_governor(governor_tier, GOVERNOR_ADAPTERS)
    except Exception:
        return "pending"

    # The actor's provenance — an operator/orchestrator names the actual
    # served model via RECURVE_ACTOR_MODEL (metadata_verified); with nothing
    # named, the actor's identity is unverified, which correctly makes
    # verified_different_identity refuse to treat any reviewer as distinct
    # (mechanical_review/human_required fail closed rather than assume it).
    actor_model = os.environ.get("RECURVE_ACTOR_MODEL")
    actor_provenance = metadata_verified(actor_model) if actor_model else unverified()

    try:
        if governor_tier == "mechanical":
            governor = cls()
        elif governor_tier == "mechanical_review":
            governor = cls(actor_provenance)
        elif governor_tier == "human_required":
            from recurvelib.adapters.governor.human_required import shell_verify_fn
            verifier_cmd = getattr(cfg, "human_verifier", "") or ""
            if not verifier_cmd:
                return "pending"
            governor = cls(cfg.state_dir / "attestations", shell_verify_fn(verifier_cmd))
        else:
            return "pending"
        verdict = governor.audit(cycle)
    except Exception:
        return "pending"

    if verdict.pending:
        return "pending"
    if verdict.vetoes:
        return "vetoed"
    return "cleared"


def verdict_for(
    open: int, regressed: int, broken: int, uncovered: int, divergent: bool = False, cfg=None,
) -> str:
    """Return the controller's verdict string for one measured progress vector.

    Without `cfg` (or with `cfg.gate_governor == "off"`), a faithful thin mirror
    of :func:`recurvelib.controller.decide`: wraps the vector in a one-cycle
    history and returns the verdict's ``.value`` — no governor to consult, so
    none is invoked. With a `cfg` naming a configured governor, and the vector
    green, the governor is resolved through the registry and actually invoked
    (see the module docstring) before the verdict is decided.

    Args:
        open: Claims still RED (work remaining).
        regressed: Claims that were GREEN and went RED this cycle.
        broken: Claims that could not be measured.
        uncovered: Frontier size — the completeness signal.
        divergent: Whether a goal-counterexample passed (fidelity signal).
        cfg: A resolved `recurvelib.core.config.Config`, or `None`.

    Returns:
        The verdict string: ``"STOP-SUCCESS"`` / ``"STOP-REVERT"`` /
        ``"CONTINUE"`` / ``"PENDING-GOVERNOR"``.

    Usage:
        verdict_for(0, 0, 0, 0)              # -> "STOP-SUCCESS" (no governor)
        verdict_for(0, 0, 0, 0, cfg=cfg)      # -> resolves cfg's real governor
    """
    progress = Progress(open, regressed, broken, uncovered, divergent)
    governor_tier = getattr(cfg, "gate_governor", "off") if cfg is not None else "off"
    gate_green = (open == 0 and regressed == 0 and broken == 0 and uncovered == 0 and not divergent)

    if not gate_green or governor_tier == "off":
        return decide([progress]).value

    status = _resolve_governor_status(cfg, governor_tier)
    return decide([progress], governor_status=status).value
