#!/usr/bin/env python3
"""Phase 1: promote text_preview_he to text_he for files where text_en fits
entirely within the 3000-char preview window. No new translation is created;
this only renames an already-complete translation into the canonical field.
"""
import json
from pathlib import Path

MANIFEST = Path(__file__).resolve().parent.parent.parent / "data" / "manifest.json"
THRESHOLD = 3000

m = json.loads(MANIFEST.read_text(encoding="utf-8"))
promoted = 0
skipped = 0
for f in m["files"]:
    te = (f.get("text_en") or "").strip()
    if not te:
        continue
    if f.get("text_he"):
        skipped += 1
        continue
    if len(te) <= THRESHOLD and (f.get("text_preview_he") or "").strip():
        f["text_he"] = f["text_preview_he"]
        promoted += 1

MANIFEST.write_text(json.dumps(m, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"promoted: {promoted}")
print(f"already had text_he: {skipped}")
