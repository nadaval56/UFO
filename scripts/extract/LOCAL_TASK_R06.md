# Local task — Release 06 (scrape + previews + OCR + video), one paste

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
`war.gov/UFO`. The mirror currently holds **375 files across Releases 01–05**.
**Release 06 was published on 18 September 2026 (71 files: 55 PDF, 15 video,
1 audio — 67 from DoW, 4 from Colorado local law enforcement) and is missing.**
Your job: bring back everything needed to add it.

**Before anything else, check the war.gov RELEASE tabs.** If there is also a
Release 07 (or later) by now, do every step below for *each* missing release
and tell me in your final message which ones you covered.

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

## Part A — scrape war.gov (this is the step that unblocks everything)

Release 06's file list only exists on the live page, so this comes first.

1. Open <https://www.war.gov/UFO/> in your browser.
2. Set the table filters to `ALL AGENCIES`, **`RELEASE 06`**, `ALL TYPES`.
   An incremental scrape is enough: `merge_release.py` matches new rows against
   the existing manifest, so scraping only the new tranche merges identically to
   a full 446-row scrape (see README). If you are also covering a Release 07+,
   either scrape each release separately or set `ALL RELEASES`.
3. DevTools (F12) → Console.
4. Paste the entire contents of `scripts/browser_scrape.js` (**v4** — it reads
   the RELEASE column from each row, the only reliable per-file release signal
   for video/audio rows) and press Enter.
5. It walks every page and downloads `manifest.json`. It prints a per-release
   tally when it finishes — **check that it shows `release_06` with ~71
   records** before moving on.

If the tally shows no `release_06`, or far fewer than 71, stop and tell me — it
means the RELEASE column changed format again and the scraper needs a fix first.
Note this release has an **audio** file (the 1952 Project Blue Book / Battelle
briefing) — make sure it's in the tally; audio rows only have a `#fragment` URL,
exactly like video rows.

Then fold the scrape into the existing manifest:

```bash
mkdir -p output
cp ~/Downloads/manifest.json ./scrape.json
python scripts/merge_release.py --new scrape.json --dry-run
```

`merge_release.py` keeps every already-enriched Release 01–05 record untouched
and appends only genuinely-new rows, assigning `release`/`release_no` from
chronological date order — so Release 06 becomes `release_06` on its own. The
dry run should report roughly **71 new records** and list `release_06`. If it
reports far more, title matching is failing and records are about to be
duplicated — stop and tell me.

Two things to watch for, both new in this release:

- **Colorado local law enforcement** is a new agency for PURSUE. Check the
  `agency` value it gets is sensible (not blank, not merged into DOW).
- The document dates run 1952–2025; that's the documents, not the release.
  `release_date` must be 9/18/26 for all 71.

When the dry run looks right:

```bash
python scripts/merge_release.py --new scrape.json
cp data/manifest.json output/manifest.json
```

> **If you only have time for one thing, do Part A.** The scrape alone gets all
> 71 files listed, titled, filtered, searchable and translatable on the site —
> it just leaves them without page previews, OCR text or inline video. Parts B
> and C are enrichment and can follow in a second pass. In that case, hand back
> `data/manifest.json` after the merge and stop there.

## Part B — page previews + OCR (the new Release 06 PDFs)

The Release 06 bundle URLs are known (read off war.gov by the user, 2026-09-26):

```
docs   https://www.war.gov/medialink/ufo/sept-18/release-06/documents_release_06_sept_18_2026.zip
video  https://d34w7g4gy10iej.cloudfront.net/release_06/pursue_vids_091826.zip
```

Only the document bundle is needed here — the site links to the video bundle
rather than processing it.

```bash
mkdir -p raw output/previews output/_classification output/_ocr
curl -L -o r06.zip "https://www.war.gov/medialink/ufo/sept-18/release-06/documents_release_06_sept_18_2026.zip"
unzip -o r06.zip -d raw/
find raw -iname '*.pdf' | wc -l      # expect ~55
```

(If `curl` 403s, download it in the browser and drop it into `raw/`.)

Release 06 is document-heavy (55 PDFs, the most since Release 03), and many are
technical study reports from the military research program — long, typed, with
equations and diagrams. Expect OCR to dominate the runtime.

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

## Part C — video (the new DVIDS videos)

```bash
export DVIDS_API_KEY="<paste the same key here>"
python scripts/fetch_dvids.py          # harvests all UAPVIDEOS assets → data/dvids/uap_videos.json
```

Sanity-check it captured the new videos with non-empty `files` lists:

```bash
python -c "import json;d=json.load(open('data/dvids/uap_videos.json'));print(len(d),'assets');print(sum(1 for v in d.values() if v.get('files')),'with playable files')"
```

The 15 Release 06 videos should be in there. Do **not** run
`merge_dvids_videos.py` — the remote session does that against the translated
manifest.

## Quality check (EXTRACT.md → Step 4)

- Random 10 files: previews are interesting content, not boring scans. A file
  with nothing interesting → empty `preview_pages` (don't pad).
- Random 5 `text_en`: coherent English.
- `du -sh output/previews/` ≈ 10–30 MB for R06 alone (if much bigger, lower
  DPI/quality).
- After writing `output/manifest.json`, re-read it and confirm Hebrew strings
  round-trip (UTF-8, no mojibake) — the Release 01–05 translations are in there
  and must survive.
- `python -c "import json;m=json.load(open('output/manifest.json'));print(m['total_files']);print([r for r in m['releases']])"`
  → total ~446, and a `release_06` entry with ~71 files.

## Hand back — ONE zip

```bash
cp data/dvids/uap_videos.json output/uap_videos.json
cd output
zip -r ../release_06_bundle.zip manifest.json previews/ uap_videos.json
cd ..
ls -lh release_06_bundle.zip
```

Send me **`release_06_bundle.zip`**. That's it.

### What the remote session takes from it

- The merged `manifest.json` — Release 06 records with `release`/`release_no`
  already assigned, plus `page_count`, `content_kinds`, `preview_pages`,
  `preview_pages_fallback`, `text_en`, `text_preview_en` — and the
  `previews/{id}/*.jpg` images.
- `uap_videos.json` → remote runs `merge_dvids_videos.py` to add inline playback.

Then remotely: Hebrew translation of the 71 new records (`title_he`,
`agency_he`, `incident_location_he`, `summary_he`, `narrative_he`, `text_he`),
and clearing the Release 06 entry from `data/pending.json` so the
"published but not yet mirrored" notice disappears.

Reminder: do not translate, do not `git push`.
