# -*- coding: utf-8 -*-
"""bib.py — minimal BibTeX library manager (stdlib only).

Usage:
    python bib.py check                          # report duplicate keys/DOIs
    python bib.py add <file.bib>                 # add entries from file into bib.bib (dedup)
    python bib.py keys                           # list all keys
    python bib.py find <keyword>                 # find entries containing keyword

bib.bib path is resolved as <workspace>/research/bib.bib, or pass --bib.
Dedup rules: same citation key OR same DOI (case-insensitive) => duplicate.
"""
import argparse
import re
import sys
from pathlib import Path

DEFAULT_BIB = Path("research/bib.bib")

ENTRY_RE = re.compile(r"@(\w+)\s*\{\s*([^,\s]+)\s*,", re.I)
FIELD_RE = re.compile(r"(\w+)\s*=\s*[{\"].*?[}\"]", re.S | re.I)


def split_entries(text):
    """Yield raw entry strings (balanced braces).

    ENTRY_RE consumes `@type{key,` including the body-opening brace, so the
    body starts at m.end() with brace depth already 1.
    """
    i = 0
    while i < len(text):
        m = ENTRY_RE.search(text, i)
        if not m:
            break
        start = m.start()
        depth, k = 1, m.end()
        while k < len(text):
            if text[k] == "{":
                depth += 1
            elif text[k] == "}":
                depth -= 1
                if depth == 0:
                    break
            k += 1
        yield text[start:k + 1]
        i = k + 1


def parse_entry(raw):
    etype = ENTRY_RE.match(raw).group(1).lower()
    key = ENTRY_RE.match(raw).group(2)
    # field name = balanced {...} or "..." (dotall so titles spanning lines work)
    fields = {}
    for fm in re.finditer(r"(\w+)\s*=\s*(\{.*?\}|\".*?\")\s*,?\s*\n", raw, re.S):
        val = fm.group(2)[1:-1]  # strip outer brace/quote
        fields[fm.group(1).lower()] = re.sub(r"\s+", " ", val).strip()
    # unbraced bare values (some exporters write `doi = 10.xxxx/y` without braces)
    for fm in re.finditer(r"(\bdoi\b|\beprint\b)\s*=\s*([^\{\}\n\"]+)", raw, re.I):
        fields.setdefault(fm.group(1).lower(), fm.group(2).strip().rstrip(","))
    return {"type": etype, "key": key, "doi": fields.get("doi", "").lower(), "raw": raw.strip()}


def load_bib(path):
    if not path.exists():
        return []
    return [parse_entry(r) for r in split_entries(path.read_text(encoding="utf-8"))]


def cmd_check(path):
    entries = load_bib(path)
    seen_key, seen_doi, dups = {}, {}, []
    for e in entries:
        if e["key"] in seen_key:
            dups.append(f"key duplicate: {e['key']}")
        if e["doi"] and e["doi"] in seen_doi:
            dups.append(f"doi duplicate: {e['key']} == {seen_doi[e['doi']]}")
        seen_key.setdefault(e["key"], e["key"])
        if e["doi"]:
            seen_doi.setdefault(e["doi"], e["key"])
    print(f"{len(entries)} entries in {path}")
    if dups:
        print("DUPLICATES:")
        print("\n".join("  - " + d for d in dups))
        sys.exit(1)
    print("No duplicates.")


def cmd_add(sources, path):
    existing = load_bib(path)
    have_keys = {e["key"] for e in existing}
    have_dois = {e["doi"] for e in existing if e["doi"]}
    added, skipped = 0, 0
    with path.open("a", encoding="utf-8") as f:
        for src in sources:
            for raw in split_entries(Path(src).read_text(encoding="utf-8")):
                e = parse_entry(raw)
                if e["key"] in have_keys or (e["doi"] and e["doi"] in have_dois):
                    skipped += 1
                    continue
                f.write(e["raw"] + "\n\n")
                have_keys.add(e["key"])
                if e["doi"]:
                    have_dois.add(e["doi"])
                added += 1
    print(f"added {added}, skipped {skipped} duplicate(s) -> {path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bib", default=str(DEFAULT_BIB))
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check")
    ap_add = sub.add_parser("add")
    ap_add.add_argument("files", nargs="+")
    sub.add_parser("keys")
    ap_f = sub.add_parser("find")
    ap_f.add_argument("keyword")
    args = ap.parse_args()
    path = Path(args.bib)

    if args.cmd == "check":
        cmd_check(path)
    elif args.cmd == "add":
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch()
        cmd_add(args.files, path)
    elif args.cmd == "keys":
        for e in load_bib(path):
            print(e["key"], f"[{e['type']}]", e.get("doi", ""))
    elif args.cmd == "find":
        kw = args.keyword.lower()
        for e in load_bib(path):
            if kw in e["raw"].lower():
                print(f"--- {e['key']} ---\n{e['raw']}\n")


if __name__ == "__main__":
    main()
