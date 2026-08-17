"""
Step 1 - Scoping: how many Pakistani genomes actually exist in public archives?

Queries the BV-BRC REST API (which mirrors NCBI/ENA assemblies with curated
metadata, including isolation_country) to count and download metadata for
clinical bacterial genomes deposited from Pakistan.

The count this produces decides project scope: we need enough Pakistani
K. pneumoniae genomes, with enough K-locus diversity, to make a national
phage-coverage map meaningful.

Usage:
    python scripts/01_scope_genomes.py --counts      # fast survey, no download
    python scripts/01_scope_genomes.py --fetch       # pull full metadata to D:
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
import urllib.parse
from pathlib import Path

import requests

BVBRC_API = "https://www.bv-brc.org/api"
from config import DATA_ROOT as DATA_DIR
OUT_DIR = DATA_DIR / "interim"

# Pilot organism first, then the expansion targets we plan to add later.
ORGANISMS = [
    "Klebsiella pneumoniae",
    "Salmonella enterica",
    "Acinetobacter baumannii",
    "Pseudomonas aeruginosa",
    "Escherichia coli",
    "Staphylococcus aureus",
]

# Metadata fields we need for the strain feature table.
GENOME_FIELDS = [
    "genome_id",
    "genome_name",
    "species",
    "strain",
    "assembly_accession",
    "bioproject_accession",
    "biosample_accession",
    "sra_accession",
    "genome_status",
    "isolation_country",
    "geographic_location",
    "collection_year",
    "collection_date",
    "host_name",
    "isolation_source",
    "mlst",
    "contigs",
    "genome_length",
    "checkm_completeness",
    "checkm_contamination",
    "public",
]


def q(value: str) -> str:
    """BV-BRC rejects literal quotes and spaces in the RQL body; encode them."""
    return urllib.parse.quote(str(value), safe="")


def rql_post(endpoint: str, query: str, accept: str = "application/json"):
    """POST an RQL query to BV-BRC. Returns (parsed_or_text, total_count)."""
    url = f"{BVBRC_API}/{endpoint}/"
    headers = {
        "Content-Type": "application/rqlquery+x-www-form-urlencoded",
        "Accept": accept,
    }
    resp = requests.post(url, data=query.encode("utf-8"), headers=headers, timeout=120)
    resp.raise_for_status()

    # BV-BRC reports the unpaged total in Content-Range: items 0-24/1234
    total = None
    cr = resp.headers.get("Content-Range", "")
    if "/" in cr:
        try:
            total = int(cr.rsplit("/", 1)[1])
        except ValueError:
            pass

    payload = resp.json() if accept == "application/json" else resp.text
    return payload, total


def count_genomes(species: str, country: str | None = None) -> int:
    """Count public genomes for a species, optionally restricted to a country."""
    parts = [f"eq(species,{q(species)})", "eq(public,true)"]
    if country:
        parts.append(f"eq(isolation_country,{q(country)})")
    query = "&".join(parts) + "&limit(1)"
    _, total = rql_post("genome", query)
    return total if total is not None else 0


def fetch_genomes(species: str, country: str) -> list[dict]:
    """Download full metadata rows for species+country."""
    query = (
        f"eq(species,{q(species)})&eq(isolation_country,{q(country)})&eq(public,true)"
        f"&select({','.join(GENOME_FIELDS)})&limit(25000)"
    )
    rows, _ = rql_post("genome", query)
    return rows


def cmd_counts() -> None:
    print(f"{'organism':<28} {'Pakistan':>10} {'global':>12}   {'% PK':>6}")
    print("-" * 62)
    for sp in ORGANISMS:
        pk = count_genomes(sp, "Pakistan")
        time.sleep(0.4)
        glob = count_genomes(sp)
        time.sleep(0.4)
        pct = (100.0 * pk / glob) if glob else 0.0
        print(f"{sp:<28} {pk:>10,} {glob:>12,}   {pct:>5.2f}%")


def cmd_fetch(species: str, country: str) -> None:
    rows = fetch_genomes(species, country)
    if not rows:
        print(f"No genomes returned for {species} / {country}")
        return

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    slug = species.lower().replace(" ", "_")
    out = OUT_DIR / f"{slug}_{country.lower()}_genomes.csv"

    with out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=GENOME_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    print(f"Wrote {len(rows):,} genome records -> {out}")
    summarise(rows)


def summarise(rows: list[dict]) -> None:
    """Quick look at whether these genomes are actually usable."""
    from collections import Counter

    def tally(field, top=12):
        c = Counter((r.get(field) or "unknown") for r in rows)
        return c.most_common(top)

    print("\nGenome status:")
    for k, v in tally("genome_status"):
        print(f"  {k:<28} {v:>6,}")

    print("\nCollection year:")
    for k, v in sorted(tally("collection_year", top=50), key=lambda x: str(x[0])):
        print(f"  {k:<28} {v:>6,}")

    print("\nTop sequence types (MLST):")
    for k, v in tally("mlst", top=15):
        print(f"  {k:<28} {v:>6,}")

    print("\nIsolation source:")
    for k, v in tally("isolation_source", top=12):
        print(f"  {k:<28} {v:>6,}")

    n_asm = sum(1 for r in rows if r.get("assembly_accession"))
    print(f"\nWith assembly accession: {n_asm:,} / {len(rows):,}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--counts", action="store_true", help="survey counts only")
    ap.add_argument("--fetch", action="store_true", help="download metadata")
    ap.add_argument("--species", default="Klebsiella pneumoniae")
    ap.add_argument("--country", default="Pakistan")
    args = ap.parse_args()

    if not (args.counts or args.fetch):
        ap.error("pick --counts or --fetch")

    if args.counts:
        cmd_counts()
    if args.fetch:
        cmd_fetch(args.species, args.country)
    return 0


if __name__ == "__main__":
    sys.exit(main())
