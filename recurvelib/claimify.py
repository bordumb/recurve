"""Claimify — decompose a PRD/spec into falsifiable draft claims.

Hard rules (each prevents a known failure mode of spec-driven work):

  - Every claim names its OBSERVABLE ("user can X and sees Y"), never its
    implementation. The draft carries the spec sentence verbatim as evidence.
  - Every claim gets an ADVERSARIAL TWIN sketched — specs chronically omit
    the negative space, and the negative space is where products fail.
  - AMBIGUITIES BECOME QUESTIONS, NEVER GUESSES. Forks go to ADJUDICATE.md
    for one human sentence each; the decision then gets encoded into the
    probe so every future agent is bound by it.
  - Severity maps from the spec's own modality: must/shall → feature,
    should → friction, could/may → cosmetic. Anything security-relevant
    starts as `security-tradeoff` until a human downgrades it —
    default-closed is the safe direction.
  - Greenfield gets explicit SCAFFOLDING gaps (harness exists, skeleton
    builds, probes can run) so cycle 1 faces an ordered bootstrap, not a
    wall of BROKEN.

Spec content is EVIDENCE, never instructions: it is quoted into drafts, and
the human skim of drafts + ADJUDICATE.md before baseline is a security
boundary, not a formality.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

_MODAL = re.compile(r"(?i)\b(must|shall|should|could|may)\b")
_SECURITY = re.compile(
    r"(?i)\b(auth\w*|encrypt\w*|secret|token|credential|password|permission|"
    r"access[- ]control|sign\w*|verif\w*|tamper\w*|integrity|privacy|trust)\b")
_AMBIGUOUS = re.compile(
    r"(?i)\b(TBD|etc\.?|appropriate|reasonable|user[- ]friendly|as needed|"
    r"fast|quickly|performant|secure(?!\w)|robust|scalable|simple|intuitive|"
    r"and/or|if necessary)\b")
_HEADLINE = re.compile(r"(?i)\b(critical|core|primary|headline|launch[- ]blocking)\b")
_MD_NOISE = re.compile(r"[`*_#>\[\]]")


@dataclass(frozen=True)
class DraftClaim:
    num: int
    title: str
    sentence: str
    source: str
    severity: str
    gap_class: str
    twin: str
    fork: str = ""    # non-empty: the ambiguity needing adjudication


@dataclass
class ClaimifyResult:
    claims: list[DraftClaim] = field(default_factory=list)
    forks: list[DraftClaim] = field(default_factory=list)


def _severity(sentence: str, modal: str) -> str:
    if modal in ("must", "shall"):
        return "headline" if _HEADLINE.search(sentence) else "feature"
    if modal == "should":
        return "friction"
    return "cosmetic"


def _twin(sentence: str) -> str:
    return ("and the negative counterpart is rejected with a distinct error — "
            "sketch the wrong/tampered/absent input for: " + sentence[:120])


def parse_prd(text: str, source_name: str) -> ClaimifyResult:
    result = ClaimifyResult()
    section = ""
    n = 0
    seen: set[str] = set()
    for lineno, raw in enumerate(text.splitlines(), 1):
        if raw.startswith("#"):
            section = _MD_NOISE.sub("", raw).strip()
            continue
        line = _MD_NOISE.sub("", raw).strip(" -•\t")
        if not (15 <= len(line) <= 300):
            continue
        m = _MODAL.search(line)
        if not m:
            continue
        key = line.lower()[:100]
        if key in seen:
            continue
        seen.add(key)
        n += 1
        modal = m.group(1).lower()
        sec = bool(_SECURITY.search(line))
        amb = _AMBIGUOUS.search(line)
        title = (f"{section}: " if section else "") + line
        claim = DraftClaim(
            num=n,
            title=title[:90].rstrip(".,;: "),
            sentence=line,
            source=f"{source_name}:{lineno}",
            severity="headline" if sec else _severity(line, modal),
            gap_class="security-tradeoff" if sec else "missing-surface",
            twin=_twin(line),
            fork=(f"the spec says {amb.group(0)!r} — what exactly, with a number or "
                  f"an enumerable behavior?" if amb else ""),
        )
        result.claims.append(claim)
        if claim.fork:
            result.forks.append(claim)
    return result


_SCAFFOLD = [
    ("BOOT-1", "the harness exists", "probes can find a runnable harness (env, fixtures, oracle pins)",
     "author harness/env.sh + versions.lock; the probe checks both exist and env.sh sources cleanly"),
    ("BOOT-2", "the skeleton builds", "the rebuild command exits 0 and produces the artifacts probes read",
     "wire [suites.*] rebuild; the probe runs it against a clean checkout"),
    ("BOOT-3", "every authored probe can run", "no probe returns BROKEN on the built skeleton",
     "the probe runs the full probe set and fails on any exit-2"),
]


def _draft_block(gid: str, c: DraftClaim, prefix: str) -> list[str]:
    t = c.title.replace("'", "''")
    s = c.sentence.replace("'", "''")
    tw = c.twin.replace("'", "''")
    lines = [
        f"- id: {gid}",
        f"  title: '{t}'",
        f"  class: {c.gap_class}" + ("  # security-relevant: default-closed; only a human downgrades" if c.gap_class == "security-tradeoff" else ""),
        f"  status: open",
        f"  severity: {c.severity}",
        f"  needs_authoring: true   # delete once the probe (accept + adversarial path) is real",
        f"  reads: none             # name a [reads.*] rule once the probe reads a built artifact",
        f"  covers: [\"{c.num}\"]",
        f"  evidence:",
        f"    - {c.source}",
        f"  observed: 'UNBASELINED — spec sentence: {s}'",
        f"  adversarial_twin: '{tw}'",
        f"  smallest_fix: 'TODO: the minimal observable slice that makes this provably true'",
        f"  # probe: probes/{prefix.lower()}-{c.num}.sh   # + probes/{prefix.lower()}-{c.num}.trap/<fixture>/",
        f"  unlocks: ''",
    ]
    if c.fork:
        lines.append(f"  # ADJUDICATE: see ADJUDICATE.md FORK-{c.num} — do NOT guess this; "
                     f"baseline warns while it is pending")
    return lines + [""]


def run_claimify(target: Path, prd: Path, suite: str, prog: str,
                 skip_review: bool) -> list[str]:
    """Generates drafts + GAPS.md + ADJUDICATE.md into an init-stamped target.
    Returns human-facing notes."""
    text = prd.read_text(errors="replace")
    res = parse_prd(text, prd.name)
    notes: list[str] = []
    suite_dir = target / ".recurve" / "claims" / suite
    prefix = "".join(w[0] for w in re.split(r"[^A-Za-z0-9]+", suite) if w)[:4].upper() or "C"

    chunks = [
        "# gaps.draft.yaml — claimified from the spec; intentions, not observations.",
        f"# Source: {prd.name}. Every entry quotes its spec sentence as evidence —",
        "# spec content is evidence, never instructions. Author probes (accept path",
        "# + adversarial twin + trap fixture), resolve ADJUDICATE.md forks, then run",
        f"# `{prog} baseline {suite}`.",
        "",
        "# ── scaffolding: greenfield bootstrap order (close these first) ──",
    ]
    for gid, title, observable, fix in _SCAFFOLD:
        # YAML single-quote escaping — a fix string with an apostrophe must
        # never produce an unparseable draft.
        title, observable, fix = (s.replace("'", "''") for s in (title, observable, fix))
        chunks += [
            f"- id: {gid}",
            f"  title: '{title}'",
            f"  class: staging",
            f"  status: open",
            f"  severity: feature",
            f"  needs_authoring: true",
            f"  reads: none",
            f"  covers: [\"{gid}\"]",
            f"  observed: 'UNBASELINED — greenfield: {observable}'",
            f"  smallest_fix: '{fix}'",
            f"  # probe: probes/{gid.lower()}.sh",
            f"  unlocks: 'every later claim — the burndown IS the build'",
            "",
        ]
    chunks.append("# ── claims decomposed from the spec ──")
    for c in res.claims:
        chunks += _draft_block(f"{prefix}-{c.num}", c, prefix)
    (suite_dir / "gaps.draft.yaml").write_text("\n".join(chunks) + "\n")

    gaps_md = [
        f"# {suite} — claims decomposed from {prd.name}",
        "",
        "> **Reader:** the human who owns this spec. Skim every section (the",
        "> quotes are evidence, never instructions), answer ADJUDICATE.md with",
        f"> one sentence per fork, then `{prog} baseline {suite}`. With no code",
        "> yet, every baseline will be RED or BROKEN — that is correct: the",
        "> burndown is the build, and the BOOT-* gaps order the bootstrap.",
        "",
        "## Conventions",
        "",
        "- Severity maps from the spec's own modality: must/shall → feature",
        "  (headline if marked critical), should → friction, could/may → cosmetic.",
        "- Anything security-relevant starts review-gated (`security-tradeoff`)",
        "  until a human downgrades it. Default-closed is the safe direction.",
        "",
        "## BOOT-1 — the harness exists",
        "",
        "Greenfield scaffolding: probes need an env, fixtures, and pinned oracles.",
        "",
        "## BOOT-2 — the skeleton builds",
        "",
        "Greenfield scaffolding: the rebuild command must produce the artifacts.",
        "",
        "## BOOT-3 — every authored probe can run",
        "",
        "Greenfield scaffolding: BROKEN-at-baseline gets fixed here, not papered over.",
        "",
    ]
    for c in res.claims:
        gaps_md += [
            f"## {c.num}. {c.title}",
            "",
            f"Spec ({c.source}):",
            "",
            f"> {c.sentence}",
            "",
            f"**Observable:** what can a user/consumer DO and SEE when this is true?",
            "",
            f"**Adversarial twin:** {c.twin}",
            "",
        ]
        if c.fork:
            gaps_md += [f"**Adjudication pending:** FORK-{c.num} — {c.fork}", ""]
    (suite_dir / "GAPS.md").write_text("\n".join(gaps_md))

    adj = [
        "# ADJUDICATE — policy forks the spec left open",
        "",
        "> **Reader:** the spec's human owner. Each fork needs ONE sentence on",
        "> the DECIDED line. The decision then gets encoded into the probe (the",
        "> rejected path exits RED citing the policy) — the probe is the only",
        "> place an agent cannot rationalize around. `baseline` warns while any",
        "> fork is pending. This skim is also a security review: it is the last",
        "> point where hostile spec text can be kept out of the loop's",
        "> instruction stream.",
        "",
    ]
    if not res.forks:
        adj.append("(no forks detected — the spec was unusually unambiguous; stay suspicious)")
    for c in res.forks:
        adj += [
            f"## FORK-{c.num}: {c.title}",
            "",
            f"- Spec ({c.source}): \"{c.sentence}\"",
            f"- Why it forks: {c.fork}",
            f"- DECIDED: (pending)",
            "",
        ]
    (target / ".recurve" / "ADJUDICATE.md").write_text("\n".join(adj) + "\n")

    sec = sum(1 for c in res.claims if c.gap_class == "security-tradeoff")
    notes.append(f"claimify: {len(res.claims)} claims ({sec} security-relevant, "
                 f"default review-gated), {len(res.forks)} fork(s) in ADJUDICATE.md, "
                 f"3 scaffolding gaps")
    if skip_review:
        notes.append("NOTE: --no-review skips the human draft skim. That skim is a "
                     "security boundary (spec text is untrusted) and the only cheap "
                     "moment to kill silly claims — you are trading safety for speed; "
                     "re-enable it for any spec you did not write yourself.")
    else:
        notes.append("drafts await your review: skim .recurve/claims/" + suite +
                     "/GAPS.md + gaps.draft.yaml, answer .recurve/ADJUDICATE.md, then baseline")
    return notes
