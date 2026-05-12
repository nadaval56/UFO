/* ============================================================================
 * PURSUE Hebrew Mirror — Browser-side manifest scraper
 *
 * Paste this entire file into the DevTools Console while on
 *   https://www.war.gov/UFO/
 * It walks every page of the file browser, scrapes the metadata of every row,
 * fetches the description from each detail panel, and downloads a JSON file
 * named `manifest_scrape.json`.
 *
 * Then in the repo:
 *   1. Save the downloaded JSON as `data/manifest.json` (overwrite).
 *   2. Commit + push.
 *   3. (optional) ask Claude Code to translate the new English summaries.
 *
 * Why this and not a GitHub Action: war.gov is protected by Akamai WAF,
 * which returns HTTP 403 for any AWS / GitHub-hosted IP. Your home browser
 * is the only environment that can actually reach the page.
 * ============================================================================ */

(async () => {
  const SLEEP = (ms) => new Promise((r) => setTimeout(r, ms));
  const log = (...a) => console.log("%c[PURSUE]", "color:#7df9ff", ...a);

  log("starting scrape on", location.href);

  /* ---------- pagination detection ---------- */

  function paginationButtons() {
    // Numeric page buttons — could be <button> or <a>.
    return Array.from(document.querySelectorAll('button, a'))
      .filter((b) => /^\d+$/.test((b.textContent || "").trim()));
  }
  function nextButton() {
    return Array.from(document.querySelectorAll('button, a'))
      .find((b) => /^NEXT$/i.test((b.textContent || "").trim()));
  }
  function prevButton() {
    return Array.from(document.querySelectorAll('button, a'))
      .find((b) => /^PREV$/i.test((b.textContent || "").trim()));
  }

  const pageBtnsInitial = paginationButtons();
  let totalPages = pageBtnsInitial.length
    ? Math.max(...pageBtnsInitial.map((b) => parseInt(b.textContent, 10)))
    : 1;

  // If pagination uses "1 ... 16", we may only see a subset; click NEXT to walk.
  log(`detected ${totalPages} pages from numeric buttons`);

  /* ---------- per-row scraping ---------- */

  function scrapeRow(anchor) {
    const href = anchor.href;
    // Walk up to find a row container with enough context
    let row = anchor;
    for (let i = 0; i < 12; i++) {
      const t = (row.textContent || "").trim();
      if (
        t.length > 80 &&
        /(FBI|DEPARTMENT OF|NASA|ODNI|AARO|\[\.[A-Z]+\])/i.test(t)
      ) break;
      if (!row.parentElement) break;
      row = row.parentElement;
    }
    const text = (row.textContent || "").trim().replace(/\s+/g, " ");
    const brackets = Array.from(text.matchAll(/\[([^\]]+)\]/g)).map((m) => m[1].trim());
    const titleClean = text.replace(/\[[^\]]+\]/g, " ").replace(/\s+/g, " ").trim();
    const filename = href.split("/").pop();

    // Classify brackets: agency (first), type (".pdf"/".img"/".vid"), dates, location.
    let agency, releaseDate, incidentDate, incidentLocation, type;
    const remaining = [];
    for (const b of brackets) {
      if (/^\.[A-Z]{2,4}$/i.test(b) && !type) { type = b.toLowerCase(); continue; }
      if (!agency && /^[A-Z][A-Z &]+$/.test(b)) { agency = b; continue; }
      if (/^\d{1,2}\/\d{1,2}\/\d{2,4}$/.test(b)) {
        if (!releaseDate) releaseDate = b;
        else if (!incidentDate) incidentDate = b;
        continue;
      }
      if (/^(LATE|EARLY|MID)\s+\d{4}$|^\d{4}$/i.test(b)) {
        if (!incidentDate) incidentDate = b;
        else if (!incidentLocation) incidentLocation = b;
        continue;
      }
      remaining.push(b);
    }
    if (!incidentLocation && remaining.length) incidentLocation = remaining[0];

    return {
      id: filename.replace(/\.[a-z0-9]+$/i, ""),
      title: titleClean,
      filename,
      source_url: href,
      agency: agency || "UNKNOWN",
      type: (type || ("." + (filename.split(".").pop() || "")).toLowerCase()).replace(/^\./, ""),
      release_date: releaseDate || null,
      incident_date: incidentDate || null,
      incident_location: incidentLocation || null,
      _rowText: text.length > 400 ? text.slice(0, 400) + "…" : text,
    };
  }

  function scrapeVisibleRows() {
    const anchors = Array.from(
      document.querySelectorAll('a[href*="/medialink/ufo/release_1/"]')
    );
    const rows = [];
    const seen = new Set();
    for (const a of anchors) {
      if (seen.has(a.href)) continue;
      // skip the bundle download buttons
      if (/bundle/i.test(a.href)) continue;
      seen.add(a.href);
      rows.push(scrapeRow(a));
    }
    return rows;
  }

  /* ---------- walk every page ---------- */

  const allRows = new Map(); // url → entry

  // Go to page 1 first if a "1" button exists
  const oneBtn = paginationButtons().find((b) => b.textContent.trim() === "1");
  if (oneBtn) { oneBtn.click(); await SLEEP(700); }

  let pageNum = 1;
  let safety = 200;
  while (safety-- > 0) {
    const rows = scrapeVisibleRows();
    log(`page ${pageNum}: scraped ${rows.length} rows (cumulative ${allRows.size + rows.filter((r) => !allRows.has(r.source_url)).length})`);
    for (const r of rows) {
      if (!allRows.has(r.source_url)) allRows.set(r.source_url, r);
    }
    const nb = nextButton();
    if (!nb || nb.disabled || nb.getAttribute("aria-disabled") === "true") break;
    nb.click();
    pageNum += 1;
    await SLEEP(700);
  }

  const entries = Array.from(allRows.values());
  log(`scraped ${entries.length} unique entries across ${pageNum} pages`);

  /* ---------- enrich each entry with its description (from hash-routed detail) ---------- */

  log("fetching descriptions from detail panels…");
  let done = 0;
  for (const e of entries) {
    try {
      window.location.hash = e.id;
      await SLEEP(350);
      // The description is the longest paragraph visible in the detail panel.
      const candidates = Array.from(document.querySelectorAll("p, .description, [class*='description'] p"));
      let best = "";
      for (const n of candidates) {
        const t = (n.textContent || "").trim();
        if (t.length > 60 && t.length < 4000 && t.length > best.length) best = t;
      }
      if (best) e.summary_en = best;
    } catch (err) {
      log("description fetch failed for", e.id, err);
    }
    done += 1;
    if (done % 20 === 0) log(`  enriched ${done}/${entries.length}`);
  }

  // Reset hash so the user sees the file list when the script ends
  history.replaceState(null, "", location.pathname);

  /* ---------- assemble + download ---------- */

  const manifest = {
    release_id: "release_01",
    release_date: "2026-05-08",
    source_page_url: "https://www.war.gov/UFO/",
    total_files: entries.length,
    generated_at: new Date().toISOString(),
    _scraped_by: "browser_scrape.js (DevTools console)",
    _note: "Run scripts/translate-instructions.md against this file via Claude Code to add Hebrew translations.",
    files: entries.map((e) => ({
      id: e.id,
      title: e.title,
      title_he: null,
      filename: e.filename,
      agency: e.agency,
      agency_he: null,
      type: e.type,
      source_url: e.source_url,
      release_date: e.release_date,
      incident_date: e.incident_date,
      incident_location: e.incident_location,
      incident_location_he: null,
      summary_en: e.summary_en || null,
      summary_he: null,
      size_bytes: null,
      url_status: null,
    })),
  };

  const blob = new Blob([JSON.stringify(manifest, null, 2)], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "manifest.json";
  document.body.appendChild(a);
  a.click();
  a.remove();

  log("done — downloaded as manifest.json. Save it to data/manifest.json in the repo.");
  log("summary:", {
    files: entries.length,
    with_description: entries.filter((e) => e.summary_en).length,
    agencies: [...new Set(entries.map((e) => e.agency))],
    locations: [...new Set(entries.map((e) => e.incident_location).filter(Boolean))],
  });
})();
