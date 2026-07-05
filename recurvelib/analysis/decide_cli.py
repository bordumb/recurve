"""`decide` — surface the stopping controller as a callable verb.

An orchestrator (or a human) needs to ask for a stop verdict from a *measured*
progress vector rather than let a mechanical cap decide blind. This module is
that surface: :func:`verdict_for` runs :func:`recurvelib.controller.decide` on a
single measured cycle and returns its verdict string. It mirrors the controller
exactly — the surface adds no policy of its own, so the verb can never disagree
with the referee it exposes.

:func:`verdict_for_configured` is the R5 live-loop wiring
(`docs/plans/oracle-strength-and-decorrelation.md` R5, `docs/plans/ablation-infra.md`
AI2): when a config is given and the gate/mechanical vector is green, it resolves
``[gate] governor=`` through the SAME registry `AB-6`/`AB-7` built, invokes the
real adapter against the ledger's currently-closed claims, and feeds its verdict
into ``decide()`` — the exact call `templates/workflows/burndown.sh`'s
``stop_verdict()`` already makes (``$PROG decide --open ... --regressed ...``),
unchanged. A configured governor is invokable via config alone; no other part of
the loop needs to change.
"""
from __future__ import annotations

from recurvelib.loop.controller import Progress, decide


def verdict_for(open: int, regressed: int, broken: int, uncovered: int, divergent: bool = False) -> str:
    """Return the controller's verdict string for one measured progress vector.

    A faithful thin mirror of :func:`recurvelib.controller.decide`: it wraps the
    vector in a one-cycle history and returns the verdict's ``.value``. Same
    inputs, same decision — the surface never overrides the controller.

    Args:
        open: Claims still RED (work remaining).
        regressed: Claims that were GREEN and went RED this cycle.
        broken: Claims that could not be measured.
        uncovered: Frontier size — the completeness signal.
        divergent: Whether a goal-counterexample passed (fidelity signal).

    Returns:
        The verdict string, one of ``"STOP-SUCCESS"`` / ``"STOP-REVERT"`` /
        ``"CONTINUE"``.

    Usage:
        verdict_for(0, 0, 0, 0)  # -> "STOP-SUCCESS"
    """
    return decide([Progress(open, regressed, broken, uncovered, divergent)]).value


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


def verdict_for_configured(
    cfg, open: int, regressed: int, broken: int, uncovered: int, divergent: bool = False,
) -> str:
    """Like :func:`verdict_for`, but consults the resolved config's
    ``[gate] governor=`` for real when the gate/mechanical vector is green —
    the R5 live-loop wiring. With ``governor="off"`` (or no config passed),
    this is byte-identical to :func:`verdict_for`.

    Scope note: the governor audits ALL currently-closed claims in the
    ledger (the full set STOP_SUCCESS is asserting about), not a
    narrower "just this run's cycles" set — recurve does not yet track
    per-run cycle boundaries finely enough to scope it tighter, and
    auditing the full closed set is the safe direction to round in (it
    can only find MORE to object to, never less).
    """
    progress = Progress(open, regressed, broken, uncovered, divergent)
    gate_green = (open == 0 and regressed == 0 and broken == 0 and uncovered == 0 and not divergent)
    governor_tier = getattr(cfg, "gate_governor", "off") if cfg is not None else "off"

    if not gate_green or governor_tier == "off":
        return decide([progress]).value

    status = _resolve_governor_status(cfg, governor_tier)
    return decide([progress], governor_status=status).value
