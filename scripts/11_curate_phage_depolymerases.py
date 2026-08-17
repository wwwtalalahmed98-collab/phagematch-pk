"""
Step 11 - Mine the Klebsiella depolymerase literature for phage <-> K-locus pairs.

Reads the cached PubMed metadata dumps and pulls out, for each paper, which
capsule types it mentions and in what sentence. This does NOT produce the final
curated table - it produces a triage list so a human reads the ~30 papers that
actually pair a phage with a capsule type instead of all 129.

Why sentence context matters: an abstract saying "KL64 is the dominant type in
CRKP" is epidemiology, while "depolymerase Dep_kp1 degraded KL64 capsule" is a
usable pairing. Only the sentence tells them apart, so we keep it.

Usage:
    python scripts/11_curate_phage_depolymerases.py
"""

from __future__ import annotations

import csv
import html
import json
import re
from pathlib import Path

from config import PROCESSED, PUBMED_CACHE

CACHE = PUBMED_CACHE
OUT = PROCESSED / "phage_depolymerase_triage.csv"

# Capsule types that matter most - the Pakistani top hitters.
PRIORITY = {"KL64", "KL51", "KL24", "KL81", "KL112", "KL17"}

# Words that mark a sentence as a real phage/enzyme claim rather than epidemiology.
CLAIM = re.compile(
    r"depolymeras|phage|lyase|hydrolase|tail *(?:fibre|fiber|spike)|"
    r"degrad|lyse|lytic|host range|spectrum",
    re.I,
)

KL_RE = re.compile(r"\bKL\s?(\d{1,3})\b")
K_RE = re.compile(r"\bK(\d{1,3})\b")


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(text or "")).strip()


def sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def load_articles() -> dict[str, dict]:
    """Every metadata dump in the cache, deduplicated by PMID."""
    seen: dict[str, dict] = {}
    files = sorted(CACHE.glob("*get_article_metadata*.txt"))
    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        for a in data.get("articles", []):
            pmid = (a.get("identifiers") or {}).get("pmid")
            if pmid:
                seen[pmid] = a
    print(f"Read {len(files)} cache files -> {len(seen)} unique articles")
    return seen


def main() -> int:
    articles = load_articles()
    if not articles:
        print(f"No metadata dumps found in {CACHE}")
        return 1

    rows = []
    for pmid, a in articles.items():
        title = clean(a.get("title", ""))
        abstract = clean(a.get("abstract", ""))
        blob = f"{title} {abstract}"

        kls = {f"KL{int(m)}" for m in KL_RE.findall(blob)}
        # Bare K-numbers only count when the paper is clearly about capsules,
        # otherwise K1/K2 collide with gene and buffer names.
        if re.search(r"capsul|serotype|K-?locus|K-?type", blob, re.I):
            kls |= {f"KL{int(m)}" for m in K_RE.findall(blob)}
        if not kls:
            continue

        # Keep only sentences that both name a capsule type and make a claim.
        ev = [
            s for s in sentences(blob)
            if (KL_RE.search(s) or K_RE.search(s)) and CLAIM.search(s)
        ]
        is_depol = bool(re.search(r"depolymeras", blob, re.I))
        is_phage = bool(re.search(r"\bphage|bacteriophage", blob, re.I))

        rows.append({
            "pmid": pmid,
            "year": (a.get("publication_date") or {}).get("year", ""),
            "journal": ((a.get("journal") or {}).get("iso_abbreviation") or ""),
            "doi": (a.get("identifiers") or {}).get("doi", ""),
            "depolymerase": "Y" if is_depol else "",
            "phage": "Y" if is_phage else "",
            "priority_hit": ",".join(sorted(kls & PRIORITY,
                                            key=lambda x: int(x[2:]))),
            "all_KL": ",".join(sorted(kls, key=lambda x: int(x[2:]))),
            "n_evidence": len(ev),
            "title": title,
            "evidence": " || ".join(ev[:4]),
        })

    # Papers that pair an enzyme with a capsule type come first, and within
    # those, the ones touching Pakistan's dominant types.
    rows.sort(key=lambda r: (r["depolymerase"] != "Y",
                             not r["priority_hit"],
                             -r["n_evidence"]))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    depol = [r for r in rows if r["depolymerase"] == "Y"]
    prio = [r for r in depol if r["priority_hit"]]
    print(f"\n{len(rows)} papers mention a capsule type")
    print(f"{len(depol)} of those are depolymerase papers")
    print(f"{len(prio)} hit a Pakistani priority type\n")

    print("=== Depolymerase papers touching priority capsule types ===")
    for r in prio:
        print(f"\nPMID {r['pmid']} ({r['year']}) {r['journal']} "
              f"[{r['priority_hit']}]")
        print(f"  {r['title'][:150]}")
        if r["evidence"]:
            print(f"  > {r['evidence'][:400]}")

    print(f"\nFull triage table -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
