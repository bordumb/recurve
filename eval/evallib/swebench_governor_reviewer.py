#!/usr/bin/env python3
"""swebench_governor_reviewer.py — the RECURVE_GOVERNOR_CMD script for SW6's
A9 cells: a REAL, decorrelated model reviews the isolated cycle snapshot's
actual current state and prints the governor's required wire-protocol JSON.

Invoked with cwd set to an ISOLATED, ARCHIVED SNAPSHOT of the workspace at a
pinned commit (`recurvelib.adapters.snapshot._archive`: `git archive` +
`tar -x` into a fresh temp dir) -- deliberately history-free by design, the
same isolation every reviewer gets (`ablation-infra.md` AI3). A git-diff-
based review is therefore structurally impossible here: there is no `.git`
to diff (an earlier version of this script tried `git diff HEAD~1 HEAD`,
which always failed silently and defaulted to an unreviewed "no veto" --
a vacuous pass, not a real one). This version instead reads what IS
present: the closed claims' own ledger entries (title/smallest_fix/
observed), their probe script's actual content (does it genuinely verify
something, or rubber-stamp?), and the current content of any files their
`evidence` names -- and judges whether that evidence genuinely supports
the claim, the way a human reviewer reads a PR description against the
diff and tests it describes.

Usage: python3 swebench_governor_reviewer.py <reviewer-model>
"""
from __future__ import annotations

import glob
import json
import re
import subprocess
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover - PyYAML is a real dependency of this suite
    yaml = None

REVIEW_PROMPT = (
    "You are an independent code reviewer auditing an autonomous coding "
    "agent's most recent work in this repository. Below is one or more "
    "claims the agent declared CLOSED (its own stated justification: "
    "title, smallest_fix, observed result), the actual content of the "
    "probe script that verified each claim, and the current content of any "
    "files its evidence names. Review for a real, load-bearing problem: a "
    "claim declared closed without genuine evidence, a probe that doesn't "
    "actually verify what it claims to (e.g. it would pass regardless of "
    "the fix), a fix that doesn't match its own description, or a fix that "
    "doesn't actually address the stated task. A stylistic nit is not a "
    "veto.\n\n"
    "Reply with EXACTLY one line of JSON and nothing else:\n"
    '  {"veto": false}\n'
    "or\n"
    '  {"veto": true, "reason": "<short reason>"}\n\n')

_EVIDENCE_PATH_RE = re.compile(r"^([^:]+\.\w+)")


def _closed_claims(root: Path) -> list[dict]:
    """Every claim marked `status: closed` across every suite's `gaps.yaml`
    under `root/.recurve/claims/` -- discovered by scanning the snapshot
    itself (the reviewer isn't handed a claim list; the ledger IS the
    record). Stdlib-only fallback if `yaml` is somehow unimportable, so
    this never hard-crashes on a missing package rather than reviewing."""
    claims = []
    for path in glob.glob(str(root / ".recurve" / "claims" / "*" / "gaps.yaml")):
        text = Path(path).read_text(errors="ignore")
        if yaml is not None:
            try:
                for entry in (yaml.safe_load(text) or []):
                    if isinstance(entry, dict) and entry.get("status") == "closed":
                        entry = dict(entry)
                        entry["_gaps_yaml_dir"] = str(Path(path).parent)
                        claims.append(entry)
                continue
            except Exception:
                pass
        for block in text.split("\n- id:"):
            if "status: closed" in block:
                claims.append({"id": (block.strip().splitlines() or ["?"])[0].strip(),
                               "_raw": block, "_gaps_yaml_dir": str(Path(path).parent)})
    return claims


def _cap(text: str, max_chars: int) -> str:
    """Truncate with an EXPLICIT marker, never silently -- an unmarked cut
    reads to a reviewer (model or human) as a genuine defect in the file
    itself (this exact confusion happened during testing: a probe script
    truncated mid-hunk was flagged as "incomplete", when the real file was
    whole and only this function's own cap had cut it)."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + f"\n...[TRUNCATED, {len(text) - max_chars} more chars]"


def _probe_text(claim: dict, *, max_chars: int = 8000) -> str:
    suite_dir = claim.get("_gaps_yaml_dir")
    probe = claim.get("probe")
    if not suite_dir or not probe:
        return ""
    p = Path(suite_dir) / probe
    return _cap(p.read_text(errors="ignore"), max_chars) if p.is_file() else ""


def _evidence_snippets(root: Path, claim: dict, *, max_chars: int = 4000) -> str:
    """Best-effort: the actual current content of files the claim's own
    `evidence` list names (a `path:line`-shaped string, or a bare path) --
    capped (with an explicit marker, never silent), this is review context,
    not a re-implementation."""
    out = []
    for ev in claim.get("evidence") or []:
        m = _EVIDENCE_PATH_RE.match(str(ev))
        if not m:
            continue
        p = root / m.group(1)
        if p.is_file():
            out.append(f"--- {m.group(1)} ---\n{_cap(p.read_text(errors='ignore'), max_chars)}")
    return "\n\n".join(out)


def _review_context(root: Path, claims: list[dict]) -> str:
    parts = []
    for c in claims:
        probe = _probe_text(c)
        evidence = _evidence_snippets(root, c)
        parts.append(
            f"## Claim {c.get('id', '?')}: {c.get('title', '')}\n"
            f"smallest_fix: {c.get('smallest_fix', '')}\n"
            f"observed: {c.get('observed', '')}\n\n"
            + (f"--- probe: {c.get('probe', '')} ---\n{probe}\n\n" if probe else "")
            + evidence)
    # Bound the reviewer's own spend (a review, not a re-implementation) --
    # marked if it actually cuts, never silent (see _cap).
    return _cap("\n\n".join(parts), 20_000)


def _extract_json(text: str) -> dict:
    for line in reversed(text.strip().splitlines()):
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    return {}


def _call_model(model: str, prompt: str, timeout: int = 180) -> str:  # pragma: no cover - real API call
    r = subprocess.run(
        ["claude", "-p", "--model", model, "--permission-mode", "bypassPermissions"],
        input=prompt, capture_output=True, text=True, timeout=timeout)
    return r.stdout


def main(*, call_model=None) -> int:
    """`call_model` is injectable (default: a real `claude -p` call) so
    everything up to and including the actual model call is hermetically
    testable -- claim discovery, truncation-marking, and the fail-closed
    empty-claims path never need a real API call to verify."""
    call_model = call_model or _call_model
    model = sys.argv[1] if len(sys.argv) > 1 else "claude-haiku-4-5"
    root = Path.cwd()
    claims = _closed_claims(root)
    if not claims:
        # A governor invocation only ever runs once the mechanical gate is
        # green, so finding zero closed claims to review is itself
        # suspicious (not merely "nothing to say") -- fail closed, the
        # same posture `_resolve_governor_status` already takes toward an
        # unreachable governor, never silently clear an unreviewable cycle.
        print(json.dumps({"served_model": model,
                           "vetoes": {"cycle": "no closed claim found in this snapshot to review"}}))
        return 0
    prompt = REVIEW_PROMPT + _review_context(root, claims)
    try:
        stdout = call_model(model, prompt)
        payload = _extract_json(stdout)
    except Exception:
        payload = {}
    veto = bool(payload.get("veto"))
    vetoes = {"cycle": payload.get("reason", "review-tier objects")} if veto else {}
    print(json.dumps({"served_model": model, "vetoes": vetoes}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
