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
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
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
            # But when the label is already the tail of the URL - an ORCID iD
            # linked to its own resolver - printing both just repeats it.
            redundant = label.startswith("10.") or url.rstrip("/").endswith(label)
            r = par.add_run(label if redundant else f"{label} ")
            r.bold, r.italic = bold, italic
            if not redundant:
                u = par.add_run(url)
                u.font.size = Pt(9)
        elif piece.startswith("*") and piece.endswith("*"):
            add_runs(par, piece[1:-1], bold=bold, italic=True)
        else:
            r = par.add_run(piece)
            r.bold, r.italic = bold or None, italic or None


def absorb_continuation(lines: list[str], i: int, body: str) -> tuple[int, str]:
    """Pull a list item's wrapped continuation lines into the item itself.

    The manuscript wraps long list items — references especially — across
    several indented source lines. Treating each as its own paragraph split
    every reference mid-sentence, so a continuation line (indented, not blank,
    and not the start of the next item) is joined onto the item it belongs to.
    """
    while i < len(lines):
        nxt = lines[i]
        if not nxt.strip():
            break
        if not nxt[:1].isspace():            # a new block, flush against it
            break
        if re.match(r"^\s*(\d+\.|[-*])\s+", nxt):   # the next list item
            break
        body += " " + nxt.strip()
        i += 1
    return i, body


def add_table(doc, rows: list[str]) -> None:
    header = [c.strip() for c in rows[0].strip().strip("|").split("|")]
    body = []
    for r in rows[2:]:                       # rows[1] is the --- separator
        cells = [c.strip() for c in r.strip().strip("|").split("|")]
        if any(cells):
            body.append(cells)

    t = doc.add_table(rows=1, cols=len(header))
    # A plain ruled grid. Word's "Accent" styles are coloured and decorative;
    # journals want an unadorned table.
    t.style = "Table Grid"
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

    # Table cells inherit the body's line spacing and 11pt type, which turns
    # a compact table into a page of its own. Journals set tables tighter.
    for r_i, row in enumerate(t.rows):
        # cantSplit stops a single row breaking mid-cell; keep_with_next on
        # every row but the last makes Word move the whole table to the next
        # page rather than stranding the header at the foot of this one.
        trPr = row._tr.get_or_add_trPr()
        trPr.append(OxmlElement("w:cantSplit"))
        if r_i == 0:
            trPr.append(OxmlElement("w:tblHeader"))   # repeat if it ever splits
        for cell in row.cells:
            for p in cell.paragraphs:
                p.paragraph_format.line_spacing = 1.0
                p.paragraph_format.space_after = Pt(2)
                p.paragraph_format.space_before = Pt(2)
                p.paragraph_format.keep_with_next = r_i < len(t.rows) - 1
                for run in p.runs:
                    run.font.size = Pt(9.5)
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
                pic = doc.paragraphs[-1]
                pic.alignment = WD_ALIGN_PARAGRAPH.CENTER
                # Hold the figure against the legend that follows it, and drop
                # the double spacing so the image is not padded off its caption.
                pic.paragraph_format.keep_with_next = True
                pic.paragraph_format.line_spacing = 1.0
                pic.paragraph_format.space_after = Pt(4)
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
            # The caption sits immediately above its table; hold them together.
            if doc.paragraphs:
                doc.paragraphs[-1].paragraph_format.keep_with_next = True
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
            body = m.group(2)
            i += 1
            i, body = absorb_continuation(lines, i, body)
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Pt(24)
            p.paragraph_format.first_line_indent = Pt(-24)
            add_runs(p, f"{m.group(1)}. {body}")
            continue

        if stripped.startswith(("- ", "* ")):
            flush()
            body = stripped[2:]
            i += 1
            i, body = absorb_continuation(lines, i, body)
            add_runs(doc.add_paragraph(style="List Bullet"), body)
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


