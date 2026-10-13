# -*- coding: utf-8 -*-
"""dblp_verify.py — verify title-only entries via OpenAlex (DBLP fallback).

Usage:
    python dblp_verify.py --title "Some Conference Paper Title"
    python dblp_verify.py --bib research/bib.bib --unverified-only

Why OpenAlex instead of DBLP: since 2025 DBLP serves an Anubis anti-bot
challenge to all programmatic clients (all mirrors), breaking scriptable
verification. OpenAlex is free, key-less, covers ALL fields (not just CS),
and returns clean JSON with DOI + year.

Strategy: title search -> positional title match (same policy as
verify_refs.title_match). A PASS hit also yields a real DOI, which lets the
entry be upgraded to DOI-verified via the stricter verify_refs path.

Politeness: 1 req/sec; mailto in UA for the polite pool.
"""
import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from bib import load_bib  # noqa: E402

API = "https://api.openalex.org/works"
MAILTO = "research@example.org"  # polite pool; users may override


def http_get_json(url, retries=3):
    last = None
    for attempt in range(retries):
        req = urllib.request.Request(url, headers={
            "User-Agent": f"dsh-research-verify/0.1 (mailto:{MAILTO})"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode("utf-8", errors="replace"))
        except urllib.error.HTTPError as e:
            last = e
            if e.code == 429:
                time.sleep(2 * (attempt + 1))
                continue
            return None
        except Exception:
            time.sleep(2)
    if last:
        raise last
    return None


def title_match(t1, t2):
    """Same policy as verify_refs.title_match (imported; local fallback)."""
    try:
        from verify_refs import title_match as tm
        return tm(t1, t2)
    except Exception:
        import re as _re
        def norm(s):
            return [t for t in _re.findall(r"[a-z0-9]+", (s or "").lower())]
        a, b = norm(t1), norm(t2)
        if not a or not b:
            return 0.0
        overlap = len(set(a) & set(b)) / min(len(set(a)), len(set(b)))
        n = min(len(a), len(b))
        pos = sum(1 for i in range(n) if a[i] == b[i]) / n
        return min(overlap, pos)


def openalex_search(title, limit=5):
    url = (f"{API}?filter=title.search:{urllib.parse.quote(title)}"
           f"&per-page={limit}&select=title,doi,publication_year,primary_location")
    data = http_get_json(url)
    if not data:
        return []
    out = []
    for w in data.get("results", []):
        doi = (w.get("doi") or "").replace("https://doi.org/", "").lower()
        src = ((w.get("primary_location") or {}).get("source") or {}).get("display_name", "")
        out.append({
            "title": re.sub(r"\s+", " ", w.get("title", "") or "").rstrip("."),
            "year": w.get("publication_year", ""),
            "venue": src,
            "doi": doi,
        })
    return out


def verify_title(title):
    """-> (status, detail, best_hit). status in PASS/FAIL/UNVERIFIED."""
    hits = openalex_search(title)
    if not hits:
        return "UNVERIFIED", "no OpenAlex hits", None
    best_score, best = 0.0, None
    for h in hits:
        s = title_match(title, h["title"])
        if s > best_score:
            best_score, best = s, h
    if best_score >= 0.8:
        src = f"{best['venue']} {best['year']}".strip()
        return "PASS", f"OpenAlex match {best_score:.2f}: {src} (doi={best['doi'] or 'none'})", best
    if best_score >= 0.5:
        return "UNVERIFIED", (f"OpenAlex closest only {best_score:.2f}: "
                              f"\"{best['title'][:80]}\""), best
    return "UNVERIFIED", "OpenAlex hits but none similar enough", best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--title")
    ap.add_argument("--bib")
    ap.add_argument("--unverified-only", action="store_true",
                    help="only process entries lacking doi/eprint")
    args = ap.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    targets = []
    if args.title:
        targets.append(("(adhoc)", args.title))
    elif args.bib:
        for e in load_bib(Path(args.bib)):
            if args.unverified_only and (e.get("doi") or "eprint" in e["raw"].lower()
                                         or "arxiv" in e["raw"].lower()):
                continue
            m = re.search(r"title\s*=\s*[{\"](.+?)[}\"]\s*,?\s*\n", e["raw"], re.S | re.I)
            if m:
                targets.append((e["key"], re.sub(r"\s+", " ", m.group(1))))
    else:
        ap.error("provide --title or --bib")

    n_pass = n_fail = 0
    for key, title in targets:
        status, detail, best = verify_title(title)
        mark = {"PASS": "[PASS]", "FAIL": "[FAIL]", "UNVERIFIED": "[UNVERIFIED]"}[status]
        print(f"{mark} {key}: {detail}")
        if status == "PASS":
            n_pass += 1
        elif status == "FAIL":
            n_fail += 1
        time.sleep(1)  # politeness
    print(f"\n{len(targets)} checked: {n_pass} PASS, {n_fail} FAIL, "
          f"{len(targets) - n_pass - n_fail} UNVERIFIED")
    sys.exit(1 if n_fail else 0)


if __name__ == "__main__":
    main()
