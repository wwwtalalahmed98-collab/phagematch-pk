"""
Step 18 - Build the supplementary workbook for submission.

Five sheets, one per supplementary table referenced in the manuscript. Written
as a single .xlsx because reviewers and editors handle one attachment better
than five CSVs, and because accession lists need to stay paired with the calls
made from them.

Sheet contents are trimmed to columns a reader needs. Kleborate emits ~120
columns per genome; shipping all of them buries the capsule call that the paper
actually rests on.

Usage:
    python scripts/18_supplementary_tables.py
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from config import CURATED_NUMBERED as CURATED
from config import DOCS
from config import PROCESSED as DATA

OUT = DOCS / "supplementary_tables.xlsx"

KCOL = "klebsiella_pneumo_complex__kaptive__K_locus"
CONF = "klebsiella_pneumo_complex__kaptive__K_locus_confidence"


def first_col(df: pd.DataFrame, *names: str) -> str | None:
    lower = {c.lower(): c for c in df.columns}
    for n in names:
        if n.lower() in lower:
            return lower[n.lower()]
    return None


def table_s1() -> pd.DataFrame:
    """Pakistani cohort: accession, metadata, capsule call."""
    t = pd.read_csv(DATA / "kp_pakistan_typed.csv", dtype=str, low_memory=False)
    keep = {
        "assembly": "assembly_accession",
        "bioproject": "bioproject",
        "biosample": "biosample",
        "year": "collection_year",
        "isolation_source": "isolation_source",
        "st": "sequence_type",
        "k_locus": "K_locus",
        "k_type": "K_type",
        "k_confidence": "K_locus_confidence",
        "carbapenemase": "carbapenemase",
        "has_carbapenemase": "carbapenemase_positive",
    }
    cols = {src: dst for src, dst in keep.items() if src in t.columns}
    out = t[list(cols)].rename(columns=cols)
    return out.sort_values("K_locus" if "K_locus" in out else out.columns[0])


def table_s2() -> pd.DataFrame:
    """Comparison cohort: accession, country group, capsule call."""
    comp = pd.read_csv(DATA / "kleborate_comparison_kp.csv", dtype=str,
                       low_memory=False)
    keys = pd.read_csv(DATA / "kp_comparison_keys.csv", dtype=str)
    m = comp.merge(keys[["assembly", "group", "bioproject", "geo_loc_name",
                         "collection_date", "isolation_source"]],
                   left_on="strain", right_on="assembly", how="left")
    st = first_col(m, "klebsiella_pneumo_complex__mlst__ST", "ST")
    cols = {
        "strain": "assembly_accession",
        "group": "region_group",
        "geo_loc_name": "geographic_location",
        "collection_date": "collection_date",
        "isolation_source": "isolation_source",
        "bioproject": "bioproject",
        KCOL: "K_locus",
        CONF: "K_locus_confidence",
    }
    if st:
        cols[st] = "sequence_type"
    present = {s: d for s, d in cols.items() if s in m.columns}
    return m[list(present)].rename(columns=present).sort_values(
        ["region_group", "K_locus"])


def table_s3() -> pd.DataFrame:
    """Curated phage-capsule evidence."""
    c = pd.read_csv(CURATED, dtype=str)
    order = [c_ for c_ in ["ref_number", "k_locus", "phage_name",
                           "depolymerase_gene", "evidence_level", "host_origin",
                           "year", "pmid", "doi", "note"] if c_ in c.columns]
    out = c[order].copy()
    if "ref_number" in out:
        out["ref_number"] = pd.to_numeric(out["ref_number"], errors="coerce")
        out = out.sort_values(["k_locus", "ref_number"])
    return out


def table_s4() -> pd.DataFrame:
    """Coverage gap across all capsule types."""
    return pd.read_csv(DATA / "kp_coverage_gap.csv")


def table_s5() -> pd.DataFrame:
    """Independence analysis: raw vs BioProject-collapsed."""
    return pd.read_csv(DATA / "kp_independence_check.csv")


CAPTIONS = {
    "Table S1": "Pakistani cohort. All 260 clinical Klebsiella pneumoniae "
                "assemblies meeting the selection criteria (NCBI Pathogen "
                "Detection PDG000000012.2494; clinical, 2015 onwards), with "
                "capsule call and carbapenemase status. Six isolates returned "
                "K_locus_confidence = Untypeable and were excluded, leaving the "
                "254 analysed here.",
    "Table S2": "Comparison cohort. 475 assemblies from India, Bangladesh, "
                "Nepal, China, Europe and the USA, sampled on identical "
                "criteria, with region group and capsule call.",
    "Table S3": "Curated phage-capsule evidence. 34 records covering 27 phages "
                "and 15 capsule types, graded by evidence level, with PMID, "
                "DOI and manuscript reference number.",
    "Table S4": "Phage coverage per capsule type. All 66 Pakistani capsule "
                "types with isolate burden, carbapenemase count, best evidence "
                "grade and coverage status.",
    "Table S5": "Independence analysis. Raw and BioProject-collapsed counts "
                "and Fisher exact p-values per capsule type, with the "
                "Pakistani single-project share.",
}


def main() -> int:
    builders = {
        "Table S1": table_s1,
        "Table S2": table_s2,
        "Table S3": table_s3,
        "Table S4": table_s4,
        "Table S5": table_s5,
    }

    frames: dict[str, pd.DataFrame] = {}
    for name, fn in builders.items():
        try:
            frames[name] = fn()
            print(f"{name}: {frames[name].shape[0]} rows, "
                  f"{frames[name].shape[1]} cols")
        except (FileNotFoundError, KeyError) as e:
            print(f"{name}: FAILED - {type(e).__name__}: {e}")

    if not frames:
        return 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(OUT, engine="openpyxl") as xw:
        # Contents sheet first so the workbook explains itself.
        pd.DataFrame({"Sheet": list(frames), "Caption":
                      [CAPTIONS[k] for k in frames]}).to_excel(
            xw, sheet_name="Contents", index=False)
        for name, df in frames.items():
            df.to_excel(xw, sheet_name=name, index=False)

        for sheet in xw.book.worksheets:
            for col in sheet.columns:
                width = max((len(str(c.value)) for c in col
                             if c.value is not None), default=10)
                sheet.column_dimensions[col[0].column_letter].width = \
                    min(max(width + 2, 10), 60)
            sheet.freeze_panes = "A2"

    print(f"\nWrote {OUT} ({OUT.stat().st_size/1024:.0f} KB, "
          f"{len(frames)+1} sheets)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
