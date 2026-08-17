"""
Step 14 - Is the Pakistani capsule profile actually different?

Joins the typed comparison genomes back to their country group and asks, per
K-locus, whether Pakistan's frequency departs from each comparison region. This
is the test that decides how the phage-gap finding gets framed: if Pakistan looks
like everywhere else, the gap list is a global statement; if it does not, the
gap list is specifically about under-served Pakistani capsule types.

Two guards matter here:

  * Kaptive confidence. Low-confidence K-locus calls are common and would inflate
    rare types. Anything below the --min-confidence bar is counted as untypeable
    rather than silently trusted.
  * Sample size. The run stopped at 435 of 500 genomes, so groups are ~87 each.
    Fisher's exact is used rather than chi-square because expected counts for
    individual capsule types are small.

Usage:
    python scripts/14_compare_pakistan_vs_world.py
    python scripts/14_compare_pakistan_vs_world.py --min-confidence None
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from config import PROCESSED as DATA
COMP = DATA / "kleborate_comparison_kp.csv"
KEYS = DATA / "kp_comparison_keys.csv"
PAK = DATA / "kp_klocus_target_list.csv"
GAP = DATA / "kp_coverage_gap.csv"
OUT = DATA / "kp_vs_world_klocus.csv"

KCOL = "klebsiella_pneumo_complex__kaptive__K_locus"
CONFCOL = "klebsiella_pneumo_complex__kaptive__K_locus_confidence"

# Kaptive v3 reports a flat Typeable/Untypeable verdict; Kaptive v2 reported a
# graded confidence ladder. Accept either so the script survives a version bump.
TRUSTED = {"Typeable", "Perfect", "Very high", "High", "Good"}
REJECTED = {"Untypeable", "Low", "None"}


def fisher(a: int, b: int, c: int, d: int) -> float:
    """Two-sided Fisher exact p for [[a,b],[c,d]].

    Implemented directly rather than via SciPy: SciPy is a heavy dependency for
    one test, and it is not installed here. Counts are small enough that summing
    the hypergeometric tail is exact and instant.
    """
    from math import comb

    n = a + b + c + d
    r1, c1 = a + b, a + c

    def p_of(x: int) -> float:
        return (comb(r1, x) * comb(n - r1, c1 - x)) / comb(n, c1)

    lo = max(0, c1 - (n - r1))
    hi = min(r1, c1)
    obs = p_of(a)
    # Two-sided: sum every table no more likely than the observed one.
    return min(1.0, sum(p for x in range(lo, hi + 1)
                        if (p := p_of(x)) <= obs * (1 + 1e-9)))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--keep-untypeable", action="store_true",
                    help="keep Kaptive Untypeable/Low-confidence calls")
    args = ap.parse_args()

    for p in (COMP, KEYS, PAK):
        if not p.exists():
            print(f"Missing {p}")
            return 1

    comp = pd.read_csv(COMP, dtype=str, low_memory=False)
    keys = pd.read_csv(KEYS, dtype=str)
    merged = comp.merge(keys[["assembly", "group"]], on="assembly", how="left")

    unmatched = merged["group"].isna().sum()
    print(f"Comparison genomes typed : {len(merged)}")
    print(f"Unmatched to a country   : {unmatched}")

    # Confidence filter. An untypeable call is not evidence of a rare capsule,
    # so keeping them would manufacture spurious "Pakistan-only" types.
    if not args.keep_untypeable:
        ok = merged[CONFCOL].isin(TRUSTED)
        dropped = int((~ok).sum())
        print(f"Dropped as untypeable    : {dropped}")
        merged = merged[ok]

    print(f"Analysed                 : {len(merged)}\n")
    print("Per-group sample sizes:")
    print(merged["group"].value_counts().to_string(), "\n")

    # Pakistani reference distribution
    pak = pd.read_csv(PAK)
    pak_total = int(pak["n_isolates"].sum())
    pak_n = dict(zip(pak["k_locus"], pak["n_isolates"]))

    world_n = merged[KCOL].value_counts().to_dict()
    world_total = len(merged)

    # Tie-break on the locus name. Without it the order comes from set
    # iteration, which Python randomises per process for string keys, so two
    # identical runs emitted different row orders - a reproducibility defect
    # even though every number was the same.
    types = sorted(set(pak_n) | set(world_n),
                   key=lambda k: (-(pak_n.get(k, 0) + world_n.get(k, 0)), k))

    gap = {}
    if GAP.exists():
        g = pd.read_csv(GAP)
        gap = dict(zip(g["k_locus"], g["status"]))

    rows = []
    for k in types:
        pn, wn = pak_n.get(k, 0), world_n.get(k, 0)
        if pn + wn < 3:
            continue
        rows.append({
            "k_locus": k,
            "pak_n": pn,
            "pak_pct": round(100 * pn / pak_total, 2),
            "world_n": wn,
            "world_pct": round(100 * wn / world_total, 2),
            "fold": round((pn / pak_total) / (wn / world_total), 2)
                    if wn else None,
            "p_fisher": round(fisher(pn, pak_total - pn,
                                     wn, world_total - wn), 4),
            "phage_status": gap.get(k, ""),
        })

    df = pd.DataFrame(rows).sort_values(["pak_n", "k_locus"],
                                        ascending=[False, True])
    df.to_csv(OUT, index=False)

    print("=== Pakistan vs pooled international (top 20 by Pakistani burden) ===")
    print(f"{'K-locus':<9}{'PAK n':>6}{'PAK %':>7}{'WORLD n':>8}{'WORLD %':>8}"
          f"{'fold':>7}{'p':>9}  phage")
    print("-" * 78)
    for _, r in df.head(20).iterrows():
        fold = f"{r['fold']:.2f}" if pd.notna(r["fold"]) else "  inf"
        print(f"{r['k_locus']:<9}{r['pak_n']:>6}{r['pak_pct']:>7.1f}"
              f"{r['world_n']:>8}{r['world_pct']:>8.1f}{fold:>7}"
              f"{r['p_fisher']:>9.4f}  {r['phage_status']}")

    # The decisive test. Phage discovery is concentrated in China, Europe and the
    # USA, so if Pakistan's uncovered capsule types are South Asian ones that are
    # rare or absent in those regions, that is a mechanism for the coverage gap
    # rather than a coincidence.
    SOUTH = {"india", "bangladesh_nepal"}
    sa = merged[merged["group"].isin(SOUTH)]
    ps = merged[~merged["group"].isin(SOUTH)]
    print(f"\n=== South Asia (n={len(sa)}) vs phage-source regions "
          f"(n={len(ps)}) ===")
    print(f"{'K-locus':<9}{'SA n':>6}{'SA %':>7}{'PS n':>6}{'PS %':>7}"
          f"{'p':>9}  phage")
    print("-" * 60)

    sa_n = sa[KCOL].value_counts().to_dict()
    ps_n = ps[KCOL].value_counts().to_dict()
    sa_rows = []
    for k in sorted(set(sa_n) | set(ps_n),
                    key=lambda k: (-(sa_n.get(k, 0) + ps_n.get(k, 0)), k)):
        s, p_ = sa_n.get(k, 0), ps_n.get(k, 0)
        if s + p_ < 4:
            continue
        pv = fisher(s, len(sa) - s, p_, len(ps) - p_)
        sa_rows.append({
            "k_locus": k,
            "sa_n": s, "sa_pct": round(100 * s / len(sa), 2),
            "ps_n": p_, "ps_pct": round(100 * p_ / len(ps), 2),
            "diff_pct": round(100 * s / len(sa) - 100 * p_ / len(ps), 2),
            "p_fisher": round(pv, 5),
            "phage_status": gap.get(k, ""),
            "sa_total": len(sa), "ps_total": len(ps),
        })
        if pv < 0.10 or gap.get(k) == "UNCOVERED":
            print(f"{k:<9}{s:>6}{100*s/len(sa):>7.1f}{p_:>6}"
                  f"{100*p_/len(ps):>7.1f}{pv:>9.4f}  {gap.get(k,'')}")

    sa_out = DATA / "kp_southasia_vs_phagesource.csv"
    pd.DataFrame(sa_rows).sort_values(["diff_pct", "k_locus"],
                                      ascending=[False, True]) \
        .to_csv(sa_out, index=False)
    print(f"\nWrote {sa_out}")

    print("\n=== Per-group breakdown for Pakistan's uncovered types ===")
    unc = [k for k, v in gap.items() if v == "UNCOVERED"]
    tab = (merged[merged[KCOL].isin(unc)]
           .groupby([KCOL, "group"]).size().unstack(fill_value=0))
    if len(tab):
        print(tab.to_string())
    else:
        print("None of Pakistan's uncovered types appear in the comparison set.")

    print(f"\nWrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
