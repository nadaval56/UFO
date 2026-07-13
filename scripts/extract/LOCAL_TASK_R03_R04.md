# Local task — Release 03 + 04 (previews + OCR + video), one paste

> Paste EVERYTHING below the line into a **local Claude Code** session on your
> own computer. Replace the one DVIDS-key placeholder. Claude does the rest and
> gives you a single zip to send back. You don't run any commands yourself.

---

You are Claude Code running **locally on my machine**. You're helping with the
PURSUE Hebrew mirror (`github.com/nadaval56/UFO`) — a Hebrew RTL mirror of
`war.gov/UFO`. war.gov, its CloudFront videos, and the DVIDS API are all
reachable from here but blocked from the remote cloud session, so this whole
job runs locally. Do everything below yourself; only ask me when a step needs
my input (a download that 403s, or the DVIDS key). **Do not translate anything
and do not `git push`** — Hebrew and integration happen remotely. Produce one
zip at the end.

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

# get the code + current data (the FEATURE branch, not main)
git clone -b claude/us-gov-updates-sync-fyt1sk https://github.com/nadaval56/UFO.git
cd UFO
```

Read `scripts/extract/EXTRACT.md` — it's the full method and the two quality
policies (what counts as an "interesting" preview; OCR every typewritten page).

## Part A — page previews + OCR (the ~67 new PDFs)

```bash
mkdir -p raw output/previews output/_classification output/_ocr
cp data/manifest.json output/manifest.json

# the two DOCUMENT bundles (ignore videos here)
curl -L -o r03.zip "https://www.war.gov/medialink/ufo/061226/release_03/release_03_documents.zip"
curl -L -o r04.zip "https://www.war.gov/medialink/ufo/071026/release_04/release_04_documents_071026.zip"
unzip -o r03.zip -d raw/ ; unzip -o r04.zip -d raw/
find raw -iname '*.pdf' | wc -l      # expect ~67
```

(If `curl` 403s, tell me — I'll download the two zips in a browser and drop them
into `raw/`.)

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

## Part B — video (the new DVIDS videos)

```bash
export DVIDS_API_KEY="<paste the same key here>"
python scripts/fetch_dvids.py          # harvests all UAPVIDEOS assets → data/dvids/uap_videos.json
```

Sanity-check it captured the new videos with non-empty `files` lists:

```bash
python -c "import json;d=json.load(open('data/dvids/uap_videos.json'));print(len(d),'assets');print(sum(1 for v in d.values() if v.get('files')),'with playable files')"
```

Do **not** run the merge — the remote session does that against the translated
manifest.

## Quality check (EXTRACT.md → Step 4)

- Random 10 files: previews are interesting content, not boring scans. A file
  with nothing interesting → empty `preview_pages` (don't pad).
- Random 5 `text_en`: coherent English.
- `du -sh output/previews/` ≈ 30–70 MB (if much bigger, lower DPI/quality).
- After writing `output/manifest.json`, re-read it and confirm Hebrew strings
  round-trip (UTF-8, no mojibake).

## Hand back — ONE zip

```bash
cp data/dvids/uap_videos.json output/uap_videos.json
cd output
zip -r ../release_03_04_bundle.zip manifest.json previews/ uap_videos.json
cd ..
ls -lh release_03_04_bundle.zip
```

Send me **`release_03_04_bundle.zip`**. That's it.

### What the remote session takes from it

- For each Release 03/04 id: `page_count`, `content_kinds`, `preview_pages`,
  `preview_pages_fallback`, `text_en`, `text_preview_en` + the `previews/{id}/*.jpg`.
- `uap_videos.json` → remote runs `merge_dvids_videos.py` to add inline playback.

Nothing else from your `manifest.json` is used, so stale Hebrew fields are fine.
Reminder: do not translate, do not `git push`.
