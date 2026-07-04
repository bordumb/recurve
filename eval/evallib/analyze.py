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


def analyze_and_emit(results_path: str | Path, out_dir: str | Path,
                     synthetic: bool = False) -> str:
    """The one deterministic pass: results.jsonl -> tables AND figures, into
    out_dir. Tables (stdlib) always emit; figures render if matplotlib is
    installed (the `figures` extra), so the truth path has no notebook step and
    every graphic regenerates from the data with one command."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = [json.loads(l) for l in Path(results_path).read_text().splitlines() if l.strip()]
    md = analyze_rows(rows)
    (out_dir / "summary.md").write_text(md)
    try:
        from evallib.render import render_figures
        render_figures(figure_specs(rows, synthetic=synthetic), out_dir)
    except ImportError:
        pass  # matplotlib absent — the tables still emit; figures are the extra
    return md


# --- figures as data --------------------------------------------------------
#
# The figure SPEC is a pure, deterministic function of the results — the same
# rows in any order give the same spec. Rendering (render.py, matplotlib) is a
# thin adapter over it, so a figure can never silently drift from the tables.
# Roles are inferred from the data (a gated arm's rows carry `gate_outcome`), so
# nothing here is baked to a particular arm name.


def _roles(rows: list[dict]) -> tuple[str | None, str | None]:
    """Infer (baseline_arm, gated_arm): a gated arm is one whose rows carry a
    `gate_outcome`; a baseline arm is one whose rows never do."""
    gated_flag: dict[str, bool] = {}
    for r in rows:
        gated_flag.setdefault(r["arm"], False)
        if r.get("gate_outcome") is not None:
            gated_flag[r["arm"]] = True
    baseline = sorted(a for a, g in gated_flag.items() if not g)
    gated = sorted(a for a, g in gated_flag.items() if g)
    return (baseline[0] if baseline else None), (gated[0] if gated else None)


def figure_specs(rows: list[dict], synthetic: bool = False) -> dict:
    """The hero dumbbell (baseline→gated shipped-bad per model, Wilson-95% on
    both endpoints, delta, refused count) and the Fig-2 decomposition (among
    baseline-shipped-bad tasks, what the gated arm did: fixed / refused /
    also-shipped-bad / process-failed). Deterministic and order-invariant."""
    rows = sorted(rows, key=lambda r: (r["model"], r["arm"], r["task_id"]))
    m = metrics(rows)
    base_arm, gated_arm = _roles(rows)

    hero_rows, decomp_rows = [], []
    for model in sorted(m):
        am = m[model]
        b, g = am.get(base_arm, {}), am.get(gated_arm, {})
        blo, bhi = wilson(b.get("false_done", 0), b.get("n", 0))
        glo, ghi = wilson(g.get("false_done", 0), g.get("n", 0))
        refused = sum(1 for r in rows if r["model"] == model
                      and r["arm"] == gated_arm and r.get("gate_outcome") == "gate_refused")
        hero_rows.append({
            "model": model,
            "baseline": {"arm": base_arm, "rate": b.get("shipped_bad_rate", 0.0),
                         "ci_lo": blo, "ci_hi": bhi, "n": b.get("n", 0)},
            "gated": {"arm": gated_arm, "rate": g.get("shipped_bad_rate", 0.0),
                      "ci_lo": glo, "ci_hi": ghi, "n": g.get("n", 0), "refused": refused},
            "delta": b.get("shipped_bad_rate", 0.0) - g.get("shipped_bad_rate", 0.0),
        })
        base_bad = {r["task_id"] for r in rows if r["model"] == model
                    and r["arm"] == base_arm and r.get("declared_done")
                    and r.get("oracle_verdict") != "pass"}
        gated_by_task = {r["task_id"]: r for r in rows if r["model"] == model
                         and r["arm"] == gated_arm}
        fixed = refused_d = also = proc = 0
        for t in sorted(base_bad):
            gr = gated_by_task.get(t, {})
            go = gr.get("gate_outcome")
            if go == "gate_refused":
                refused_d += 1
            elif go == "process_failed":
                proc += 1
            elif gr.get("declared_done") and gr.get("oracle_verdict") == "pass":
                fixed += 1
            elif gr.get("declared_done"):
                also += 1
            else:
                refused_d += 1
        decomp_rows.append({"model": model, "among_baseline_bad": len(base_bad),
                            "fixed": fixed, "refused": refused_d, "also_bad": also,
                            "process_failed": proc})

    spec = {
        "synthetic": synthetic,
        "hero": {"kind": "dumbbell", "metric": "shipped_bad_rate",
                 "x_domain": [0.0, 1.0], "baseline_arm": base_arm,
                 "gated_arm": gated_arm, "rows": hero_rows},
        "decomposition": {"kind": "stacked_bar", "rows": decomp_rows},
    }
    if synthetic:
        spec["watermark"] = "(synthetic placeholders)"
    return spec


def spec_is_honest(spec: dict) -> bool:
    """The honesty craft rules, as a guard: the hero x-axis spans the full
    [0,1] (never truncated to inflate an effect), and a synthetic spec carries a
    watermark that the renderer stamps onto the image itself."""
    if spec.get("hero", {}).get("x_domain") != [0.0, 1.0]:
        return False
    if spec.get("synthetic") and not spec.get("watermark"):
        return False
    return True
