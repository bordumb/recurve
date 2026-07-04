"""analyze.py — results.jsonl → the §4 tables, deterministically.

A pure function of the results: same rows in any order produce byte-identical
output. No notebook state, no scipy — Wilson intervals and paired McNemar are
closed-form in stdlib, so the analysis is reproducible from the JSONL alone.
The metrics are the plan's §4: shipped-bad-work rate, FDR (false-done rate),
ΔFDR per model, oracle pass rate, and the paired McNemar within each model.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

_Z = 1.959963984540054  # 95% normal quantile


def wilson(k: int, n: int) -> tuple[float, float]:
    """Wilson 95% score interval for a binomial rate. (0.0, 0.0) for n=0."""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    z2 = _Z * _Z
    denom = 1 + z2 / n
    center = (p + z2 / (2 * n)) / denom
    half = (_Z * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n))) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def _rate(k: int, n: int) -> float:
    return k / n if n else 0.0


def metrics(rows: list[dict]) -> dict:
    """Per-model, per-arm metrics plus ΔFDR. `oracle_verdict == 'pass'` is an
    oracle pass; `declared_done ∧ not pass` is shipped-bad / false-done."""
    by: dict[str, dict[str, dict]] = {}
    for r in rows:
        arm = by.setdefault(r["model"], {}).setdefault(
            r["arm"], {"n": 0, "declared": 0, "oracle_pass": 0, "false_done": 0})
        arm["n"] += 1
        passed = r.get("oracle_verdict") == "pass"
        declared = bool(r.get("declared_done"))
        arm["oracle_pass"] += int(passed)
        arm["declared"] += int(declared)
        arm["false_done"] += int(declared and not passed)
    out: dict[str, dict] = {}
    for model in sorted(by):
        arms = {}
        for arm in sorted(by[model]):
            a = by[model][arm]
            arms[arm] = {
                **a,
                "shipped_bad_rate": _rate(a["false_done"], a["n"]),
                "oracle_pass_rate": _rate(a["oracle_pass"], a["n"]),
                "fdr": _rate(a["false_done"], a["declared"]),
            }
        entry = dict(arms)
        if "A0" in arms and "A3" in arms:
            entry["delta_fdr"] = arms["A0"]["fdr"] - arms["A3"]["fdr"]
        out[model] = entry
    return out


def mcnemar(rows: list[dict], model: str) -> dict:
    """Paired McNemar on oracle outcomes for A0 vs A3 on the same task within a
    model. b = A0-pass/A3-fail, c = A0-fail/A3-pass; the discordant pairs are
    what carry the signal. Continuity-corrected chi-square."""
    a0 = {r["task_id"]: (r.get("oracle_verdict") == "pass")
          for r in rows if r["model"] == model and r["arm"] == "A0"}
    a3 = {r["task_id"]: (r.get("oracle_verdict") == "pass")
          for r in rows if r["model"] == model and r["arm"] == "A3"}
    b = c = 0
    for t in sorted(set(a0) & set(a3)):
        if a0[t] and not a3[t]:
            b += 1
        elif a3[t] and not a0[t]:
            c += 1
    stat = ((abs(b - c) - 1) ** 2) / (b + c) if (b + c) else 0.0
    return {"b": b, "c": c, "statistic": stat, "discordant": b + c}


def analyze_rows(rows: list[dict]) -> str:
    """Render the deterministic summary. Rows may arrive in any order; the
    output is byte-identical for the same multiset of rows."""
    rows = sorted(rows, key=lambda r: (r["model"], r["arm"], r["task_id"]))
    m = metrics(rows)
    lines = ["# Eval summary", "",
             "Per model × arm (raw fractions shown; Wilson 95%).", ""]
    for model in sorted(m):
        lines.append(f"## {model}")
        lines.append("")
        lines.append("| arm | n | declared | oracle_pass | shipped_bad | FDR | FDR 95% |")
        lines.append("|---|---|---|---|---|---|---|")
        for arm in sorted(k for k in m[model] if k != "delta_fdr"):
            a = m[model][arm]
            lo, hi = wilson(a["false_done"], a["declared"])
            lines.append(
                f"| {arm} | {a['n']} | {a['declared']} | "
                f"{a['oracle_pass']}/{a['n']} ({a['oracle_pass_rate']:.3f}) | "
                f"{a['false_done']}/{a['n']} ({a['shipped_bad_rate']:.3f}) | "
                f"{a['false_done']}/{a['declared']} ({a['fdr']:.3f}) | "
                f"[{lo:.3f}, {hi:.3f}] |")
        if "delta_fdr" in m[model]:
            mc = mcnemar(rows, model)
            lines.append("")
            lines.append(f"ΔFDR (A0 − A3): {m[model]['delta_fdr']:.3f}  ·  "
                         f"McNemar b={mc['b']} c={mc['c']} χ²={mc['statistic']:.3f} "
                         f"(discordant {mc['discordant']})")
        lines.append("")
    return "\n".join(lines) + "\n"


def analyze_file(path: str | Path) -> str:
    rows = [json.loads(l) for l in Path(path).read_text().splitlines() if l.strip()]
    return analyze_rows(rows)