def style_for_submission(doc: Document) -> None:
    """Strip Word's theme styling and apply manuscript conventions.

    Out of the box python-docx inherits Word's default theme: a 26pt blue
    title and blue Calibri Light headings. A manuscript sent to an editor is
    plain black serif throughout, continuously line-numbered so reviewers can
    cite a line, and page-numbered.
    """
    for name, size, bold in (("Title", 16, True), ("Heading 1", 13, True),
                             ("Heading 2", 12, True), ("Heading 3", 11, True),
                             ("Heading 4", 11, True)):
        if name not in [s.name for s in doc.styles]:
            continue
        st = doc.styles[name]
        st.font.name = "Times New Roman"
        # Word's built-in heading styles name a *theme* font (asciiTheme=
        # "majorHAnsi"), which wins over w:ascii and renders them in Calibri
        # Light whatever font.name says. Drop the theme attributes so the
        # explicit face applies.
        rPr = st.element.get_or_add_rPr()
        rFonts = rPr.get_or_add_rFonts()
        for attr in ("asciiTheme", "hAnsiTheme", "eastAsiaTheme", "cstheme"):
            rFonts.attrib.pop(qn(f"w:{attr}"), None)
        for attr in ("ascii", "hAnsi", "cs"):
            rFonts.set(qn(f"w:{attr}"), "Times New Roman")
        st.font.size = Pt(size)
        st.font.bold = bold
        st.font.italic = False
        st.font.color.rgb = RGBColor(0, 0, 0)
        st.paragraph_format.space_before = Pt(12)
        st.paragraph_format.space_after = Pt(6)
        st.paragraph_format.line_spacing = 1.0
        st.paragraph_format.keep_with_next = True
        # Word's Title style carries a bottom border from the theme.
        pPr = st.element.get_or_add_pPr()
        for bdr in pPr.findall(qn("w:pBdr")):
            pPr.remove(bdr)

    # Justified text without hyphenation opens rivers of white space, badly so
    # in the narrow reference column where a DOI cannot break. Word hyphenates
    # only when asked.
    settings = doc.settings.element
    for tag, val in (("w:autoHyphenation", "true"),
                     ("w:doNotHyphenateCaps", "true")):
        el = OxmlElement(tag)
        el.set(qn("w:val"), val)
        settings.append(el)

    sec = doc.sections[0]
    # Page number, centred in the footer, as a real Word field.
    p = sec.footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run()
    for el, attrs, text in (("w:fldChar", {"w:fldCharType": "begin"}, None),
                            ("w:instrText", {"xml:space": "preserve"}, " PAGE "),
                            ("w:fldChar", {"w:fldCharType": "end"}, None)):
        e = OxmlElement(el)
        for k, v in attrs.items():
            e.set(qn(k), v)
        if text:
            e.text = text
        run._r.append(e)
    run.font.name = "Times New Roman"
    run.font.size = Pt(10)


def delete(par) -> None:
    par._element.getparent().remove(par._element)


def apply_layout(doc: Document, review: bool) -> None:
    """Impose journal page layout once the content is in place.

    Done as a pass over the finished document rather than inline, because the
    rules are positional - what counts as the title block, a figure legend or a
    reference depends on where a paragraph sits relative to the headings.
    """
    paras = doc.paragraphs
    idx = {p.text.strip().lower(): i for i, p in enumerate(paras)
           if p.style.name.startswith("Heading")}
    abstract = idx.get("abstract", 0)
    refs = idx.get("references", len(paras))

    # Title block: everything above the Abstract heading, centred, single
    # spaced. The standalone "Authors" heading is scaffolding - the names
    # under the title already say what they are.
    for p in paras[:abstract]:
        if p.style.name.startswith("Heading") and p.text.strip() == "Authors":
            delete(p)
            continue
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.line_spacing = 1.0
        p.paragraph_format.space_after = Pt(6)

    for p in paras[abstract:]:
        txt = p.text.strip()
        if p.style.name.startswith("Heading") or not txt:
            continue
        # Justified body text, as the exemplar sets it.
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        is_legend = txt.startswith(("Fig. ", "Figure ", "Table "))
        is_ref = bool(re.match(r"^\d+\.\s", txt)) and paras.index(p) > refs
        if is_legend or is_ref:
            # Legends and references are set smaller and tighter than body text
            # in every journal, and it keeps a legend on its figure's page.
            p.paragraph_format.line_spacing = 1.0
            p.paragraph_format.space_after = Pt(6)
            for run in p.runs:
                run.font.size = Pt(9.5)

    if not review:
        return
    # Review copy: continuous line numbers, as Microbiology Society asks. The
    # double spacing is set on the Normal style back in main().
    sectPr = doc.sections[0]._sectPr
    ln = OxmlElement("w:lnNumType")
    ln.set(qn("w:countBy"), "1")
    ln.set(qn("w:start"), "1")
    ln.set(qn("w:restart"), "continuous")
    sectPr.append(ln)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", type=Path, default=DEFAULT_IN)
    ap.add_argument("--review", action="store_true",
                    help="double-spaced with line numbers, for journal review; "
                         "the default is the single-spaced preprint layout")
    args = ap.parse_args()

    md = args.input.read_text(encoding="utf-8")

    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Times New Roman"
    style.font.size = Pt(11)
    style.paragraph_format.space_after = Pt(8)
    # Single spacing reads as a finished paper; review copies go double spaced
    # with line numbers under --review.
    style.paragraph_format.line_spacing = 2.0 if args.review else 1.15

    style_for_submission(doc)
    convert(md, doc)
    apply_layout(doc, args.review)

    # Flag the outstanding-information markers in red so they cannot be missed.
    for p in doc.paragraphs:
        if "⚠" in p.text:
            for run in p.runs:
                run.font.color.rgb = RGBColor(0xC0, 0x39, 0x2B)

    # The two layouts are different documents; they must not overwrite each
    # other, or building the review copy silently replaces the preprint.
    out = OUTDIR / (args.input.stem + ("_review" if args.review else "") + ".docx")
    doc.save(out)
    warn = sum(1 for p in doc.paragraphs if "⚠" in p.text)
    print(f"Wrote {out} ({out.stat().st_size/1024:.0f} KB, "
          f"{len(doc.paragraphs)} paragraphs, {len(doc.tables)} tables)")
    print(f"{warn} paragraphs flagged as needing author input (shown in red)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
