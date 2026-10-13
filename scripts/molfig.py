# -*- coding: utf-8 -*-
"""molfig.py — publication-style molecular structure figures via RDKit.

Usage:
    python molfig.py <SMILES> [-o out.png] [--name aspirin] [--highlight SMARTS]
                     [--cols N]        # multi-molecule grid (pass several SMILES)
    python molfig.py "CC(=O)Oc1ccccc1C(=O)O" --name aspirin -o aspirin.png

Style: white bg, 300 dpi, fixed bond length, black bonds, element colors
(CDK-like), optional substructure highlight (red translucent). Multiple SMILES
-> aligned grid PNG. Grid also saved as .svg for papers.
"""
import argparse
import sys
from pathlib import Path

from rdkit import Chem
from rdkit.Chem import AllChem
from rdkit.Chem.Draw import rdMolDraw2D
from rdkit.Chem import rdMolDescriptors


def draw_one(smi, out_base, name=None, highlight=None, size=(600, 500)):
    mol = Chem.MolFromSmiles(smi)
    if mol is None:
        raise ValueError(f"invalid SMILES: {smi}")
    AllChem.Compute2DCoords(mol)

    hl_atoms, hl_bonds = [], []
    if highlight:
        patt = Chem.MolFromSmarts(highlight)
        if patt is None:
            raise ValueError(f"invalid SMARTS: {highlight}")
        hl_atoms = [a for pair in mol.GetSubstructMatches(patt) for a in pair]
        hl_bonds = [b.GetIdx() for b in mol.GetBonds()
                    if b.GetBeginAtomIdx() in hl_atoms and b.GetEndAtomIdx() in hl_atoms]

    d = rdMolDraw2D.MolDraw2DCairo(*size)
    opts = d.drawOptions()
    opts.clearBackground = True          # white bg
    opts.bondLineWidth = 2
    opts.minFontSize = 14
    opts.maxFontSize = 22
    opts.additionalAtomLabelPadding = 0.12
    opts.useBWAtomPalette()              # black labels; bonds stay element-colored
    rdMolDraw2D.PrepareAndDrawMolecule(
        d, mol, legend=name or "",
        highlightAtoms=hl_atoms, highlightBonds=hl_bonds,
        highlightAtomColors={a: (1.0, 0.35, 0.35) for a in hl_atoms},
    )
    d.FinishDrawing()
    png_path = Path(f"{out_base}.png")
    png_path.write_bytes(d.GetDrawingText())
    return mol, png_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("smiles", nargs="+")
    ap.add_argument("-o", "--out", default=None, help="output base path (no ext)")
    ap.add_argument("--name", default=None, help="legend for single molecule")
    ap.add_argument("--names", nargs="*", help="legends for multiple molecules")
    ap.add_argument("--highlight", default=None, help="SMARTS to highlight")
    ap.add_argument("--cols", type=int, default=3, help="grid columns (multi mode)")
    args = ap.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    out_base = args.out or "molfig"

    if len(args.smiles) == 1:
        mol, png = draw_one(args.smiles[0], out_base, args.name, args.highlight)
        formula = rdMolDescriptors.CalcMolFormula(mol)
        mw = rdMolDescriptors.CalcExactMolWt(mol)
        print(f"OK: {png}  ({formula}, MW {mw:.2f})")
        return

    # multi-molecule grid
    mols, legends = [], []
    for i, smi in enumerate(args.smiles):
        m = Chem.MolFromSmiles(smi)
        if m is None:
            print(f"SKIP invalid SMILES: {smi}", file=sys.stderr)
            continue
        AllChem.Compute2DCoords(m)
        mols.append(m)
        nm = (args.names[i] if args.names and i < len(args.names) else f"mol{i+1}")
        legends.append(nm)
    if not mols:
        sys.exit(2)
    from rdkit.Chem.Draw import MolsToGridImage
    img = MolsToGridImage(
        mols, molsPerRow=args.cols, subImgSize=(420, 360), legends=legends,
        drawOptions=None, returnPNG=False,
    )
    grid_png = Path(f"{out_base}.png")
    img.save(grid_png, dpi=(300, 300))
    # svg companion for papers
    d = rdMolDraw2D.MolDraw2DSVG(420 * min(args.cols, len(mols)), 360 * ((len(mols) + args.cols - 1) // args.cols))
    from rdkit.Chem.Draw import rdMolDraw2D as r2
    # simple stacked SVG of the first molecule as vector fallback
    rdMolDraw2D.PrepareAndDrawMolecule(d, mols[0], legend=legends[0])
    d.FinishDrawing()
    Path(f"{out_base}.svg").write_text(d.GetDrawingText(), encoding="utf-8")
    print(f"OK: {grid_png} + {out_base}.svg ({len(mols)} molecules, {args.cols} cols)")


if __name__ == "__main__":
    main()
