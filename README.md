# PhageMatch-PK

Analysis code for **"Capsule types driving carbapenem-resistant *Klebsiella
pneumoniae* in Pakistan are largely absent from the phage literature."**

Most lytic *Klebsiella* phages bind a single capsule (K) type, so a phage is
only clinically useful where that capsule type circulates. This repository types
the capsule loci of Pakistani clinical *K. pneumoniae* genomes, curates the
published phage and depolymerase literature into a phage↔capsule table, and asks
which circulating capsule types have no phage described anywhere — then tests
whether the uncovered types are specifically South Asian.

## Main findings

- **121 of 254 Pakistani clinical isolates (47.6%)**, across 51 of 66 capsule
  types, belong to types with no published phage. 67 carry a carbapenemase.
  Collapsing each BioProject to one isolate per type raises this to 51.8%.
- **KL81** occurs in 6.3% of South Asian genomes and **0 of 275** from China,
  Europe and the USA (*p* = 0.0014 after collapsing BioProjects), and has no
  published phage or depolymerase.
- **KL107** is the mirror image: 9.8% in those regions, absent from South Asia.
- Four further apparent geographic differences (KL15, KL48, KL51, KL64) did not
  survive BioProject collapsing and are clonal artefacts.

## Data

No new sequence data were generated. All genomes are public NCBI assemblies,
selected from **NCBI Pathogen Detection release PDG000000012.2494**
(https://www.ncbi.nlm.nih.gov/pathogens/).

| Cohort | n | Criteria |
|---|--:|---|
| Pakistan | 254 typed (260 selected) | *K. pneumoniae*, `epi_type = clinical`, collected 2015+, assembly available |
| Comparison | 475 typed (500 sampled) | Same criteria; 100 sampled per region from India, Bangladesh + Nepal, China, western Europe, USA (seed 20260815) |

Accession lists are in `docs/supplementary_tables.xlsx` (Tables S1 and S2) and
as plain text in `D:\bacteriophage-data\processed\*_accessions.txt` when the
pipeline is run.

## Layout

```
scripts/     numbered in execution order
notebooks/   Colab notebooks for the capsule-typing step
data/        hand-curated inputs (the phage↔capsule evidence table)
docs/        figures, supplementary workbook, reference list
```

The manuscript text is withheld until the paper is accepted; the code, curated
data, figures and supplementary tables needed to check the analysis are all
here. `scripts/19` and `scripts/20` build the manuscript from sources not in
this repository and will not run without them.

`data/phage_klocus_curated.csv` is the only **hand-curated** file in the
repository — 34 phage–capsule records read out of 27 papers, each with a PMID and
an evidence grade. Everything else is derived from it and from public metadata.

## Pipeline

Scripts are numbered in execution order. **All paths resolve from
`scripts/config.py`** — the repository root is derived from the file's own
location, and the large working directory is set once:

```bash
# Windows
set PHAGEMATCH_DATA=E:\phage-data
# POSIX
export PHAGEMATCH_DATA=/scratch/phage-data
```

The default is `D:\bacteriophage-data`. Run `python scripts/config.py` to print
the resolved paths and see which exist. No script contains a hardcoded absolute
path.

| Step | Script / notebook | Does |
|---|---|---|
| 01 | `01_scope_genomes.py` | Scope how many Pakistani genomes exist, via the BV-BRC REST API |
| 02 | `02_build_cohort.py` | Turn the BV-BRC dump into a QC-passed strain cohort |
| 03 | `03_ncbi_pathogen_detection.py` | Fetch NCBI Pathogen Detection metadata |
| 04 | `04_merge_cohort.py` | Merge BV-BRC and NCBI PD, deduplicated on assembly accession |
| 05 | `05_export_accessions.py` | Export the accession list for typing |
| 06 | `notebooks/06b_kleborate_colab_selfcontained.ipynb` | Capsule typing (Colab) |
| 07 | `07_join_typing.py` | Join Kleborate output back to the cohort, rank K loci by burden |
| 08 | `08_make_colab_notebook.py` | Emit a self-contained typing notebook (`--cohort core` or `comparison`) |
| 09 | `09_build_comparison_cohort.py` | Sample the international comparison cohort |
| 10 | `notebooks/10_kleborate_comparison.ipynb` | Typing for the comparison cohort |
| 11 | `11_curate_phage_depolymerases.py` | Triage the depolymerase literature into a review list |
| 11b | `notebooks/11_collate_comparison.ipynb` | Rebuild results from finished chunks after a lost runtime |
| 12 | `12_coverage_gap.py` | Join curated evidence to cohort burden |
| 13 | `13_make_collate_notebook.py` | Generate the collation notebook above |
| 14 | `14_compare_pakistan_vs_world.py` | Geographic comparison, Fisher exact |
| 15 | `15_figures.py` | Figures 1–3 (PNG + PDF, 300 dpi) |
| 16 | `16_independence_check.py` | BioProject-collapsed sensitivity analysis |
| 17 | `17_format_curated_refs.py` | Reference list in Microbiology Society style |
| 18 | `18_supplementary_tables.py` | Supplementary workbook |
| 19 | `19_build_docx.py` | Manuscript as .docx |

Ordering caveats. Steps 01–02 use BV-BRC and were superseded by the NCBI
Pathogen Detection route (03–05) once it proved the better metadata source;
they are kept because step 04 merges both. Steps 15 and 18 require 16 to have
run — step 15 exits with a message if the independence table is missing. Step 17
needs network access for Crossref lookups and caches them.

## Reproducing the typing step

Capsule typing needs Kleborate and Kaptive plus ~3 GB of genome downloads, so it
runs on Google Colab rather than locally:

1. `python scripts/08_make_colab_notebook.py --cohort core`
2. Upload `notebooks/06b_kleborate_colab_selfcontained.ipynb` to Colab and run
   all cells. Accession lists are embedded, so nothing needs uploading.
3. Cell 3 restarts the runtime deliberately (a NumPy ABI conflict); resume at
   Cell 4.
4. Results are written to Google Drive after every 20-genome chunk, so a
   reclaimed runtime resumes rather than restarts. If the session dies, rerun
   and it continues from the last completed chunk.
5. Repeat with `--cohort comparison`.

Two details matter for reproducibility. **Kaptive is pinned to 3.2.2** — 3.3.0
removed `kaptive.database`, which Kleborate's capsule module imports. And
genomes are processed in **shuffled** accession order: accession numbers cluster
by submitting centre, so an interrupted sorted run yields a geographically
skewed subset, whereas any prefix of a shuffled run is still a balanced random
sample.

## A note on the statistics

Public bacterial genome collections are dominated by outbreak investigations, so
genomes sharing a BioProject may represent one transmission chain rather than
independent observations. Every geographic comparison here is therefore run
twice — on all genomes, and with each BioProject collapsed to one genome per
capsule type — and **only results surviving the collapse are reported as
findings** (`scripts/16_independence_check.py`).

This is not a formality. Four of six nominally significant differences in this
dataset did not survive it.

## Local environment

```bash
pip install -r requirements.txt
```

Python 3.14.6 on Windows 11. SciPy is intentionally not a dependency: the only
statistical test used is a two-sided Fisher exact, computed directly.

### Reproducibility

Outputs are byte-identical across runs. Row ordering is fully specified — every
sort that could tie carries the capsule locus as a secondary key, because
untied orderings derived from Python `set` iteration vary between processes and
made consecutive identical runs produce different files. Verify with:

```bash
python scripts/14_compare_pakistan_vs_world.py && md5sum "$PHAGEMATCH_DATA/processed/kp_vs_world_klocus.csv"
```

Two runs must agree.

## Citing

If you use this code or the curated phage–capsule table, please cite the paper
(reference to be added on acceptance) and this archived release. See
`CITATION.cff`.

## Licence

Code is released under the MIT Licence (`LICENSE`). The hand-curated
phage–capsule table in `data/` is released under CC BY 4.0 — reuse it freely
with attribution. Genome data are public NCBI records and carry their own terms.
