"""
Step 9 - Build the international comparison cohort.

The Pakistani K-locus distribution only means something relative to somewhere
else. This assembles matched comparison sets from the cached NCBI Pathogen
Detection metadata (no new download needed) so the same Kleborate pipeline can
type them.

Comparator choice is deliberate:
  * India, Bangladesh - regional neighbours; tests whether the pattern is
    Pakistani or South Asian. This is the comparison that matters most, because
    "South Asian" is a much bigger claim than "Pakistani".
  * China            - the largest producer of Klebsiella phage studies, so its
                       capsule landscape is what most published phages target.
  * United Kingdom / Germany / Italy, USA - the other main sources of
                       characterised phages and reference databases.

Matched on the same criteria as the Pakistani core set: K. pneumoniae, clinical
isolation, 2015 or later, assembly available.

Usage:
    python scripts/09_build_comparison_cohort.py
    python scripts/09_build_comparison_cohort.py --per-group 150
"""

from __future__ import annotations

import argparse
import csv
import random
import re
import sys
from collections import Counter
from pathlib import Path

from config import PD_TSV
from config import PROCESSED as OUT_DIR

SPECIES = "Klebsiella pneumoniae"
MIN_YEAR = 2015
SEED = 20260815  # fixed so the sample is reproducible

# group label -> country strings to match in geo_loc_name
GROUPS = {
    "india": ["India"],
    "bangladesh_nepal": ["Bangladesh", "Nepal"],
    "china": ["China"],
    "europe": ["United Kingdom", "Germany", "Italy", "France", "Spain",
               "Netherlands", "Norway", "Sweden", "Denmark"],
    "usa": ["USA", "United States"],
}


def year_of(row: dict) -> int | None:
    m = re.match(r"(\d{4})", (row.get("collection_date") or "").strip())
    return int(m.group(1)) if m else None


def group_of(geo: str) -> str | None:
    g = geo.lower()
    for label, countries in GROUPS.items():
        for c in countries:
            # match on the country segment; PD writes "India: Delhi" etc.
            if g.startswith(c.lower()) or f":{c.lower()}" in g or g == c.lower():
                return label
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--per-group", type=int, default=100,
                    help="genomes to sample per comparison group")
    args = ap.parse_args()

    if not PD_TSV.exists():
        print(f"Missing {PD_TSV}. Run 03_ncbi_pathogen_detection.py first.")
        return 1

    pools: dict[str, list[dict]] = {k: [] for k in GROUPS}
    scanned = 0

    with PD_TSV.open("r", encoding="utf-8", errors="replace", newline="") as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            scanned += 1
            if SPECIES.lower() not in (row.get("scientific_name") or "").lower():
                continue
            if (row.get("asm_acc") or "NULL").strip() in ("", "NULL"):
                continue
            if (row.get("epi_type") or "").strip().lower() != "clinical":
                continue
            y = year_of(row)
            if y is None or y < MIN_YEAR:
                continue
            g = group_of((row.get("geo_loc_name") or "").strip())
            if g:
                pools[g].append(row)

    print(f"Scanned {scanned:,} isolates\n")
    print(f"{'group':<20} {'available':>10} {'sampled':>9}")
    print("-" * 42)

    rng = random.Random(SEED)
    selected: dict[str, list[dict]] = {}
    for label, rows in pools.items():
        n = min(args.per_group, len(rows))
        selected[label] = rng.sample(rows, n) if n else []
        print(f"{label:<20} {len(rows):>10,} {n:>9,}")

    total = sum(len(v) for v in selected.values())
    print(f"{'TOTAL':<20} {'':>10} {total:>9,}")

    if not total:
        print("\nNothing selected - check the country matching.")
        return 1

    # accession list for the Colab notebook
    acc_file = OUT_DIR / "kp_comparison_accessions.txt"
    accs = [r["asm_acc"].strip() for rows in selected.values() for r in rows]
    acc_file.write_text("\n".join(accs) + "\n", encoding="utf-8")
    print(f"\nWrote {len(accs):,} accessions -> {acc_file}")

    # key table so results can be grouped by country afterwards
    key_file = OUT_DIR / "kp_comparison_keys.csv"
    with key_file.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["assembly", "group", "geo_loc_name", "collection_date",
                    "year", "isolation_source", "bioproject"])
        for label, rows in selected.items():
            for r in rows:
                w.writerow([r["asm_acc"].strip(), label,
                            r.get("geo_loc_name", ""), r.get("collection_date", ""),
                            year_of(r) or "", r.get("isolation_source", ""),
                            r.get("bioproject_acc", "")])
    print(f"Wrote key table   -> {key_file}")

    print("\nYear spread of the sampled set:")
    years = Counter(year_of(r) for rows in selected.values() for r in rows)
    for y in sorted(k for k in years if k):
        print(f"  {y}  {years[y]:>4}")

    mins = total * 21 / 60
    print(f"\nEstimated Colab typing time: ~{mins:.0f} min "
          f"(~{total * 5.5 / 1024:.1f} GB download)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
