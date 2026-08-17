# Getting the code DOI

*Microbial Genomics* requires a DOI for supporting code under its Open Data
policy. Zenodo mints one from a GitHub release. The order below matters — the
usual mistake is connecting Zenodo *after* releasing, which produces no archive.

## Before you push

1. **Fill in `CITATION.cff`** — every author in the paper's order, with ORCIDs
   and affiliations. Zenodo reads this file to build the archive's author list,
   so an incomplete file yields a record crediting one person.
2. **Fill in `.zenodo.json`** `creators` to match. Where both files exist,
   `.zenodo.json` wins.
3. **Set the repository URL** in `CITATION.cff` (`repository-code`) once you know
   the GitHub username.
4. **Check the copyright line** in `LICENSE` names the right holder — it may need
   to be your institution rather than you personally. Ask before assuming.
5. **Decide the data licence.** Currently MIT for code, CC BY 4.0 for the curated
   phage–capsule table. CC BY is the right default for a table you want cited,
   but confirm it against any institutional policy.

## Repository hygiene

The repo must contain no genome files and no absolute paths that leak anything
private. `.gitignore` covers `*.fna`, `*.zip` and the API caches.

Paths are no longer an issue: all seventeen scripts resolve through
`scripts/config.py`, which derives the repository root from its own location and
takes the data root from `PHAGEMATCH_DATA` (default `D:\bacteriophage-data`). No
absolute path is hardcoded anywhere. `python scripts/config.py` prints what
resolves and flags anything missing.

## The deposit sequence

```bash
cd C:\Bacteriophage
git init
git add .
git status                # read this properly — confirm no .fna, no large files
git commit -m "Analysis code for Klebsiella capsule phage-coverage study"
git branch -M main
git remote add origin https://github.com/wwwtalalahmed98-collab/phagematch-pk.git
git push -u origin main
```

Then, **in this order**:

1. Sign in to https://zenodo.org with GitHub.
2. Go to **Zenodo → GitHub** and flip the repository's switch **on**. Do this
   before creating the release; Zenodo only archives releases made while the
   switch is on.
3. On GitHub, **Releases → Create a new release**, tag `v1.0.0`, title
   "Analysis code v1.0.0", publish.
4. Zenodo picks up the release within a few minutes and mints a DOI.
5. Take the **Concept DOI** (the version-independent one, labelled "Cite all
   versions"), not the version-specific DOI. The concept DOI keeps resolving if
   you release a v1.0.1 after review.

## Then update the manuscript

Paste the concept DOI into the Data Summary section, replacing the ⚠ placeholder:

> Analysis code is available at https://github.com/wwwtalalahmed98-collab/phagematch-pk and
> archived at Zenodo, doi:10.5281/zenodo.XXXXXXX.

Rebuild the Word file so the submitted version contains it:

```bash
python scripts/19_build_docx.py
```

## Sanity check before submitting

- The DOI resolves in a private browser window.
- The Zenodo record's author list matches the manuscript's.
- The archive contains `scripts/`, `data/`, `notebooks/`, `README.md`,
  `LICENSE`, `requirements.txt` — and no genome files.
- `data/phage_klocus_curated.csv` is present. It is the only irreplaceable file
  in the repository; everything else can be regenerated from public data.
