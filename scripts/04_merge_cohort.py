"""
Step 4 - Master cohort: merge BV-BRC and NCBI Pathogen Detection into one
strain table, deduplicated on assembly accession.

The two sources disagree substantially (only ~190 assemblies in common), so
neither alone is sufficient. NCBI PD is authoritative for epi_type (clinical
vs environmental) and ships pre-computed AMRFinderPlus genotypes; BV-BRC
contributes MLST and some assemblies PD does not carry.

We stratify by era because the pre-2015 Pakistani genomes come overwhelmingly
from one or two old studies and predate the local carbapenemase surge -
pooling them with contemporary isolates would silently misrepresent what is
circulating now.

Usage:
    python scripts/04_merge_cohort.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd

from config import DATA_ROOT as DATA
BVBRC = DATA / "processed" / "kp_pakistan_cohort.csv"
NCBI = DATA / "interim" / "ncbi_pd_klebsiella_pakistan.tsv"
OUT = DATA / "processed" / "kp_pakistan_master_cohort.csv"

CONTEMPORARY_FROM = 2015

# Carbapenemase families that define the XDR phenotype we care about, plus ESBL.
CARBAPENEMASES = ["NDM", "OXA-48", "OXA-181", "OXA-232", "KPC", "VIM", "IMP"]
ESBL = ["CTX-M", "SHV", "TEM", "OXA-1"]


def load_ncbi() -> pd.DataFrame:
    df = pd.read_csv(NCBI, sep="\t", dtype=str, low_memory=False)
    df = df[df["scientific_name"].fillna("").str.contains("Klebsiella pneumoniae")]
    df = df[df["asm_acc"].fillna("NULL").ne("NULL")]

    out = pd.DataFrame({
        "assembly": df["asm_acc"],
        "biosample": df["biosample_acc"],
        "bioproject": df["bioproject_acc"],
        "strain": df["strain"],
        "collection_date": df["collection_date"],
        "geo_loc": df["geo_loc_name"],
        "epi_type": df["epi_type"],
        "host": df["host"],
        "host_disease": df["host_disease"],
        "isolation_source": df["isolation_source"],
        "n_contigs": pd.to_numeric(df["asm_stats_n_contig"], errors="coerce"),
        "asm_length": pd.to_numeric(df["asm_stats_length_bp"], errors="coerce"),
        "asm_level": df["asm_level"],
        "amr_genotypes": df["AMR_genotypes"],
        "virulence_genotypes": df["virulence_genotypes"],
        "n_amr_genes": pd.to_numeric(df["number_amr_genes"], errors="coerce"),
        "source_db": "ncbi_pd",
    })
    return out


def load_bvbrc() -> pd.DataFrame:
    df = pd.read_csv(BVBRC, dtype=str, low_memory=False)
    out = pd.DataFrame({
        "assembly": df["assembly_accession"],
        "biosample": df["biosample_accession"],
        "bioproject": df["bioproject_accession"],
        "strain": df["strain"],
        "collection_date": df["collection_date"].fillna(df["collection_year"]),
        "geo_loc": df["geographic_location"],
        "epi_type": df["source_class"].map({
            "clinical": "clinical",
            "hospital_environment": "environmental/other",
            "animal_food": "environmental/other",
        }),
        "host": df["host_name"],
        "host_disease": None,
        "isolation_source": df["isolation_source"],
        "n_contigs": pd.to_numeric(df["contigs"], errors="coerce"),
        "asm_length": pd.to_numeric(df["genome_length"], errors="coerce"),
        "asm_level": df["genome_status"],
        "amr_genotypes": None,
        "virulence_genotypes": None,
        "n_amr_genes": None,
        "source_db": "bvbrc",
    })
    out["st"] = df["st"]
    return out


def has_any(genotypes: str, families: list[str]) -> bool:
    if not isinstance(genotypes, str):
        return False
    g = genotypes.upper()
    return any(f.upper() in g for f in families)


def carbapenemase_families(genotypes: str) -> str:
    if not isinstance(genotypes, str):
        return ""
    g = genotypes.upper()
    return ";".join(f for f in CARBAPENEMASES if f.upper() in g)


def main() -> int:
    for p in (BVBRC, NCBI):
        if not p.exists():
            print(f"Missing {p}")
            return 1

    ncbi, bv = load_ncbi(), load_bvbrc()
    print(f"NCBI PD assemblies : {len(ncbi):,}")
    print(f"BV-BRC assemblies  : {len(bv):,}")

    # NCBI PD wins on conflicts (curated epi_type + AMRFinderPlus genotypes);
    # BV-BRC contributes its unique assemblies and the MLST calls.
    st_map = bv.set_index("assembly")["st"].to_dict()
    bv_only = bv[~bv["assembly"].isin(set(ncbi["assembly"]))]
    print(f"BV-BRC-only rows   : {len(bv_only):,}")

    master = pd.concat([ncbi, bv_only.drop(columns=["st"])], ignore_index=True)
    master = master.drop_duplicates(subset=["assembly"])
    master["st"] = master["assembly"].map(st_map).fillna("unknown")

    master["year"] = pd.to_numeric(
        master["collection_date"].fillna("").astype(str).str.extract(r"(\d{4})")[0],
        errors="coerce",
    )
    master["era"] = master["year"].apply(
        lambda y: "unknown" if pd.isna(y)
        else ("contemporary" if y >= CONTEMPORARY_FROM else "historical")
    )
    master["epi_type"] = master["epi_type"].fillna("unknown")

    master["carbapenemase"] = master["amr_genotypes"].apply(carbapenemase_families)
    master["has_carbapenemase"] = master["carbapenemase"].ne("")
    master["has_esbl"] = master["amr_genotypes"].apply(lambda g: has_any(g, ESBL))

    print(f"\nMaster cohort: {len(master):,} unique assemblies")
    print("\nepi_type x era:")
    print(pd.crosstab(master["epi_type"], master["era"], margins=True).to_string())

    core = master[(master["epi_type"] == "clinical") & (master["era"] == "contemporary")]
    print(f"\n=== CORE ANALYSIS SET (clinical, {CONTEMPORARY_FROM}+): {len(core):,} ===")

    print("\nBioProject spread (core):")
    print(core["bioproject"].value_counts().head(8).to_string())

    typed = core[core["amr_genotypes"].notna()]
    print(f"\nWith AMRFinderPlus genotypes: {len(typed):,} / {len(core):,}")
    if len(typed):
        print(f"  carbapenemase-positive: {typed['has_carbapenemase'].sum():,} "
              f"({100*typed['has_carbapenemase'].mean():.1f}%)")
        print(f"  ESBL-positive         : {typed['has_esbl'].sum():,} "
              f"({100*typed['has_esbl'].mean():.1f}%)")
        fams = typed[typed["has_carbapenemase"]]["carbapenemase"].value_counts()
        print("\n  carbapenemase families:")
        print("   " + fams.head(10).to_string().replace("\n", "\n   "))

    print("\nKnown STs in core set:")
    print(core[core["st"] != "unknown"]["st"].value_counts().head(10).to_string())

    OUT.parent.mkdir(parents=True, exist_ok=True)
    master.to_csv(OUT, index=False)
    print(f"\nWrote -> {OUT}")

    core_out = OUT.with_name("kp_pakistan_core_clinical.csv")
    core.to_csv(core_out, index=False)
    print(f"Wrote -> {core_out}")

    print(f"\nFASTA download estimate (core set): ~{len(core)*5.5/1024:.2f} GB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
