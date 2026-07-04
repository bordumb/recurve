"""The run report — the loop's dataset, rendered for the human who signs.

Deterministic by default: progress comes from the ledger, cycle metrics and
the ETA projection from the run records, and the honesty scan from the git
range those records cover. No model, no network — the page a maintainer
reads before signing is computed from the same artifacts the gate trusts.

`--narrate` optionally pipes the rendered report plus a JSON array of the
cycle records to a configured narrator command and appends its stdout as a
Narrative section. The narrator may editorialize over the numbers; it can
never alter them — and a narrator that fails or times out costs only the
prose, never the deterministic report above it.
"""

from __future__ import annotations

import fnmatch
import json
import re
import shlex
import statistics
import subprocess
import time
from pathlib import Path

from recurvelib.core.config import Config
from recurvelib.core.model import Gap, Status
from recurvelib.loop.parked import ParkedStore
from recurvelib.analysis.triage import review_gated


class NarratorError(Exception):
    """The narrator command failed — the deterministic report must survive it."""


# Diffing from a repository's first commit needs a parent that does not
# exist; git's well-known empty-tree object stands in for it.
_EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"

# How many of the largest per-file diffs the sensitive-touch heuristic reads.
_TOP_FILES = 10


def load_records(cfg: Config, suite: str | None = None) -> list[dict]:
    """The cycle records, in append order. `record append` schema-validates
    every line, so the journal is clean by construction."""
    path = cfg.state_dir / "records.jsonl"
    if not path.exists():
        return []
    records = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
    if suite:
        records = [r for r in records if r.get("suite") == suite]
    return records


def gather(cfg: Config, gaps: list[Gap], records: list[dict],
           suite: str | None = None) -> dict:
    """Everything the report states, as one plain dict — the markdown and the
    JSON format render the same gathered facts."""
    parked_ids = ParkedStore(cfg.root).ids()
    progress = _progress(cfg, gaps, parked_ids)
    return {
        "project": cfg.name,
        "generated_at": time.strftime("%Y-%m-%d %H:%M"),
        "suite": suite or "",
        "progress": progress,
        "cycles": _cycles(records),
        "eta": _eta(progress["workable"], records),
        "diff": _diff(cfg, records),
        "residuals": _residuals(records),
    }


def _progress(cfg: Config, gaps: list[Gap], parked_ids: set[str]) -> dict:
    """Closed/open/parked counts per suite, class, and severity. Parking is
    run state, so a parked gap is counted in its own column, not under open."""
    def bucket(key) -> list[dict]:
        rows: dict[str, dict] = {}
        for g in gaps:
            row = rows.setdefault(key(g), {"closed": 0, "open": 0, "parked": 0})
            if g.status is Status.CLOSED:
                row["closed"] += 1
            elif g.status in (Status.OPEN, Status.SCULPTING):
                row["parked" if g.id in parked_ids else "open"] += 1
        return [{"name": k, **v} for k, v in sorted(rows.items())]

    is_open = [g for g in gaps if g.status in (Status.OPEN, Status.SCULPTING)]
    return {
        "by_suite": bucket(lambda g: g.suite),
        "by_class": bucket(lambda g: g.gap_class.value),
        "by_severity": bucket(lambda g: g.severity.value),
        # Workable = open minus review-gated; permanent claims never count as
        # open. Parked gaps stay workable — they wait on a human, not the loop.
        "workable": sum(1 for g in is_open if not review_gated(g)),
        "review_gated": sum(1 for g in is_open if review_gated(g)),
        "parked": sum(1 for g in is_open if g.id in parked_ids),
    }


def _cycles(records: list[dict]) -> dict:
    rows = [{"cycle": r.get("cycle", ""), "gap": r.get("gap", ""),
             "status": r.get("status", ""),
             "wall_clock_s": float(r.get("wall_clock_s", 0)),
             "net_new_gaps": int(r.get("net_new_gaps", 0))} for r in records]
    durs = [r["wall_clock_s"] for r in rows]
    return {
        "rows": rows,
        "mean_s": statistics.mean(durs) if durs else None,
        "median_s": statistics.median(durs) if durs else None,
        "last5_mean_s": statistics.mean(durs[-5:]) if durs else None,
    }


def _eta(workable: int, records: list[dict]) -> dict:
    """remaining workable × the median of the last 5 closed-cycle durations,
    bounded by the fastest and slowest of those cycles. Under two closed
    cycles there is no distribution to project from — say so."""
    closed = [float(r.get("wall_clock_s", 0))
              for r in records if r.get("status") == "closed"]
    if len(closed) < 2:
        return {"insufficient": True, "closed_cycles": len(closed)}
    basis = closed[-5:]
    median = statistics.median(basis)
    return {
        "insufficient": False,
        "remaining_workable": workable,
        "basis_cycles": len(basis),
        "median_s": median,
        "expected_s": workable * median,
        "optimistic_s": workable * min(basis),
        "pessimistic_s": workable * max(basis),
    }


