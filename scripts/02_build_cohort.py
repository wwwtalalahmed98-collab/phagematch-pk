"""
Step 2 - Cohort definition: turn the raw BV-BRC metadata dump into a clean,
QC-passed strain cohort ready for K-locus typing and phage matching.

Public metadata is messy in predictable ways: 'Blood' vs 'blood', two different
MLST field formats, deprecated assemblies, and non-clinical isolates (dairy
farms, hospital sinks) mixed in with patient isolates. We keep the
non-clinical ones but label them, because environmental/One-Health isolates
are a legitimate secondary analysis - they just must not silently inflate the
clinical coverage map.

Usage:
    python scripts/02_build_cohort.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd

from config import DATA_ROOT as DATA_DIR
IN_CSV = DATA_DIR / "interim" / "klebsiella_pneumoniae_pakistan_genomes.csv"
OUT_CSV = DATA_DIR / "processed" / "kp_pakistan_cohort.csv"

# Minimum assembly quality to be worth typing. Deliberately lenient - public
# Pakistani genomes are often modest-depth Illumina drafts, and over-strict
# filters would bias the cohort toward a couple of well-funded studies.
MIN_COMPLETENESS = 90.0
MAX_CONTAMINATION = 5.0
MAX_CONTIGS = 800
GENOME_LEN_RANGE = (4_500_000, 6_800_000)

CLINICAL_TERMS = [
    "blood", "urine", "pus", "sputum", "wound", "csf", "cerebrospinal",
    "endotracheal", "tracheal", "catheter", "aspirate", "abscess", "swab ear",
    "tissue", "bile", "pleural", "peritoneal", "stool", "faec", "fecal",
    "rectal", "throat", "nasal", "respiratory", "bronch", "drain", "tip",
    "burn", "skin", "eye", "semen", "synovial", "ascitic",
]
ENVIRONMENT_TERMS = [
    "hospital surface", "sink", "surface swab", "environment", "water",
    "sewage", "soil", "air", "floor", "bed", "equipment", "ward",
]
ANIMAL_FOOD_TERMS = [
    "dairy", "farm", "milk", "cattle", "buffalo", "poultry", "chicken",
    "meat", "animal", "bovine", "goat", "sheep", "food", "vegetable",
]


def classify_source(raw: str) -> str:
    """Bucket free-text isolation_source into analysis categories."""
    if not isinstance(raw, str) or not raw.strip():
        return "unknown"
    s = raw.strip().lower()
    # Order matters: environment/animal checked first so 'hospital surface
    # swab' does not get caught by the clinical 'swab' term.
    for term in ANIMAL_FOOD_TERMS:
        if term in s:
            return "animal_food"
    for term in ENVIRONMENT_TERMS:
        if term in s:
            return "hospital_environment"
    for term in CLINICAL_TERMS:
        if term in s:
            return "clinical"
    return "other"


def normalise_st(raw) -> str:
    """'MLST.klebsiella.147' and 'MLST.Klebsiella_pneumoniae.147' -> 'ST147'."""
    if not isinstance(raw, str) or not raw.strip():
        return "unknown"
    m = re.search(r"\.(\d+)\s*$", raw.strip())
    return f"ST{m.group(1)}" if m else "unknown"


def main() -> int:
    if not IN_CSV.exists():
        print(f"Missing {IN_CSV}. Run 01_scope_genomes.py --fetch first.")
        return 1

    df = pd.read_csv(IN_CSV)
    n0 = len(df)
    print(f"Loaded {n0:,} records\n")

    df["st"] = df["mlst"].map(normalise_st)
    df["source_class"] = df["isolation_source"].map(classify_source)

    # --- filtering, reported step by step so the attrition is auditable ---
    steps = []

    df = df[df["genome_status"] != "Deprecated"]
    steps.append(("drop deprecated assemblies", len(df)))

    df = df[df["assembly_accession"].notna()]
    steps.append(("require assembly accession", len(df)))

    qc = (
        (df["checkm_completeness"].fillna(0) >= MIN_COMPLETENESS)
        & (df["checkm_contamination"].fillna(100) <= MAX_CONTAMINATION)
    )
    df = df[qc]
    steps.append((f"checkm >={MIN_COMPLETENESS}% / <={MAX_CONTAMINATION}% contam", len(df)))

    df = df[df["contigs"].fillna(10**9) <= MAX_CONTIGS]
    steps.append((f"contigs <= {MAX_CONTIGS}", len(df)))

    lo, hi = GENOME_LEN_RANGE
    df = df[df["genome_length"].between(lo, hi)]
    steps.append((f"genome length {lo/1e6:.1f}-{hi/1e6:.1f} Mb", len(df)))

    df = df.drop_duplicates(subset=["assembly_accession"])
    steps.append(("dedupe by assembly", len(df)))

    print("Filtering:")
    prev = n0
    for label, n in steps:
        print(f"  {label:<48} {n:>5,}  ({n - prev:+,})")
        prev = n
    print()

    print("Cohort by isolation source class:")
    print(df["source_class"].value_counts().to_string())
    print()

    clin = df[df["source_class"] == "clinical"]
    print(f"Clinical isolates: {len(clin):,}")
    print("\nTop STs (clinical only):")
    print(clin["st"].value_counts().head(12).to_string())
    print()

    print("Clinical isolates by collection year:")
    print(clin["collection_year"].value_counts().sort_index().to_string())
    print()

    est_gb = len(df) * 5.5 / 1024
    print(f"Estimated FASTA download for full cohort ({len(df):,}): ~{est_gb:.2f} GB")

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_CSV, index=False)
    print(f"\nWrote cohort -> {OUT_CSV}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
