"""
Single source of truth for every path the pipeline touches.

Previously each script hardcoded `D:\\bacteriophage-data` and `C:\\Bacteriophage`
as module-level constants, which meant anyone rerunning the analysis had to edit
seventeen files. Everything now resolves from here.

Two roots:

* **Repository root** — derived from this file's own location, so the code works
  wherever the repository is cloned. Never configure this.
* **Data root** — the large working directory holding downloaded metadata,
  genome assemblies and derived tables. Kept outside the repository because it
  runs to several gigabytes and is regenerable from the accession lists.

Override the data root without editing code:

    # Windows
    set PHAGEMATCH_DATA=E:\\phage-data
    # POSIX
    export PHAGEMATCH_DATA=/scratch/phage-data

The PubMed metadata cache is a third, optional location: it holds JSON dumps
returned by the PubMed API during literature curation. It is machine-specific and
absent on a fresh clone, so scripts that read it must tolerate its absence rather
than assume it.
"""

from __future__ import annotations

import os
from pathlib import Path

# --------------------------------------------------------------- repository
REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "scripts"
NOTEBOOKS = REPO_ROOT / "notebooks"
PKG_DATA = REPO_ROOT / "data"          # small, hand-curated inputs (tracked)
DOCS = REPO_ROOT / "docs"
FIGURES = DOCS / "figures"

# --------------------------------------------------------------- data root
_DEFAULT_DATA_ROOT = Path(r"D:\bacteriophage-data")
DATA_ROOT = Path(os.environ.get("PHAGEMATCH_DATA", _DEFAULT_DATA_ROOT))
RAW = DATA_ROOT / "raw"                # untouched downloads
RAW_BACTERIA = RAW / "bacteria"
INTERIM = DATA_ROOT / "interim"        # intermediate extracts (steps 01-04)
PROCESSED = DATA_ROOT / "processed"    # analysis-ready tables

# ------------------------------------------------------- well-known inputs
# NCBI Pathogen Detection release analysed in the paper. Pinned deliberately:
# PD reissues numbered releases and results would drift silently otherwise.
PD_RELEASE = "PDG000000012.2494"
PD_TSV = RAW_BACTERIA / f"{PD_RELEASE}.metadata.tsv"

# The one irreplaceable file in the repository.
CURATED = PKG_DATA / "phage_klocus_curated.csv"
CURATED_NUMBERED = PKG_DATA / "phage_klocus_curated_numbered.csv"

# ------------------------------------------------- optional PubMed cache
# Written by the Claude Code session that performed the literature search. Set
# PHAGEMATCH_PUBMED_CACHE to point elsewhere; scripts fall back gracefully when
# the directory does not exist.
_DEFAULT_PUBMED_CACHE = (
    Path.home() / ".claude" / "projects" / "C--Bacteriophage"
    / "a5935bb1-882a-4a70-8267-eeb19415dcd7" / "tool-results"
)
PUBMED_CACHE = Path(os.environ.get("PHAGEMATCH_PUBMED_CACHE",
                                   _DEFAULT_PUBMED_CACHE))


def ensure_dirs() -> None:
    """Create the output directories a script is about to write into."""
    for d in (PROCESSED, INTERIM, RAW_BACTERIA, FIGURES, DOCS, PKG_DATA):
        d.mkdir(parents=True, exist_ok=True)


def describe() -> str:
    return (
        f"repository : {REPO_ROOT}\n"
        f"data root  : {DATA_ROOT}"
        f"{'' if DATA_ROOT.exists() else '   [MISSING]'}\n"
        f"  raw      : {RAW_BACTERIA}\n"
        f"  processed: {PROCESSED}"
        f"{'' if PROCESSED.exists() else '   [MISSING]'}\n"
        f"pubmed cache: {PUBMED_CACHE}"
        f"{'' if PUBMED_CACHE.exists() else '   [absent - optional]'}"
    )


if __name__ == "__main__":
    print(describe())
