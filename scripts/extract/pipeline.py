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


# Which of the shared path options each step accepts, and under what flag.
# classify.py calls its classification directory --out-dir; the others read it
# as --class-dir. Options left unset fall through to each script's default.
PATH_FLAGS: dict[str, dict[str, str]] = {
    "classify.py": {"manifest": "--manifest", "class_dir": "--out-dir"},
    "sample.py":   {"manifest": "--manifest", "class_dir": "--class-dir",
                    "preview_dir": "--preview-dir"},
    "ocr.py":      {"manifest": "--manifest", "class_dir": "--class-dir",
                    "ocr_dir": "--ocr-dir"},
}


def run(script: str, args: argparse.Namespace) -> int:
    cmd = [sys.executable, str(HERE / script), "--raw-dir", args.raw_dir]
    for key, flag in PATH_FLAGS[script].items():
        value = getattr(args, key)
        if value is not None:
            cmd += [flag, value]
    if args.limit is not None:
        cmd += ["--limit", str(args.limit)]
    print("\n" + "=" * 70 + f"\n  running {script}\n" + "=" * 70, flush=True)
    return subprocess.call(cmd)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--raw-dir", required=True,
                    help="Directory of extracted Release_1 PDFs")
    ap.add_argument("--limit", type=int, default=None,
                    help="Limit to N files for smoke-testing the pipeline")
    ap.add_argument("--manifest", default=None,
                    help="manifest.json to read and update (forwarded to every step)")
    ap.add_argument("--class-dir", default=None,
                    help="per-page classification directory")
    ap.add_argument("--preview-dir", default=None,
                    help="where sample.py writes preview JPEGs")
    ap.add_argument("--ocr-dir", default=None,
                    help="where ocr.py writes per-file OCR text")
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
        rc = run(script, args)
        if rc != 0:
            print(f"  step {script} exited {rc}; stopping", file=sys.stderr)
            return rc
    print("\n✓ pipeline complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
