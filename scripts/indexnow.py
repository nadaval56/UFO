#!/usr/bin/env python3
"""
indexnow.py — tell IndexNow search engines (Bing, Yandex, Seznam, Naver, …;
Bing also feeds DuckDuckGo and ChatGPT search) which pages just changed, so
they recrawl in minutes instead of whenever they next visit. Google does not
take part; it reads sitemap.xml.

Run by .github/workflows/deploy.yml after each successful deploy:
    python scripts/indexnow.py            # pages changed in the last commit
    python scripts/indexnow.py --all      # every URL in sitemap.xml

The key is the 32-hex-char <key>.txt at the site root, whose content is the
key itself. It is public by design: it only proves the pinger controls the
site, it grants nothing.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOST = "pursue.co.il"
BASE = f"https://{HOST}"
ENDPOINT = "https://api.indexnow.org/indexnow"


def find_key() -> str:
    for p in ROOT.glob("*.txt"):
        if re.fullmatch(r"[0-9a-f]{32}", p.stem) and p.read_text().strip() == p.stem:
            return p.stem
    raise SystemExit("no IndexNow key file (<32 hex>.txt containing its own name) at repo root")


def changed_urls() -> list[str]:
    out = subprocess.run(["git", "diff", "--name-only", "HEAD~1", "HEAD"],
                         cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
    urls = []
    for path in out:
        if path.startswith("doc/") and path.endswith(".html"):
            urls.append(f"{BASE}/{path}")
        elif path == "index.html":
            urls.append(f"{BASE}/")
        elif path == "archive.html":
            urls.append(f"{BASE}/archive.html")
    return urls


def all_urls() -> list[str]:
    return re.findall(r"<loc>([^<]+)</loc>", (ROOT / "sitemap.xml").read_text(encoding="utf-8"))


def main() -> int:
    key = find_key()
    urls = all_urls() if "--all" in sys.argv else changed_urls()
    if not urls:
        print("indexnow: no page changes to report")
        return 0
    for i in range(0, len(urls), 10000):          # protocol limit per request
        body = json.dumps({"host": HOST, "key": key,
                           "keyLocation": f"{BASE}/{key}.txt",
                           "urlList": urls[i:i + 10000]}).encode()
        req = urllib.request.Request(ENDPOINT, data=body, method="POST",
                                     headers={"Content-Type": "application/json; charset=utf-8"})
        with urllib.request.urlopen(req, timeout=30) as res:
            print(f"indexnow: submitted {len(urls[i:i + 10000])} URLs -> HTTP {res.status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
