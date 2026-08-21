"""
Step 21 - Produce the clean, submission-ready manuscript.

Step 20 assembles the working manuscript, which deliberately carries editorial
notes: a "submission version" banner, parenthetical word counts, and warning
markers for information only the authors can supply. Those belong in a working
draft and must not reach an editor.

This step takes the assembled manuscript and produces `manuscript_publication.md`:
notes removed, figures placed after their legends, and a short list of
copy-editing corrections applied. It refuses to write the file if a warning
marker survives, so an unfinished draft cannot be shipped by accident.

Run step 20 first.

Usage:
    python scripts/21_build_publication.py
"""

from __future__ import annotations

import re
import sys

from config import DOCS, FIGURES

SRC = DOCS / "manuscript_final.md"
OUT = DOCS / "manuscript_publication.md"

# Editorial scaffolding to delete outright.
STRIP_BLOCKS = [
    # the banner under the title
    re.compile(r"\*\*Submission version — structured for \*Microbial Genomics\*"
               r" \(Microbiology Society\)\.\*\*\nFields marked ⚠ require "
               r"information only the authors can supply\.\s*\n---\s*\n", re.S),
    # parenthetical word counts
    re.compile(r"\n\*\(233 words; journal limit 250\.\)\*\n"),
    re.compile(r"\n\*\(141 words; Microbiology Society journals normally cap "
               r"this at 150\.\* ⚠ \*Confirm\nagainst the current author "
               r"guidelines\.\)\*\n"),
    # the optional-acknowledgements note; the section itself is replaced below
    re.compile(r"\*\*Acknowledgements\.\*\* ⚠ \*Optional — add anyone who "
               r"helped but does not meet\nauthorship criteria\.\*\n\n"),
]

# Targeted copy-edits, each with a stated reason.
EDITS: list[tuple[str, str, str]] = [
    (
        "Half the cohort was unmatched: 121 of 254 isolates",
        "Nearly half the cohort was unmatched: 121 of 254 isolates",
        "47.6% is not half; 'nearly half' is accurate and still striking",
    ),
    (
        "(p=0.0014 and p=0.0002)",
        "(*P* = 0.0014 and *P* = 0.0002)",
        "abstract p-values: italicised, spaced",
    ),
    # The manuscript mixed bare 'p', italic '*p*' and unspaced 'p=' across
    # sections. Microbiology Society style sets the probability symbol italic;
    # these normalise every remaining occurrence to '*P*'.
    (
        "| *p* raw | *p* collapsed |",
        "| *P* raw | *P* collapsed |",
        "Table 1 header: italic capital P",
    ),
    (
        "survives collapsing (7 vs 0, p = 0.0014)",
        "survives collapsing (7 vs 0, *P* = 0.0014)",
        "Results: KL81 collapsed p-value italicised",
    ),
    (
        "(p = 0.443, 0.158, 0.091 and 0.185)",
        "(*P* = 0.443, 0.158, 0.091 and 0.185)",
        "Results: clonal p-values italicised",
    ),
    (
        "to reach p < 0.05,",
        "to reach *P* < 0.05,",
        "Limitations: threshold italicised",
    ),
    (
        "Two *p*-value columns are given",
        "Two *P*-value columns are given",
        "Fig. 3 legend: capital P",
    ),
    (
        "counts and *p*-values per capsule type",
        "counts and *P*-values per capsule type",
        "Table S5 caption: capital P",
    ),
    (
        "Bonferroni threshold of α = 0.05/16 = 0.003",
        "Bonferroni-corrected threshold of α = 0.05/16 = 0.003",
        "'Bonferroni threshold' is loose; the threshold is the corrected alpha",
    ),
    (
        "| KL107 | 0.0% | 9.8% (27) | <0.0001 | **0.0002** | robust | — |",
        "| KL107 | 0.0% | 9.8% (27) | <0.0001 | **0.0002** | robust | "
        "n/a — absent from the Pakistani cohort |",
        "a bare dash in the phage column was ambiguous",
    ),
    (
        "**Author contributions.** ⚠ *Draft below — confirm or correct it; it "
        "must reflect\nwhat each author actually did.*\nT.A.,",
        "**Author contributions.** T.A.,",
        "note removed; statement retained",
    ),
    (
        "interest. ⚠ *Confirm this is true for both authors before submitting.*",
        "interest.",
        "note removed; declaration retained",
    ),
    (
        "work. ⚠ *Draft wording — check it against the journal's current policy "
        "and your\ninstitution's rules, and amend if either specifies a form of "
        "words.*",
        "work.",
        "note removed; disclosure retained",
    ),
    (
        "Talal Ahmed¹\\*, Ahmed Hussain Shah¹",
        "Talal Ahmed¹*, Ahmed Hussain Shah¹",
        "backslash escape renders literally in Word; the unicode superscript needs none",
    ),
]

# Figures go immediately after their legends.
FIGURE_FILES = {
    "Fig. 1.": "figures/fig1_capsule_diversity.png",
    "Fig. 2.": "figures/fig2_phage_coverage.png",
    "Fig. 3.": "figures/fig3_geography.png",
}


def insert_after_legends(md: str) -> tuple[str, list[str]]:
    """Append each figure image after the paragraph carrying its legend."""
    paragraphs = md.split("\n\n")
    out, placed = [], []
    for para in paragraphs:
        out.append(para)
        for tag, src in FIGURE_FILES.items():
            if para.lstrip().startswith(f"**{tag}**"):
                out.append(f"![{tag}]({src})")
                placed.append(tag)
    return "\n\n".join(out), placed


def main() -> int:
    if not SRC.exists():
        print(f"Missing {SRC}. Run 20_assemble_manuscript.py first.")
        return 1

    md = SRC.read_text(encoding="utf-8")
    original_len = len(md)

    for pat in STRIP_BLOCKS:
        md, n = pat.subn("", md)
        if not n:
            print(f"  note: pattern not matched (already removed?): "
                  f"{pat.pattern[:48]}...")

    applied = []
    for old, new, why in EDITS:
        if old in md:
            md = md.replace(old, new)
            applied.append(why)
        else:
            print(f"  note: edit target absent (already applied?): {why}")

    # Acknowledgements: keep the heading with an explicit statement rather than
    # leaving a bare heading, which reads as an omission.
    if "**Acknowledgements.**" not in md:
        md = md.replace(
            "**Author contributions.**",
            "**Acknowledgements.** The authors thank the research groups whose "
            "public genome deposits and published phage characterisations made "
            "this analysis possible.\n\n**Author contributions.**", 1)

    md, placed = insert_after_legends(md)

    # Refuse to emit a file that still contains editorial markers.
    leftover = [ln for ln in md.splitlines() if "⚠" in ln]
    if leftover:
        print("\nREFUSING TO WRITE - warning markers still present:")
        for ln in leftover:
            print("   ", ln[:90])
        return 1

    md = md.rstrip() + "\n"
    OUT.write_text(md, encoding="utf-8")

    missing = [t for t, s in FIGURE_FILES.items()
               if not (DOCS / s).exists()]
    print(f"Wrote {OUT}")
    print(f"  {original_len - len(md)} characters of editorial scaffolding removed")
    print(f"  {len(applied)} copy-edits applied")
    for w in applied:
        print(f"     - {w}")
    print(f"  figures placed: {', '.join(placed) if placed else 'NONE'}")
    if missing:
        print(f"  WARNING missing figure files: {missing}")
    print(f"  warning markers remaining: 0")
    return 0


if __name__ == "__main__":
    sys.exit(main())
