# Briefing: PURSUE — PDF Content Extraction (standalone)

You're running locally on the user's machine. You have access to:
- This briefing file (`EXTRACT.md`)
- A directory of extracted PDFs (the user will tell you where, e.g. `./Release_1/`)
- The filesystem in general
- Internet via `curl` / `wget` (but **no GitHub MCP tools**)
- Python 3.10+, `pip`, and the user's shell

You **do not** have GitHub MCP tools. Do not attempt to open PRs, list
branches, or push remotes via tools. You can `git` from the shell if the
user has a clone — but the recommended flow is to produce a local `output/`
directory which the user will hand back to their **remote** Claude (running
in claude.ai/code) for integration.

## What is this project?

The user runs a Hebrew-language mirror of the U.S. Department of War's
PURSUE landing page (`https://www.war.gov/UFO/`) — a release of 158
declassified UAP-related files. The site lives at
`https://nadaval56.github.io/UFO/`, source at `github.com/nadaval56/UFO`.

The existing `data/manifest.json` has metadata for every file (title,
agency, dates, location, English description, Hebrew translation, source
URL). Your job: **enrich each entry with per-page page-classification,
preview thumbnails, and OCR text** so the public site can show "what's
inside" before users download the multi-hundred-page PDFs.

The PDFs are mostly scanned investigation files. Page 1 is typically a
folder cover (useless). Real content is mixed throughout: typewritten
reports, newspaper clippings, photographs, handwritten notes.

## What you need to install

The user should run before starting you:

```bash
# System binaries
brew install poppler tesseract       # macOS
# or: sudo apt install poppler-utils tesseract-ocr   # Linux

# Python deps
pip install pdf2image PyMuPDF Pillow numpy pytesseract tqdm
```

If any are missing, ask the user to install them first.

## Step 1 — bootstrap your working directory

Set up `output/` next to the PDFs and pull the current manifest + starter
scripts from GitHub raw. The starter scripts are not gospel — they're
educated guesses. **You're expected to refine the heuristics against real
files** once you see what they look like.

```bash
mkdir -p output/previews output/_classification output/_ocr scripts
cd scripts
for f in classify.py sample.py ocr.py pipeline.py; do
  curl -O https://raw.githubusercontent.com/nadaval56/UFO/main/scripts/extract/$f
done
curl -o ../output/manifest.json https://raw.githubusercontent.com/nadaval56/UFO/main/data/manifest.json
cd ..
```

After this you should have:
```
./Release_1/        ← the user's PDFs (158 of them)
./scripts/          ← classify.py, sample.py, ocr.py, pipeline.py
./output/
   manifest.json    ← current state from GitHub
   previews/        ← will be filled with JPEGs
   _classification/ ← per-PDF classification dumps (local cache)
   _ocr/            ← per-page raw OCR (local cache)
EXTRACT.md          ← this file
```

The scripts default to repo-relative paths. Override with `--manifest`,
`--class-dir`, `--preview-dir`, `--ocr-dir`, `--raw-dir`.

## Step 2 — smoke-test on 3 files

Don't process all 158 first. Pick 3-5 representative files (one investigation
file, one short non-FBI file, ideally one that has photos) and run:

```bash
python scripts/pipeline.py --raw-dir ./Release_1 --limit 3 \
  --manifest output/manifest.json \
  --class-dir output/_classification \
  --preview-dir output/previews \
  --ocr-dir output/_ocr
```

Then **open the previews visually** (`open output/previews/*/`). Are they
real content or covers/blanks? Look at the classification JSONs. Are the
labels plausible?

Tune the thresholds in `classify.py` if classification is bad. Common
adjustments for scanned investigation files:

- `dark_ratio` thresholds shift down for grey/yellowed scans
- `line_peaks` threshold for `typewritten` may need lowering — old typewriter
  ribbons leave fainter rows
- `midtone_ratio` for `photo` may need to go up — half-tone-printed photos
  in clippings have lots of mid-grey
- Add a "stamp/seal" pre-filter: pages with very dark concentrated regions
  but no line structure are often stamps/labels — reclassify as `cover`

