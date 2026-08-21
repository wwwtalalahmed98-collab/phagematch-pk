"""
Step 19 - Render the submission manuscript as a .docx.

Journals take Word files, not Markdown. Neither pandoc nor Node is available
here, so this walks the Markdown itself and emits a document with real Word
heading styles, italic/bold runs, and native tables.

The converter is deliberately narrow: it handles only the constructs the
manuscript actually uses (ATX headings, paragraphs, pipe tables, ordered and
unordered lists, `**bold**`, `*italic*`, `` `code` ``, and markdown links, which
are flattened to their text plus a bare URL). Anything else passes through as
plain text rather than being silently mangled.

Usage:
    python scripts/19_build_docx.py
    python scripts/19_build_docx.py --input docs/manuscript_draft.md
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt, RGBColor

from config import DOCS as OUTDIR

DEFAULT_IN = OUTDIR / "manuscript_submission.md"

# **bold**, *italic*, `code`, [text](url)
TOKEN = re.compile(
    r"(\*\*.+?\*\*|(?<!\*)\*(?!\s)[^*]+?\*(?!\*)|`[^`]+`|\[[^\]]+\]\([^)]+\))")


def add_runs(par, text: str, bold: bool = False, italic: bool = False) -> None:
    """Write inline-formatted text into a paragraph.

    Recurses into bold and italic spans so nested markup survives: a journal
    name italicised inside a bold sentence ("**... *Microb Genom* ...**") must
    come out bold *and* italic, not bold with literal asterisks.
    """
    for piece in TOKEN.split(text):
        if not piece:
            continue
        if piece.startswith("**") and piece.endswith("**"):
            add_runs(par, piece[2:-2], bold=True, italic=italic)
        elif piece.startswith("`") and piece.endswith("`"):
            r = par.add_run(piece[1:-1])
            r.font.name = "Consolas"
            r.font.size = Pt(9.5)
            r.bold, r.italic = bold, italic
        elif piece.startswith("[") and "](" in piece:
            label, url = re.match(r"\[([^\]]+)\]\(([^)]+)\)", piece).groups()
            # Keep the DOI visible: a Word reader cannot hover a markdown link.
            r = par.add_run(label if label.startswith("10.") else f"{label} ")
            r.bold, r.italic = bold, italic
            if not label.startswith("10."):
                u = par.add_run(url)
                u.font.size = Pt(9)
        elif piece.startswith("*") and piece.endswith("*"):
            add_runs(par, piece[1:-1], bold=bold, italic=True)
        else:
            r = par.add_run(piece)
            r.bold, r.italic = bold or None, italic or None


def add_table(doc, rows: list[str]) -> None:
    header = [c.strip() for c in rows[0].strip().strip("|").split("|")]
    body = []
    for r in rows[2:]:                       # rows[1] is the --- separator
        cells = [c.strip() for c in r.strip().strip("|").split("|")]
        if any(cells):
            body.append(cells)

    t = doc.add_table(rows=1, cols=len(header))
    t.style = "Light Grid Accent 1"
    for i, h in enumerate(header):
        cell = t.rows[0].cells[i]
        cell.text = ""
        add_runs(cell.paragraphs[0], h)
        for run in cell.paragraphs[0].runs:
            run.bold = True
    for cells in body:
        row = t.add_row()
        for i, c in enumerate(cells[:len(header)]):
            row.cells[i].text = ""
            add_runs(row.cells[i].paragraphs[0], c)
    doc.add_paragraph()


def convert(md: str, doc: Document) -> None:
    lines = md.splitlines()
    i, para = 0, []

    def flush() -> None:
        nonlocal para
        if para:
            add_runs(doc.add_paragraph(), " ".join(para).strip())
            para = []

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            flush()
            i += 1
            continue

        if stripped.startswith("#"):
            flush()
            level = len(stripped) - len(stripped.lstrip("#"))
            text = stripped[level:].strip()
            # Markdown H1 is the title; H2 becomes Word Heading 1 so the
            # document outline starts at the section level.
            h = doc.add_heading(level=0 if level == 1 else min(level - 1, 4))
            add_runs(h, text)
            i += 1
            continue

        if stripped.startswith("---"):
            flush()
            i += 1
            continue

        m_img = re.match(r"^!\[([^\]]*)\]\(([^)]+)\)\s*$", stripped)
        if m_img:
            flush()
            alt, src = m_img.groups()
            path = (Path(src) if Path(src).is_absolute()
                    else (OUTDIR / src).resolve())
            if path.exists():
                # 6.2 in fits the default Word text column with margins intact;
                # python-docx scales height proportionally from width alone.
                doc.add_picture(str(path), width=Inches(6.2))
                doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
            else:
                # Never silently drop a figure - a missing image must be visible.
                warn = doc.add_paragraph()
                r = warn.add_run(f"[MISSING FIGURE: {src}]")
                r.bold = True
                r.font.color.rgb = RGBColor(0xC0, 0x39, 0x2B)
            i += 1
            continue

        if stripped.startswith("|"):
            flush()
            block = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                block.append(lines[i])
                i += 1
            if len(block) >= 2:
                add_table(doc, block)
            continue

        m = re.match(r"^(\d+)\.\s+(.*)", stripped)
        if m:
            flush()
            # Reference lists are numbered explicitly in the source; keep those
            # numerals rather than letting Word renumber them.
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Pt(24)
            p.paragraph_format.first_line_indent = Pt(-24)
            add_runs(p, f"{m.group(1)}. {m.group(2)}")
            i += 1
            continue

        if stripped.startswith(("- ", "* ")):
            flush()
            add_runs(doc.add_paragraph(style="List Bullet"), stripped[2:])
            i += 1
            continue

        if stripped.startswith(">"):
            flush()
            p = doc.add_paragraph(style="Intense Quote")
            add_runs(p, stripped.lstrip("> "))
            i += 1
            continue

        para.append(stripped)
        i += 1

    flush()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", type=Path, default=DEFAULT_IN)
    args = ap.parse_args()

    md = args.input.read_text(encoding="utf-8")

    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Times New Roman"
    style.font.size = Pt(11)
    style.paragraph_format.space_after = Pt(6)
    style.paragraph_format.line_spacing = 2.0   # journals ask for double spacing

    convert(md, doc)

    # Flag the outstanding-information markers in red so they cannot be missed.
    for p in doc.paragraphs:
        if "⚠" in p.text:
            for run in p.runs:
                run.font.color.rgb = RGBColor(0xC0, 0x39, 0x2B)

    out = OUTDIR / (args.input.stem + ".docx")
    doc.save(out)
    warn = sum(1 for p in doc.paragraphs if "⚠" in p.text)
    print(f"Wrote {out} ({out.stat().st_size/1024:.0f} KB, "
          f"{len(doc.paragraphs)} paragraphs, {len(doc.tables)} tables)")
    print(f"{warn} paragraphs flagged as needing author input (shown in red)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