def _residuals(records: list[dict]) -> dict:
    """The claims-filed-vs-closed honesty line: cycles that net-filed gaps."""
    return {
        "cycles": len(records),
        "net_new_filed": sum(int(r.get("net_new_gaps", 0)) for r in records
                             if int(r.get("net_new_gaps", 0)) > 0),
    }


# ── git range analysis ────────────────────────────────────────────────────


def _git(tree: Path, *args: str) -> str | None:
    try:
        r = subprocess.run(["git", "-C", str(tree), *args],
                           capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout if r.returncode == 0 else None


def _parent(tree: Path, commit: str) -> str:
    out = _git(tree, "rev-parse", f"{commit}^")
    return out.strip() if out else _EMPTY_TREE


def _range(tree: Path, records: list[dict]) -> tuple[str | None, str | None, str]:
    """(base, head, how-derived). Commit hashes in the records pin the range
    exactly; records without them cover everything committed since the first
    record began."""
    hashes: list[str] = []
    for r in records:
        c = r.get("commit") or r.get("commits")
        if isinstance(c, str) and c:
            hashes.append(c)
        elif isinstance(c, list):
            hashes.extend(str(x) for x in c if x)
    if hashes:
        return _parent(tree, hashes[0]), hashes[-1], "commits recorded by the cycles"
    stamps = sorted(str(r.get("started_at") or r.get("finished_at") or "")
                    for r in records)
    since = next((s for s in stamps if s), "")
    if not since:
        return None, None, "records carry no commits and no timestamps"
    out = _git(tree, "log", "--since", since, "--reverse", "--pretty=%H")
    commits = out.split() if out else []
    if not commits:
        return None, None, f"no commits since the first record ({since})"
    return _parent(tree, commits[0]), "HEAD", f"--since={since} (first record)"


def _diff(cfg: Config, records: list[dict]) -> dict | None:
    """Lines, files, top dirs, the honesty scan, and the sensitive-touch list
    over the run's git range. None when the target tree is not a git repo."""
    tree = cfg.tree
    if tree is None or _git(tree, "rev-parse", "--is-inside-work-tree") is None:
        return None
    base, head, how = _range(tree, records)
    if base is None:
        return {"note": how}
    span = f"{base}..{head}"

    added = deleted = 0
    files: list[tuple[int, str]] = []   # (churn, path)
    for line in (_git(tree, "diff", "--numstat", span) or "").splitlines():
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        a = int(parts[0]) if parts[0].isdigit() else 0
        d = int(parts[1]) if parts[1].isdigit() else 0
        added, deleted = added + a, deleted + d
        files.append((a + d, parts[2]))
    files.sort(key=lambda t: t[0], reverse=True)

    dirs: list[tuple[float, str]] = []
    for line in (_git(tree, "diff", "--dirstat", span) or "").splitlines():
        pct, _, d = line.strip().partition("% ")
        try:
            dirs.append((float(pct), d))
        except ValueError:
            continue
    dirs.sort(key=lambda t: t[0], reverse=True)

    patch = _git(tree, "diff", span) or ""
    added_lines = [l[1:] for l in patch.splitlines()
                   if l.startswith("+") and not l.startswith("+++")]
    markers = [{"pattern": pat,
                "added_lines": sum(1 for l in added_lines if rx.search(l))}
               for pat in cfg.report_suppression_patterns
               for rx in (re.compile(pat),)]

    top = [p for _, p in files[:_TOP_FILES]]
    sensitive = [p for p in top
                 if any(fnmatch.fnmatch(p, g) for g in cfg.report_sensitive_paths)]

    return {
        "range": f"{base[:12]}..{head if head == 'HEAD' else head[:12]}",
        "how": how,
        "added": added,
        "deleted": deleted,
        "files_touched": len(files),
        "top_dirs": [{"percent": p, "dir": d} for p, d in dirs[:5]],
        "markers": markers,
        "sensitive": sensitive,
        "note": "",
    }


# ── rendering ─────────────────────────────────────────────────────────────


def _dur(seconds: float) -> str:
    s = int(round(seconds))
    if s < 60:
        return f"{s}s"
    if s < 3600:
        return f"{s // 60}m" + (f" {s % 60}s" if s % 60 else "")
    return f"{s // 3600}h" + (f" {s % 3600 // 60}m" if s % 3600 // 60 else "")


def _table(headers: list[str], rows: list[list[str]], numeric_from: int = 1) -> list[str]:
    align = ["---" if i < numeric_from else "---:" for i in range(len(headers))]
    out = ["| " + " | ".join(headers) + " |", "| " + " | ".join(align) + " |"]
    out += ["| " + " | ".join(r) + " |" for r in rows]
    return out


def to_markdown(data: dict) -> str:
    out = [f"# run report — {data['project']}"
           + (f" · suite {data['suite']}" if data["suite"] else "")
           + f" · {data['generated_at']}"]

    prog = data["progress"]
    out += ["", "## Progress"]
    for label, key in (("suite", "by_suite"), ("class", "by_class"),
                       ("severity", "by_severity")):
        rows = [[r["name"], str(r["closed"]), str(r["open"]), str(r["parked"])]
                for r in prog[key]]
        out += [""] + _table([label, "closed", "open", "parked"], rows)
    out += ["", f"workable now: {prog['workable']} "
            f"(open minus the {prog['review_gated']} review-gated; "
            f"permanent claims never count)"]

    cyc = data["cycles"]
    out += ["", "## Cycles", ""]
    if not cyc["rows"]:
        out += ["no run records yet — the dataset starts with the first cycle."]
    else:
        rows = [[r["cycle"], r["gap"], r["status"], _dur(r["wall_clock_s"]),
                 str(r["net_new_gaps"])] for r in cyc["rows"]]
        out += _table(["cycle", "gap", "status", "wall-clock", "net new gaps"],
                      rows, numeric_from=3)
        out += ["", f"mean {_dur(cyc['mean_s'])} · median {_dur(cyc['median_s'])} "
                f"· last-5 mean {_dur(cyc['last5_mean_s'])}"]

    eta = data["eta"]
    out += ["", "## ETA", ""]
    if eta["insufficient"]:
        out += [f"insufficient data — {eta['closed_cycles']} closed cycle(s) "
                f"recorded; the projection starts at the second close."]
    else:
        out += [f"remaining workable: {eta['remaining_workable']} gap(s)",
                f"expected: {eta['remaining_workable']} × {_dur(eta['median_s'])} "
                f"(median of the last {eta['basis_cycles']} closed cycles) "
                f"≈ {_dur(eta['expected_s'])}",
                f"optimistic {_dur(eta['optimistic_s'])} (fastest of those) · "
                f"pessimistic {_dur(eta['pessimistic_s'])} (slowest)",
                "",
                "assumes future cycles resemble the recent closed ones; parked "
                "gaps still count as workable (they wait on a human, not the loop)."]

    diff = data["diff"]
    out += ["", "## Diff", ""]
    if diff is None:
        out += ["target tree is not a git repository — diff analysis skipped."]
    elif diff.get("note"):
        out += [f"no range to diff: {diff['note']}."]
    else:
        out += [f"range {diff['range']} ({diff['how']})",
                f"+{diff['added']} / −{diff['deleted']} line(s) "
                f"across {diff['files_touched']} file(s)"]
        if diff["top_dirs"]:
            out += ["top dirs: " + " · ".join(
                f"{d['dir']} {d['percent']:.1f}%" for d in diff["top_dirs"])]
        out += ["", "### Honesty markers (added lines)", ""]
        marker_rows = []
        for m in diff["markers"]:
            cell = m["pattern"].replace("|", "\\|")  # keep the table a table
            marker_rows.append([f"`{cell}`", str(m["added_lines"])])
        out += _table(["pattern", "hits"], marker_rows)
        if diff["sensitive"]:
            out += ["", "### Review before signing", ""]
            out += [f"- {p}" for p in diff["sensitive"]]

    res = data["residuals"]
    out += ["", "## Residuals", "",
            f"{res['cycles']} cycle record(s) · net +{res['net_new_filed']} "
            f"gap(s) filed beyond those closed — a loop that only ever closes "
            f"is not looking."]
    return "\n".join(out)


def run_narrator(command: str, timeout_s: int, markdown: str,
                 records: list[dict]) -> str:
    """Feed the deterministic report + the raw cycle records to the narrator;
    return its prose. Every failure mode raises — the caller already holds
    the deterministic report and must emit it regardless."""
    payload = markdown + "\n" + json.dumps(records, sort_keys=True) + "\n"
    try:
        proc = subprocess.run(shlex.split(command), input=payload,
                              capture_output=True, text=True, timeout=timeout_s)
    except subprocess.TimeoutExpired:
        raise NarratorError(f"narrator timed out after {timeout_s}s")
    except (OSError, ValueError) as e:
        raise NarratorError(f"narrator could not run: {e}")
    if proc.returncode != 0:
        raise NarratorError(f"narrator exited {proc.returncode}: "
                            f"{(proc.stderr or proc.stdout).strip()[:200]}")
    return proc.stdout.strip()
