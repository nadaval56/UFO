# Local extraction prompt — Release 03 + 04 (previews + OCR)

> Paste the block below into a **local** Claude Code session (on your own
> machine, where war.gov is reachable and poppler/tesseract can run). It
> downloads the R03+R04 document bundles, extracts page previews + OCR, and
> produces one zip to hand back to the remote session. No API key needed —
> the pipeline is deterministic Python; Hebrew translation is done remotely.

---

You are Claude Code running **locally on my machine**, helping with the PURSUE
Hebrew mirror (`github.com/nadaval56/UFO`) — a Hebrew RTL mirror of
`war.gov/UFO`. Your job: extract **page-preview thumbnails + OCR text** from the
**Release 03 and Release 04 PDF bundles**, so the remote Claude (working on
branch `claude/us-gov-updates-sync-fyt1sk`) can fold them into the site.

You do **not** push to GitHub, open PRs, or use any GitHub tools. You produce a
local **zip** that I will hand back to the remote session.

## 0. Prerequisites

```bash
# macOS
brew install poppler tesseract
# Linux
# sudo apt install poppler-utils tesseract-ocr

pip install pdf2image PyMuPDF Pillow numpy pytesseract tqdm
```

## 1. Get the code + current data — the FEATURE BRANCH, not main

```bash
git clone -b claude/us-gov-updates-sync-fyt1sk https://github.com/nadaval56/UFO.git
cd UFO
```

You now have `scripts/extract/*.py`, `data/manifest.json` (334 files, incl. the
new Release 03/04 records), and `scripts/extract/EXTRACT.md`. **Read
`EXTRACT.md` first** — it is the full method and the two quality policies
(what counts as an "interesting" preview, and "OCR every typewritten page").

## 2. Download + unzip the two DOCUMENT bundles into one `raw/` folder

```bash
mkdir -p raw
curl -L -o r03.zip "https://www.war.gov/medialink/ufo/061226/release_03/release_03_documents.zip"
curl -L -o r04.zip "https://www.war.gov/medialink/ufo/071026/release_04/release_04_documents_071026.zip"
unzip -o r03.zip -d raw/
unzip -o r04.zip -d raw/
find raw -iname '*.pdf' | wc -l    # expect ~67 PDFs across R03 + R04
```

(These are the **document** bundles only. Videos are handled separately — ignore
any video zips. If `curl` to war.gov 403s on your network too, download the two
zips in a browser and drop them into `raw/`.)

## 3. Set up output dirs

```bash
mkdir -p output/previews output/_classification output/_ocr
cp data/manifest.json output/manifest.json
```

## 4. Smoke-test 3 files, LOOK at them, tune the classifier

```bash
python scripts/extract/pipeline.py --raw-dir ./raw --limit 3 \
  --manifest output/manifest.json --class-dir output/_classification \
  --preview-dir output/previews --ocr-dir output/_ocr
```

Open `output/previews/*/`. The thumbnails must be **visually interesting
content** — photographs, sky/scene shots, newspaper clippings, hand-drawn
sketches, diagrams. If you see plain typed-text scans in the preview pool, the
classifier is mislabeling them; **tighten it per `EXTRACT.md` → "Step 2" and
"Two policy points"** and re-run on the same 3 files until you trust it. Do not
start the full run until the previews are genuinely interesting.

## 5. Full run

```bash
python scripts/extract/pipeline.py --raw-dir ./raw \
  --manifest output/manifest.json --class-dir output/_classification \
  --preview-dir output/previews --ocr-dir output/_ocr
```

Only R03/R04 PDFs are in `raw/`, so only they get processed. Resumable — Ctrl+C
and re-run any time. OCR **every** typewritten page (confidence ≥ 60),
concatenated per file into `text_en`, with the first ~3000 sentence-aligned
chars in `text_preview_en`.

## 6. Quality check (EXTRACT.md → Step 4)

- Random 10 files: previews are interesting content, **not** boring scans. A
  file with nothing interesting should have an **empty** `preview_pages`.
- Random 5 `text_en`: coherent English (OCR typos fine, gibberish not).
- `du -sh output/previews/` → roughly **30–70 MB** for R03+R04. If much larger,
  re-render at lower DPI/quality.
- **UTF-8:** after writing `output/manifest.json`, re-read it and confirm any
  Hebrew string round-trips (no mojibake).

## 7. Hand back — EXACTLY this

```bash
cd output
zip -r ../extraction_R03_R04.zip manifest.json previews/
cd ..
ls -lh extraction_R03_R04.zip
```

Send me **`extraction_R03_R04.zip`**.

### What the remote session takes from your zip

For each **Release 03 / 04** id, only these six fields —
`page_count`, `content_kinds`, `preview_pages`, `preview_pages_fallback`,
`text_en`, `text_preview_en` — plus the `previews/{id}/*.jpg` images. Nothing
else from your `manifest.json` is used, so stale Hebrew fields don't matter.

### Rules

- **Do not translate anything** — Hebrew is done remotely.
- **Do not** `git push` or open PRs.
- Key everything by the manifest `id` (already in `data/manifest.json`; the
  pipeline matches PDFs to ids by filename automatically — don't rename files).
- Standalone image files (`type: "img"`, e.g. the NASA STS-80 stills) don't need
  the PDF pipeline; the site shows them directly from their source URL. Focus on
  the PDFs.
