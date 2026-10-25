#!/usr/bin/env python3
"""check.py - validate extended-summary files before they are published.

    python3 scripts/digest/check.py FILE.md [FILE.md ...]

Fails (exit 1) on anything the renderer or the site style cannot take: an
empty file, em/en dashes, Markdown beyond `### ` headings and `- ` lists, a
heading as the first block (the opening paragraph is the page's snippet), or a
missing core section. Also fails a file whose name matches no manifest record.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REQUIRED = ("רקע", "מה כתוב במסמך", "פרטים בולטים", "מה לא נמצא במסמך")
MIN_WORDS = 200


def stems() -> set[str]:
    files = json.loads((ROOT / "data" / "manifest.json").read_text(encoding="utf-8"))["files"]
    return {re.sub(r"[^A-Za-z0-9._-]+", "_", f["id"]).strip("_") for f in files}


def problems(path: Path, known: set[str]) -> list[str]:
    out = []
    if path.stem not in known:
        out.append("file name matches no manifest record")
    t = path.read_text(encoding="utf-8").strip()
    if not t:
        return out + ["empty"]
    if re.search("[–—]", t):
        out.append("em/en dash")
    if re.search(r"^#{1,2} |^#{4,} |\*\*|__|\[[^\]]*\]\(|^\s*\d+\.\s|^\s*[*+] |^\s*\|", t, re.M):
        out.append("unsupported Markdown")
    if t.startswith("### "):
        out.append("starts with a heading (needs an opening paragraph)")
    heads = re.findall(r"^### (.+)$", t, re.M)
    for h in REQUIRED:
        if h not in heads:
            out.append(f"missing section '### {h}'")
    words = len(t.split())
    if words < MIN_WORDS:
        out.append(f"only {words} words")
    return out


def main() -> int:
    known = stems()
    bad = 0
    for arg in sys.argv[1:]:
        p = Path(arg)
        errs = problems(p, known)
        if errs:
            bad += 1
            print(f"FAIL {p.name}: {'; '.join(errs)}")
    print(f"checked {len(sys.argv) - 1} files, {bad} failed")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
