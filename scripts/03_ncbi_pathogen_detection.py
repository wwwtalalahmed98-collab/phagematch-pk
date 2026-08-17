"""
Step 3 - Cross-check BV-BRC against NCBI Pathogen Detection.

BV-BRC lags NCBI ingestion, so the BV-BRC cohort (392 Pakistani K. pneumoniae,
zero clinical isolates after 2020) may simply be stale rather than a true
picture of what has been sequenced. NCBI Pathogen Detection is the
authoritative source: it publishes one metadata TSV per organism group with
curated geo_loc_name, isolation_type (clinical vs environmental), collection
date, AMR genotypes and assembly accessions.

We stream-filter that TSV for Pakistan rather than loading it whole - the file
is large and this laptop has 8 GB of RAM.

Usage:
    python scripts/03_ncbi_pathogen_detection.py
    python scripts/03_ncbi_pathogen_detection.py --organism Salmonella
"""

from __future__ import annotations

import argparse
import csv
import io
import re
import sys
from pathlib import Path

import requests

FTP_BASE = "https://ftp.ncbi.nlm.nih.gov/pathogen/Results"
from config import DATA_ROOT as DATA_DIR
OUT_DIR = DATA_DIR / "interim"

COUNTRY = "Pakistan"
# Species filter applied within the organism group (the Klebsiella group also
# contains K. quasipneumoniae, K. variicola, K. aerogenes etc.)
SPECIES_MATCH = "Klebsiella pneumoniae"


def session() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = "phagematch-pk/0.1 (student research; public data)"
    return s


def latest_version(s: requests.Session, organism: str) -> str:
    """Find the newest PDG release. Versions must be sorted numerically -
    lexicographic sorting puts .836 above .2310, which is wrong."""
    r = s.get(f"{FTP_BASE}/{organism}/", timeout=180)
    r.raise_for_status()
    vers = set(re.findall(r'href="(PDG\d+\.(\d+))/"', r.text))
    if not vers:
        raise RuntimeError(f"No PDG releases found for {organism}")
    return max(vers, key=lambda v: int(v[1]))[0]


def download(s: requests.Session, organism: str, version: str) -> Path:
    """Fetch the metadata TSV to disk (cached - these releases are immutable)."""
    url = f"{FTP_BASE}/{organism}/{version}/Metadata/{version}.metadata.tsv"
    dest = DATA_DIR / "raw" / "bacteria" / f"{version}.metadata.tsv"
    dest.parent.mkdir(parents=True, exist_ok=True)

    if dest.exists() and dest.stat().st_size > 0:
        print(f"Using cached {dest} ({dest.stat().st_size/1e6:.1f} MB)")
        return dest

    print(f"Downloading {url}")
    with s.get(url, stream=True, timeout=1800) as r:
        r.raise_for_status()
        size = int(r.headers.get("Content-Length") or 0)
        done = 0
        with dest.open("wb") as fh:
            for chunk in r.iter_content(chunk_size=1 << 20):
                fh.write(chunk)
                done += len(chunk)
                if size and done % (20 << 20) < (1 << 20):
                    print(f"  {done/1e6:>7.1f} / {size/1e6:.1f} MB")
    print(f"  saved -> {dest} ({dest.stat().st_size/1e6:.1f} MB)")
    return dest


def filter_country(path: Path) -> tuple[list[dict], list[str], int]:
    """Keep only rows whose curated geo_loc_name names the target country."""
    kept: list[dict] = []
    total = 0
    with path.open("r", encoding="utf-8", errors="replace", newline="") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        header = reader.fieldnames or []
        for row in reader:
            total += 1
            if COUNTRY.lower() in (row.get("geo_loc_name") or "").lower():
                kept.append(row)
    return kept, header, total


def report(rows: list[dict]) -> None:
    from collections import Counter

    def tally(field, top=15, rows=rows):
        c = Counter((r.get(field) or "").strip() or "unknown" for r in rows)
        return c.most_common(top)

    def show(title, pairs):
        print(f"\n{title}")
        for k, v in pairs:
            print(f"  {k[:44]:<46} {v:>6,}")

    show("Scientific name:", tally("scientific_name"))

    kp = [r for r in rows if SPECIES_MATCH.lower() in (r.get("scientific_name") or "").lower()]
    print(f"\n--- restricting to {SPECIES_MATCH}: {len(kp):,} isolates ---")

    show("Isolation type:", tally("isolation_type", rows=kp))
    show("Isolation source:", tally("isolation_source", top=12, rows=kp))

    years = Counter()
    for r in kp:
        d = (r.get("collection_date") or "").strip()
        m = re.match(r"(\d{4})", d)
        years[m.group(1) if m else "unknown"] += 1
    show("Collection year:", sorted(years.items()))

    with_asm = [r for r in kp if (r.get("asm_acc") or "").strip() not in ("", "NULL")]
    print(f"\nWith assembly (asm_acc): {len(with_asm):,} / {len(kp):,}")

    clinical_recent = [
        r for r in with_asm
        if (r.get("isolation_type") or "").lower() == "clinical"
        and re.match(r"(20(1[5-9]|2\d))", (r.get("collection_date") or "").strip() or "")
    ]
    print(f"Clinical + assembled + 2015 or later: {len(clinical_recent):,}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--organism", default="Klebsiella", help="PD organism group")
    args = ap.parse_args()

    s = session()
    version = latest_version(s, args.organism)
    print(f"Latest {args.organism} release: {version}\n")

    path = download(s, args.organism, version)
    rows, header, total = filter_country(path)
    print(f"\nScanned {total:,} isolates; {len(rows):,} from {COUNTRY}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"ncbi_pd_{args.organism.lower()}_{COUNTRY.lower()}.tsv"
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=header, delimiter="\t", extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote -> {out}")

    report(rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())
