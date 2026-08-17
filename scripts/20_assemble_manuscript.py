"""
Step 20 - Assemble the final manuscript with a single complete reference list.

The submission manuscript carries references [1]-[7]; the 27 curated
phage-capsule pairings [8]-[34] are generated separately by step 17 because they
are rebuilt whenever the curated table changes. A submitted paper cannot ask an
editor to look in a second file, so this splices them into one numbered list and
writes `manuscript_final.md`, which step 19 then renders to .docx.

Kept as its own step rather than folded into 17 or 19: 17 owns reference
formatting, 19 owns Word rendering, and neither should own document assembly.

Usage:
    python scripts/20_assemble_manuscript.py
"""

from __future__ import annotations

import re
import sys

from config import DOCS

SRC = DOCS / "manuscript_submission.md"
REFS = DOCS / "curated_references.md"
OUT = DOCS / "manuscript_final.md"

# The paragraph in the source that defers to the separate file.
DEFER = re.compile(
    r"References \[1\]–\[7\] are given below.*?at submission\.\s*", re.S)


def curated_entries(text: str) -> list[str]:
    """Numbered reference lines from the curated file, in order.

    Stops at the review sections ('Sentence-case changes', 'Needing an article
    number'), which are working notes and must not reach the manuscript.
    """
    out = []
    for line in text.splitlines():
        if line.startswith("## "):
            if out:            # a heading after the list has started ends it
                break
            continue
        if re.match(r"^\d+\.\s", line):
            out.append(line.rstrip())
    return out


def main() -> int:
    for p in (SRC, REFS):
        if not p.exists():
            print(f"Missing {p}")
            return 1

    md = SRC.read_text(encoding="utf-8")
    entries = curated_entries(REFS.read_text(encoding="utf-8"))
    if not entries:
        print(f"No numbered references found in {REFS}")
        return 1

    numbers = [int(re.match(r"^(\d+)\.", e).group(1)) for e in entries]
    expected = list(range(numbers[0], numbers[0] + len(numbers)))
    if numbers != expected:
        print(f"Reference numbering is not contiguous: {numbers}")
        return 1

    md = DEFER.sub("", md)
    if md.rstrip().endswith(entries[-1]):
        print("Already assembled; nothing to do.")

    md = md.rstrip() + "\n" + "\n".join(entries) + "\n"

    # Every in-text citation must resolve to a listed reference.
    cited: set[int] = set()
    for m in re.finditer(r"\[(\d+(?:\s*[,–-]\s*\d+)*)\]", md):
        for part in re.split(r"[,\s]+", m.group(1)):
            if part.isdigit():
                cited.add(int(part))
            elif re.match(r"^\d+[–-]\d+$", part):
                a, b = re.split(r"[–-]", part)
                cited.update(range(int(a), int(b) + 1))
    listed = set(range(1, numbers[-1] + 1))
    dangling = sorted(cited - listed)
    unused = sorted(listed - cited)

    OUT.write_text(md, encoding="utf-8")
    print(f"Wrote {OUT}")
    print(f"  references [1]-[7] from the manuscript + "
          f"[{numbers[0]}]-[{numbers[-1]}] curated = {numbers[-1]} total")
    if dangling:
        print(f"  WARNING cited but not listed: {dangling}")
    print(f"  listed but not cited in text: {len(unused)} "
          f"({unused[:6]}{'...' if len(unused) > 6 else ''})")
    print("  (curated references are cited via the evidence table, "
          "Table S3, not individually in the running text)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
