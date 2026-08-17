"""
Step 17 - Turn the curated phage-capsule table into a formatted reference list.

Every row in data/phage_klocus_curated.csv carries a PMID. This resolves those
PMIDs against the cached PubMed metadata, emits a numbered reference list in
Vancouver-ish style, and rewrites the curated table with a citation number so
the manuscript can cite [12] instead of "PMID 34156584".

Any PMID with no cached metadata is reported rather than silently dropped - a
missing reference in a submitted manuscript is worse than a loud failure here.

Usage:
    python scripts/17_format_curated_refs.py
"""

from __future__ import annotations

import csv
import glob
import html
import json
import re
from pathlib import Path

from config import CURATED, CURATED_NUMBERED, DOCS, PUBMED_CACHE

CACHE = PUBMED_CACHE
OUT_MD = DOCS / "curated_references.md"
OUT_CSV = CURATED_NUMBERED

# The manuscript already uses [1]-[7]; curated refs continue from there.
START_AT = 8

# Microbiology Society house style (Microbial Genomics), as documented in the
# journal's style guides:
#   **Surname AB, Surname CD, Surname EF, Surname GH, Surname IJ, et al.**
#   Title in sentence case. *J Abbrev* Year;**Volume**:pages
# Author names bold, journal abbreviation italic, volume bold, en-dashed page
# ranges, and the first five authors listed before 'et al.' when six or more.
MAX_AUTHORS = 5


