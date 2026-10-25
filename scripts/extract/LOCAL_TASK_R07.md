# Local task — Release 07 (scrape + previews + OCR), one paste

> Paste EVERYTHING below the line into a **local Claude Code** session on your
> own computer. Claude does the rest and gives you a single zip to send back. You don't run any commands yourself.
>
> Why local: war.gov (Akamai) refuses cloud IPs, and the Claude Code web sandbox blocks them at the egress
> proxy too. Your home browser is the only environment that can reach any of it.

---

You are Claude Code running **locally on my machine**. You're helping with the
PURSUE Hebrew mirror (`github.com/nadaval56/UFO`) — a Hebrew RTL mirror of
`war.gov/UFO`. The mirror currently holds **450 files across Releases 01–06**.
**Release 07 was published on 23 October 2026 (28 files, confirmed on the page;
the R07 tab says "NO VIDEOS", so expect PDFs only - confirm agencies and types
off the page) and is missing.**
Your job: bring back everything needed to add it.

**Before anything else, check the war.gov RELEASE tabs.** If there is also a
Release 08 (or later) by now, do every step below for *each* missing release
and tell me in your final message which ones you covered.

war.gov is reachable from here but blocked from the remote cloud session, so
this whole job runs locally. Do everything below yourself; only ask me when a
step needs my input (a download that 403s). **Do not translate anything and do not `git push`** — Hebrew and
integration happen remotely. Produce one zip at the end.

## Setup

```bash
# system tools (macOS shown; Linux: sudo apt install poppler-utils tesseract-ocr;
# Windows: use WSL, or install Poppler + Tesseract and add both to PATH)
brew install poppler tesseract
pip install pdf2image PyMuPDF Pillow numpy pytesseract tqdm requests

git clone https://github.com/nadaval56/UFO.git
cd UFO
```

Read `scripts/extract/EXTRACT.md` — it's the full method and the two quality
policies (what counts as an "interesting" preview; OCR every typewritten page).

## Part A — scrape war.gov (this is the step that unblocks everything)

Release 07's file list only exists on the live page, so this comes first.

If you have the Claude app's built-in browser, run steps 1-5 there yourself;
otherwise walk me through them in my own browser and wait for the download.

1. Open <https://www.war.gov/UFO/> in the browser.
2. Set the table filters to `ALL AGENCIES`, **`RELEASE 07`**, `ALL TYPES`.
   An incremental scrape is enough: `merge_release.py` matches new rows against
   the existing manifest, so scraping only the new tranche merges identically to
   a full 478-row scrape (see README). If you are also covering a Release 08+,
   either scrape each release separately or set `ALL RELEASES`.
3. DevTools (F12) → Console.
4. Paste the entire contents of `scripts/browser_scrape.js` (**v4** — it reads
   the RELEASE column from each row, the only reliable per-file release signal
   for video/audio rows) and press Enter.
5. It walks every page and downloads `manifest.json`. It prints a per-release
   tally when it finishes — **check that it shows `release_07` with ~28
   records** before moving on.

If the tally shows no `release_07`, or far fewer than 28, stop and tell me — it
means the RELEASE column changed format again and the scraper needs a fix first.
The page says Release 07 has no videos. If the tally nevertheless shows any
video/audio/image rows, keep them and mention them in your final message.

Then fold the scrape into the existing manifest:

```bash
mkdir -p output
cp ~/Downloads/manifest.json ./scrape.json
python scripts/merge_release.py --new scrape.json --dry-run
```

`merge_release.py` keeps every already-enriched Release 01–06 record untouched
and appends only genuinely-new rows, assigning `release`/`release_no` from
chronological date order — so Release 07 becomes `release_07` on its own. The
dry run should report roughly **28 new records** and list `release_07`. If it
reports far more, title matching is failing and records are about to be
duplicated — stop and tell me.

Two things to watch for, both new in this release:

- Check any **new agency** gets a sensible `agency` value (not blank, not merged into DOW).
- The document dates run 1952–2025; that's the documents, not the release.
  `release_date` must be 10/23/26 for all of them.

When the dry run looks right:

```bash
python scripts/merge_release.py --new scrape.json
cp data/manifest.json output/manifest.json
```

