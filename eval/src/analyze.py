"""analyze.py — results.jsonl -> tables, with the comparison pair NAMED,
never hardcoded.

The pre-refactor `metrics`/`mcnemar` (`evallib/analyze.py`) compute ΔFDR and
the paired significance test for the literal arms "A0"/"A3" only -- an
ablation run (A4-A10) or SWE-bench (A0 vs A9) gets tables with no ΔFDR line
and no McNemar, and nothing says why. `figure_specs`/`_roles` in the same
file already infer the baseline/gated pair from the data instead of a
literal name -- reused here unchanged, since that part was already right.
This module brings `metrics`/`mcnemar` up to that same standard, and adds
what wasn't there at all: N treatments against one baseline (the ablation
ladder's own shape), a declared `(baseline, treatments)` pair from a
manifest's `[analysis]` table, and a loud, visible message (never a
silent blank) when a declared arm has no rows.
"""

from __future__ import annotations

import json
from pathlib import Path

from evallib.analyze import _endpoint_honest, _roles, figure_specs, spec_is_honest, wilson  # noqa: F401 -- re-exported, reused unchanged


def _rate(k: int, n: int) -> float:
    return k / n if n else 0.0


def _resolve_comparison(rows: list[dict], baseline: str | None,
                        treatments: list[str] | None) -> tuple[str | None, list[str]]:
    """A manifest-declared `(baseline, treatments)` wins; absent one, infer
    via `_roles` (unchanged from `evallib.analyze` -- already correct)."""
    if baseline is not None:
        return baseline, list(treatments or [])
    base, gated = _roles(rows)
    return base, ([gated] if gated else [])


def metrics(rows: list[dict], *, baseline: str | None = None,
           treatments: list[str] | None = None) -> dict:
    """Per-model, per-arm metrics, plus `delta_fdr[<treatment>]` for EVERY
    declared or inferred treatment against the baseline -- not just a
    hardcoded A0-vs-A3 pair. `missing_comparisons` names any declared arm
    absent from this model's own rows, loudly, rather than silently
    producing no ΔFDR line at all."""
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

    base, treats = _resolve_comparison(rows, baseline, treatments)

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
        missing = []
        if base is not None and base in arms:
            for t in sorted(treats):
                if t in arms:
                    entry.setdefault("delta_fdr", {})[t] = arms[base]["fdr"] - arms[t]["fdr"]
                else:
                    missing.append(t)
        elif base is not None:
            missing.append(base)
            missing.extend(sorted(treats))
        if missing:
            entry["missing_comparisons"] = sorted(set(missing))
        out[model] = entry
    return out


def mcnemar(rows: list[dict], model: str, baseline: str, treatment: str) -> dict:
    """Paired McNemar on oracle outcomes for `baseline` vs `treatment` on the
    same task within `model` -- a parameterized pair, not a literal."""
    base = {r["task_id"]: (r.get("oracle_verdict") == "pass")
            for r in rows if r["model"] == model and r["arm"] == baseline}
    treat = {r["task_id"]: (r.get("oracle_verdict") == "pass")
             for r in rows if r["model"] == model and r["arm"] == treatment}
    b = c = 0
    for t in sorted(set(base) & set(treat)):
        if base[t] and not treat[t]:
            b += 1
        elif treat[t] and not base[t]:
            c += 1
    stat = ((abs(b - c) - 1) ** 2) / (b + c) if (b + c) else 0.0
    return {"b": b, "c": c, "statistic": stat, "discordant": b + c}


def analyze_rows(rows: list[dict], *, baseline: str | None = None,
                 treatments: list[str] | None = None) -> str:
    """Render the deterministic summary -- one ΔFDR + McNemar block per
    treatment, and an explicit line for any declared-but-absent arm rather
    than a silent gap. Rows may arrive in any order; the output is
    byte-identical for the same multiset of rows."""
    rows = sorted(rows, key=lambda r: (r["model"], r["arm"], r["task_id"]))
    resolved_base, resolved_treats = _resolve_comparison(rows, baseline, treatments)
    m = metrics(rows, baseline=resolved_base, treatments=resolved_treats)
    lines = ["# Eval summary", "",
             "Per model × arm (raw fractions shown; Wilson 95%).", ""]
    for model in sorted(m):
        lines.append(f"## {model}")
        lines.append("")
        lines.append("| arm | n | declared | oracle_pass | shipped_bad | FDR | FDR 95% |")
        lines.append("|---|---|---|---|---|---|---|")
        for arm in sorted(k for k in m[model] if k not in ("delta_fdr", "missing_comparisons")):
            a = m[model][arm]
            lo, hi = wilson(a["false_done"], a["declared"])
            lines.append(
                f"| {arm} | {a['n']} | {a['declared']} | "
                f"{a['oracle_pass']}/{a['n']} ({a['oracle_pass_rate']:.3f}) | "
                f"{a['false_done']}/{a['n']} ({a['shipped_bad_rate']:.3f}) | "
                f"{a['false_done']}/{a['declared']} ({a['fdr']:.3f}) | "
                f"[{lo:.3f}, {hi:.3f}] |")
        for t in sorted(m[model].get("delta_fdr", {})):
            mc = mcnemar(rows, model, resolved_base, t)
            lines.append("")
            lines.append(f"ΔFDR ({resolved_base} − {t}): {m[model]['delta_fdr'][t]:.3f}  ·  "
                         f"McNemar b={mc['b']} c={mc['c']} χ²={mc['statistic']:.3f} "
                         f"(discordant {mc['discordant']})")
        if m[model].get("missing_comparisons"):
            lines.append("")
            lines.append(f"**missing**: {', '.join(m[model]['missing_comparisons'])} "
                         f"requested but no rows for this model -- no ΔFDR/McNemar computed "
                         f"for {'it' if len(m[model]['missing_comparisons']) == 1 else 'them'}.")
        lines.append("")
    return "\n".join(lines) + "\n"


def analyze_file(path: str | Path, **kw) -> str:
    rows = [json.loads(l) for l in Path(path).read_text().splitlines() if l.strip()]
    return analyze_rows(rows, **kw)


def _read_analysis_manifest(manifest: dict | None) -> tuple[str | None, list[str] | None]:
    a = (manifest or {}).get("analysis") or {}
    return a.get("baseline"), a.get("treatments")


def analyze_and_emit(results_path: str | Path, out_dir: str | Path, *,
                     manifest: dict | None = None, synthetic: bool = False) -> str:
    """The one deterministic pass: results.jsonl -> tables AND figures.
    `manifest`'s own `[analysis]` table (`baseline`/`treatments`) is read if
    given; absent, the existing `_roles` inference is used, unchanged."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = [json.loads(l) for l in Path(results_path).read_text().splitlines() if l.strip()]
    baseline, treatments = _read_analysis_manifest(manifest)
    md = analyze_rows(rows, baseline=baseline, treatments=treatments)
    (out_dir / "summary.md").write_text(md)
    try:
        from evallib.render import render_figures
        render_figures(figure_specs(rows, synthetic=synthetic), out_dir)
    except ImportError:
        pass  # matplotlib absent -- the tables still emit; figures are the extra
    return md
