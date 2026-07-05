"""The promotion ceremony — the epistemological boundary of the whole system.

Drafts (`gaps.draft.yaml`) are schema-shaped intentions. The ledger
(`gaps.yaml`) records verified observations. `baseline` is the only door
between them:

    draft entry → probe written → baseline runs the probe FOR REAL
        RED    → promote as `open`   (observed = actual quoted output, dated)
        GREEN  → promote as `closed` — but only once the probe has been seen
                 RED against a trap (a free win with an unfalsified probe is
                 indistinguishable from a probe that exits 0 unconditionally)
        BROKEN → stays a draft; fix the harness first (a broken baseline
                 blocks all cycles)

An unattended agent must be able to trust that every line in gaps.yaml is a
real, reproducible measurement — never someone's prediction.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from recurvelib.core.config import Config
from recurvelib.loop.lock import TreeLock
from recurvelib.core.model import Gap, GapParseError
from recurvelib.core.probe import Outcome, ShellProbeRunner, run_traps


@dataclass(frozen=True)
class BaselineOutcome:
    gap_id: str
    action: str    # promoted-open | promoted-closed | kept-draft | skipped
    detail: str


_LEDGER_HEADER = (
    "# gaps.yaml — the live ledger: verified observations only.\n"
    "# Entries arrive here through `baseline` (the promotion ceremony); the\n"
    "# `observed` field quotes actual dated output, never a prediction.\n"
)


def _entry_yaml(entry: dict) -> str:
    ordered = {}
    for key in ("id", "title", "class", "status", "severity", "reads", "covers",
                "evidence", "observed", "smallest_fix", "probe", "unlocks",
                "trap_waiver", "oracle_waiver", "reference", "min_governor_tier"):
        if key in entry and entry[key] not in (None, "", [], ()):
            ordered[key] = entry[key]
    return yaml.safe_dump([ordered], sort_keys=False, allow_unicode=True, width=88)


def run_baseline(config: Config, suite_name: str, today: str,
                 timeout_s: int = 120) -> tuple[list[BaselineOutcome], bool]:
    """Returns (outcomes, ok). ok is False if any probe came back BROKEN or a
    GREEN promotion was blocked — both block cycles until repaired."""
    sc = config.suite_for(suite_name)
    draft_path = sc.dir / "gaps.draft.yaml"
    ledger_path = sc.dir / "gaps.yaml"
    if not draft_path.exists():
        return [BaselineOutcome("-", "skipped", f"no {draft_path.name} in {sc.dir}")], True

    doc = yaml.safe_load(draft_path.read_text()) or []
    if not isinstance(doc, list):
        raise GapParseError(f"{draft_path}: top level must be a list of draft entries")

    runner = ShellProbeRunner()
    outcomes: list[BaselineOutcome] = []
    remaining: list[dict] = []
    promoted: list[dict] = []
    ok = True

    # Ids already recorded in the ledger. A draft entry repeating one of these is
    # not re-promoted, so re-running baseline over a full draft never duplicates a
    # ledger line.
    existing_ids = set()
    if ledger_path.exists():
        led = yaml.safe_load(ledger_path.read_text()) or []
        if isinstance(led, list):
            existing_ids = {str(e.get("id")) for e in led if isinstance(e, dict)}

    with TreeLock(config.tree or config.root):
        for raw in doc:
            gid = str(raw.get("id", "?"))
            # A draft entry whose id is already in the ledger is not re-promoted;
            # appending it again would duplicate the ledger line.
            if gid in existing_ids:
                remaining.append(raw)
                outcomes.append(BaselineOutcome(gid, "kept-draft",
                                                "already in the ledger — not re-promoted"))
                continue
            if raw.get("needs_authoring") or not raw.get("probe"):
                remaining.append(raw)
                outcomes.append(BaselineOutcome(gid, "skipped",
                                                "no probe yet — author it, then re-run baseline"))
                continue

            # Validate the would-be ledger entry BEFORE measuring: a promotion
            # that can't parse must fail before it writes anything.
            candidate = dict(raw)
            candidate.pop("needs_authoring", None)
            candidate.setdefault("status", "open")
            try:
                gap = Gap.parse(candidate, sc.name, sc.dir, ledger_path,
                                tuple(sc.reads.keys()), config.default_reads)
            except GapParseError as e:
                remaining.append(raw)
                outcomes.append(BaselineOutcome(gid, "kept-draft", f"will not parse: {e}"))
                ok = False
                continue

            result = runner.run(gap, timeout_s=timeout_s)

            if result.outcome is Outcome.RED:
                candidate["status"] = "open"
                candidate["observed"] = f"RED at baseline {today}: {result.detail or '(no output)'}"
                promoted.append(candidate)
                outcomes.append(BaselineOutcome(gid, "promoted-open", result.detail[:80]))
            elif result.outcome is Outcome.GREEN:
                if config.traps == "required" and not raw.get("trap_waiver"):
                    traps = run_traps(gap, runner, timeout_s)
                    bad = [t for t in traps if not t.ok]
                    if not traps:
                        remaining.append(raw)
                        outcomes.append(BaselineOutcome(
                            gid, "kept-draft",
                            "GREEN but unfalsified: add a counterexample under "
                            f"probes/{gap.probe.stem}.trap/ (or a trap_waiver) — a probe "
                            "never seen RED is not yet evidence"))
                        ok = False
                        continue
                    if bad:
                        remaining.append(raw)
                        outcomes.append(BaselineOutcome(
                            gid, "kept-draft",
                            f"GREEN but trap {bad[0].trap} came back {bad[0].outcome.value} "
                            f"— {bad[0].detail[:60]}"))
                        ok = False
                        continue
                candidate["status"] = "closed"
                candidate["observed"] = f"GREEN at baseline {today}: {result.detail or '(no output)'}"
                promoted.append(candidate)
                outcomes.append(BaselineOutcome(gid, "promoted-closed",
                                                "a free win — probe stays as a regression guard"))
            else:
                remaining.append(raw)
                outcomes.append(BaselineOutcome(
                    gid, "kept-draft",
                    f"{result.outcome.value}: {result.detail[:70] or 'probe could not decide'} "
                    f"— fix the harness; a broken baseline blocks all cycles"))
                ok = False

        if promoted:
            existing = ledger_path.read_text() if ledger_path.exists() else _LEDGER_HEADER
            blocks = "".join("\n" + _entry_yaml(e) for e in promoted)
            ledger_path.write_text(existing.rstrip("\n") + "\n" + blocks)

            # Promotion must leave a parseable ledger — verify or roll back.
            from recurvelib.core.model import load_ledger
            try:
                load_ledger(config)
            except GapParseError as e:
                ledger_path.write_text(existing)
                raise GapParseError(f"promotion rolled back — ledger would not parse: {e}")

        if remaining != doc:
            if remaining:
                header = ("# gaps.draft.yaml — schema-shaped intentions awaiting the baseline\n"
                          "# ceremony. Nothing here is an observation yet.\n")
                draft_path.write_text(header + yaml.safe_dump(remaining, sort_keys=False,
                                                              allow_unicode=True, width=88))
            else:
                draft_path.unlink()

    return outcomes, ok
