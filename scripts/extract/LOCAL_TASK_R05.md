# Local task — Release 05 (scrape + previews + OCR + video), one paste

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
`war.gov/UFO`. The mirror currently holds **334 files across Releases 01–04**.
**Release 05 was published on 7 August 2026 (41 files) and is missing entirely.**
Your job: bring back everything needed to add it.

war.gov, CloudFront and DVIDS are reachable from here but blocked from the
remote cloud session, so this whole job runs locally. Do everything below
yourself; only ask me when a step needs my input (a download that 403s, or the
DVIDS key). **Do not translate anything and do not `git push`** — Hebrew and
integration happen remotely. Produce one zip at the end.

My DVIDS API key (for the video step):

```
DVIDS_API_KEY = <<PASTE YOUR DVIDS API KEY HERE — from your dvidshub.net email>>
```

If that placeholder is still there or the key doesn't work, tell me and I'll get
one from https://api.dvidshub.net/ (free, instant registration).

## Setup

```bash
# system tools (macOS shown; Linux: sudo apt install poppler-utils tesseract-ocr)
brew install poppler tesseract
pip install pdf2image PyMuPDF Pillow numpy pytesseract tqdm requests

git clone https://github.com/nadaval56/UFO.git
cd UFO
```

Read `scripts/extract/EXTRACT.md` — it's the full method and the two quality
policies (what counts as an "interesting" preview; OCR every typewritten page).

## Part A — scrape war.gov (this is the step that unblocks everything)

Release 05's file list only exists on the live page, so this comes first.

1. Open <https://www.war.gov/UFO/> in your browser.
2. **Set all three table filters to ALL** — `ALL AGENCIES`, `ALL RELEASES`,
   `ALL TYPES`. The scraper only sees what the table shows; if the table is
   filtered to one release you will silently get a partial scrape.
3. DevTools (F12) → Console.
4. Paste the entire contents of `scripts/browser_scrape.js` (**v4** — it reads
   the RELEASE column from each row, which is the only reliable per-file
   release signal for video/audio rows) and press Enter.
5. It walks every page and downloads `manifest.json`. It prints a per-release
   tally when it finishes — **check that it shows `release_05` with ~41
   records** before moving on. Expect ~375 rows in total.

If the tally shows no `release_05`, or shows far fewer than 41, stop and tell me
— it means the RELEASE column changed format again (this broke once before, in
July 2026) and the scraper needs a fix before anything else is worth doing.

Then fold the scrape into the existing manifest:

```bash
mkdir -p output
cp ~/Downloads/manifest.json ./scrape.json
python scripts/merge_release.py --new scrape.json --dry-run
```

`merge_release.py` keeps every already-enriched Release 01–04 record untouched
and appends only genuinely-new rows, assigning `release`/`release_no` from
chronological date order — so Release 05 becomes `release_05` on its own. The
dry run should report roughly **41 new records** and list `release_05` in the
summary. If it reports far more, the canonical-title matching is failing and
records are about to be duplicated — stop and tell me.

When the dry run looks right:

```bash
python scripts/merge_release.py --new scrape.json
cp data/manifest.json output/manifest.json
```

## Part B — page previews + OCR (the new Release 05 PDFs)

```bash
mkdir -p raw output/previews output/_classification output/_ocr
```

Download the Release 05 **document** bundle. The exact URL is not known — every
release has used a different path, so **read it off the page** rather than
guessing: on war.gov/UFO the download buttons sit above the table. For
reference, the previous releases were:

```
R02 docs  https://www.war.gov/medialink/ufo/052226/release_02/release_02_document_bundle.zip
R03 docs  https://www.war.gov/medialink/ufo/061226/release_03/release_03_documents.zip
R04 docs  https://www.war.gov/medialink/ufo/071026/release_04/release_04_documents_071026.zip
R02 video https://d34w7g4gy10iej.cloudfront.net/uap052226.zip
R03 video https://d34w7g4gy10iej.cloudfront.net/release_03/uap_videos_061226.zip
R04 video https://d34w7g4gy10iej.cloudfront.net/release_04/uap_release04_videos_071026.zip
```

**Tell me both Release 05 URLs once you have them** — the remote session needs
them for the download buttons, and a guessed URL has already shipped broken once
(PR #39 existed only to fix invented R02 bundle links).

```bash
curl -L -o r05.zip "<THE RELEASE 05 DOCUMENT BUNDLE URL>"
unzip -o r05.zip -d raw/
find raw -iname '*.pdf' | wc -l      # expect roughly 20-25 (the rest are video)
```

(If `curl` 403s, download it in the browser and drop it into `raw/`.)

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
```

Resumable (Ctrl+C safe). OCR every typewritten page (confidence ≥ 60) into
`text_en`, first ~3000 sentence-aligned chars into `text_preview_en`.

Release 05 is video-heavy (16 DOW videos of the 41), so expect fewer PDFs than
Release 03 — that's correct, not a failed download.

## Part C — video (the new DVIDS videos)

```bash
export DVIDS_API_KEY="<paste the same key here>"
python scripts/fetch_dvids.py          # harvests all UAPVIDEOS assets → data/dvids/uap_videos.json
```

Sanity-check it captured the new videos with non-empty `files` lists:

```bash
python -c "import json;d=json.load(open('data/dvids/uap_videos.json'));print(len(d),'assets');print(sum(1 for v in d.values() if v.get('files')),'with playable files')"
```

The Gulf of Oman AC-130J material (six clips) should be in there. Do **not** run
`merge_dvids_videos.py` — the remote session does that against the translated
manifest.

## Quality check (EXTRACT.md → Step 4)

- Random 10 files: previews are interesting content, not boring scans. A file
  with nothing interesting → empty `preview_pages` (don't pad).
- Random 5 `text_en`: coherent English.
- `du -sh output/previews/` ≈ 10–30 MB for R05 alone (if much bigger, lower
  DPI/quality).
- After writing `output/manifest.json`, re-read it and confirm Hebrew strings
  round-trip (UTF-8, no mojibake) — the Release 01–04 translations are in there
  and must survive.
- `python -c "import json;m=json.load(open('output/manifest.json'));print(m['total_files']);print([r for r in m['releases']])"`
  → total ~375, and a `release_05` entry with ~41 files.

## Hand back — ONE zip

```bash
cp data/dvids/uap_videos.json output/uap_videos.json
cd output
zip -r ../release_05_bundle.zip manifest.json previews/ uap_videos.json
cd ..
ls -lh release_05_bundle.zip
```

Send me **`release_05_bundle.zip`**, plus the two Release 05 bundle URLs from
Part B. That's it.

### What the remote session takes from it

- The merged `manifest.json` — Release 05 records with `release`/`release_no`
  already assigned, plus `page_count`, `content_kinds`, `preview_pages`,
  `preview_pages_fallback`, `text_en`, `text_preview_en` — and the
  `previews/{id}/*.jpg` images.
- `uap_videos.json` → remote runs `merge_dvids_videos.py` to add inline playback.
- The two bundle URLs → the Release 05 download column in `index.html`.

Then remotely: Hebrew translation of the 41 new records (`title_he`,
`agency_he`, `incident_location_he`, `summary_he`, `narrative_he`, `text_he`),
and clearing the Release 05 entry from `data/pending.json` so the
"published but not yet mirrored" notice disappears.

Reminder: do not translate, do not `git push`.
