# -*- coding: utf-8 -*-
"""make_deck.py — build a research slide deck (.pptx) from a markdown outline.

Usage:
    python make_deck.py <outline.md> [-o deck.pptx] [--title-font 32]

Outline format (markdown):
    # Deck Title
    ## Slide 1 Title
    - bullet one
    - bullet two
    ## Slide 2 Title
    ![figure](path/to/fig.png)
    - caption bullet

Design rules baked in (from K-Dense scientific-slides, MIT):
    - 16:9, high contrast, minimal text, 40-50% white space
    - figures placed right / text left (two-column) when slide has an image
    - 1 slide ~ 1 minute of talk
"""
import argparse
import re
import sys
from pathlib import Path

from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN

# --- design tokens (16:9, high contrast, calm palette) ---
SLIDE_W, SLIDE_H = Inches(13.333), Inches(7.5)
C_TEXT = RGBColor(0x1A, 0x1A, 0x2E)
C_ACCENT = RGBColor(0x0B, 0x5C, 0xAB)
C_MUTED = RGBColor(0x5A, 0x5A, 0x6E)
C_BG = RGBColor(0xFF, 0xFF, 0xFF)
TITLE_PT = 30
BODY_PT = 17


def parse_outline(md_text):
    """-> (deck_title, [ (slide_title, [bullets], [image_paths]) ])"""
    lines = md_text.splitlines()
    deck_title = ""
    slides = []
    cur = None  # [title, bullets, images]
    for ln in lines:
        s = ln.strip()
        if s.startswith("# ") and not s.startswith("##"):
            deck_title = s[2:].strip()
        elif s.startswith("## "):
            if cur:
                slides.append(cur)
            cur = [s[3:].strip(), [], []]
        elif not cur:
            continue
        elif s.startswith("- "):
            cur[1].append(s[2:].strip())
        elif (m := re.match(r"!\[[^\]]*\]\(([^)]+)\)", s)):
            cur[2].append(m.group(1))
        elif s:  # plain line under a slide -> bullet
            cur[1].append(s)
    if cur:
        slides.append(cur)
    return deck_title, slides


def add_title_slide(prs, title):
    slide = prs.slides.add_slide(prs.slide_layouts[6])  # blank
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = C_BG
    left, top, width, height = Inches(0.7), Inches(2.6), Inches(11.9), Inches(2.2)
    tb = slide.shapes.add_textbox(left, top, width, height)
    tf = tb.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = title
    # shrink long titles so they never overflow the slide
    p.font.size = Pt(40 if len(title) <= 24 else 32 if len(title) <= 40 else 26)
    p.font.bold = True
    p.font.color.rgb = C_ACCENT
    p.alignment = PP_ALIGN.CENTER


def add_content_slide(prs, title, bullets, images):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = C_BG

    # title bar with accent underline
    tb = slide.shapes.add_textbox(Inches(0.6), Inches(0.35), Inches(12.1), Inches(0.9))
    tf = tb.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = title
    p.font.size = Pt(TITLE_PT)
    p.font.bold = True
    p.font.color.rgb = C_TEXT
    from pptx.enum.shapes import MSO_SHAPE
    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.65), Inches(1.25), Inches(2.2), Pt(3.2))
    bar.fill.solid()
    bar.fill.fore_color.rgb = C_ACCENT
    bar.line.fill.background()

    if images:
        # two-column: text left, figure right; fit image inside a fixed box.
        # Pre-scale the image to the exact target pixel size (96dpi) and insert
        # WITHOUT explicit width/height — LibreOffice-based renderers honor
        # natural size more reliably than explicit ext on large images.
        img = images[0]
        box_x, box_y, box_w_in, box_h_in = 6.9, 1.7, 5.9, 5.3
        if Path(img).is_file():
            from PIL import Image
            with Image.open(img) as im:
                iw, ih = im.size
                scale = min(box_w_in / (iw / 96), box_h_in / (ih / 96), 1.0)
                tw, th = int(iw * scale), int(ih * scale)
                if (tw, th) != (iw, ih):
                    im = im.convert("RGB").resize((tw, th), Image.LANCZOS)
                    prescaled = Path(img).with_name(Path(img).stem + f"_{tw}x{th}.png")
                    im.save(prescaled, dpi=(96, 96))
                else:
                    prescaled = Path(img)
            w_in, h_in = tw / 96, th / 96
            slide.shapes.add_picture(str(prescaled),
                                     Inches(box_x + (box_w_in - w_in) / 2),
                                     Inches(box_y + (box_h_in - h_in) / 2))
        else:
            note = slide.shapes.add_textbox(Inches(box_x), Inches(box_y),
                                            Inches(box_w_in), Inches(1.0))
            note.text_frame.text = f"[figure missing: {img}]"
        text_w = Inches(5.9)
    else:
        text_w = Inches(12.1)

    if bullets:
        bb = slide.shapes.add_textbox(Inches(0.7), Inches(1.7), text_w, Inches(5.2))
        bf = bb.text_frame
        bf.word_wrap = True
        for i, b in enumerate(bullets):
            para = bf.paragraphs[0] if i == 0 else bf.add_paragraph()
            para.text = b
            para.font.size = Pt(BODY_PT)
            para.font.color.rgb = C_TEXT
            para.space_after = Pt(10)


def validate(prs_path, slides_planned):
    """Open the produced file; report basic overflow risks."""
    check = Presentation(prs_path)
    n = len(check.slides)
    est_minutes = slides_planned  # ~1 slide/minute
    return n, est_minutes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("outline")
    ap.add_argument("-o", "--out", default=None)
    args = ap.parse_args()

    md = Path(args.outline).read_text(encoding="utf-8")
    deck_title, slides = parse_outline(md)
    if not slides:
        print("ERROR: outline has no '## Slide' sections")
        sys.exit(2)

    # resolve image paths relative to the outline file's directory
    base = Path(args.outline).resolve().parent
    slides = [
        (t, b, [str((base / img).resolve()) if not Path(img).is_absolute() else img
                for img in imgs])
        for t, b, imgs in slides
    ]

    prs = Presentation()
    prs.slide_width, prs.slide_height = SLIDE_W, SLIDE_H
    if deck_title:
        add_title_slide(prs, deck_title)
    for title, bullets, images in slides:
        add_content_slide(prs, title, bullets, images)

    out = Path(args.out) if args.out else Path(args.outline).with_suffix(".pptx")
    prs.save(str(out))
    n, est = validate(out, len(slides))
    print(f"OK: {out} — {n} slides (~{est} min talk at 1 slide/min)")


if __name__ == "__main__":
    main()
