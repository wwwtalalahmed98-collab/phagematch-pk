"""
Step 16 - How independent are the observations?

Sample size is the obvious question to ask of a comparative genomics study, but
it is rarely the binding one. Public genome collections are built from outbreak
investigations and single-centre studies, so ten genomes from one BioProject may
represent one transmission chain rather than ten independent samples. Where that
happens, a Fisher test on raw counts is answering a question nobody asked.

This script reports, for each capsule type of interest, how many distinct
BioProjects contribute to it - on both the Pakistani and comparison sides - and
re-runs the geographic test with each BioProject collapsed to one genome per
capsule type. Findings that survive that collapse are driven by geography;
findings that vanish were driven by clonal expansion.

Usage:
    python scripts/16_independence_check.py
"""

from __future__ import annotations

from math import comb
from pathlib import Path

import pandas as pd

from config import PROCESSED as DATA
KCOL = "klebsiella_pneumo_complex__kaptive__K_locus"
CONF = "klebsiella_pneumo_complex__kaptive__K_locus_confidence"
SOUTH = {"india", "bangladesh_nepal"}
FOCUS = ["KL81", "KL10", "KL15", "KL36", "KL48", "KL107", "KL51", "KL64"]


def fisher(a: int, b: int, c: int, d: int) -> float:
    n, r1, c1 = a + b + c + d, a + b, a + c

    def p_of(x: int) -> float:
        return comb(r1, x) * comb(n - r1, c1 - x) / comb(n, c1)

    lo, hi = max(0, c1 - (n - r1)), min(r1, c1)
    obs = p_of(a)
    return min(1.0, sum(q for x in range(lo, hi + 1)
                        if (q := p_of(x)) <= obs * (1 + 1e-9)))


def load_comparison() -> pd.DataFrame:
    comp = pd.read_csv(DATA / "kleborate_comparison_kp.csv",
                       dtype=str, low_memory=False)
    keys = pd.read_csv(DATA / "kp_comparison_keys.csv", dtype=str)
    m = comp.merge(keys[["assembly", "group", "bioproject"]],
                   left_on="strain", right_on="assembly", how="left")
    return m[m[CONF] == "Typeable"]


def load_pakistan() -> pd.DataFrame | None:
    """The Pakistani table was already tidied upstream: it carries a normalised
    lowercase `k_locus` column and its own `bioproject`, so no merge is needed.
    Matching is case-insensitive because the two cohorts came through different
    tidying paths and their K-locus columns are not named identically."""
    typed = DATA / "kp_pakistan_typed.csv"
    if not typed.exists():
        return None
    t = pd.read_csv(typed, dtype=str, low_memory=False)
    kc = next((c for c in t.columns if c.lower() == "k_locus"), None)
    if kc is None:
        kc = next((c for c in t.columns
                   if c.lower().endswith("kaptive__k_locus")), None)
    if kc is None or "bioproject" not in t.columns:
        return None
    return t.rename(columns={kc: KCOL})


def main() -> int:
    m = load_comparison()

    print("=== Comparison set: BioProject spread per capsule type ===")
    print(f"{'K-locus':<9}{'n':>4}{'projects':>10}   largest project share")
    print("-" * 58)
    for k in FOCUS:
        s = m[m[KCOL] == k]
        if not len(s):
            continue
        vc = s["bioproject"].value_counts()
        share = vc.iloc[0] / len(s)
        warn = "  <-- clonal risk" if share >= 0.5 and len(s) >= 4 else ""
        print(f"{k:<9}{len(s):>4}{s['bioproject'].nunique():>10}   "
              f"{vc.iloc[0]}/{len(s)} ({share:.0%}){warn}")

    pak = load_pakistan()
    if pak is not None:
        print("\n=== Pakistani cohort: BioProject spread per capsule type ===")
        print(f"{'K-locus':<9}{'n':>4}{'projects':>10}   largest project share")
        print("-" * 58)
        for k in FOCUS:
            s = pak[pak[KCOL] == k]
            if not len(s):
                continue
            vc = s["bioproject"].value_counts(dropna=False)
            share = vc.iloc[0] / len(s)
            warn = "  <-- clonal risk" if share >= 0.5 and len(s) >= 4 else ""
            print(f"{k:<9}{len(s):>4}{s['bioproject'].nunique():>10}   "
                  f"{vc.iloc[0]}/{len(s)} ({share:.0%}){warn}")

    print("\n=== Geographic test, raw vs BioProject-collapsed ===")
    ded = m.drop_duplicates(subset=["bioproject", KCOL])

    # Every type the figure might show, not just the hand-picked focus list -
    # the figure must not report a raw p for a type whose collapsed p was never
    # computed.
    counts = m[KCOL].value_counts()
    all_types = sorted(counts[counts >= 4].index.tolist())

    rows = []
    for label, df in [("raw", m), ("collapsed", ded)]:
        sa = df[df["group"].isin(SOUTH)]
        ps = df[~df["group"].isin(SOUTH)]
        for k in all_types:
            s = int((sa[KCOL] == k).sum())
            p_ = int((ps[KCOL] == k).sum())
            rows.append({
                "k_locus": k, "mode": label,
                "sa_n": s, "ps_n": p_,
                "sa_total": len(sa), "ps_total": len(ps),
                "p": round(fisher(s, len(sa) - s, p_, len(ps) - p_), 5),
            })

    df = pd.DataFrame(rows)
    print(f"{'K-locus':<9}{'raw SA/PS':>12}{'raw p':>10}"
          f"{'coll SA/PS':>13}{'coll p':>10}   verdict")
    print("-" * 74)
    for k in FOCUS:
        r = df[(df.k_locus == k) & (df["mode"] == "raw")].iloc[0]
        c = df[(df.k_locus == k) & (df["mode"] == "collapsed")].iloc[0]
        if c["p"] < 0.003:
            verdict = "ROBUST"
        elif c["p"] < 0.05:
            verdict = "weakened"
        elif r["p"] < 0.05:
            verdict = "COLLAPSES - clonal"
        else:
            verdict = "not significant"
        print(f"{k:<9}{f'{r.sa_n}/{r.ps_n}':>12}{r['p']:>10.5f}"
              f"{f'{c.sa_n}/{c.ps_n}':>13}{c['p']:>10.5f}   {verdict}")

    # One row per capsule type, both modes side by side - the shape the figure
    # script and the manuscript table both want.
    wide = (df.pivot(index="k_locus", columns="mode",
                     values=["sa_n", "ps_n", "p"]))
    wide.columns = [f"{a}_{b}" for a, b in wide.columns]
    wide = wide.reset_index()
    wide["verdict"] = [
        "robust" if cp < 0.003 else
        ("weakened" if cp < 0.05 else
         ("clonal" if rp < 0.05 else "ns"))
        for cp, rp in zip(wide["p_collapsed"], wide["p_raw"])
    ]

    # Pakistani-side clonality flag: does one BioProject dominate this type?
    if pak is not None:
        conc = {}
        for k in wide["k_locus"]:
            s = pak[pak[KCOL] == k]
            if len(s):
                vc = s["bioproject"].value_counts(dropna=False)
                conc[k] = round(vc.iloc[0] / len(s), 3)
        wide["pak_max_project_share"] = wide["k_locus"].map(conc)

    out = DATA / "kp_independence_check.csv"
    wide.to_csv(out, index=False)
    print(f"\nCollapsed totals: South Asia {int(df[df['mode']=='collapsed'].sa_total.iloc[0])}, "
          f"phage-source {int(df[df['mode']=='collapsed'].ps_total.iloc[0])}")
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
