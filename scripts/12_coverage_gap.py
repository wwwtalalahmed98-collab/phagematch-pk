"""
Step 12 - Join the Pakistani K-locus burden to the curated phage evidence.

This is the output the whole project points at: for every capsule type circulating
in Pakistani clinical K. pneumoniae, does a phage or depolymerase exist anywhere
in the published literature, and how good is that evidence?

Evidence is graded rather than binary, because "a phage lyses this type" and "an
enzyme was expressed and shown to degrade this capsule" are very different
starting points for a dry-lab matching engine:

    depolymerase_characterized > structure_solved > phage_host_confirmed > genome_only

Absence of evidence here means absence in PubMed as searched - it is a claim about
the published record, not proof no phage exists. Types flagged UNCOVERED are the
ones worth a targeted isolation effort.

Usage:
    python scripts/12_coverage_gap.py
"""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

from config import CURATED, PROCESSED

TARGETS = PROCESSED / "kp_klocus_target_list.csv"
OUT = PROCESSED / "kp_coverage_gap.csv"

RANK = {
    "depolymerase_characterized": 4,
    "structure_solved": 3,
    "phage_host_confirmed": 2,
    "genome_only": 1,
}


def main() -> int:
    for p in (TARGETS, CURATED):
        if not p.exists():
            print(f"Missing {p}")
            return 1

    evidence: dict[str, list[dict]] = defaultdict(list)
    with CURATED.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            evidence[row["k_locus"].strip()].append(row)

    rows = []
    with TARGETS.open(encoding="utf-8", newline="") as fh:
        for t in csv.DictReader(fh):
            kl = t["k_locus"].strip()
            hits = evidence.get(kl, [])
            best = max((RANK.get(h["evidence_level"], 0) for h in hits), default=0)
            rows.append({
                "k_locus": kl,
                "n_isolates": int(t["n_isolates"]),
                "n_carbapenemase": int(t["n_carbapenemase"]),
                "pct_of_cohort": round(float(t["pct_of_cohort"]), 2),
                "n_phage_records": len(hits),
                "best_evidence": next(
                    (k for k, v in RANK.items() if v == best), "NONE"),
                "status": "COVERED" if best >= 2 else
                          ("WEAK" if best == 1 else "UNCOVERED"),
                "phages": ";".join(sorted({h["phage_name"] for h in hits})),
                "pmids": ";".join(sorted({h["pmid"] for h in hits if h["pmid"]})),
            })

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    total = sum(r["n_isolates"] for r in rows)
    covered = sum(r["n_isolates"] for r in rows if r["status"] == "COVERED")
    unc = [r for r in rows if r["status"] == "UNCOVERED"]
    unc_n = sum(r["n_isolates"] for r in unc)
    unc_carb = sum(r["n_carbapenemase"] for r in unc)

    print(f"Pakistani clinical K. pneumoniae: {total} isolates, "
          f"{len(rows)} capsule types\n")
    print(f"  covered by a published phage/enzyme : {covered:>4} "
          f"({covered/total:.1%} of isolates)")
    print(f"  no published phage at all           : {unc_n:>4} "
          f"({unc_n/total:.1%}), of which {unc_carb} carbapenemase-positive\n")

    print("=== Top 15 types by burden ===")
    print(f"{'K-locus':<9}{'n':>4}{'carb':>6}  {'status':<11}{'evidence':<28}phages")
    print("-" * 96)
    for r in rows[:15]:
        print(f"{r['k_locus']:<9}{r['n_isolates']:>4}{r['n_carbapenemase']:>6}  "
              f"{r['status']:<11}{r['best_evidence']:<28}{r['phages'][:34]}")

    print("\n=== Uncovered types, ranked by carbapenemase burden ===")
    for r in sorted(unc, key=lambda x: (-x["n_carbapenemase"],
                                        -x["n_isolates"]))[:12]:
        if r["n_isolates"] >= 2:
            print(f"  {r['k_locus']:<8} {r['n_isolates']:>3} isolates, "
                  f"{r['n_carbapenemase']:>3} carbapenemase-positive")

    print(f"\nWrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