> **If you only have time for one thing, do Part A.** The scrape alone gets all
> 28 files listed, titled, filtered, searchable and translatable on the site —
> it just leaves them without page previews or OCR text. Part B is enrichment
> and can follow in a second pass. In that case, hand back
> `data/manifest.json` after the merge and stop there.

## Part B — page previews + OCR (the new Release 07 PDFs)

The documents bundle (325 MB, read off the war.gov page by the user):
`https://www.war.gov/medialink/ufo/release-07/documents_release_07_oct_23_2026.zip`
There is no video bundle for this release.

```bash
mkdir -p raw output/previews output/_classification output/_ocr
curl -L -o r07.zip "https://www.war.gov/medialink/ufo/release-07/documents_release_07_oct_23_2026.zip"
unzip -o r07.zip -d raw/
find raw -iname '*.pdf' | wc -l      # expect 28
```

(If `curl` 403s, download it in the browser and drop it into `raw/`.)

Release 07 is all documents (28 PDFs, 325 MB): field reports, investigation
reports (Skinwalker Ranch), 1940s-50s sighting files and NASA/DoD coordination
memos - mostly typed pages. Expect OCR to dominate the runtime.

Smoke-test 3 files, **open the previews and look at them**, tune the classifier
per EXTRACT.md until the preview pool is genuinely interesting content (photos,
sky/scene, clippings, sketches, diagrams — never plain typed-text scans), then
do the full run. `pipeline.py` now forwards the path options to each step:

```bash
# smoke test
python scripts/extract/pipeline.py --raw-dir ./raw --limit 3 \
  --manifest output/manifest.json --class-dir output/_classification \
  --preview-dir output/previews --ocr-dir output/_ocr
# ...inspect output/previews/*/ , tune, then full run:
python scripts/extract/pipeline.py --raw-dir ./raw \
  --manifest output/manifest.json --class-dir output/_classification \
  --preview-dir output/previews --ocr-dir output/_ocr
# then fallback previews for documents with no curated page:
python scripts/extract/fallback_previews.py --raw-dir ./raw \
  --manifest output/manifest.json --class-dir output/_classification \
  --preview-dir output/previews
```

Resumable (Ctrl+C safe). `ocr.py` gate is confidence ≥ 45 plus the wordish
filters; first ~3000 sentence-aligned chars go into `text_preview_en`.

**Known defect to watch:** `page_metrics` thresholds ink at an absolute
`arr < 180`, so pages on strongly tinted paper read as all-ink and can be
misclassified as `photo` and skipped by OCR (`wants_ocr()` only patches part of
this). If you see typed pages on coloured stock with no OCR text, list their ids
in your final message — don't rewrite the metric here.

## Quality check (EXTRACT.md → Step 4)

- Random 10 files: previews are interesting content, not boring scans. A file
  with nothing interesting → empty `preview_pages` (don't pad).
- Random 5 `text_en`: coherent English.
- `du -sh output/previews/` ≈ 10–30 MB for R07 alone (if much bigger, lower
  DPI/quality).
- After writing `output/manifest.json`, re-read it and confirm Hebrew strings
  round-trip (UTF-8, no mojibake) — the Release 01–06 translations are in there
  and must survive.
- `python -c "import json;m=json.load(open('output/manifest.json'));print(m['total_files']);print([r for r in m['releases']])"`
  → total ~478, and a `release_07` entry with ~28 files.

## Hand back — ONE zip

```bash
cd output
zip -r ../release_07_bundle.zip manifest.json previews/
cd ..
ls -lh release_07_bundle.zip
```

Send me **`release_07_bundle.zip`**. That's it.

### What the remote session takes from it

- The merged `manifest.json` — Release 07 records with `release`/`release_no`
  already assigned, plus `page_count`, `content_kinds`, `preview_pages`,
  `preview_pages_fallback`, `text_en`, `text_preview_en` — and the
  `previews/{id}/*.jpg` images.

Then remotely: Hebrew translation of the 28 new records (`title_he`,
`agency_he`, `incident_location_he`, `summary_he`, `narrative_he`, `text_he`),
and clearing the Release 07 entry from `data/pending.json` so the
"published but not yet mirrored" notice disappears.

Reminder: do not translate, do not `git push`.
