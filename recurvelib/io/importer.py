"""Bootstrap a starter draft ledger from an existing prose GAPS.md.

The prose stays the record of truth; this only seeds the machine layer so a
human (or agent) completes severity/class/probe. Every imported gap is marked
`status: open` with `probe:` commented out and `needs_authoring: true`, so
`validate` honestly reports "these gaps have no probe yet" rather than
pretending the ledger is complete.

Heuristic, not a parser: it pulls `## N. Title` (or `## N Title`) headings and
the first `Smallest platform fix:` / `Smallest fix:` block beneath each.
Suites whose GAPS.md predates this convention import as best-effort skeletons.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Accept both numbering styles:
#   "## 6b. Title"       (dotted number)
#   "## T-TOKEN — Title"  (token id + em-dash or colon)
_HEADING = re.compile(
    r"^##\s+(?P<num>[A-Za-z0-9][A-Za-z0-9-]*?)(?:\.|\s+[—:-])\s*(?P<title>.+?)\s*$"
)
_FIX = re.compile(r"smallest (?:platform )?fix:\s*(?P<fix>.+)", re.IGNORECASE)
# Headings that are not gaps (narrative sections, verdict maps).
_SKIP_TITLES = re.compile(r"verdict map|falls short|where this", re.IGNORECASE)


@dataclass
class ImportedGap:
    num: str
    title: str
    smallest_fix: str
    body: str


def parse_gaps_md(text: str) -> list[ImportedGap]:
    lines = text.splitlines()
    sections: list[tuple[str, str, list[str]]] = []
    cur: tuple[str, str, list[str]] | None = None
    for line in lines:
        m = _HEADING.match(line)
        if m:
            if cur:
                sections.append(cur)
            cur = (m.group("num"), m.group("title").strip(), [])
        elif cur:
            cur[2].append(line)
    if cur:
        sections.append(cur)

    out: list[ImportedGap] = []
    for num, title, body_lines in sections:
        if _SKIP_TITLES.search(title):
            continue
        body = "\n".join(body_lines).strip()
        fix = ""
        joined = " ".join(b.strip() for b in body_lines)
        fm = _FIX.search(joined)
        if fm:
            fix = fm.group("fix").strip()
        out.append(ImportedGap(num=num, title=title, smallest_fix=fix, body=body))
    return out


def to_yaml_skeleton(suite: str, prefix: str, gaps: list[ImportedGap], prog: str = "recurve") -> str:
    """Emit a YAML skeleton. IDs are <PREFIX>-<num> to match GAPS.md numbering."""
    chunks = [
        f"# {suite}/gaps.yaml — machine layer for the improvement loop.",
        f"# Imported from GAPS.md by `{prog} import`. COMPLETE each entry: set class,",
        f"# severity, author a probe (probes/<id>.sh), then delete needs_authoring.",
        "",
    ]
    for g in gaps:
        # Numeric headings ("6b") get the suite prefix; token headings already
        # carry their own id ("T-TOKEN") — keep it, just uppercased.
        gid = f"{prefix}-{g.num}" if g.num[:1].isdigit() else g.num.upper()
        fix = g.smallest_fix or "TODO: name the smallest change in the target tree that closes this."
        chunks.append(f"- id: {gid}")
        chunks.append(f"  title: {_q(g.title)}")
        chunks.append(f"  class: TODO            # missing-surface | broken-route | wire-mismatch | security-tradeoff | staging | friction")
        chunks.append(f"  status: open")
        chunks.append(f"  severity: TODO         # headline | feature | friction | cosmetic")
        chunks.append(f"  needs_authoring: true  # delete once class/severity/probe are real")
        chunks.append(f"  evidence: []           # <tree path>:LINE")
        chunks.append(f"  observed: ''")
        chunks.append(f"  smallest_fix: >")
        chunks.append(f"    {fix}")
        chunks.append(f"  # probe: probes/{gid.lower()}.sh   # author this; RED today, GREEN when fixed")
        chunks.append(f"  unlocks: ''")
        chunks.append("")
    return "\n".join(chunks) + "\n"


def _q(s: str) -> str:
    s = s.replace("'", "''")
    return f"'{s}'"