When you tune, re-run on the same 3 files and inspect again. Iterate
until you trust the classification.

## Step 3 — full run

Once you trust the heuristics:

```bash
python scripts/pipeline.py --raw-dir ./Release_1 \
  --manifest output/manifest.json \
  --class-dir output/_classification \
  --preview-dir output/previews \
  --ocr-dir output/_ocr
```

Expect: ~1-2 hours for classification, ~30 minutes for sampling/render,
~2-3 hours for OCR on 158 files × 3 pages × 5-15 sec/page.

The pipeline is **resumable**. Interrupt with Ctrl+C anytime, resume by
running again — already-done files are skipped.

## Step 4 — quality check

Before handing back the output, spot-check:

1. **Random 10 files**: open `output/previews/{id}/` for each. Do the
   thumbnails look like meaningful content? (At least 1 photo or
   clipping is great; 6 covers is bad.)
2. **Random 5 files** with `text_preview_en`: read them. Coherent
   English? OCR errors are fine; gibberish is not.
3. **manifest.json sanity**: `total_files` still 158, no entry lost any
   existing field, all new fields present where expected.
4. **Repo size estimate**: `du -sh output/previews/` — should be
   ~50-100 MB. If over 200 MB, JPEG quality is too high or you're
   rendering at too high a DPI; rerun sampling with lower DPI/quality.

If you find systematic issues, **tune and re-run the affected stage**.
Don't ship low-quality output.

## Step 5 — hand back to the user

Bundle the result and hand to the user:

```bash
cd output
zip -r ../extraction_output.zip manifest.json previews/
cd ..
ls -lh extraction_output.zip
# expected: ~50-100 MB
```

Tell the user: "extraction_output.zip is ready. Give it to your remote
Claude (claude.ai/code session for nadaval56/UFO) — they'll integrate
the previews + text into the site, translate text_preview_en to Hebrew,
commit and push."

Don't include `_classification/` or `_ocr/` in the zip — those are local
caches for resumability, not part of the deliverable.

## Output schema (what gets added to manifest.json)

Per `files[i]`, add only these fields. Don't touch existing ones:

```jsonc
{
  // ... all existing fields ...

  "page_count": 247,

  "content_kinds": ["typewritten", "photo", "clipping", "handwritten"],
  // Deduped, ordered by descending count of pages of each kind.

  "preview_pages": [
    { "page": 23,  "kind": "photo",       "path": "data/previews/059uap00012/p023.jpg" },
    { "page": 87,  "kind": "clipping",    "path": "data/previews/059uap00012/p087.jpg" },
    { "page": 145, "kind": "typewritten", "path": "data/previews/059uap00012/p145.jpg" }
    // 4-6 entries per file. Path is relative to repo root (data/previews/...).
  ],

  "text_preview_en": "OCR'd content from typewritten pages, ≤3000 chars, sentence-aligned cut.",
  "text_preview_he": null,    // DO NOT FILL. Remote Claude does the translation.

  "_extracted_at": "2026-05-12T15:00:00Z"
}
```

### Allowed `kind` values

`cover` · `blank` · `divider` · `typewritten` · `handwritten` · `clipping`
· `photo` · `mixed`

Skip `cover` / `blank` / `divider` / `handwritten` when choosing
`preview_pages`, unless a file has nothing else available.

## What NOT to do

- Don't translate to Hebrew. (Cost goes through the remote session's
  Claude Code quota, which is what the user wants.)
- Don't push to GitHub directly even if you have credentials. The user
  prefers reviewing your output in the zip before integration.
- Don't try to OCR `handwritten` or `photo` pages — output is gibberish.
- Don't render at >300 DPI for previews. 250-300 DPI is plenty.
- Don't include raw PDFs or the per-page `_classification` JSONs in the
  zip you hand back — they're caches.

## When you finish

Tell the user the path to `extraction_output.zip`, summarize what you
did (e.g. "158/158 files processed, 142 had at least one photo or
clipping, 116 produced clean OCR text, 16 files had only handwritten
content and got no text preview"). Then stop — the remote Claude takes
over from there.

Good luck. Make it look like archaeology.
