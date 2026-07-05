"""The unified `challenge_event` schema (`docs/plans/ablation-infra.md` AI8).

`oracle-strength-and-decorrelation.md`'s R4 "reversal event" and R5 "veto
event" are the same concept at different points in time — a GREEN
challenged by a stronger check, either before the run publishes success
(veto, `phase="pre_publication"`) or after (reversal,
`phase="post_publication"`). Pre-launch, with no existing ledger data to
migrate, they are ONE event type. There is deliberately no dual-schema
compatibility path: an event in either of the old, separate shapes fails
validation outright.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

PHASES = ("pre_publication", "post_publication")
REQUIRED_FIELDS = ("schema", "claim_id", "phase", "tier_at_challenge", "reason", "challenged_at")
SCHEMA = "challenge_event/1"
_LEGACY_MARKERS = ("reversal", "veto", "event_type")


class ChallengeEventError(ValueError):
    """A challenge_event failed structural validation."""


def make_challenge_event(
    *, claim_id: str, phase: str, tier_at_challenge: str, reason: str,
    human_attestation_ref: str | None = None, challenged_at: str | None = None,
) -> dict:
    """Build one challenge_event. `reason` is required — a challenge without
    one is a bare rejection, not evidence, and this constructor refuses to
    produce one."""
    if not reason:
        raise ChallengeEventError(
            "a challenge_event without a reason is a bare rejection, not evidence — "
            "reason is required")
    if phase not in PHASES:
        raise ChallengeEventError(f"phase must be one of {PHASES}, got {phase!r}")
    event = {
        "schema": SCHEMA,
        "claim_id": claim_id,
        "phase": phase,
        "tier_at_challenge": tier_at_challenge,
        "reason": reason,
        "challenged_at": challenged_at or time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    if human_attestation_ref is not None:
        event["human_attestation_ref"] = human_attestation_ref
    return event


def validate_challenge_event(event: dict) -> None:
    """Refuse the OLD, separate reversal/veto shapes outright — there is
    deliberately no dual-schema compatibility path (pre-launch; nothing
    depends on the old shape)."""
    if any(m in event for m in _LEGACY_MARKERS):
        raise ChallengeEventError(
            "legacy reversal/veto event shape detected (carries "
            f"{[m for m in _LEGACY_MARKERS if m in event]!r}) — challenge_event is the "
            "only schema; there is no dual-schema compatibility path")
    missing = [f for f in REQUIRED_FIELDS if f not in event]
    if missing:
        raise ChallengeEventError(f"challenge_event missing required field(s): {missing}")
    if event["phase"] not in PHASES:
        raise ChallengeEventError(f"phase must be one of {PHASES}, got {event['phase']!r}")
    if not event.get("reason"):
        raise ChallengeEventError("challenge_event.reason is required — never a bare rejection")


class ChallengeLog:
    """Append-only `challenge_event` log, one file per suite
    (`.recurve/state/challenges/<suite>.jsonl`) — the single record R4's
    reversal rate and R5's captured vetoes both write to."""

    def __init__(self, config, suite: str):
        self.suite = suite
        self.path = config.state_dir / "challenges" / f"{suite}.jsonl"

    def events(self) -> list[dict]:
        if not self.path.exists():
            return []
        return [json.loads(l) for l in self.path.read_text().splitlines() if l.strip()]

    def append(self, event: dict) -> None:
        validate_challenge_event(event)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a") as f:
            f.write(json.dumps(event, sort_keys=True) + "\n")

    def combined_rate(self, total_closed: int) -> float:
        """The combined challenge rate `recurve stats` reports — 0/N until
        any challenge occurs, sliceable by phase (`events_by_phase`)."""
        n = len(self.events())
        return n / total_closed if total_closed else 0.0

    def events_by_phase(self, phase: str) -> list[dict]:
        return [e for e in self.events() if e.get("phase") == phase]
