"""render.py — the deterministic figure renderer (matplotlib).

A thin adapter over `analyze.figure_specs`: the same spec renders to
byte-identical SVG. Fixed rcParams, no timestamps, the paper's validated
colorblind-safe palette (docs/papers/preamble.tex), so the figures are visually
continuous with the paper's tikz and never drift from the tables. The honesty
craft rules the spec pins are drawn here: the hero x-axis spans the full
0–100% (never truncated), Wilson whiskers sit on BOTH dumbbell endpoints, the Δ
is annotated on each segment, refusals are labelled (shipped-bad is
unconditional), and a synthetic watermark is stamped onto the image itself.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

# Paper palette (preamble.tex), validated colorblind-safe with the dataviz
# skill: hero baseline=gred / gated=gblue; decomposition traffic-light with a
# neutral gray for the process-failure noise bucket. Text/axes always ink.
GRED, GBLUE, GGREEN, GAMBER, INK, GRAY = (
    "#D93025", "#4285F4", "#34A853", "#F29900", "#3C4043", "#9AA0A6")


def _rc() -> None:
    plt.rcParams.update({
        "svg.hashsalt": "recurve-eval",   # fixed → deterministic SVG ids
        "svg.fonttype": "none",           # text as text, no font-hash embedding
        "pdf.fonttype": 42,
        "font.family": "serif", "font.size": 9,
        "axes.edgecolor": INK, "axes.labelcolor": INK, "text.color": INK,
        "xtick.color": INK, "ytick.color": INK,
        "axes.spines.top": False, "axes.spines.right": False,
    })


def _save(fig, out_dir, name: str) -> None:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_dir / f"{name}.svg", format="svg", metadata={"Date": None},
                bbox_inches="tight")
    fig.savefig(out_dir / f"{name}.pdf", format="pdf", metadata={"CreationDate": None},
                bbox_inches="tight")
    fig.savefig(out_dir / f"{name}.png", format="png", dpi=200, bbox_inches="tight")
    plt.close(fig)


def _watermark(ax, spec) -> None:
    # Top-left, above the axes — opposite corner from the bottom-right legend, so
    # the synthetic marker travels with the image without competing with it.
    if spec.get("synthetic"):
        ax.text(0.0, 1.04, spec.get("watermark", "(synthetic placeholders)"),
                transform=ax.transAxes, ha="left", va="bottom",
                fontsize=7, color=GRAY, style="italic")


def render_hero(spec, out_dir) -> None:
    rows = spec["hero"]["rows"]
    _rc()
    fig, ax = plt.subplots(figsize=(5.0, 0.8 * len(rows) + 1.2))
    for i, r in enumerate(rows):
        y = len(rows) - 1 - i
        b, g = r["baseline"], r["gated"]
        ax.plot([b["rate"], g["rate"]], [y, y], color=INK, lw=1.2, zorder=1)
        ax.errorbar(b["rate"], y, xerr=[[b["rate"] - b["ci_lo"]], [b["ci_hi"] - b["rate"]]],
                    fmt="o", color=GRED, ms=7, capsize=2, lw=1.2, zorder=3)
        ax.errorbar(g["rate"], y, xerr=[[g["rate"] - g["ci_lo"]], [g["ci_hi"] - g["rate"]]],
                    fmt="o", color=GBLUE, ms=7, capsize=2, lw=1.2, zorder=3)
        ax.annotate(f"Δ {r['delta'] * 100:.1f} pts", ((b["rate"] + g["rate"]) / 2, y),
                    textcoords="offset points", xytext=(0, 9), ha="center", fontsize=8)
        if g.get("refused"):
            # Anchor to the gated dot and extend RIGHT (below the segment), so a
            # low-rate dot's label never hangs off the left edge.
            ax.annotate(f"{g['refused']} refused", (g["rate"], y),
                        textcoords="offset points", xytext=(-3, -13), ha="left",
                        va="top", fontsize=7, color=GRAY)
    ax.set_xlim(0, 1)
    ax.set_xticks([0, .25, .5, .75, 1.0])
    ax.set_xticklabels(["0%", "25%", "50%", "75%", "100%"])
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([r["model"] for r in reversed(rows)])
    ax.set_ylim(-0.6, len(rows) - 0.4)
    ax.set_xlabel("shipped-bad-work rate")
    h = spec["hero"]
    ax.legend([Line2D([0], [0], marker="o", color="w", markerfacecolor=GRED, ms=7),
               Line2D([0], [0], marker="o", color="w", markerfacecolor=GBLUE, ms=7)],
              [f"{h['baseline_arm']} (baseline)", f"{h['gated_arm']} (gated)"],
              loc="lower right", frameon=False, fontsize=8)
    _watermark(ax, spec)
    _save(fig, out_dir, "hero")


def render_decomposition(spec, out_dir) -> None:
    rows = spec["decomposition"]["rows"]
    _rc()
    fig, ax = plt.subplots(figsize=(5.0, 0.8 * len(rows) + 1.2))
    cats = [("fixed", GGREEN), ("refused", GAMBER), ("also_bad", GRED),
            ("process_failed", GRAY)]
    for i, r in enumerate(rows):
        y = len(rows) - 1 - i
        total = max(1, r["among_baseline_bad"])
        left = 0.0
        for key, color in cats:
            v = r.get(key, 0)
            if v <= 0:
                continue
            w = v / total
            ax.barh(y, w, left=left, color=color, height=0.5,
                    edgecolor="white", linewidth=1.4)   # 2px surface gap between fills
            if w > 0.06:
                ax.text(left + w / 2, y, str(v), ha="center", va="center",
                        fontsize=7, color="white")
            left += w
    ax.set_xlim(0, 1)
    ax.set_xticks([0, .25, .5, .75, 1.0])
    ax.set_xticklabels(["0%", "25%", "50%", "75%", "100%"])
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([r["model"] for r in reversed(rows)])
    ax.set_ylim(-0.6, len(rows) - 0.4)
    ax.set_xlabel("of tasks the baseline shipped bad")
    ax.legend([Patch(color=c) for _, c in cats], [k for k, _ in cats],
              loc="lower right", frameon=False, fontsize=7, ncol=2)
    _watermark(ax, spec)
    _save(fig, out_dir, "decomposition")


def render_figures(spec, out_dir) -> None:
    """Render every figure for a spec into out_dir (SVG + PDF)."""
    render_hero(spec, out_dir)
    render_decomposition(spec, out_dir)
