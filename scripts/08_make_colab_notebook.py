"""
Step 8 - Generate a self-contained Colab notebook.

The interactive `files.upload()` step in the hand-run notebook opens a native
file dialog, which is fragile when the notebook is driven through browser
automation. This script emits an equivalent notebook with the accession list
embedded directly, so the notebook can run start-to-finish without any local
file interaction.

Usage:
    python scripts/08_make_colab_notebook.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from config import NOTEBOOKS, PROCESSED

# Named cohorts this generator can build a notebook for.
COHORTS = {
    "core": {
        "accessions": PROCESSED / "kp_core_accessions.txt",
        "notebook": NOTEBOOKS / "06b_kleborate_colab_selfcontained.ipynb",
        "drive_subdir": "phagematch-pk",
        "result": "kleborate_pakistan_kp",
        "title": "Pakistani clinical K. pneumoniae",
    },
    "comparison": {
        "accessions": PROCESSED / "kp_comparison_accessions.txt",
        "notebook": NOTEBOOKS / "10_kleborate_comparison.ipynb",
        "drive_subdir": "phagematch-pk-comparison",
        "result": "kleborate_comparison_kp",
        "title": "International comparison K. pneumoniae",
    },
}


def md(text: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": text.splitlines(keepends=True)}


def code(text: str) -> dict:
    return {"cell_type": "code", "execution_count": None, "metadata": {},
            "outputs": [], "source": text.splitlines(keepends=True)}


def build(accessions: list[str], cfg: dict) -> dict:
    acc_literal = json.dumps(accessions, indent=0).replace("\n", "")
    drive_dir = cfg["drive_subdir"]
    result = cfg["result"]

    cells = [
        md("# PhageMatch-PK - Kleborate typing (self-contained)\n"
           "\n"
           f"Types {len(accessions)} clinical *K. pneumoniae* genomes - {cfg['title']}:\n"
           "ST, **K-locus (capsule)**, O-locus, AMR, virulence.\n"
           "\n"
           "Accessions are embedded below - no uploads needed. Run cells in order.\n"
           "**Cell 3 restarts the runtime on purpose**; resume at Cell 4 afterwards.\n"),

        md("## Cell 1 - System tools"),
        code(
            "%%bash\n"
            "# No `set -e`: keep diagnostics visible even if one probe fails.\n"
            "# mash is REQUIRED - Kleborate's species check shells out to the mash\n"
            "# binary and aborts with 'could not find mash'. The pip package named\n"
            "# 'mash' is a different project and does NOT provide the executable.\n"
            "apt-get -qq update > /dev/null 2>&1\n"
            "apt-get -qq install -y minimap2 ncbi-blast+ mash > /dev/null 2>&1\n"
            "curl -sSL -o /usr/local/bin/datasets \\\n"
            "  https://ftp.ncbi.nlm.nih.gov/pub/datasets/command-line/v2/linux-amd64/datasets\n"
            "chmod +x /usr/local/bin/datasets\n"
            "echo '--- versions ---'\n"
            "minimap2 --version || echo 'minimap2 MISSING'\n"
            "datasets --version || echo 'datasets MISSING'\n"
            "mash --version || echo 'mash MISSING'\n"
        ),

        md("## Cell 2 - Install Kleborate + Kaptive\n"
           "\n"
           "**Kaptive is pinned to 3.2.2 on purpose.** Kleborate 3.2.4 declares an unpinned\n"
           "`kaptive` dependency, but Kaptive 3.3.0 restructured its package and removed\n"
           "`kaptive.database`, which Kleborate's capsule module imports. Installing latest\n"
           "Kaptive gives `ModuleNotFoundError: No module named 'kaptive.database'`.\n"
           "3.2.2 is the newest release that still provides it.\n"),
        code(
            "import subprocess, sys\n"
            "\n"
            "KAPTIVE_PIN = 'kaptive==3.2.2'   # see note above - do not unpin\n"
            "\n"
            "def npver():\n"
            "    r = subprocess.run([sys.executable, '-c', 'import numpy; print(numpy.__version__)'],\n"
            "                       capture_output=True, text=True)\n"
            "    return r.stdout.strip() or '(none)'\n"
            "\n"
            "before = npver()\n"
            "print('numpy before:', before)\n"
            "r = subprocess.run([sys.executable, '-m', 'pip', 'install', 'kleborate', KAPTIVE_PIN],\n"
            "                   capture_output=True, text=True)\n"
            "print(r.stdout[-3000:])\n"
            "if r.returncode != 0:\n"
            "    print('PIP FAILED:', r.stderr[-3000:])\n"
            "print('numpy after :', npver())\n"
        ),

        md("## Cell 3 - Restart runtime (expected; resume at Cell 4)"),
        code(
            "import os\n"
            "print('Restarting - this is expected. Continue at Cell 4.')\n"
            "os.kill(os.getpid(), 9)\n"
        ),

        md("## Cell 4 - Verify install, detect CLI"),
        code(
            "import subprocess\n"
            "\n"
            "for mod in ['numpy', 'numba', 'kaptive', 'kleborate']:\n"
            "    try:\n"
            "        m = __import__(mod)\n"
            "        print(f'{mod:<10}', getattr(m, '__version__', 'ok'))\n"
            "    except Exception as e:\n"
            "        print(f'{mod:<10} FAILED: {type(e).__name__}: {e}')\n"
            "\n"
            "h = subprocess.run(['kleborate', '--help'], capture_output=True, text=True)\n"
            "help_text = h.stdout + h.stderr\n"
            "print(help_text[:4000])\n"
            "\n"
            "for flag in ['--list-presets', '--list-modules']:\n"
            "    r = subprocess.run(['kleborate', flag], capture_output=True, text=True)\n"
            "    out = (r.stdout + r.stderr).strip()\n"
            "    if r.returncode == 0 and out:\n"
            "        print(f'\\n=== {flag} ===\\n' + out[:2500])\n"
        ),

        md("## Cell 4b - Mount Google Drive (crash protection)\n"
           "\n"
           "Colab free runtimes get reclaimed without warning, and anything in `/content`\n"
           "dies with them. Typing takes ~50 min, so we keep the **results and per-chunk\n"
           "progress markers on Drive** - a few MB. The 1.5 GB of genome FASTAs stay in\n"
           "local scratch because re-downloading them costs only ~45 s.\n"
           "\n"
           "Net effect: if the session dies, rerun Cells 1-7 and the typing resumes from\n"
           "the last finished chunk instead of starting over.\n"
           "\n"
           "**This cell asks for Google Drive access - approve it in the popup.**\n"),
        code(
            "from pathlib import Path\n"
            "from google.colab import drive\n"
            "\n"
            "drive.mount('/content/drive')\n"
            "\n"
            f"PERSIST = Path('/content/drive/MyDrive/{drive_dir}')\n"
            "PERSIST.mkdir(parents=True, exist_ok=True)\n"
            "print('persisting results to:', PERSIST)\n"
            "\n"
            "existing = sorted(PERSIST.rglob('chunk_*.done'))\n"
            "print(f'chunks already finished from a previous session: {len(existing)}')\n"
        ),

        md(f"## Cell 5 - Download {len(accessions)} genomes from NCBI"),
        code(
            "import shutil, subprocess, zipfile\n"
            "from pathlib import Path\n"
            "\n"
            f"accessions = {acc_literal}\n"
            "print(len(accessions), 'accessions')\n"
            "\n"
            "WORK = Path('/content/work'); ASM = WORK / 'assemblies'\n"
            "ASM.mkdir(parents=True, exist_ok=True)\n"
            "BATCH = 25\n"
            "batches = [accessions[i:i+BATCH] for i in range(0, len(accessions), BATCH)]\n"
            "\n"
            "for n, batch in enumerate(batches, 1):\n"
            "    marker = WORK / f'.b{n}.done'\n"
            "    if marker.exists():\n"
            "        print(f'batch {n}/{len(batches)} cached'); continue\n"
            "    lf = WORK / f'b{n}.txt'; lf.write_text('\\n'.join(batch) + '\\n')\n"
            "    zp = WORK / f'b{n}.zip'\n"
            "    res = subprocess.run(['datasets','download','genome','accession',\n"
            "                          '--inputfile',str(lf),'--include','genome',\n"
            "                          '--filename',str(zp),'--no-progressbar'],\n"
            "                         capture_output=True, text=True)\n"
            "    if res.returncode != 0 or not zp.exists():\n"
            "        print(f'batch {n} FAILED:', res.stderr.strip()[:250]); continue\n"
            "    with zipfile.ZipFile(zp) as zf:\n"
            "        for m in zf.namelist():\n"
            "            if not m.endswith(('.fna','.fa','.fasta')):\n"
            "                continue\n"
            "            parts = m.split('/')\n"
            "            acc = parts[2] if len(parts) >= 3 else Path(m).stem\n"
            "            with zf.open(m) as s, (ASM / f'{acc}.fna').open('wb') as d:\n"
            "                shutil.copyfileobj(s, d)\n"
            "    zp.unlink(); marker.touch()\n"
            "    print(f'batch {n}/{len(batches)} ok ({len(list(ASM.glob(\"*.fna\")))} genomes)')\n"
            "\n"
            "fastas = sorted(ASM.glob('*.fna'))\n"
            "print(f'\\nDownloaded {len(fastas)}/{len(accessions)} '\n"
            "      f'({sum(f.stat().st_size for f in fastas)/1e6:.0f} MB)')\n"
        ),

        md("## Cell 6 - Smoke test (finds the working CLI form)"),
        code(
            "import subprocess\n"
            "from pathlib import Path\n"
            "\n"
            "TEST = WORK / 'smoke'; TEST.mkdir(exist_ok=True)\n"
            "one = sorted(ASM.glob('*.fna'))[0]\n"
            "print('test genome:', one.name)\n"
            "\n"
            "variants = [\n"
            "    ('v3 preset kpsc', ['kleborate','-a',str(one),'-o',str(TEST/'t1'),'-p','kpsc']),\n"
            "    ('v3 preset kp',   ['kleborate','-a',str(one),'-o',str(TEST/'t2'),'-p','kp']),\n"
            "    ('v3 module kpsc', ['kleborate','-a',str(one),'-o',str(TEST/'t3'),\n"
            "                        '-m','klebsiella_pneumo_complex']),\n"
            "    ('v2 --all',       ['kleborate','-a',str(one),'--all','-o',str(TEST/'t4.txt')]),\n"
            "]\n"
            "\n"
            "WORKING_CMD = None\n"
            "for label, cmd in variants:\n"
            "    print('--- trying:', label)\n"
            "    r = subprocess.run(cmd, capture_output=True, text=True)\n"
            "    if r.returncode == 0:\n"
            "        print('    OK'); WORKING_CMD = label; break\n"
            "    print('    rc=', r.returncode)\n"
            "    print('    stderr:', (r.stderr or '').strip()[-700:] or '(none)')\n"
            "\n"
            "if WORKING_CMD is None:\n"
            "    raise SystemExit('All variants failed - send the output above.')\n"
            "print('\\n>>> using:', WORKING_CMD)\n"
            "\n"
            "import pandas as pd\n"
            "for p in sorted(TEST.rglob('*')):\n"
            "    if p.is_file() and p.suffix in {'.txt','.tsv'} and p.stat().st_size > 0:\n"
            "        df = pd.read_csv(p, sep='\\t', dtype=str)\n"
            "        print(p.name, df.shape); print('columns:', list(df.columns)); break\n"
        ),

        md("## Cell 7 - Full run"),
        code(
            "import subprocess, time\n"
            "from pathlib import Path\n"
            "\n"
            "# Results live on Drive so a reclaimed runtime does not cost the whole run.\n"
            "OUT = PERSIST / 'kleborate'; OUT.mkdir(parents=True, exist_ok=True)\n"
            "CHUNK = 20\n"
            "\n"
            "def build_cmd(chunk, tag):\n"
            "    f = list(map(str, chunk))\n"
            "    if WORKING_CMD == 'v3 preset kpsc':\n"
            "        return ['kleborate','-a',*f,'-o',str(tag),'-p','kpsc']\n"
            "    if WORKING_CMD == 'v3 preset kp':\n"
            "        return ['kleborate','-a',*f,'-o',str(tag),'-p','kp']\n"
            "    if WORKING_CMD == 'v3 module kpsc':\n"
            "        return ['kleborate','-a',*f,'-o',str(tag),'-m','klebsiella_pneumo_complex']\n"
            "    return ['kleborate','-a',*f,'--all','-o',str(tag)+'.txt']\n"
            "\n"
            "# Process in the order of the (shuffled) accession list rather than\n"
            "# sorted filename order. Accession numbers cluster by submitting centre\n"
            "# and region, so a sorted run that stops early leaves a geographically\n"
            "# skewed subset. In list order, any prefix is still a balanced random\n"
            "# sample across groups - which matters because long runs get interrupted.\n"
            "fastas = [ASM / f'{a}.fna' for a in accessions if (ASM / f'{a}.fna').exists()]\n"
            "chunks = [fastas[i:i+CHUNK] for i in range(0, len(fastas), CHUNK)]\n"
            "print(len(fastas), 'genomes in', len(chunks), 'chunks')\n"
            "\n"
            "failed = []; t0 = time.time()\n"
            "for n, chunk in enumerate(chunks, 1):\n"
            "    tag = OUT / f'chunk_{n:03d}'; done = OUT / f'chunk_{n:03d}.done'\n"
            "    if done.exists():\n"
            "        print(f'chunk {n}/{len(chunks)} cached'); continue\n"
            "    r = subprocess.run(build_cmd(chunk, tag), capture_output=True, text=True)\n"
            "    if r.returncode != 0:\n"
            "        failed.append(n)\n"
            "        print(f'chunk {n} FAILED:', (r.stderr or '').strip()[-500:]); continue\n"
            "    done.touch(); el = time.time() - t0\n"
            "    print(f'chunk {n}/{len(chunks)} ok [{el/60:.1f} min, '\n"
            "          f'~{(el/n)*(len(chunks)-n)/60:.1f} min left]')\n"
            "\n"
            "print(f'\\nTotal {(time.time()-t0)/60:.1f} min; failed: {failed}')\n"
        ),

        md("## Cell 8 - Collect, summarise, save"),
        code(
            "import pandas as pd\n"
            "\n"
            "# Kleborate v3 writes TWO tables per run:\n"
            "#   klebsiella_pneumo_complex_output.txt               <- main, 1 row/genome\n"
            "#   klebsiella_pneumo_complex_hAMRonization_output.txt <- AMR long format\n"
            "# Concatenating both would interleave two different schemas, so take the\n"
            "# main table only. The AMR table is collected separately below.\n"
            "MAIN = 'klebsiella_pneumo_complex_output.txt'\n"
            "AMRH = 'hAMRonization'\n"
            "\n"
            "frames, amr_frames = [], []\n"
            "for p in sorted(OUT.rglob('*.txt')):\n"
            "    if not p.is_file() or p.stat().st_size == 0:\n"
            "        continue\n"
            "    try:\n"
            "        df = pd.read_csv(p, sep='\\t', dtype=str)\n"
            "    except Exception as e:\n"
            "        print('skip', p.name, e); continue\n"
            "    if p.name == MAIN:\n"
            "        frames.append(df)\n"
            "    elif AMRH in p.name:\n"
            "        amr_frames.append(df)\n"
            "\n"
            "if not frames:\n"
            "    raise SystemExit(f'No {MAIN} found - check the Cell 7 output.')\n"
            "\n"
            "kleb = pd.concat(frames, ignore_index=True).drop_duplicates()\n"
            "print('main table :', kleb.shape)\n"
            "print('columns:', list(kleb.columns))\n"
            "\n"
            "if amr_frames:\n"
            "    amr = pd.concat(amr_frames, ignore_index=True).drop_duplicates()\n"
            f"    amr.to_csv('/content/{result}_amr.csv', index=False)\n"
            f"    amr.to_csv(PERSIST / '{result}_amr.csv', index=False)\n"
            f"    print('AMR table  :', amr.shape, '-> {result}_amr.csv')\n"
            "\n"
            "def pick(df, *cands):\n"
            "    low = {c.lower().replace(' ','_'): c for c in df.columns}\n"
            "    for c in cands:\n"
            "        if c in df.columns: return c\n"
            "        k = c.lower().replace(' ','_')\n"
            "        if k in low: return low[k]\n"
            "    return None\n"
            "\n"
            "col_strain = pick(kleb,'strain','Genome Name','Name','assembly')\n"
            "col_k      = pick(kleb,'K_locus','K locus','Best match locus','K_type')\n"
            "col_kconf  = pick(kleb,'K_locus_confidence','K locus confidence','Match confidence')\n"
            "col_o      = pick(kleb,'O_locus','O locus','O_type')\n"
            "col_st     = pick(kleb,'ST','MLST ST','st')\n"
            "print('resolved:', col_strain, col_k, col_kconf, col_o, col_st)\n"
            "\n"
            "if col_k:\n"
            "    kd = kleb[col_k].fillna('unknown').value_counts()\n"
            "    print(f'\\n=== K-locus distribution ({kd.size} types) ===')\n"
            "    print(kd.head(30).to_string())\n"
            "    print(f'\\nTop 10 cover {kd.head(10).sum()/kd.sum()*100:.1f}%')\n"
            "for lab, c in [('K confidence',col_kconf),('O-locus',col_o),('ST',col_st)]:\n"
            "    if c:\n"
            "        print(f'\\n=== {lab} ===')\n"
            "        print(kleb[c].fillna('unknown').value_counts().head(15).to_string())\n"
            "\n"
            "if col_strain:\n"
            "    kleb['assembly'] = (kleb[col_strain].astype(str)\n"
            "                        .str.replace(r'\\.(fna|fa|fasta)$','',regex=True).str.strip())\n"
            "\n"
            "# Write to Drive as well as local scratch, so the result survives even if\n"
            "# the browser download in the next cell is missed.\n"
            f"kleb.to_csv('/content/{result}.csv', index=False)\n"
            f"kleb.to_csv(PERSIST / '{result}.csv', index=False)\n"
            f"print('\\nwrote {result}.csv', kleb.shape)\n"
            "print('  -> /content/ and', PERSIST)\n"
        ),

        md("## Cell 9 - Download the result"),
        code(
            "from google.colab import files\n"
            f"files.download('/content/{result}.csv')\n"
        ),
    ]

    return {
        "cells": cells,
        "metadata": {
            "colab": {"provenance": [], "toc_visible": True},
            "kernelspec": {"display_name": "Python 3", "name": "python3"},
            "language_info": {"name": "python"},
        },
        "nbformat": 4,
        "nbformat_minor": 0,
    }


def main() -> int:
    import argparse
    import random

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cohort", default="core", choices=sorted(COHORTS))
    args = ap.parse_args()

    cfg = COHORTS[args.cohort]
    acc_path, OUT = cfg["accessions"], cfg["notebook"]

    if not acc_path.exists():
        print(f"Missing {acc_path}.")
        return 1

    accessions = [ln.strip() for ln in acc_path.read_text().splitlines() if ln.strip()]

    # Shuffle so that an interrupted run still leaves a balanced random sample
    # across comparison groups. Fixed seed keeps it reproducible.
    random.Random(20260815).shuffle(accessions)

    nb = build(accessions, cfg)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(nb, indent=1), encoding="utf-8")

    size_kb = OUT.stat().st_size / 1024
    print(f"Cohort '{args.cohort}': embedded {len(accessions)} accessions")
    print(f"Wrote {OUT} ({size_kb:.1f} KB, {len(nb['cells'])} cells)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
