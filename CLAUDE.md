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
- 2026-05-26 — Release 02 bundle download URLs in `index.html` are a best guess (`Release_2.zip` / `Release_2_Videos.zip`, mirroring the Release_1 pattern). **Verify against the real "Download Release 02" links on war.gov before merging.**
