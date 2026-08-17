"""
Step 13 - Emit a tiny Colab notebook that collates finished Kleborate chunks.

The comparison runtime was reclaimed after 22 of 25 chunks. Everything those
chunks produced is already on Drive, so recovering the result needs no Kleborate
install and no genome downloads - just Drive plus pandas. That makes this a
~2 minute job instead of a ~30 minute one.

Deliberately separate from the typing notebook: collation must stay runnable
even when the typing environment is gone, which is exactly the situation it
gets used in.

Usage:
    python scripts/13_make_collate_notebook.py
"""

from __future__ import annotations

import json
from pathlib import Path

from config import NOTEBOOKS

OUT = NOTEBOOKS / "11_collate_comparison.ipynb"
DRIVE_DIR = "phagematch-pk-comparison"
RESULT = "kleborate_comparison_kp"


def md(text: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": text}


def code(text: str) -> dict:
    return {"cell_type": "code", "execution_count": None, "metadata": {},
            "outputs": [], "source": text}


def build() -> dict:
    cells = [
        md("# Collate comparison chunks\n\n"
           "The typing runtime was reclaimed after chunk 22 of 25. The finished "
           "chunks are on Drive; this rebuilds the combined table from them.\n\n"
           "Run all cells. No Kleborate, no downloads."),

        md("## Cell 1 - Mount Drive"),
        code("from pathlib import Path\n"
             "from google.colab import drive\n"
             "\n"
             "drive.mount('/content/drive')\n"
             f"PERSIST = Path('/content/drive/MyDrive/{DRIVE_DIR}')\n"
             "KLEB = PERSIST / 'kleborate'\n"
             "print('exists:', KLEB.exists())\n"
             "chunks = sorted(KLEB.glob('chunk_*'))\n"
             "done  = sorted(KLEB.glob('chunk_*.done'))\n"
             "print(f'{len(chunks)} chunk dirs, {len(done)} done markers')\n"),

        md("## Cell 2 - Find the per-chunk Kleborate output"),
        code("import pandas as pd\n"
             "\n"
             "# Kleborate writes a few TSV/TXT files per run; the main table is the\n"
             "# one carrying a strain/assembly column. Probe rather than hardcode a\n"
             "# filename, because the name differs between presets and versions.\n"
             "cands = {}\n"
             "for d in sorted(p for p in KLEB.glob('chunk_*') if p.is_dir()):\n"
             "    for f in sorted(d.rglob('*')):\n"
             "        if f.suffix.lower() in {'.txt', '.tsv'} and f.stat().st_size > 0:\n"
             "            cands.setdefault(f.name, []).append(f)\n"
             "\n"
             "for name, files in sorted(cands.items(), key=lambda kv: -len(kv[1])):\n"
             "    print(f'{len(files):>3}  {name}')\n"),

        md("## Cell 3 - Concatenate\n\n"
           "Picks the file present in the most chunks that actually carries typing "
           "columns, so an AMR-only side table cannot be mistaken for the main one."),
        code("import re\n"
             "\n"
             "# Anchored on purpose. A loose r'ST' matched 'Input_gene_start' in the\n"
             "# hAMRonization table, so the AMR side-file passed this check and got\n"
             "# concatenated instead of the typing table.\n"
             "WANT = re.compile(r'K_locus|K_type|__ST$|species', re.I)\n"
             "\n"
             "best, best_n = None, 0\n"
             "for name, files in cands.items():\n"
             "    try:\n"
             "        head = pd.read_csv(files[0], sep='\\t', nrows=1, dtype=str)\n"
             "    except Exception:\n"
             "        continue\n"
             "    if any(WANT.search(c) for c in head.columns) and len(files) > best_n:\n"
             "        best, best_n = name, len(files)\n"
             "\n"
             "print('using:', best, f'({best_n} chunks)')\n"
             "\n"
             "frames = []\n"
             "for f in cands[best]:\n"
             "    df = pd.read_csv(f, sep='\\t', dtype=str)\n"
             "    df['chunk'] = f.parent.name if f.parent.name.startswith('chunk') \\\n"
             "                  else f.parents[1].name\n"
             "    frames.append(df)\n"
             "\n"
             "kleb = pd.concat(frames, ignore_index=True)\n"
             "print('combined:', kleb.shape)\n"
             "print('chunks represented:', kleb['chunk'].nunique())\n"
             "print(kleb.columns.tolist()[:20])\n"),

        md("## Cell 4 - Sanity check before saving\n\n"
           "A silent duplicate or a wave of unassigned K-loci would poison the "
           "comparison, so check here rather than discover it during analysis."),
        code("col = next((c for c in kleb.columns if c.lower() in\n"
             "            {'strain', 'assembly', 'name', 'input_file_name'}), None)\n"
             "print('id column:', col)\n"
             "if col:\n"
             "    kleb['assembly'] = (kleb[col].astype(str)\n"
             "                        .str.replace(r'\\.(fna|fa|fasta)$', '', regex=True)\n"
             "                        .str.strip())\n"
             "    print('unique genomes:', kleb['assembly'].nunique(), 'of', len(kleb))\n"
             "\n"
             "kcol = next((c for c in kleb.columns if 'K_locus' in c or c == 'K_type'), None)\n"
             "print('K column:', kcol)\n"
             "if kcol:\n"
             "    print(kleb[kcol].value_counts().head(15))\n"),

        md("## Cell 5 - Save and download"),
        code(f"kleb.to_csv('/content/{RESULT}.csv', index=False)\n"
             f"kleb.to_csv(PERSIST / '{RESULT}.csv', index=False)\n"
             f"print('wrote {RESULT}.csv', kleb.shape)\n"
             "\n"
             "from google.colab import files\n"
             f"files.download('/content/{RESULT}.csv')\n"),
    ]

    return {
        "nbformat": 4, "nbformat_minor": 0,
        "metadata": {"colab": {"provenance": []},
                     "kernelspec": {"name": "python3",
                                    "display_name": "Python 3"},
                     "language_info": {"name": "python"}},
        "cells": cells,
    }


def main() -> int:
    nb = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(nb, indent=1), encoding="utf-8")
    print(f"Wrote {OUT} ({OUT.stat().st_size/1024:.1f} KB, {len(nb['cells'])} cells)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
