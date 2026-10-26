#!/usr/bin/env python3
"""Apply data/corrections.json to data/manifest.json.

The mirror fixes metadata errors on war.gov that can be proven from the
material itself, and points out likely errors it does not fix. Each entry:

  {"id": "...", "kind": "fix" | "note", "set": {...}, "note_he": "..."}

"set" fields overwrite what war.gov serves (fix entries only); "note_he" is
stored as correction_he and rendered on the document page, so a reader
comparing with war.gov sees why the two differ. Idempotent: safe to run
after every merge or re-scrape. build_sitemap.py runs it first.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "data" / "manifest.json"
CORRECTIONS = ROOT / "data" / "corrections.json"


def apply(manifest_path: Path = MANIFEST, corrections_path: Path = CORRECTIONS) -> int:
    if not corrections_path.exists():
        return 0
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    by_id = {f["id"]: f for f in manifest["files"]}
    corrections = json.loads(corrections_path.read_text(encoding="utf-8"))["corrections"]
    changed = 0
    for c in corrections:
        f = by_id.get(c["id"])
        if f is None:
            sys.exit(f"apply_corrections: no record with id {c['id']!r}")
        if c.get("kind") not in ("fix", "note"):
            sys.exit(f"apply_corrections: bad kind {c.get('kind')!r} for {c['id']!r}")
        wanted = dict(c.get("set") or {}) if c["kind"] == "fix" else {}
        wanted["correction_he"] = c["note_he"]
        for k, v in wanted.items():
            if f.get(k) != v:
                f[k] = v
                changed += 1
    if changed:
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"apply_corrections: {len(corrections)} entries, {changed} fields changed")
    return changed


if __name__ == "__main__":
    apply()
