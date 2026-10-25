#!/usr/bin/env python3
"""plan_batch.py - plan the next batch of extended Hebrew summaries (data/digest/).

A document is pending when it has full OCR (`text_en_path`) and no
data/digest/<page>.md yet, so progress lives in the repository itself and an
interrupted run simply leaves its documents pending for the next one.

Packs pending documents, newest release first, into agent tasks of at most
--agent-chars of OCR each, until --budget characters are planned. A document
larger than --agent-chars is split into parts (at line breaks): each part gets
its own notes task, and a merge task turns the notes into the final summary.
A document bigger than the whole budget is still taken when it comes first,
so it can never block the queue.

    python3 scripts/digest/plan_batch.py --budget 850000 --work /tmp/digest-run
    python3 scripts/digest/plan_batch.py --status

Writes <work>/plan.json; see RUNBOOK.md for how it is executed.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "data" / "manifest.json"
DIGEST_DIR = ROOT / "data" / "digest"
FIELDS = ("id", "title", "title_he", "agency", "agency_he", "incident_date",
          "incident_location", "incident_location_he", "page_count",
          "summary_en", "summary_he")


def page_stem(record_id: str) -> str:
    # same rule as build_static_pages.page_name()
    return re.sub(r"[^A-Za-z0-9._-]+", "_", record_id).strip("_")


def pending(files: list[dict]) -> list[tuple[dict, int]]:
    out = []
    for f in files:
        p = f.get("text_en_path")
        if not p or not (ROOT / p).exists():
            continue
        if (DIGEST_DIR / f"{page_stem(f['id'])}.md").exists():
            continue
        out.append((f, (ROOT / p).stat().st_size))
    # newest release first, then by id; ties are stable
    out.sort(key=lambda x: (-int(x[0].get("release_no") or 0), x[0]["id"]))
    return out


def split_text(text: str, limit: int) -> list[str]:
    """Split into the fewest parts of at most ~limit characters, of roughly
    equal size, at line breaks (so no part is a stub)."""
    n = -(-len(text) // limit)
    target = len(text) / n
    parts, cur, size = [], [], 0
    for line in text.splitlines(keepends=True):
        if size >= target and len(parts) < n - 1:
            parts.append("".join(cur))
            cur, size = [], 0
        cur.append(line)
        size += len(line)
    if cur:
        parts.append("".join(cur))
    return parts


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget", type=int, default=850_000, help="OCR characters to plan")
    ap.add_argument("--agent-chars", type=int, default=120_000)
    ap.add_argument("--work", type=Path, help="scratch directory for this run")
    ap.add_argument("--status", action="store_true", help="print progress and exit")
    a = ap.parse_args()

    files = json.loads(MANIFEST.read_text(encoding="utf-8"))["files"]
    todo = pending(files)
    total = [f for f in files if f.get("text_en_path")]
    if a.status:
        left = sum(s for _, s in todo)
        print(f"done {len(total) - len(todo)}/{len(total)} documents; "
              f"{len(todo)} pending, {left:,} OCR characters left")
        return 0
    if not a.work:
        ap.error("--work is required")

    out_dir = a.work / "digest"
    parts_dir = a.work / "parts"
    out_dir.mkdir(parents=True, exist_ok=True)
    parts_dir.mkdir(parents=True, exist_ok=True)

    tasks, merges, group, group_chars, planned = [], [], [], 0, 0

    def flush():
        nonlocal group, group_chars
        if group:
            tasks.append({"kind": "docs", "records": group, "chars": group_chars})
            group, group_chars = [], 0

    for f, size in todo:
        if planned and planned + size > a.budget:
            continue  # try smaller documents further down the queue
        stem = page_stem(f["id"])
        rec = {k: f.get(k) for k in FIELDS}
        rec["ocr_chars"] = size
        rec["out_file"] = str(out_dir / f"{stem}.md")
        if size <= a.agent_chars:
            if group_chars + size > a.agent_chars:
                flush()
            rec["ocr_file"] = str(ROOT / f["text_en_path"])
            group.append(rec)
            group_chars += size
        else:
            text = (ROOT / f["text_en_path"]).read_text(encoding="utf-8")
            chunks = split_text(text, a.agent_chars)
            notes = []
            for i, chunk in enumerate(chunks, 1):
                pf = parts_dir / f"{stem}.p{i:02d}.txt"
                pf.write_text(chunk, encoding="utf-8")
                nf = parts_dir / f"{stem}.p{i:02d}.notes.md"
                notes.append(str(nf))
                tasks.append({"kind": "part", "record": rec, "part": i, "of": len(chunks),
                              "part_file": str(pf), "notes_file": str(nf), "chars": len(chunk)})
            merges.append({"record": rec, "notes_files": notes})
        planned += size
        if planned >= a.budget:
            break
    flush()

    plan = {"budget": a.budget, "planned_chars": planned, "tasks": tasks, "merges": merges,
            "documents": sum(len(t["records"]) for t in tasks if t["kind"] == "docs") + len(merges)}
    (a.work / "plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"planned {plan['documents']} documents, {planned:,} OCR characters: "
          f"{len(tasks)} agent tasks ({len(merges)} split documents need a merge step) "
          f"-> {a.work / 'plan.json'}")
    if not tasks:
        print("queue is empty: every document with OCR has a summary", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