def clean(s: str) -> str:
    """Normalise whitespace and turn publisher markup into markdown.

    Crossref returns titles containing literal <i>...</i> around species and
    gene names. Those become markdown italics; any other tag is dropped.
    """
    s = html.unescape(s or "")
    s = re.sub(r"</?(?:i|em)>", "*", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    s = re.sub(r"\*\s+\*", " ", s)      # collapse empty italic runs
    s = re.sub(r"\*{2,}", "*", s)
    return re.sub(r"\s+", " ", s).strip()


def load_cache() -> dict[str, dict]:
    seen: dict[str, dict] = {}
    for f in sorted(CACHE.glob("*.txt")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            continue
        for a in data.get("articles", []) if isinstance(data, dict) else []:
            pmid = (a.get("identifiers") or {}).get("pmid")
            if pmid:
                seen[str(pmid)] = a
    return seen


# Words that must keep their capitals when a title is lowered to sentence case.
# Anything with a digit, an internal capital, an underscore or a non-ASCII
# character is protected automatically, so this list only needs plain
# alphabetic proper nouns.
PROTECTED = {
    # taxa
    "Klebsiella", "Acinetobacter", "Raoultella", "Enterobacter", "Escherichia",
    "Salmonella", "Pseudomonas", "Autographivirales", "Autographiviridae",
    "Sugarlandvirus", "Kaypoctavirus", "Teetrevirus", "Przondovirus",
    "Drulisvirus", "Slopekvirinae", "Caudovirales", "Podoviridae",
    "Siphoviridae", "Myoviridae", "Galleria", "mellonella",
    # places and nationalities
    "Pakistan", "Pakistani", "India", "Indian", "China", "Chinese", "Tunisia",
    "Tunisian", "Thailand", "Thai", "Egypt", "Egyptian", "Taiwan", "Taiwanese",
    "Iraq", "Bangladesh", "Nepal", "Korea", "Korean", "Japan", "Japanese",
    "Europe", "European", "American", "Hungary", "Russia", "Russian",
    # phage names that are plain alphabetic
    "Kiwi", "Nika", "Pie",
    # tools and resources
    "Kaptive", "Kleborate", "GenBank", "PubMed", "Illumina", "Nanopore",
}


def sentence_case(title: str) -> tuple[str, list[str]]:
    """Lower a publisher title to sentence case, protecting proper nouns.

    Returns the new title and every word changed, so each substitution can be
    reviewed. Automatic protection covers tokens containing a digit, an internal
    capital, an underscore or any non-ASCII character — that catches KL64,
    ΦK64-1, vB_KpnM_P-KP2 and wzc without listing them individually. Only plain
    Capitalised words are candidates for lowering.
    """
    def lower_part(part: str, token_has_digit: bool) -> tuple[str, str | None]:
        """Decide one hyphen-separated fragment.

        `token_has_digit` guards serotype designators. In "K-17" the fragment
        "K" is a plain capital letter and would otherwise be lowered to "k-17",
        silently renaming the capsule type. A lone capital inside a token that
        contains a digit is therefore protected, while a lone capital elsewhere
        (the article "A" in "KP-C01: A novel phage") is still lowered.
        """
        core = part.strip("*_()[],.;:'\"")
        if (not core
                or core in PROTECTED
                or any(ch.isdigit() for ch in core)
                or not core.isascii()
                or "_" in core
                or not core[:1].isupper()
                or any(ch.isupper() for ch in core[1:])
                or (len(core) == 1 and token_has_digit)):
            return part, None
        return part.replace(core, core.lower(), 1), f"{core} → {core.lower()}"

    out, changed = [], []
    first = True
    for tok in title.split(" "):
        if first and tok.strip("*_([\"'"):
            # Only the opening word of the title keeps its capital. Microbiology
            # Society titles lowercase after a colon — the published Kaptive
            # title reads "Kaptive 2.0: updated capsule and ... typing".
            out.append(tok)
            first = False
            continue
        # Hyphenated compounds are decided part by part, otherwise "Anti-Biofilm"
        # is protected wholesale by its internal capital and "K64-Serotype" by
        # its digit.
        parts, notes = [], []
        tok_has_digit = any(ch.isdigit() for ch in tok)
        for part in tok.split("-"):
            new, note = lower_part(part, tok_has_digit)
            parts.append(new)
            if note:
                notes.append(note)
        out.append("-".join(parts))
        changed.extend(notes)
    return " ".join(out), changed


def crossref_titles(dois: list[str]) -> dict[str, str]:
    """Fetch titles from Crossref, keyed by DOI.

    PubMed's API strips the italic markup around species names, which silently
    deletes words: "Identification of a Depolymerase Specific for K64-Serotype
    *Klebsiella pneumoniae*: Potential Applications" comes back as
    "...K64-SerotypePotential Applications". Crossref returns the full string,
    so titles are taken from there wherever a DOI resolves.
    """
    import time
    import urllib.error
    import urllib.request

    # Renamed from _crossref_titles.json: entries used to be plain strings and
    # now carry title + authors, so an old cache must not be reused.
    cache_file = Path(__file__).with_name("_crossref_meta.json")
    got: dict[str, str] = {}
    if cache_file.exists():
        try:
            got = json.loads(cache_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            got = {}

    todo = [d for d in dois if d and d not in got]
    for i, doi in enumerate(todo, 1):
        req = urllib.request.Request(
            f"https://api.crossref.org/works/{doi}",
            headers={"User-Agent": "PhageMatch-PK/1.0 (mailto:researcher@example.org)"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                msg = json.load(r)["message"]
            titles = msg.get("title") or []
            entry: dict = {}
            if titles:
                entry["title"] = clean(titles[0])
            # Publisher-supplied author records handle mononyms correctly
            # (a single-name author has `family` and no `given`), whereas
            # PubMed forces every author into last-name + initials and can
            # alter capitalisation of compound names.
            auths = []
            for a in msg.get("author") or []:
                fam = clean(a.get("family") or a.get("name") or "")
                given = clean(a.get("given") or "")
                if fam:
                    auths.append({"family": fam, "given": given})
            if auths:
                entry["authors"] = auths
            # Journals that number articles instead of paginating put the
            # number in `article-number`; PubMed often records neither, which
            # is why 7 references had no page field.
            page = clean(msg.get("page") or "")
            artno = clean(str(msg.get("article-number") or ""))
            if page:
                entry["page"] = page
            elif artno:
                entry["page"] = artno
            vol = clean(str(msg.get("volume") or ""))
            if vol:
                entry["volume"] = vol
            if entry:
                got[doi] = entry
        except (urllib.error.URLError, KeyError, json.JSONDecodeError, TimeoutError):
            pass
        if i % 5 == 0:
            print(f"  crossref {i}/{len(todo)}")
        time.sleep(0.25)  # Crossref etiquette

    cache_file.write_text(json.dumps(got, indent=1), encoding="utf-8")
    return got


def format_ref(a: dict, cr: dict[str, dict] | None = None) -> str:
    doi_for_title = (a.get("identifiers") or {}).get("doi", "")
    xref = (cr or {}).get(doi_for_title, {})

    names = []
    if xref.get("authors"):
        for au in xref["authors"][:MAX_AUTHORS]:
            # Split on hyphens as well as spaces: "Yi-Jiun" must yield "YJ",
            # not "Y". Chinese and Taiwanese given names are routinely
            # hyphenated in Crossref records.
            parts = [w for w in re.split(r"[\s\-‐-―]+", au["given"]) if w]
            initials = "".join(w[0].upper() for w in parts)
            names.append(f"{au['family']} {initials}".strip())
        n_authors = len(xref["authors"])
    else:
        authors = a.get("authors") or []
        for au in authors[:MAX_AUTHORS]:
            last = clean(au.get("last_name", ""))
            init = clean(au.get("initials", ""))
            if last:
                names.append(f"{last} {init}".strip())
        n_authors = len(authors)

    # Bold wraps the names only; 'et al.' sits outside it in italic. Nesting
    # italic inside bold ("**... *et al.***") produces ambiguous markdown.
    author_str = f"**{', '.join(names)}**"
    author_str += ", *et al.*" if n_authors > MAX_AUTHORS else "."

    title = clean(xref.get("title") or a.get("title", "")).rstrip(".")
    title, _changes = sentence_case(title)
    jour = clean((a.get("journal") or {}).get("iso_abbreviation", ""))
    year = (a.get("publication_date") or {}).get("year", "")
    cit = a.get("citation") or {}
    vol = xref.get("volume") or cit.get("volume", "")
    pages = cit.get("pages", "") or xref.get("page", "")

    # Microbiology Society: *Journal* Year;**Volume**:pages - no issue number,
    # en-dashed page ranges.
    pages = re.sub(r"(\d)\s*-\s*(\d)", r"\1–\2", pages)
    loc = f"*{jour}*"
    if year:
        loc += f" {year}"
    if vol:
        loc += f";**{vol}**"
    if pages:
        loc += f":{pages}"
    else:
        loc += ":[article no.]"   # publisher article number - fill before submission

    doi = (a.get("identifiers") or {}).get("doi", "")
    ref = f"{author_str} {title}. {loc}."
    if doi:
        ref += f" doi:[{doi}](https://doi.org/{doi})"
    return re.sub(r"\s+", " ", ref).replace(" .", ".")


def main() -> int:
    cache = load_cache()
    print(f"Cached PubMed records: {len(cache)}")

    rows = list(csv.DictReader(CURATED.open(encoding="utf-8", newline="")))
    pmids = []
    for r in rows:
        p = (r.get("pmid") or "").strip()
        if p and p not in pmids:
            pmids.append(p)
    print(f"Distinct PMIDs in curated table: {len(pmids)}")

    missing = [p for p in pmids if p not in cache]
    resolved = [p for p in pmids if p in cache]
    if missing:
        print(f"\nMISSING metadata for {len(missing)} PMIDs - fetch these:")
        print("  " + ",".join(missing))

    # Number by first appearance in the curated table, so reference order
    # follows the order a reader meets them in the evidence table.
    numbers = {p: START_AT + i for i, p in enumerate(resolved)}

    print("\nFetching titles and author records from Crossref (PubMed strips "
          "italicised species names and normalises mononyms away)...")
    titles = crossref_titles([(cache[p].get("identifiers") or {}).get("doi", "")
                              for p in resolved])
    fixed = sum(1 for p in resolved
                if (cache[p].get("identifiers") or {}).get("doi", "") in titles)
    print(f"  resolved {fixed}/{len(resolved)} records via Crossref")

    # Anything still showing a run-together word is a title PubMed mangled and
    # Crossref could not replace - flag it rather than ship it.
    suspect = []
    for p in resolved:
        t = titles.get((cache[p].get("identifiers") or {}).get("doi", ""), {}) \
            .get("title") or cache[p].get("title", "")
        if re.search(r"[a-z]{2}[A-Z][a-z]", clean(t)):
            suspect.append((numbers[p], p, clean(t)[:80]))

    lines = [
        "# Curated phage–capsule references",
        "",
        "Formatted in Microbiology Society (*Microbial Genomics*) style: author "
        "names bold, first five authors then *et al.*, journal abbreviation "
        "italic, volume bold, en-dashed page ranges. In-text citations are "
        "square-bracketed numerals — [1], [1, 2], [1–4].",
        "",
        "Reference numbers continue from the main manuscript list, which ends "
        f"at [7]; these run from [{START_AT}].",
        "",
        "Each entry is a phage–capsule pairing used in the coverage analysis. "
        "Literature identified through PubMed; titles and author records "
        "verified against Crossref.",
        "",
    ]
    for p in resolved:
        lines.append(f"{numbers[p]}. {format_ref(cache[p], titles)}")
    if missing:
        lines += ["", "## Unresolved", "",
                  "Metadata not cached for: " + ", ".join(missing)]
    if suspect:
        lines += ["", "## Titles needing manual check", "",
                  "PubMed drops italicised species names, merging adjacent "
                  "words. Crossref could not supply a clean title for these; "
                  "check each against the journal page before submission.", ""]
        lines += [f"- [{n}] PMID {p}: {t}" for n, p, t in suspect]

    def has_locator(p: str) -> bool:
        doi = (cache[p].get("identifiers") or {}).get("doi", "")
        return bool((cache[p].get("citation") or {}).get("pages")
                    or titles.get(doi, {}).get("page"))

    needs_pages = [numbers[p] for p in resolved if not has_locator(p)]
    if needs_pages:
        lines += ["", "## Needing an article number", "",
                  "PubMed holds no page range for these; the Microbiology "
                  "Society style expects the publisher's article number in "
                  "that position. Fill in from the journal page: "
                  + ", ".join(f"[{n}]" for n in needs_pages)]

    # Every sentence-case substitution, listed for review. Automatic
    # lower-casing of titles is the step most likely to damage a proper noun,
    # so it is logged rather than trusted.
    log = []
    for p in resolved:
        doi = (cache[p].get("identifiers") or {}).get("doi", "")
        raw = clean(titles.get(doi, {}).get("title") or cache[p].get("title", ""))
        _new, ch = sentence_case(raw.rstrip("."))
        if ch:
            log.append(f"- **[{numbers[p]}]** " + "; ".join(ch))
    if log:
        lines += ["", "## Sentence-case changes for review", "",
                  "Words lowered when converting publisher titles to "
                  "Microbiology Society sentence case. Scan for any proper "
                  "noun that should have been left capitalised.", ""] + log

    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nWrote {OUT_MD} ({len(resolved)} references)")
    if needs_pages:
        print(f"  {len(needs_pages)} refs need an article number: "
              + ", ".join(f"[{n}]" for n in needs_pages))

    # Curated table with citation numbers attached
    fields = list(rows[0].keys()) + ["ref_number"]
    with OUT_CSV.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for r in rows:
            r["ref_number"] = numbers.get((r.get("pmid") or "").strip(), "")
            w.writerow(r)
    print(f"Wrote {OUT_CSV}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
