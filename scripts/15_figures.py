"""
Step 15 - Publication figures.

Three figures, each carrying one claim:

  Fig 1  Pakistani K. pneumoniae is extraordinarily capsule-diverse.
  Fig 2  The types with no phage are high-burden and carbapenemase-heavy.
  Fig 3  Those same types are South Asian ones, absent where phages are made.

Colour choices are constrained, not decorative:

  * Okabe-Ito is used throughout. It is a published colourblind-safe palette;
    the skill's own validator needs Node, which is not installed here, so a
    pre-validated palette is the honest substitute for running the check.
  * Colour never encodes rank, only identity/status, so filtering or reordering
    cannot repaint a series.
  * No dual axes anywhere. Where two measures appear they share one scale.
  * Identity is never colour-alone: every coloured category is also either
    directly labelled or marked with a glyph.

Usage:
    python scripts/15_figures.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.patches import Patch

from config import FIGURES as OUTDIR
from config import PROCESSED as DATA

# Okabe-Ito
BLUE = "#0072B2"
VERM = "#D55E00"
ORANGE = "#E69F00"
GREEN = "#009E73"
GREY = "#BDBDBD"

INK = "#222222"
INK2 = "#555555"
INK3 = "#888888"


def style() -> None:
    plt.rcParams.update({
        "figure.dpi": 300,
        "savefig.dpi": 300,
        "font.family": "DejaVu Sans",
        "font.size": 8,
        "axes.edgecolor": INK3,
        "axes.linewidth": 0.6,
        "axes.labelcolor": INK,
        "axes.titlesize": 9.5,
        "axes.titleweight": "bold",
        "axes.titlecolor": INK,
        "xtick.color": INK2,
        "ytick.color": INK2,
        "xtick.labelsize": 7.5,
        "ytick.labelsize": 7.5,
        "legend.frameon": False,
        "legend.fontsize": 7.5,
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.03,
    })


def despine(ax, keep=("left", "bottom")) -> None:
    for side in ("top", "right", "left", "bottom"):
        ax.spines[side].set_visible(side in keep)


def save(fig, name: str) -> None:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    for ext in ("png", "pdf"):
        fig.savefig(OUTDIR / f"{name}.{ext}")
    plt.close(fig)
    print(f"  wrote {name}.png / .pdf")


# ---------------------------------------------------------------- figure 1
def figure1(tgt: pd.DataFrame) -> None:
    """Rank-abundance of all 66 capsule types - the diversity claim.

    Every type is drawn, not just the top slice: the flat tail *is* the finding,
    and truncating it would hide exactly what the figure is meant to show.
    """
    d = tgt.sort_values("n_isolates", ascending=False).reset_index(drop=True)
    x = range(len(d))

    fig, ax = plt.subplots(figsize=(7.2, 2.9))
    ax.bar(x, d["n_carbapenemase"], width=0.78, color=BLUE,
           label="carbapenemase-positive", zorder=3)
    ax.bar(x, d["n_isolates"] - d["n_carbapenemase"], width=0.78,
           bottom=d["n_carbapenemase"], color=GREY,
           label="carbapenemase-negative", zorder=3)

    for i in range(6):
        ax.text(i, d.loc[i, "n_isolates"] + 0.6, d.loc[i, "k_locus"],
                ha="center", va="bottom", fontsize=6.5, color=INK,
                rotation=90)

    n_single = int((d["n_isolates"] == 1).sum())
    top6 = 100 * d.head(6)["n_isolates"].sum() / d["n_isolates"].sum()
    ax.annotate(f"{n_single} types seen in only one patient",
                xy=(len(d) - n_single / 2, 1.4), xytext=(len(d) * 0.60, 12),
                fontsize=7, color=INK2,
                arrowprops=dict(arrowstyle="->", color=INK3, lw=0.6))

    ax.set_xlim(-1, len(d))
    ax.set_ylim(0, 28)
    ax.set_xlabel("capsule (K-locus) type, ranked by frequency", color=INK2)
    ax.set_ylabel("isolates", color=INK2)
    ax.set_title(f"Pakistani clinical $\\it{{K.\\ pneumoniae}}$: "
                 f"{len(d)} capsule types among "
                 f"{int(d['n_isolates'].sum())} isolates", loc="left")
    ax.set_xticks([])
    ax.grid(axis="y", color=INK3, alpha=0.22, lw=0.5, zorder=0)
    despine(ax, keep=("bottom",))
    ax.legend(loc="upper right", handlelength=1.2)
    ax.text(0.995, 0.62, f"top 6 types = {top6:.0f}% of isolates",
            transform=ax.transAxes, ha="right", fontsize=7, color=INK2)
    save(fig, "fig1_capsule_diversity")


# ---------------------------------------------------------------- figure 2
def figure2(gap: pd.DataFrame, ind: pd.DataFrame | None) -> None:
    """Burden vs published phage coverage, top 20 types.

    Types whose Pakistani isolates come overwhelmingly from one BioProject are
    daggered. Without that mark the bar for KL81 reads as 13 independent
    patients when it is one sampling event, which is the single most misleading
    thing this figure could do.
    """
    d = gap.sort_values("n_isolates", ascending=False).head(20).copy()
    share = {}
    if ind is not None and "pak_max_project_share" in ind:
        share = dict(zip(ind["k_locus"], ind["pak_max_project_share"]))
    d = d.iloc[::-1]  # largest at top after barh
    y = range(len(d))
    colors = [VERM if s == "UNCOVERED" else BLUE for s in d["status"]]

    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    ax.barh(y, d["n_isolates"], height=0.72, color=colors, zorder=3)
    # Carbapenemase load as an inset tick, sharing the same x scale (no 2nd axis)
    ax.barh(y, d["n_carbapenemase"], height=0.26, color=INK, alpha=0.55,
            zorder=4)

    labels = [f"{k} †" if share.get(k, 0) >= 0.75 else k for k in d["k_locus"]]
    ax.set_yticks(list(y))
    ax.set_yticklabels(labels, fontsize=7.5)
    for tick, s in zip(ax.get_yticklabels(), d["status"]):
        if s == "UNCOVERED":
            tick.set_fontweight("bold")
            tick.set_color(INK)

    for i, (n, st) in enumerate(zip(d["n_isolates"], d["status"])):
        if st == "UNCOVERED":
            ax.text(n + 0.4, i, "no phage", va="center", fontsize=6.8,
                    color=VERM, fontweight="bold")

    ax.set_xlabel("isolates  (inner dark bar = carbapenemase-positive)",
                  color=INK2)
    fig.text(0.5, -0.015,
             "† ≥75% of this type's Pakistani isolates come from a single "
             "BioProject — treat the count as one sampling event, not "
             "independent patients.",
             ha="center", fontsize=6.6, color=INK2)
    ax.set_title("Published phage coverage of Pakistan's commonest capsule types",
                 loc="left")
    ax.set_xlim(0, 30)
    ax.grid(axis="x", color=INK3, alpha=0.22, lw=0.5, zorder=0)
    despine(ax, keep=("left",))
    ax.legend(handles=[
        Patch(facecolor=BLUE, label="phage or depolymerase published"),
        Patch(facecolor=VERM, label="no published phage"),
    ], loc="lower right", handlelength=1.2)
    save(fig, "fig2_phage_coverage")


# ---------------------------------------------------------------- figure 3
def figure3(sa: pd.DataFrame, ind: pd.DataFrame) -> None:
    """South Asia vs the phage-producing regions - the mechanism.

    Sorted by difference so the two poles read as one gradient: South
    Asian-enriched types at the top, phage-source-enriched at the bottom.
    """
    d = sa[(sa["p_fisher"] < 0.05) | (sa["diff_pct"].abs() >= 2)].copy()
    d = d.merge(ind[["k_locus", "p_raw", "p_collapsed", "verdict"]],
                on="k_locus", how="left")
    d = d.sort_values(["diff_pct", "k_locus"],
                      ascending=[True, True]).reset_index(drop=True)
    y = range(len(d))
    h = 0.36

    fig, ax = plt.subplots(figsize=(7.2, 5.0))
    ax.barh([i + h / 2 for i in y], d["sa_pct"], height=h, color=BLUE,
            label=f"South Asia (n={int(d['sa_total'].iloc[0])})", zorder=3)
    ax.barh([i - h / 2 for i in y], d["ps_pct"], height=h, color=ORANGE,
            label=f"China / Europe / USA (n={int(d['ps_total'].iloc[0])})",
            zorder=3)

    labels = []
    for _, r in d.iterrows():
        mark = " *" if r["phage_status"] == "UNCOVERED" else ""
        labels.append(f"{r['k_locus']}{mark}")
    ax.set_yticks(list(y))
    ax.set_yticklabels(labels, fontsize=7.5)
    for tick, s in zip(ax.get_yticklabels(), d["phage_status"]):
        if s == "UNCOVERED":
            tick.set_fontweight("bold")

    xmax = max(d["sa_pct"].max(), d["ps_pct"].max())

    # A zero bar renders as nothing, which reads as missing data rather than as
    # a real absence - and absence is the entire point for KL81 and KL107.
    for i, r in d.iterrows():
        if r["sa_pct"] == 0:
            ax.text(0.12, i + h / 2, "0", va="center", fontsize=6.4,
                    color=BLUE, fontweight="bold")
        if r["ps_pct"] == 0:
            ax.text(0.12, i - h / 2, "0", va="center", fontsize=6.4,
                    color=ORANGE, fontweight="bold")

    # Two p-value columns. The raw one is what a naive analysis reports; the
    # collapsed one is what survives when each BioProject counts once. Showing
    # both is the point of the figure - the gap between them is the clonality.
    p_raw_x, p_col_x = xmax * 1.06, xmax * 1.30
    ax.text(p_raw_x, len(d) - 0.45, "p raw", fontsize=6.4, color=INK3)
    ax.text(p_col_x, len(d) - 0.45, "p collapsed", fontsize=6.4, color=INK)
    for i, r in d.iterrows():
        raw, col, v = r["p_raw"], r["p_collapsed"], r["verdict"]
        ax.text(p_raw_x, i, f"{raw:.3f}" if raw >= 0.001 else "<0.001",
                va="center", fontsize=6.4, color=INK3)
        if pd.isna(col):
            continue
        robust = v == "robust"
        ax.text(p_col_x, i, f"{col:.3f}" if col >= 0.001 else "<0.001",
                va="center", fontsize=6.6,
                color=INK if robust else (VERM if v == "clonal" else INK2),
                fontweight="bold" if robust else "normal")
        if v == "clonal":
            ax.text(p_col_x + xmax * 0.11, i, "clonal", va="center",
                    fontsize=6.0, color=VERM, style="italic")

    ax.set_xlim(0, xmax * 1.62)
    ax.set_ylim(-0.8, len(d) - 0.2)
    ax.set_xlabel("% of typed genomes in region", color=INK2)
    ax.set_title("Capsule types differ between South Asia and the regions\n"
                 "where $\\it{Klebsiella}$ phages are isolated", loc="left")
    ax.grid(axis="x", color=INK3, alpha=0.22, lw=0.5, zorder=0)
    despine(ax, keep=("left",))
    # Parked in the whitespace beside the short bars: the lower-right corner is
    # taken by the longest bars, the upper-right by the p-value column, and
    # above the axes by a two-line title.
    ax.legend(loc="center left", bbox_to_anchor=(0.30, 0.47), ncol=1,
              handlelength=1.2)
    fig.text(0.5, -0.035,
             "* no published phage for this capsule type.    Bars show raw "
             "frequencies; 'p collapsed' counts each BioProject once per type.\n"
             "Bold = survives Bonferroni correction (α = 0.003) after "
             "collapsing.  'clonal' = significant only before collapsing.",
             ha="center", fontsize=6.6, color=INK2)
    save(fig, "fig3_geography")


def main() -> int:
    style()
    tgt = pd.read_csv(DATA / "kp_klocus_target_list.csv")
    gap = pd.read_csv(DATA / "kp_coverage_gap.csv")
    sa = pd.read_csv(DATA / "kp_southasia_vs_phagesource.csv")
    sa["phage_status"] = sa["phage_status"].fillna("not_in_PK_cohort")
    ind_path = DATA / "kp_independence_check.csv"
    if not ind_path.exists():
        print("Run 16_independence_check.py first - figures 2 and 3 report "
              "BioProject-collapsed statistics.")
        return 1
    ind = pd.read_csv(ind_path)

    print("Rendering figures:")
    figure1(tgt)
    figure2(gap, ind)
    figure3(sa, ind)
    print(f"\nAll figures -> {OUTDIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
