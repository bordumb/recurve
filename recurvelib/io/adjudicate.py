"""Adjudication — one human sentence, recorded where agents cannot lose it.

When a gap admits multiple honest resolutions, the human decision lands in
THREE synchronized places:

  1. the ledger's `smallest_fix` — "DECIDED <date>: …" (the alternative is
     NOT an acceptable close);
  2. the prose — "Adjudicated (<date>): …" under the section it covers;
  3. the probe itself — a POLICY marker, with the obligation that the
     rejected path exits RED citing it. The probe is the only one of the
     three an agent cannot rationalize around.

The same command is the AMENDMENT/RETIREMENT ceremony: requirements change,
and a closed claim can become wrong without its probe ever turning RED. A
retirement leaves a tombstone in the prose and deletes the probe in the same
change — a ledger that silently rewrites its past is no longer a record of
observations.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from recurvelib.core.config import Config
from recurvelib.core.model import Gap, GapParseError


def _entry_bounds(lines: list[str], gap_id: str) -> tuple[int, int]:
    start = None
    for i, line in enumerate(lines):
        if line.startswith("- id:") and line.split(":", 1)[1].strip() == gap_id:
            start = i
            break
    if start is None:
        raise GapParseError(f"entry {gap_id!r} not found in ledger text")
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if lines[j].startswith("- id:"):
            end = j
            break
    return start, end


def _rewrite_entry(ledger_path: Path, gap_id: str, mutate) -> None:
    """Splice ONE entry: parse it, mutate the dict, re-emit just that block.
    The rest of the file (including comments) is preserved byte-for-byte."""
    text = ledger_path.read_text()
    lines = text.splitlines(keepends=True)
    start, end = _entry_bounds([l.rstrip("\n") for l in lines], gap_id)
    block = "".join(lines[start:end])
    entry = yaml.safe_load(block)[0]
    entry = mutate(entry)
    if entry is None:
        new_block = ""
    else:
        ordered = {k: entry[k] for k in
                   ("id", "title", "class", "status", "severity", "reads", "covers",
                    "evidence", "observed", "smallest_fix", "probe", "unlocks",
                    "trap_waiver") if k in entry and entry[k] not in (None, "", [], ())}
        for k in entry:
            if k not in ordered and entry[k] not in (None, "", [], ()):
                ordered[k] = entry[k]
        new_block = yaml.safe_dump([ordered], sort_keys=False, allow_unicode=True, width=88)
    ledger_path.write_text("".join(lines[:start]) + new_block + "".join(lines[end:]))


def _prose_note(suite_dir: Path, gap: Gap, note: str) -> bool:
    gaps_md = suite_dir / "GAPS.md"
    if not gaps_md.exists() or not gap.covers:
        return False
    anchor = gap.covers[0]
    lines = gaps_md.read_text().splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.startswith("## ") and (line.startswith(f"## {anchor}.")
                                       or line.startswith(f"## {anchor} ")
                                       or line.startswith(f"## {anchor} —")
                                       or line.startswith(f"## {anchor}—")):
            start = i
            break
    if start is None:
        return False
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if lines[j].startswith("## "):
            end = j
            break
    lines.insert(end, "")
    lines.insert(end, note)
    gaps_md.write_text("\n".join(lines) + "\n")
    return True


_POLICY_MARKER = """
# ── POLICY (DECIDED {date}) ──────────────────────────────────────────────
# {decision}
# The alternative resolution is NOT an acceptable close. If this probe is
# ever loosened toward it, the rejected path MUST exit RED citing this
# policy line — encode the decision in behavior, not only in this comment.
"""


def adjudicate(config: Config, gap: Gap, decision: str, date: str) -> list[str]:
    """The three-place synchronized edit. Returns notes of what was touched."""
    notes = []
    sc = config.suite_for(gap.suite)

    def mutate(entry: dict) -> dict:
        prior = str(entry.get("smallest_fix", "")).strip()
        entry["smallest_fix"] = (f"DECIDED {date}: {decision} — the alternative is NOT "
                                 f"an acceptable close. (was: {prior})" if prior
                                 else f"DECIDED {date}: {decision}")
        return entry

    _rewrite_entry(gap.source_file, gap.id, mutate)
    notes.append(f"ledger: smallest_fix now opens with DECIDED {date}")

    if _prose_note(sc.dir, gap, f"Adjudicated ({date}): {decision}"):
        notes.append(f"prose: GAPS.md §{gap.covers[0]} records the adjudication")
    else:
        notes.append("prose: no covered GAPS.md section found — record the "
                     "adjudication there by hand (coverage will keep you honest)")

    if gap.probe is not None and gap.probe.exists():
        with gap.probe.open("a") as f:
            f.write(_POLICY_MARKER.format(date=date, decision=decision))
        notes.append(f"probe: POLICY marker appended to {gap.probe.name} — now encode "
                     f"the rejected path to exit RED citing it (the probe is the only "
                     f"place an agent cannot rationalize around)")
    return notes


def retire(config: Config, gap: Gap, reason: str, date: str) -> list[str]:
    """Amendment's terminal form: tombstone the prose, delete probe + traps,
    remove the ledger entry — all in one change."""
    notes = []
    sc = config.suite_for(gap.suite)
    _rewrite_entry(gap.source_file, gap.id, lambda e: None)
    notes.append("ledger: entry removed")
    if _prose_note(sc.dir, gap, f"Retired {date}: {reason}"):
        notes.append(f"prose: tombstone written under §{gap.covers[0]}")
    # Delete the probe only if no surviving entry still relies on it — a
    # retirement must never blind another claim's guard.
    from recurvelib.core.model import load_ledger
    still_referenced = any(g.probe == gap.probe for g in load_ledger(config).gaps)
    if gap.probe is not None and gap.probe.exists() and not still_referenced:
        gap.probe.unlink()
        notes.append(f"probe: {gap.probe.name} deleted in the same change")
        if gap.trap_dir is not None and gap.trap_dir.is_dir():
            import shutil
            shutil.rmtree(gap.trap_dir)
            notes.append("traps: fixtures removed with their probe")
    elif still_referenced:
        notes.append(f"probe: kept — another entry still relies on {gap.probe.name}")
    return notes
