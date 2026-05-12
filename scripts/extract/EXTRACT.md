# Briefing: PDF Content Extraction Pipeline (Phase 2)

You're running locally on the user's machine inside the PURSUE Hebrew Mirror
repo. The user has extracted `Release_1.zip` (~3.2 GB, 158 files) somewhere
on the filesystem. Your job: enrich `data/manifest.json` with per-page
classification, smart-sample preview thumbnails, and OCR text for typewritten
pages. The result gets committed and pushed; the public site then renders the
new fields. Hebrew translation of the OCR'd text happens later in a separate
Claude Code session — leave `*_he` fields alone.

The "remote" Claude (in the user's conversational session, where the
project was built) will write UI integration once it sees the first batch
of output. Don't touch `assets/` or `index.html`. Only produce data.

## What you'll find when you start

```
data/manifest.json          # 158 entries, each with id/title/source_url/etc.
                             # KEEP all existing fields. Only ADD new ones.
scripts/extract/
├── EXTRACT.md              # this briefing
├── classify.py             # starter: page-by-page classifier
├── sample.py               # starter: pick + render preview thumbnails
├── ocr.py                  # starter: OCR typewritten pages
├── pipeline.py             # orchestrator: runs the three in order
└── requirements.txt        # pdf2image, Pillow, pytesseract, PyMuPDF
```

The user will tell you where they extracted the ZIP, e.g.
`~/Downloads/Release_1/`. Expect filenames matching the `source_url`
basename in the manifest — that's the join key. **Always work from the
filename → manifest `id` mapping.** A file `059uap00012.pdf` joins to the
manifest entry whose `source_url` ends in `059uap00012.pdf`.

## System dependencies the user needs installed

- Python 3.10+
- `poppler-utils` (Mac: `brew install poppler` / Linux: `apt install poppler-utils`)
- `tesseract` (Mac: `brew install tesseract` / Linux: `apt install tesseract-ocr`)
- Then: `pip install -r scripts/extract/requirements.txt`

The starter scripts are templates. Adjust heuristics, thresholds, page-pick
strategy etc. as you discover what the actual files look like. **Iterate.**

## Output schema — what to add per manifest entry

Add the following fields to each `files[i]` in `data/manifest.json`. Don't
touch existing fields:

```jsonc
{
  // ... existing fields unchanged ...

  "page_count": 247,
  "content_kinds": ["typewritten", "photo", "clipping", "handwritten"],
  // Deduped list, sorted by descending count of pages of each kind.

  "preview_pages": [
    { "page": 23, "kind": "photo",       "path": "data/previews/059uap00012/p023.jpg" },
    { "page": 87, "kind": "clipping",    "path": "data/previews/059uap00012/p087.jpg" },
    { "page": 145, "kind": "typewritten","path": "data/previews/059uap00012/p145.jpg" }
    // 4-6 entries per file. Prefer photo > clipping > typewritten.
    // Skip cover/blank/divider/handwritten unless nothing else available.
  ],

  "text_preview_en": "The first ~3000 chars of OCR'd typewritten content...",
  "text_preview_he": null,   // ← do NOT fill. Remote Claude handles it.

  "_extracted_at": "2026-05-12T15:00:00Z"
}
```

### Per-page classification kinds

Use these exact strings (the UI will key off them):

| kind | meaning |
|---|---|
| `cover` | Folder cover, title page, FBI vault headers |
| `blank` | Mostly empty page or scanning artifacts |
| `divider` | Section divider with just a label |
| `typewritten` | Printed/typed body content. OCR target. |
| `handwritten` | Cursive or manuscript. Skip OCR. |
| `clipping` | Newspaper / magazine clipping (multi-column, dense, image-like) |
| `photo` | Photograph or photo-like image (faces, scenes, vehicles, sky) |
| `mixed` | Multiple kinds on the same page; pick the dominant one |

### Heuristics (starting point — refine as you go)

