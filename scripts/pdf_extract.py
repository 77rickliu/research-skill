# -*- coding: utf-8 -*-
"""pdf_extract.py — PDF -> structured text for research reading notes.

Usage:
    python pdf_extract.py <input.pdf> [--out <output.md>] [--max-pages N]

Output: markdown with per-page text; two-column layouts are re-ordered by
x-coordinate clustering (left column first). Falls back to raw per-line
extraction when column detection is unreliable. Scanned (no text layer)
PDFs are detected and reported.
"""
import argparse
import sys
from pathlib import Path

try:
    import pymupdf  # PyMuPDF >= 1.26; `import fitz` deprecated
except ImportError:
    try:
        import fitz as pymupdf  # type: ignore
    except ImportError:
        print("ERROR: PyMuPDF not installed. Run: pip install pymupdf", file=sys.stderr)
        sys.exit(2)


def extract_blocks(page):
    """Return words sorted into one or two column order for a page."""
    words = page.get_text("words")  # (x0, y0, x1, y1, word, block, line, wordno)
    if not words:
        return None  # no text layer (likely scanned)
    # Detect 2-column layout: histogram of word centers near page midline
    mid = page.rect.width / 2
    left = [w for w in words if (w[0] + w[2]) / 2 < mid]
    right = [w for w in words if (w[0] + w[2]) / 2 >= mid]
    # two columns if both halves have words AND a clear gutter
    # (few words crossing the midline).
    crossing = [
        w for w in words
        if w[0] < mid - 10 and w[2] > mid + 10
    ]
    # Count text lines on each side (a word row counts once per side).
    def n_lines(ws):
        ys = sorted((w[1] + w[3]) / 2 for w in ws)
        n, prev = 0, None
        for y in ys:
            if prev is None or y - prev > 3.0:
                n += 1
            prev = y
        return n
    use_cols = (
        n_lines(left) >= 3 and n_lines(right) >= 3
        and len(crossing) < 0.15 * len(words)
    )
    groups = (left, right) if use_cols else (words,)
    lines_out = []
    for g in groups:
        # group words into lines by y center with tolerance
        g = sorted(g, key=lambda w: (w[1], w[0]))
        cur, cur_y = [], None
        for w in g:
            yc = (w[1] + w[3]) / 2
            if cur_y is None or abs(yc - cur_y) <= 3.0:
                cur.append(w)
                cur_y = yc if cur_y is None else (cur_y + yc) / 2
            else:
                lines_out.append(" ".join(t[4] for t in sorted(cur, key=lambda t: t[0])))
                cur, cur_y = [w], yc
        if cur:
            lines_out.append(" ".join(t[4] for t in sorted(cur, key=lambda t: t[0])))
        if use_cols:
            lines_out.append("\n--- column break ---\n")
    return lines_out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("--out", default=None)
    ap.add_argument("--max-pages", type=int, default=0, help="0 = all pages")
    args = ap.parse_args()

    src = Path(args.pdf)
    if not src.is_file():
        print(f"ERROR: file not found: {src}", file=sys.stderr)
        sys.exit(1)

    doc = pymupdf.open(str(src))
    n_pages = len(doc) if args.max_pages <= 0 else min(len(doc), args.max_pages)

    parts = [f"# Extracted text: {src.name}\n", f"Pages: {n_pages}/{len(doc)}\n"]
    scanned_pages = []
    for i in range(n_pages):
        parts.append(f"\n## Page {i + 1}\n")
        lines = extract_blocks(doc[i])
        if lines is None:
            scanned_pages.append(i + 1)
            parts.append("_[no text layer — likely scanned image]_\n")
            continue
        parts.extend(l + "\n" for l in lines)
    doc.close()

    text = "\n".join(parts)
    out = Path(args.out) if args.out else src.with_suffix(".extracted.md")
    out.write_text(text, encoding="utf-8")
    print(f"OK: wrote {out} ({n_pages} pages)")
    if scanned_pages:
        print(f"WARN: scanned pages without text layer: {scanned_pages}")
        print("Suggest: use a text-based PDF or OCR before reading notes.")


if __name__ == "__main__":
    main()
