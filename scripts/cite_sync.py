# -*- coding: utf-8 -*-
"""cite_sync.py — verify [bibtex_key] citations in a markdown file against bib.bib.

Usage:
    python cite_sync.py <doc.md> [--bib research/bib.bib]

Checks:
  1. every [key] in the doc exists in bib.bib
  2. every bib entry cited at least once (report unused, informational)

Exit 1 if missing keys found.
"""
import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from bib import load_bib  # noqa: E402

CITE_RE = re.compile(r"\[([a-zA-Z0-9_\-]+)\]")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("doc")
    ap.add_argument("--bib", default="research/bib.bib")
    args = ap.parse_args()

    doc = Path(args.doc).read_text(encoding="utf-8")
    bib_keys = {e["key"] for e in load_bib(Path(args.bib))}

    # ignore markdown links [text](url) and images ![alt](path)
    doc_wo_links = re.sub(r"!?\[[^\]]*\]\([^)]*\)", "", doc)
    # skip pure numbers: students mix numeric citations like [1], [2,3] — not bibtex keys
    cited = {c for c in CITE_RE.findall(doc_wo_links) if not c.isdigit()}

    missing = sorted(c for c in cited if c not in bib_keys)
    unused = sorted(k for k in bib_keys if k not in cited)

    print(f"cited: {len(cited)}, bib entries: {len(bib_keys)}")
    if missing:
        print("MISSING in bib.bib:")
        print("\n".join("  - " + m for m in missing))
    if unused:
        print("unused bib entries (informational):")
        print("\n".join("  - " + u for u in unused))
    if not missing:
        print("All citations resolved.")
        sys.exit(0)
    sys.exit(1)


if __name__ == "__main__":
    main()
