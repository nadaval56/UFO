#!/usr/bin/env python3
"""Apply Hebrew translations of text_preview_en to data/manifest.json.

Run repeatedly with batches of {id: he_text}. Idempotent: if text_preview_he
is already set for an id, the script overwrites (latest wins). Preserves
all other manifest fields and the file ordering.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

MANIFEST = Path(__file__).resolve().parent.parent.parent / "data" / "manifest.json"


def apply(translations: dict[str, str], field: str = "text_preview_he") -> None:
    m = json.loads(MANIFEST.read_text(encoding="utf-8"))
    by_id = {f.get("id"): f for f in m["files"]}
    applied, missing = 0, []
    for eid, he in translations.items():
        if eid not in by_id:
            missing.append(eid)
            continue
        by_id[eid][field] = he.strip()
        applied += 1
    MANIFEST.write_text(
        json.dumps(m, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"applied: {applied} (field={field})", file=sys.stderr)
    if missing:
        print(f"missing ids: {missing}", file=sys.stderr)
