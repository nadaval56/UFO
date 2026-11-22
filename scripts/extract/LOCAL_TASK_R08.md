# Local task — Release 08 (scrape + bundle URLs + previews + OCR + video), one paste

> Paste EVERYTHING below the line into a **local Claude Code** session on your
> own computer. Replace the one DVIDS-key placeholder. Claude does the rest and
> gives you a single zip to send back. You don't run any commands yourself.
>
> Why local: war.gov (Akamai), its CloudFront video host and the DVIDS API all
> refuse cloud IPs, and the Claude Code web sandbox blocks them at the egress
> proxy too. Your home browser is the only environment that can reach any of it.

---

You are Claude Code running **locally on my machine**. You're helping with the
PURSUE Hebrew mirror (`github.com/nadaval56/UFO`) — a Hebrew RTL mirror of
`war.gov/UFO`. The mirror currently holds **478 files across Releases 01–07**.
**Release 08 was published on 20 November 2026 and is missing.** Press reports
**43 files: 40 documents and 3 videos, from DoW and the CIA** (archive total
521). Highlights: a 1952 CIA evaluation of flying-saucer reports, a 1953
sighting of a dark elliptical object by Lockheed engineer Kelly Johnson, and
three CENTCOM videos (Middle East, 2020 / 2023 / 2026) submitted to AARO.
These counts come from the press, not the page — confirm them off war.gov.
Your job: bring back everything needed to add it.

**Before anything else, check the war.gov RELEASE tabs.** If there is also a
Release 09 (or later) by now, do every step below for *each* missing release
and tell me in your final message which ones you covered.

war.gov, CloudFront and DVIDS are reachable from here but blocked from the
remote cloud session, so this whole job runs locally. Do everything below
yourself; only ask me when a step needs my input (a download that 403s, or the
DVIDS key). **Do not translate anything and do not `git push`** — Hebrew and
integration happen remotely. Work on `main` (do not check out any other
branch). Produce one zip at the end.

My DVIDS API key (for the video step):

```
DVIDS_API_KEY = <<PASTE YOUR DVIDS API KEY HERE — from your dvidshub.net email>>
```

If that placeholder is still there or the key doesn't work, tell me and I'll get
one from https://api.dvidshub.net/ (free, instant registration). Never write the
key into any file in the repo.

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
`RELEASE_PROCESS.md` describes the whole release workflow end to end.

## Part A — scrape war.gov + read the bundle URLs (this unblocks everything)

Release 08's file list and download links only exist on the live page, so this
comes first.

If you have the Claude app's built-in browser, run steps 1-6 there yourself;
otherwise walk me through them in my own browser and wait for the download.

1. Open <https://www.war.gov/UFO/> in the browser.
2. **Read the Release 08 bundle download URLs off the page** (the documents zip
   and, if there is one, the videos zip — usually the CloudFront host
   `d34w7g4gy10iej.cloudfront.net`). Copy them exactly. **Never guess or
   construct them**: war.gov has used a different path scheme for almost every
   release. Report both URLs (and the bundle sizes if shown) in your final
   message. If the R08 tab says "NO VIDEOS", say so.
3. Set the table filters to `ALL AGENCIES`, **`RELEASE 08`**, `ALL TYPES`.
   An incremental scrape is enough: `merge_release.py` matches new rows against
   the existing manifest, so scraping only the new tranche merges identically to
   a full ~521-row scrape (see README). If you are also covering a Release 09+,
   either scrape each release separately or set `ALL RELEASES`.
4. DevTools (F12) → Console.
5. Paste the entire contents of `scripts/browser_scrape.js` (**v4** — it reads
   the RELEASE column from each row, the only reliable per-file release signal
   for video/audio rows) and press Enter.
6. It walks every page and downloads `manifest.json`. It prints a per-release
   tally when it finishes — **check that it shows `release_08` with ~43
   records** before moving on.

If the tally shows no `release_08`, or far fewer than 43, stop and tell me — it
means the RELEASE column changed format again and the scraper needs a fix first.
Video rows only have a `#fragment` URL; make sure the 3 videos are in the tally.

Then fold the scrape into the existing manifest:

```bash
mkdir -p output
cp ~/Downloads/manifest.json ./scrape.json
python scripts/merge_release.py --new scrape.json --dry-run
```

`merge_release.py` keeps every already-enriched Release 01–07 record untouched
and appends only genuinely-new rows, assigning `release`/`release_no` from
chronological date order — so Release 08 becomes `release_08` on its own. The
dry run should report roughly **43 new records** and list `release_08`. If it
reports far more, title matching is failing and records are about to be
duplicated — stop and tell me.

