"""
Step 7 - Join Kleborate typing back to the cohort and rank K-loci by burden.

Input:  kleborate_pakistan_kp.csv  (downloaded from the Colab notebook)
Output: the typed strain table, and the K-locus target list - capsule types
        ranked by how much contemporary Pakistani clinical disease they account
        for. That ranking is what a phage library has to cover, and its tail is
        what phage hunting should target.

Kleborate column names shift between releases, so columns are resolved by
lookup rather than hard-coded.

Usage:
    python scripts/07_join_typing.py --kleborate D:\\path\\kleborate_pakistan_kp.csv
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from config import DATA_ROOT as DATA
KEYS = DATA / "processed" / "kp_core_keys.csv"
OUT_TYPED = DATA / "processed" / "kp_pakistan_typed.csv"
OUT_TARGETS = DATA / "processed" / "kp_klocus_target_list.csv"

# Kaptive confidence levels we trust for receptor-level inference. Low-confidence
# calls are kept in the table but excluded from the target ranking, because a
# wrong K-locus means a wrong phage. Kaptive 3.2 reports Typeable/Untypeable;
# older releases used a graded scale, so accept both vocabularies.
GOOD_CONFIDENCE = {"Typeable", "Perfect", "Very high", "High", "Good"}


def pick(df: pd.DataFrame, *candidates: str) -> str | None:
    for c in candidates:
        if c in df.columns:
            return c
    lowered = {c.lower().replace(" ", "_"): c for c in df.columns}
    for c in candidates:
        key = c.lower().replace(" ", "_")
        if key in lowered:
            return lowered[key]
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--kleborate", required=True, help="CSV from the Colab notebook")
    args = ap.parse_args()

    kleb_path = Path(args.kleborate)
    for p in (kleb_path, KEYS):
        if not p.exists():
            print(f"Missing {p}")
            return 1

    kleb = pd.read_csv(kleb_path, dtype=str, low_memory=False)
    keys = pd.read_csv(KEYS, dtype=str, low_memory=False)

    # Kleborate v3 prefixes every column with its module path; v2 used bare
    # names. List the v3 names first so they win when both could match.
    col_asm = pick(kleb, "assembly", "strain", "Genome Name", "Name")
    col_k = pick(kleb, "klebsiella_pneumo_complex__kaptive__K_locus",
                 "K_locus", "K locus", "Best match locus")
    col_kconf = pick(kleb, "klebsiella_pneumo_complex__kaptive__K_locus_confidence",
                     "K_locus_confidence", "K locus confidence", "Match confidence")
    col_o = pick(kleb, "klebsiella_pneumo_complex__kaptive__O_locus",
                 "O_locus", "O locus", "O_type")
    col_st = pick(kleb, "klebsiella_pneumo_complex__mlst__ST", "ST", "MLST ST", "st")
    col_ktype = pick(kleb, "klebsiella_pneumo_complex__kaptive__K_type", "K_type")
    if col_ktype:
        kleb = kleb.rename(columns={col_ktype: "k_type"})

    print(f"resolved columns: assembly={col_asm} K={col_k} conf={col_kconf} "
          f"O={col_o} ST={col_st}")
    if not (col_asm and col_k):
        print("Could not resolve assembly/K-locus columns. Columns present:")
        print(list(kleb.columns))
        return 1

    kleb = kleb.rename(columns={col_asm: "assembly", col_k: "k_locus"})
    if col_kconf:
        kleb = kleb.rename(columns={col_kconf: "k_confidence"})
    if col_o:
        kleb = kleb.rename(columns={col_o: "o_locus"})
    if col_st:
        kleb = kleb.rename(columns={col_st: "st_kleborate"})

    kleb["assembly"] = kleb["assembly"].astype(str).str.strip()

    merged = keys.merge(kleb, on="assembly", how="left", suffixes=("", "_kleb"))
    n_typed = merged["k_locus"].notna().sum()
    print(f"\nCohort {len(merged):,} | typed {n_typed:,} | untyped {len(merged)-n_typed:,}")

    merged.to_csv(OUT_TYPED, index=False)
    print(f"Wrote typed table -> {OUT_TYPED}")

    typed = merged[merged["k_locus"].notna()].copy()
    if typed.empty:
        print("\nNothing typed - check the join key in the Kleborate output.")
        return 1

    if "k_confidence" in typed.columns:
        print("\nK-locus call confidence:")
        print(typed["k_confidence"].fillna("unknown").value_counts().to_string())
        confident = typed[typed["k_confidence"].isin(GOOD_CONFIDENCE)]
        if confident.empty:
            print("\n! No calls matched the expected confidence labels; "
                  "using all typed calls and flagging for manual review.")
            confident = typed
    else:
        confident = typed

    print(f"\nConfident K-locus calls: {len(confident):,}")

    # --- the target list ---
    burden = (confident.groupby("k_locus")
              .agg(n_isolates=("assembly", "count"),
                   n_carbapenemase=("has_carbapenemase",
                                    lambda s: (s.astype(str).str.lower() == "true").sum()))
              .sort_values("n_isolates", ascending=False))
    burden["pct_of_cohort"] = 100 * burden["n_isolates"] / len(confident)
    burden["cumulative_pct"] = burden["pct_of_cohort"].cumsum()

    print(f"\n=== K-LOCUS TARGET LIST ({len(burden)} distinct capsule types) ===")
    print(burden.head(25).round(1).to_string())

    n_for_half = (burden["cumulative_pct"] < 50).sum() + 1
    n_for_80 = (burden["cumulative_pct"] < 80).sum() + 1
    print(f"\nCapsule types needed to cover 50% of isolates: {n_for_half}")
    print(f"Capsule types needed to cover 80% of isolates: {n_for_80}")
    print("\n-> A phage library must carry depolymerase activity against at least "
          f"these {n_for_80} K-loci to reach 80% coverage of contemporary "
          "Pakistani clinical K. pneumoniae.")

    burden.to_csv(OUT_TARGETS)
    print(f"\nWrote target list -> {OUT_TARGETS}")

    if "st_kleborate" in confident.columns:
        print("\n=== Dominant ST x K-locus pairings ===")
        print(confident.groupby(["st_kleborate", "k_locus"]).size()
              .sort_values(ascending=False).head(15).to_string())

    if "era" in confident.columns:
        print("\n=== K-locus by era (is the capsule landscape shifting?) ===")
        top = burden.head(10).index
        sub = confident[confident["k_locus"].isin(top)]
        print(pd.crosstab(sub["k_locus"], sub["era"]).to_string())

    return 0


if __name__ == "__main__":
    sys.exit(main())
