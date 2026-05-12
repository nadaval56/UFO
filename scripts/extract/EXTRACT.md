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
preview thumbnails of *visually interesting* content, and full OCR text**
so the public site can show "what's inside" before users download
multi-hundred-page PDFs.

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

## ⚠️ Two important policy points

**1. Preview goal: "what visually interesting content is inside?"**
The preview thumbnails are meant to make a viewer want to open the file.
A boring scan of a typewritten memo does NOT achieve that. The user is
specifically looking for: photographs (UAP, sky, witnesses, vehicles,
scenes), newspaper/magazine clippings, hand-drawn sketches and witness
illustrations, diagrams. **Pages that are 100% typed text or 100% covers
or 100% handwriting are EXCLUDED from previews, full stop, even if a file
has nothing else to offer.** Better that a file shows zero previews than
that it shows 4 boring document scans.

**2. OCR scope: every typewritten page, not a sample.**
You used to be told "top 3 typewritten pages per file" — that was too
conservative. The right behavior is OCR every page classified as
`typewritten` (and where you trust the OCR confidence ≥60). Concatenate
them per file. Store the full text in a new field `text_en`, and store
the first 3000 chars (sentence-aligned) in `text_preview_en` for the UI.
Yes, this means the full run is slower — that's fine.

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

## ⚠️ File encoding — write UTF-8 explicitly

When you write `output/manifest.json` make sure you use `utf-8` encoding
(in Python: `open(path, "w", encoding="utf-8")` and
`json.dump(..., ensure_ascii=False)`). The remote Claude has seen one of
your previous runs ship with the Hebrew strings mojibake-corrupted — that
costs the user a manual repair step. Test it: after writing, re-read and
verify that any string containing Hebrew round-trips identically.

## Step 2 — smoke-test on 3 files

Don't process all 158 first. Pick 3-5 representative files (ideally
including one with photos / clippings, one with mostly typed reports, and
one with handwritten content) and run:

```bash
python scripts/pipeline.py --raw-dir ./Release_1 --limit 3 \
  --manifest output/manifest.json \
  --class-dir output/_classification \
  --preview-dir output/previews \
  --ocr-dir output/_ocr
```

Then **open the previews visually** (`open output/previews/*/`). Are they
**photos / clippings / sketches** — visually interesting content? If
you're seeing typed-document scans in the preview pool, **the classifier
is mis-labeling them as `photo` or `clipping` and you must tighten it.**
Common adjustments for scanned investigation files:

- `dark_ratio` thresholds shift down for grey/yellowed scans
- `line_peaks` threshold for `typewritten` may need lowering — old typewriter
  ribbons leave fainter rows
- `midtone_ratio` for `photo` may need to go up — scanned typed pages have
  many midtone pixels too, so 0.35 isn't enough alone; consider also requiring
  large connected non-text regions or absence of regular line spacing
- Add a "stamp/seal" pre-filter: pages with very dark concentrated regions
  but no line structure are often stamps/labels — reclassify as `cover`
- **Add a "false-positive photo" guard**: if a page is classified `photo`
  but has `line_peaks` >= 20, it's actually a scanned text page. Reclassify
  as `typewritten`.

When you tune, re-run on the same 3 files and inspect again. Iterate
until you trust the classification. **Do not start the full run until
you're seeing genuinely interesting visual content in the preview pool.**

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
~5-15 hours for OCR on 158 files × every typewritten page × 5-15
sec/page. (Yes, OCR is slow; this is normal. The OCR step is resumable —
interrupt with Ctrl+C and re-run any time.)

The pipeline is **resumable**. Interrupt with Ctrl+C anytime, resume by
running again — already-done files are skipped.

## Step 4 — quality check

Before handing back the output, spot-check:

1. **Random 10 files**: open `output/previews/{id}/` for each.
   - Do the thumbnails show **photos / clippings / sketches**? Not
     typed-document scans?
   - If a file has NO interesting visual content, it should have an
     empty/missing `preview_pages` (better than padding with boring scans).
2. **Random 5 files** with `text_en`: read it. Coherent
   English? OCR errors are fine; gibberish is not.
3. **manifest.json sanity**:
   - `total_files` still 158
   - No entry lost any existing field
   - Hebrew round-trips correctly (open the file, find any `summary_he`
     value, eyeball: is it Hebrew letters or Latin garbage?)
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
the previews + text into the site, translate text_preview_en /
text_en to Hebrew, commit and push."

Don't include `_classification/` or `_ocr/` in the zip — those are local
caches for resumability, not part of the deliverable.

## Output schema (what gets added to manifest.json)

Per `files[i]`, add only these fields. Don't touch existing ones, and
**never write Hebrew translations** (`title_he`, `agency_he`,
`incident_location_he`, `summary_he`, `text_preview_he`). The remote
session owns translations.

```jsonc
{
  // ... all existing fields unchanged, INCLUDING existing summary_he etc. ...

  "page_count": 247,

  "content_kinds": ["typewritten", "photo", "clipping", "handwritten"],
  // Deduped, ordered by descending count of pages of each kind.

  "preview_pages": [
    { "page": 23,  "kind": "photo",       "path": "data/previews/059uap00012/p023.jpg" },
    { "page": 87,  "kind": "clipping",    "path": "data/previews/059uap00012/p087.jpg" }
    // ONLY photo / clipping / illustration kinds. Up to 6.
    // If a file has none of these kinds, preview_pages is an empty list [].
  ],

  "text_en":         "Full concatenated OCR text from all typewritten pages...",
  "text_preview_en": "First 3000 chars (sentence-aligned cut) for the UI excerpt.",
  "text_preview_he": null,    // ← do NOT fill. Remote Claude handles translations.

  "_extracted_at": "2026-05-12T15:00:00Z"
}
```

### Allowed `kind` values

`cover` · `blank` · `divider` · `typewritten` · `handwritten` · `clipping`
· `photo` · `illustration` · `mixed`

**For `preview_pages`, ONLY use `photo`, `clipping`, or `illustration`.**
Never include `typewritten` / `mixed` / `handwritten` / `cover` / `blank`
/ `divider` in `preview_pages`, even as a fallback when nothing else is
available. If nothing visually interesting exists in a file, the file
simply has no previews.

### Illustration kind (new)

Hand-drawn sketches and witness drawings count as `illustration` —
distinct from `photo` (photographic) and `clipping` (printed media).
Witness illustrations of UAP shapes are exactly the kind of content the
user wants in previews.

## What NOT to do

- Don't translate to Hebrew. (Cost goes through the remote session's
  Claude Code quota, which is what the user wants.)
- Don't push to GitHub directly even if you have credentials. The user
  prefers reviewing your output in the zip before integration.
- Don't try to OCR `handwritten` or `photo` pages — output is gibberish.
- Don't render at >300 DPI for previews. 250-300 DPI is plenty.
- Don't include raw PDFs or the per-page `_classification` JSONs in the
  zip you hand back — they're caches.
- **Don't pad `preview_pages` with boring kinds to hit a target count.**
  Empty is better than misleading.

## When you finish

Tell the user the path to `extraction_output.zip`, summarize what you
did (e.g. "158/158 files processed, 87 had at least one photo / clipping
/ illustration in their preview pool, the remaining 71 are pure
document/handwritten content so preview_pages is empty for them; 142
files produced OCR text; 16 files had only handwritten content and got
no text_en"). Then stop — the remote Claude takes over from there.

Good luck. Make it look like archaeology.
