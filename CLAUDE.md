# CLAUDE.md — PURSUE Hebrew Mirror (v2)

> **Change from v1:** File browser is now part of Phase 1, not Phase 2. It is the most important user-facing feature and a 1:1 clone is incomplete without it. Phase 2 is now PDF content analysis / Hebrew summaries.

## Project Overview

A Hebrew-language popular-facing mirror of the U.S. Department of War's PURSUE landing page (Presidential Unsealing and Reporting System for UAP Encounters).

**Source:** https://www.war.gov/UFO/
**Goal (Phase 1):** Faithful 1:1 visual + structural clone, fully translated to Hebrew RTL, **including a working document browser with pagination and filters**.
**Future phases:** PDF content analysis, AI Hebrew summaries, interactive map, auto-updates.

This project follows the same pattern as `geniza-explorer`: static GitHub Pages site, Hebrew RTL, dark theme, popular-facing portal to a public archive.

---

## Legal & Attribution

- Source content is a U.S. federal government work → **public domain** under 17 U.S.C. § 105.
- This is an **unofficial community translation**, not affiliated with the U.S. government.
- Every page must include the disclaimer:
  > **כתב ויתור:** תרגום עברי בלתי רשמי. למקור הרשמי באנגלית: [war.gov/UFO](https://www.war.gov/UFO/)
- Footer must link to original source and to this project's GitHub repo.

---

## Tech Stack

- **Frontend:** static HTML5 + vanilla CSS + vanilla JS.
- **Data:** single `manifest.json` file describing all documents; loaded client-side.
- **Hosting:** GitHub Pages (`pursue-he` or similar).
- **Language:** `<html dir="rtl" lang="he">`.
- **Fonts:** Heebo or Rubik via Google Fonts; mono font (JetBrains Mono / Fira Code) for coordinates, filenames, and metadata.

---

## Data Pipeline

This pipeline produces the `manifest.json` that drives the file browser. It is a separate Python step, run once per release, output committed to the repo.

### Step 1: Acquire bundle

- Download `Release_1.zip` from https://www.war.gov/medialink/ufo/bundle/Release_1.zip
- Extract to `/data/release_01/raw/`

### Step 2: Investigate source manifest

Before parsing filenames manually, check if the war.gov page exposes a JSON manifest via XHR. Open the original page in browser DevTools → Network tab → look for `.json` requests when the file list loads. If found, use it as the basis for `manifest.json`.

### Step 3: Fallback — parse filenames

FBI filename pattern:
```
65_HS1-834228961_62-HQ-83894_SERIAL_130
```
- `62` is an FBI classification code.
- `HQ-83894` is the FBI Headquarters case file number.
- `SERIAL_NNN` is the document index.

Heuristics:
- **Agency:** filenames containing `HQ-` → FBI; other agencies have different patterns.
- **Type:** file extension.
- **Source ID:** the full filename without extension.

Fields left null until Phase 2:
- `incident_date`
- `incident_location`
- `summary_he`

### Step 4: Emit manifest.json

Commit `manifest.json` to `/data/manifest.json`.

---

## Site Structure (Phase 1)

1. **Header / Navigation**
2. **Hero**
3. **Trump Directive Quote**
4. **Directive** (`#directive`)
5. **Release 01** (`#release`) — file browser with filters, pagination, search
6. **Learn More** (`#learn`)
7. **Footer**

---

## Acceptance Criteria (Phase 1)

**Visual shell:**
- [ ] All 7 sections present.
- [ ] RTL layout correct.
- [ ] Trump quote, Directive, Hegseth statement translated.
- [ ] Pentagon coordinates in mono font.
- [ ] Disclaimer in footer + top banner.

**File browser:**
- [ ] `manifest.json` loaded.
- [ ] 10 cards per page.
- [ ] Pagination `PREV / 1 / ... / N / NEXT`.
- [ ] Page number reflected in URL hash.
- [ ] Working filters: Agency, Release Date, Type.
- [ ] Disabled filters: Incident Date, Incident Location.
- [ ] Free-text search.
- [ ] Download link to original .gov URL.
- [ ] File counter updates with filters.

**Quality:**
- [ ] Mobile-responsive (375px, 768px, 1440px).
- [ ] Manifest under 500 KB.
- [ ] HTML validates.

---

## Out of Scope (Phase 1)

- PDF content analysis / OCR.
- Hebrew summaries per document.
- Incident Date / Location filters.
- Interactive map.

---

## Roadmap

- **Phase 2:** PDF text extraction + Hebrew summaries via Claude API.
- **Phase 3:** Interactive map.
- **Phase 4:** Weekly poll of war.gov for new releases.
- **Phase 5:** "ידעת ש?" facts feed.

## Investigation log

- 2026-05-12 — war.gov/UFO returned HTTP 403 to a server-side fetch. The "is there a JSON manifest exposed?" check (CLAUDE.md Step 2) must be done from a real browser DevTools session before relying on filename heuristics in production.
- 2026-05-12 — `SOURCE_FILE_URL_BASE` in `scripts/build_manifest.py` is a best guess (`https://www.war.gov/medialink/ufo/files/`); verify against a real download link.
- 2026-05-26 — war.gov shipped **Release 02** (cleared 2026-05-22). The page now has `RELEASE 01 / RELEASE 02` tabs above a single unified table (~222 files) with an `ALL RELEASES` filter. Decision: the mirror keeps one unified table + a working release filter (not tab cloning). `manifest.json` schema went multi-release — top-level `releases[]` (data-driven), `release_id: "combined"`, and per-file `release_date` is the source of truth for the filter. `browser_scrape.js` bumped to v3: set all three table filters to ALL, then one pagination walk captures every release. Confirmed again from this cloud env: `curl https://www.war.gov/UFO/` → `403 host_not_allowed`, so the scrape still must run in the user's home browser.
- 2026-05-27 — Release 02 bundle download URLs verified from war.gov and wired into `index.html`: documents → `https://www.war.gov/medialink/ufo/052226/release_02/release_02_document_bundle.zip`, videos → `https://d34w7g4gy10iej.cloudfront.net/uap052226.zip` (CloudFront, ~5.6GB). Note war.gov changed its bundle URL scheme for Release 02 (date-stamped `/052226/release_02/...` path + CloudFront for video), unlike Release 01's `/medialink/ufo/bundle/Release_1*.zip`.
- 2026-07-12 — war.gov shipped **Release 03** (cleared 6/12/26) and **Release 04** (cleared 7/10/26); the page now has `ALL / RELEASE 01–04` tabs above a unified table of **334 files**. **Decision reversed** (per user): the mirror will now clone the per-release **tabs** (ALL / 01 / 02 / 03 / 04), matching the original site, while keeping the release filter alongside. Bundle URLs verified: R03 docs → `https://www.war.gov/medialink/ufo/061226/release_03/release_03_documents.zip`, R03 video → `https://d34w7g4gy10iej.cloudfront.net/release_03/uap_videos_061226.zip`; R04 docs → `https://www.war.gov/medialink/ufo/071026/release_04/release_04_documents_071026.zip`, R04 video → `https://d34w7g4gy10iej.cloudfront.net/release_04/uap_release04_videos_071026.zip`.
- 2026-07-12 — **Scraper regression found:** war.gov moved the release out of the modal fact list into the table's **RELEASE column** (formatted `[7/10/26 - RELEASE 04]`), so v3's `facts["Release Date"]` came back `null` for all 334 rows. Release is recoverable from `source_url` for PDFs/images (`/ufo/061226/release_03/…`) but **not** for video/audio rows, whose URL is only a `#fragment` — 32 new R03/R04 videos could not be tab-assigned. Fixed in **`browser_scrape.js` v4**: read the RELEASE column straight from each row before opening the modal, emitting stable per-file `release` (`release_04`) + `release_no` keys. Requires one fresh re-scrape with v4.
- 2026-08-23 — war.gov shipped **Release 05** on 7 August 2026 (**41 files**) and the mirror missed it for two weeks: nothing in the project watches for new tranches, and the archive heading was hand-written (`מהדורות 01–04`), so a missing release looked identical to a complete archive. Contents per the DoW announcement and press coverage: six videos of a 2021 **Gulf of Oman** encounter in which an AC-130J gunship crew tracked ~25 objects at 250–1,300 mph; a declassified **FBI FD-302** interview describing a silent ~500-foot triangle over **Bagram**, Afghanistan (2002) — the first FD-302s in the archive, with digital renderings; the 1953 Navy analysis of the Great Falls and Tremonton films; 1947–48 Air Materiel Command and "ghost rocket" records; CIA Puerto Rico material; and 1963 State Department cables on the Bahia, Brazil incident. Agencies: DOW, FBI, CIA, State, Executive Office of the President. Announcement: `https://www.war.gov/News/Releases/Release/Article/4565994/`.
- 2026-08-23 — **Both hardcodings that hid the gap are gone.** The archive heading and its date line are now derived from the manifest's `releases[]` (`renderReleaseHeader()` in `file-browser.js`), so they can no longer go stale; and `data/pending.json` lists tranches that are published but not yet mirrored, rendered as a visible notice above the release tabs. Add an entry the day a release is announced, delete it when the files are merged. Verified that `merge_release.py` needs **no** change for Release 05: it assigns `release`/`release_no` from chronological date order, so a scrape containing the new rows produces `release_05` on its own (simulated end-to-end against a synthetic 375-row scrape).
- 2026-08-23 — Release 05 bundle URLs are **deliberately not in the repo**: every release so far has used a different path scheme, and PR #39 existed solely to fix invented Release 02 links. They must be read off war.gov and reported back — see `scripts/extract/LOCAL_TASK_R05.md`, the one-paste briefing for the local session that does the scrape, the merge, previews/OCR and DVIDS harvest.
- 2026-08-23 — Network reality in a Claude Code **web** session is stricter than the old Akamai note: `war.gov`, `d34w7g4gy10iej.cloudfront.net`, `dvidshub.net` and even `web.archive.org` are all refused at the sandbox's egress proxy (CONNECT 403), not just by the origin. There is no cloud-side path to the data at all — the local-session hand-off is the only workflow.
