# -*- coding: utf-8 -*-
"""figstyle.py — unified matplotlib style for research figures.

Usage (inside your run.py):
    import figstyle
    figstyle.apply()
    ... plot ...
    figstyle.save("fig1")          # -> fig1.png (300 dpi)

Style: 300 dpi, tab10 colors, no top/right spines, English labels by default,
consistent font sizes for paper/report embedding.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

TAB10 = plt.cm.tab10.colors


def apply():
    plt.rcParams.update({
        "figure.dpi": 100,
        "savefig.dpi": 300,
        "font.size": 11,
        "axes.titlesize": 12,
        "axes.labelsize": 11,
        "legend.fontsize": 10,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": False,
        "axes.prop_cycle": plt.cycler(color=TAB10),
        "lines.linewidth": 1.8,
        "figure.constrained_layout.use": True,
    })


def save(name, formats=("png",)):
    """Save current figure to <name>.png (and extra formats), 300 dpi."""
    out = []
    for ext in formats:
        path = f"{name}.{ext}"
        plt.savefig(path, dpi=300, bbox_inches="tight")
        out.append(path)
    print("saved:", ", ".join(out))
    return out
