#!/usr/bin/env python3
"""
pipeline.py — runs classify → sample → ocr in order.

Usage:
    python scripts/extract/pipeline.py --raw-dir ~/Downloads/Release_1
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def run(script: str, raw_dir: str, limit: int | None) -> int:
    cmd = [sys.executable, str(HERE / script), "--raw-dir", raw_dir]
    if limit is not None:
        cmd += ["--limit", str(limit)]
    print("\n" + "=" * 70 + f"\n  running {script}\n" + "=" * 70, flush=True)
    return subprocess.call(cmd)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--raw-dir", required=True,
                    help="Directory of extracted Release_1 PDFs")
    ap.add_argument("--limit", type=int, default=None,
                    help="Limit to N files for smoke-testing the pipeline")
    ap.add_argument("--skip-classify", action="store_true")
    ap.add_argument("--skip-sample", action="store_true")
    ap.add_argument("--skip-ocr", action="store_true")
    args = ap.parse_args()

    steps: list[tuple[str, str]] = []
    if not args.skip_classify: steps.append(("1/3 classify", "classify.py"))
    if not args.skip_sample:   steps.append(("2/3 sample", "sample.py"))
    if not args.skip_ocr:      steps.append(("3/3 ocr", "ocr.py"))

    for label, script in steps:
        print(f"\n>>> {label}")
        rc = run(script, args.raw_dir, args.limit)
        if rc != 0:
            print(f"  step {script} exited {rc}; stopping", file=sys.stderr)
            return rc
    print("\n✓ pipeline complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