Things to watch for:

- The **CIA** has been in PURSUE before; check its rows get the same `agency`
  value as earlier CIA rows. Any genuinely **new agency** must get a sensible
  `agency` value (not blank, not merged into DOW) — list it in your final
  message, it will need a Hebrew label.
- The document dates are the documents' (1950s onward), not the release.
  `release_date` must be 11/20/26 for all of them.

When the dry run looks right:

```bash
python scripts/merge_release.py --new scrape.json
cp data/manifest.json output/manifest.json
```

> **If you only have time for one thing, do Part A.** The scrape alone gets all
> 43 files listed, titled, filtered, searchable and translatable on the site —
> it just leaves them without page previews, OCR text or inline video. Parts B
> and C are enrichment and can follow in a second pass. In that case, hand back
> `data/manifest.json` after the merge plus the two bundle URLs, and stop there.

## Part B — page previews + OCR (the new Release 08 PDFs)

Use the **documents bundle URL you read off the page in Part A step 2**:

```bash
mkdir -p raw output/previews output/_classification output/_ocr
curl -L -o r08.zip "<R08 DOCUMENTS BUNDLE URL FROM THE PAGE>"
unzip -o r08.zip -d raw/
find raw -iname '*.pdf' | wc -l      # expect ~40
```

(If `curl` 403s, download it in the browser and drop it into `raw/`.)
Only the document bundle is needed here — the site links to the video bundle
rather than processing it.

Smoke-test 3 files, **open the previews and look at them**, tune the classifier
per EXTRACT.md until the preview pool is genuinely interesting content (photos,
sky/scene, clippings, sketches, diagrams — never plain typed-text scans), then
do the full run:

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
this). In Release 07, normalising each page to its own paper tone before
tesseract recovered blank-reading typed pages; you may do that locally again.
If you see typed pages on coloured stock with no OCR text, list their ids in
your final message — don't rewrite the metric in the repo.

## Part C — video (the 3 new DVIDS videos)

```bash
export DVIDS_API_KEY="<paste the same key here>"
python scripts/fetch_dvids.py          # harvests all UAPVIDEOS assets → data/dvids/uap_videos.json
```

`fetch_dvids.py` scrubs `api_key=` from every string before writing — check
`grep -c api_key data/dvids/uap_videos.json` prints 0. Then sanity-check it
captured the new videos with non-empty `files` lists:

```bash
python -c "import json;d=json.load(open('data/dvids/uap_videos.json'));print(len(d),'assets');print(sum(1 for v in d.values() if v.get('files')),'with playable files')"
```

The 3 Release 08 CENTCOM videos should be in there (DVIDS sometimes publishes a
few days after war.gov; if they are missing, say so). Do **not** run
`merge_dvids_videos.py` — the remote session does that against the translated
manifest.

## Quality check (EXTRACT.md → Step 4)

- Random 10 files: previews are interesting content, not boring scans. A file
  with nothing interesting → empty `preview_pages` (don't pad).
- Random 5 `text_en`: coherent English.
- `du -sh output/previews/` ≈ 10–30 MB for R08 alone (if much bigger, lower
  DPI/quality).
- After writing `output/manifest.json`, re-read it and confirm Hebrew strings
  round-trip (UTF-8, no mojibake) — the Release 01–07 translations are in there
  and must survive.
- `python -c "import json;m=json.load(open('output/manifest.json'));print(m['total_files']);print([r for r in m['releases']])"`
  → total ~521, and a `release_08` entry with ~43 files.

## Hand back — ONE zip + two URLs

```bash
cp data/dvids/uap_videos.json output/uap_videos.json
cd output
zip -r ../release_08_bundle.zip manifest.json previews/ uap_videos.json
cd ..
ls -lh release_08_bundle.zip
```

Send me **`release_08_bundle.zip`**, and in your final message the **two
Release 08 bundle URLs** exactly as they appear on war.gov (documents, videos).

### What the remote session takes from it

- The merged `manifest.json` — Release 08 records with `release`/`release_no`
  already assigned, plus `page_count`, `content_kinds`, `preview_pages`,
  `preview_pages_fallback`, `text_en`, `text_preview_en` — and the
  `previews/{id}/*.jpg` images.
- `uap_videos.json` → remote runs `merge_dvids_videos.py` to add inline playback.
- The bundle URLs → `data/pending.json` now, the download column in `index.html`
  once merged.

Then remotely: Hebrew translation of the new records, extended summaries
(`data/digest/`), and clearing the Release 08 entry from `data/pending.json` so
the "published but not yet mirrored" notice disappears.

Reminder: do not translate, do not `git push`.
