"""
Step 5 - Export the accession list that the Kleborate notebook consumes.

Kleborate runs on Colab (this laptop has no conda/WSL and 8 GB RAM), so the
handoff between local and cloud is a plain text file of assembly accessions
plus a slim key table for joining the typing results back to our metadata.

Usage:
    python scripts/05_export_accessions.py                 # core clinical set
    python scripts/05_export_accessions.py --set master    # all 557
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from config import DATA_ROOT as DATA
SETS = {
    "core": DATA / "processed" / "kp_pakistan_core_clinical.csv",
    "master": DATA / "processed" / "kp_pakistan_master_cohort.csv",
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--set", dest="which", default="core", choices=sorted(SETS))
    args = ap.parse_args()

    src = SETS[args.which]
    if not src.exists():
        print(f"Missing {src}. Run 04_merge_cohort.py first.")
        return 1

    df = pd.read_csv(src, dtype=str, low_memory=False)
    accs = df["assembly"].dropna().str.strip()
    accs = accs[accs.ne("") & accs.str.match(r"^GC[AF]_")]
    accs = accs.drop_duplicates()

    print(f"{args.which} set: {len(df):,} rows -> {len(accs):,} valid accessions")
    print("\nAccession prefixes:")
    print(accs.str[:4].value_counts().to_string())

    out_dir = DATA / "processed"
    acc_file = out_dir / f"kp_{args.which}_accessions.txt"
    acc_file.write_text("\n".join(accs) + "\n", encoding="utf-8")
    print(f"\nWrote {len(accs):,} accessions -> {acc_file}")

    # Slim key table so typing results can be rejoined without shipping
    # the full metadata to Colab.
    keys = ["assembly", "biosample", "bioproject", "strain", "year", "era",
            "epi_type", "isolation_source", "host_disease", "st",
            "carbapenemase", "has_carbapenemase", "has_esbl"]
    keys = [k for k in keys if k in df.columns]
    key_file = out_dir / f"kp_{args.which}_keys.csv"
    df[keys].to_csv(key_file, index=False)
    print(f"Wrote key table   -> {key_file}")

    print(f"\nEstimated Colab download: ~{len(accs)*5.5/1024:.2f} GB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