In `classify.py` the starter uses:
1. Render page at 100 DPI → numpy array.
2. Black-pixel density. Very low → `blank` / `divider`.
3. Connected-component analysis on text-like blobs to spot regular line
   spacing → `typewritten`.
4. Histogram of brightness — bimodal continuous regions → `photo`.
5. Many short horizontal text lines + image regions → `clipping`.
6. Irregular ascender heights / variable stroke widths → `handwritten`.

These are coarse. Adjust thresholds against a sample of files you visually
inspect before bulk-running. The user can help you eyeball outputs.

## Repo size budget

- Previews: 4-6 JPEGs per file × 158 files × ~80 KB target = **~50-60 MB**.
  Render at 250 DPI as JPEG quality 75, target ≤ 100 KB each.
- OCR text in `text_preview_en` is inline in `manifest.json` (~3 KB each
  × 158 = ~500 KB). That's fine.
- Don't commit:
  - `data/release_01/raw/` (raw PDFs — already in `.gitignore`)
  - `data/_classification/*.json` (per-file classification dumps — keep
    locally for re-runs but don't push)
  - `data/_ocr/*.txt` (full OCR dumps — local cache only)
- Do commit:
  - `data/previews/{id}/p*.jpg`
  - The updated `data/manifest.json`

## Pipeline order

1. **classify.py** — walks every PDF, renders every page at 100 DPI, writes
   `data/_classification/{id}.json` with one entry per page (`page`, `kind`,
   `score`, plus a few raw metrics for debugging).
2. **sample.py** — reads the classification JSONs, picks the 4-6 best
   pages per file, re-renders those at 300 DPI as compressed JPEG,
   writes them to `data/previews/{id}/p{NNN}.jpg`. Updates manifest with
   `preview_pages` and `content_kinds`.
3. **ocr.py** — for every page classified `typewritten` (or `clipping` if
   you can extract column text), runs `pytesseract` and concatenates
   results. Updates manifest with `text_preview_en` (first 3000 chars,
   sentence-aligned cut).
4. **pipeline.py** — runs all three in sequence with a progress bar.

Each script is **idempotent** and **resumable**. If `data/_classification/{id}.json`
exists, skip. If a preview JPEG already exists, skip. The user can interrupt
and resume.

## Quality bar before you commit

- Spot-check 8-10 random files: open the preview JPEGs. Do they look like
  meaningful content (not all covers, not all blanks)?
- Check that `text_preview_en` for at least 5 random files reads as
  coherent English. If OCR confidence is consistently low (<60), skip the
  file (set `text_preview_en` to `null`) — bad OCR is worse than none.
- Verify `data/manifest.json` is still valid JSON and `total_files` is
  still 158.
- Verify `apply_translations.py` still passes (don't break existing translations).

## Delivery

When you're satisfied:

```bash
git add data/manifest.json data/previews/
git status   # confirm no stray binaries / huge files
git commit -m "data: extract page classifications + preview thumbnails + OCR text"
git push origin claude/local-extraction-run-N   # any branch name
```

Then open a PR titled "Phase 2 extraction: previews + OCR".

The remote Claude (the one running in the user's web/cloud session) will
review, integrate into the UI, and translate `text_preview_en` →
`text_preview_he` in a follow-up.

## What NOT to do

- Don't translate to Hebrew. That's the remote Claude's job (cost goes
  through the user's Claude Code quota; we set it up that way deliberately).
- Don't modify `index.html`, `assets/`, `apply_translations.py`,
  `browser_scrape.js`. They're stable.
- Don't try to run OCR on handwritten or photo pages — it produces gibberish.
- Don't commit raw PDFs or per-page classification JSONs.

## If anything is unclear

The remote Claude's working notes are in the conversation history at
`claude.ai/code/session_01X7tLrZZwaCb78srULaBwUC`. The user can paste a
question to the remote session and bring an answer back. But ideally the
starter scripts + this brief are self-sufficient.

Good luck. Make it look like actual primary-source archaeology.
