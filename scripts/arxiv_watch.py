# -*- coding: utf-8 -*-
"""arxiv_watch.py — fetch latest arXiv papers for keywords, report new ones.

Usage:
    python arxiv_watch.py --query "transformer efficiency" [--max 20] [--state research/lit/_arxiv_state.json]

- Queries the arXiv API (http://export.arxiv.org/api/query, Atom XML, stdlib only).
- State file records seen arXiv ids; run daily to get only NEW papers since last run.
- Output: markdown list with title/authors/date/abstract-link to stdout.
"""
import argparse
import json
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

ATOM = "{http://www.w3.org/2005/Atom}"
API = "https://export.arxiv.org/api/query"


def fetch(query, max_results, retries=3):
    import time
    # arXiv API rejects some raw multi-word space queries (429/timeout);
    # AND-join the terms ourselves and only urlencode colon.
    terms = query.split()
    q = " AND ".join(f"all:{t}" for t in terms) if len(terms) > 1 else f"all:{query}"
    params = urllib.parse.urlencode({
        "search_query": q,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
        "max_results": max_results,
    }, safe=":")
    url = f"{API}?{params}"
    last_err = None
    for attempt in range(retries):
        req = urllib.request.Request(url, headers={"User-Agent": "dsh-research/0.1"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code == 429:  # arXiv rate limit: back off and retry
                time.sleep(3 * (attempt + 1))
            else:
                raise
        except urllib.error.URLError as e:
            last_err = e
            time.sleep(3 * (attempt + 1))
    print(f"ERROR: arXiv API failed after {retries} retries ({last_err}). Wait a minute and rerun.", file=sys.stderr)
    raise last_err


def parse(xml_text):
    entries = []
    root = ET.fromstring(xml_text)
    for e in root.findall(f"{ATOM}entry"):
        eid = e.findtext(f"{ATOM}id", "").rsplit("/", 1)[-1]
        title = re.sub(r"\s+", " ", e.findtext(f"{ATOM}title", "")).strip()
        authors = [a.findtext(f"{ATOM}name") for a in e.findall(f"{ATOM}author")]
        published = e.findtext(f"{ATOM}published", "")[:10]
        summary = re.sub(r"\s+", " ", e.findtext(f"{ATOM}summary", "")).strip()[:400]
        link = e.findtext(f"{ATOM}id", "")
        entries.append({"id": eid, "title": title, "authors": authors,
                        "date": published, "summary": summary, "link": link})
    return entries


def main():
    # Windows GBK console crashes printing titles with special unicode chars
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--query", required=True)
    ap.add_argument("--max", type=int, default=20)
    ap.add_argument("--state", default="research/lit/_arxiv_state.json")
    ap.add_argument("--all", action="store_true", help="report all fetched, ignore state")
    args = ap.parse_args()

    entries = parse(fetch(args.query, args.max))

    state_path = Path(args.state)
    seen = set()
    if state_path.exists() and not args.all:
        seen = set(json.loads(state_path.read_text(encoding="utf-8")))

    fresh = [e for e in entries if e["id"] not in seen]

    print(f"# arXiv watch: {args.query}")
    print(f"fetched {len(entries)}, new {len(fresh)} (state: {state_path})\n")
    for e in fresh:
        print(f"## {e['title']}")
        print(f"- **{e['date']}** | {', '.join(e['authors'][:4])}{' et al.' if len(e['authors']) > 4 else ''} | [{e['id']}]({e['link']})")
        print(f"- {e['summary']}...\n")

    # update state regardless of --all
    state_path.parent.mkdir(parents=True, exist_ok=True)
    seen |= {e["id"] for e in entries}
    state_path.write_text(json.dumps(sorted(seen), ensure_ascii=False), encoding="utf-8")
    if not fresh:
        print("(no new papers since last run)")


if __name__ == "__main__":
    main()
