# -*- coding: utf-8 -*-
"""verify_refs.py — authenticity check for bibliography entries.

Usage:
    python verify_refs.py [--bib research/bib.bib] [--entry <key>] [--mail you@example.com]

Checks each entry:
  - DOI present  -> query https://api.crossref.org/works/<doi> (or doi.org for
    non-Crossref DOIs) and compare stored title vs registered title (token overlap).
  - no DOI but has eprint/arxiv id -> query arXiv API.
  - neither      -> UNVERIFIED (flagged, must not be cited as fact).

Exit 0 = all pass; exit 1 = at least one FAIL (mismatch or not found).
"""
import argparse
import json
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from bib import load_bib  # noqa: E402

ATOM = "{http://www.w3.org/2005/Atom}"


def http_get(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": "dsh-research-verify/0.1 (mailto:research@example.org)"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


def norm_tokens(s):
    return [t for t in re.findall(r"[a-z0-9]+", (s or "").lower())
            if t not in {"a", "an", "the", "of", "for", "and", "in", "on", "to",
                         "with", "via", "by", "is", "are", "you"}]


def title_match(t1, t2):
    """Combined gate: token overlap (recall) AND positional word agreement.
    Pure set overlap passes word-shuffled/rotated fake titles; requiring words
    to agree IN POSITION (allowing one list to be a contiguous sub-list of the
    other, for registry prefixes like '[1706.03762]') closes that hole."""
    a, b = norm_tokens(t1 or ""), norm_tokens(t2 or "")
    if not a or not b:
        return 0.0
    overlap = len(set(a) & set(b)) / min(len(set(a)), len(set(b)))
    n = min(len(a), len(b))
    pos = sum(1 for i in range(n) if a[i] == b[i]) / n
    # contiguous-slice containment: registry titles often gain prefix/suffix tokens
    if len(a) > len(b):
        pos2 = max((sum(1 for i in range(len(b)) if a[s + i] == b[i]) / len(b))
                   for s in range(len(a) - len(b) + 1)) if len(a) >= len(b) else 0.0
    else:
        pos2 = max((sum(1 for i in range(len(a)) if a[i] == b[s + i]) / len(a))
                   for s in range(len(b) - len(a) + 1)) if len(b) >= len(a) else 0.0
    return min(overlap, max(pos, pos2))


def check_doi(doi, mailto=""):
    """Resolve DOI existence via doi.org handle API (agency-agnostic), then
    fetch registered title from Crossref or DataCite depending on prefix."""
    import time
    # 1) does the DOI exist at all? (404 here = unregistered DOI)
    try:
        handle = json.loads(http_get(f"https://doi.org/api/handles/{urllib.parse.quote(doi)}"))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return False, "", "DOI not registered (handle not found)"
        return None, "", f"network: HTTP {e.code}"
    except Exception as e:
        return None, "", f"network: {e}"
    if handle.get("responseCode") != 1:
        return False, "", "DOI not registered (handle not found)"
    # 2) registered title, try Crossref then DataCite
    for api, base in (("crossref", "https://api.crossref.org/works/"),
                      ("datacite", "https://api.datacite.org/dois/")):
        for attempt in range(2):
            try:
                data = json.loads(http_get(base + urllib.parse.quote(doi)))
                msg = data.get("message", data.get("data", {}).get("attributes", {}))
                titles = msg.get("title") or msg.get("titles") or [{}]
                t = titles[0]
                reg = t.get("title") if isinstance(t, dict) else t
                return True, (reg or ""), api
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    break  # not this agency, try next
                if e.code == 429:
                    time.sleep(2 * (attempt + 1))
                    continue
                return None, "", f"HTTP {e.code}"
            except Exception as e:
                return None, "", f"network: {e}"
    return None, "", "DOI exists but title lookup failed (both agencies)"


def check_arxiv(arxiv_id):
    url = f"https://export.arxiv.org/api/query?id_list={urllib.parse.quote(arxiv_id)}"
    try:
        root = ET.fromstring(http_get(url))
        e = root.find(f"{ATOM}entry")
        if e is None:
            return False, "", "arXiv id not found"
        return True, re.sub(r"\s+", " ", e.findtext(f"{ATOM}title", "")).strip(), "arXiv"
    except Exception as e:
        return None, "", f"network: {e}"


def verify_entry(e, mailto=""):
    """Return (status, detail). status in PASS / FAIL / UNVERIFIED."""
    doi = e.get("doi", "").strip()
    raw = e["raw"].lower()
    if doi:
        ok, reg_title, src = check_doi(doi, mailto)
        if ok is None:
            return "UNVERIFIED", src
        if not ok:
            return "FAIL", f"DOI {doi} not registered ({src})"
        sim = title_match(reg_title, e["raw"])
        if sim < 0.5:
            return "FAIL", (f"DOI {doi} resolves to a DIFFERENT title: "
                            f"\"{reg_title[:90]}\" (similarity {sim:.2f})")
        return "PASS", f"DOI ok, title match {sim:.2f} ({src})"
    m = re.search(r"eprint\s*=\s*[{\"]([\w.\-/]+)[}\" ]", raw) or \
        re.search(r"arxiv\s*[:=]\s*[{\"]?([\w.\-/]+)", raw)
    if m:
        ok, reg_title, src = check_arxiv(m.group(1))
        if ok is None:
            return "UNVERIFIED", src
        if not ok:
            return "FAIL", f"arXiv {m.group(1)} not found"
        sim = title_match(reg_title, e["raw"])
        if sim < 0.5:
            return "FAIL", f"arXiv title mismatch: \"{reg_title[:90]}\" (sim {sim:.2f})"
        return "PASS", f"arXiv ok, title match {sim:.2f}"
    return "UNVERIFIED", "no DOI and no arXiv id — cannot verify"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bib", default="research/bib.bib")
    ap.add_argument("--entry", default=None, help="verify only this key")
    ap.add_argument("--mail", default="", help="contact email for Crossref polite pool")
    args = ap.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    entries = load_bib(Path(args.bib))
    if args.entry:
        entries = [e for e in entries if e["key"] == args.entry]
        if not entries:
            print(f"key not found: {args.entry}")
            sys.exit(2)

    n_fail = 0
    for e in entries:
        status, detail = verify_entry(e, args.mail)
        mark = {"PASS": "[PASS]", "FAIL": "[FAIL]", "UNVERIFIED": "[UNVERIFIED]"}[status]
        print(f"{mark} {e['key']}: {detail}")
        if status == "FAIL":
            n_fail += 1
    total = len(entries)
    print(f"\n{total} checked, {n_fail} failed, "
          f"{total - n_fail - sum(1 for e in entries)} unverified-or-passed")
    sys.exit(1 if n_fail else 0)


if __name__ == "__main__":
    main()
