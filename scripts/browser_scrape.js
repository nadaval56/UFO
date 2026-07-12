/* ============================================================================
 * PURSUE Hebrew Mirror — Browser-side manifest scraper v4 (per-release tabs)
 *
 * Paste into the DevTools Console on https://www.war.gov/UFO/.
 * Downloads `manifest.json` describing every file across ALL releases.
 *
 * ⚠ BEFORE RUNNING: set the three table filters to their defaults —
 *   "ALL AGENCIES", "ALL RELEASES", "ALL TYPES" — so the unified table
 *   contains every record (e.g. all 222 across Release 01 + Release 02).
 *   The scraper walks the visible table's pagination; whatever the filters
 *   hide, it won't see. Each row is tagged with its own Release Date, so a
 *   single walk captures every release.
 *
 * Save the result to data/manifest.json in the repo, commit, push.
 *
 * DOM (verified from a live diagnostic, 2026-05-12):
 *   - Each row:  <button class="record-row" data-record-id="record-N">
 *                  <span class="record-title">…</span>
 *                  <span class="record-meta">[Agency]</span>
 *                  <span class="record-meta">[Release Date]</span>
 *                  <span class="record-meta">[Incident Date]</span>
 *                  <span class="record-meta">[Location]</span>
 *                  <span class="record-meta">[.pdf]</span>
 *                </button>
 *   - Clicking a row populates #record-modal with title, description,
 *     a <dl> of facts, and a Download button that on click synthesizes
 *     an <a href="..." download> and clicks it. We intercept that click
 *     to capture the URL without actually downloading 158 files.
 *   - Pagination: .pagination-button elements (numeric pages plus Prev/Next).
 *
 * Why this lives in the browser and not in CI: war.gov is behind Akamai WAF
 * which 403s every datacenter IP. The user's home browser is the only
 * environment that can reach the page.
 * ============================================================================ */

(async () => {
  const SLEEP = (ms) => new Promise((r) => setTimeout(r, ms));
  const log = (...a) => console.log("%c[PURSUE]", "color:#7df9ff;font-weight:bold", ...a);

  log("starting on", location.href);

  /* ---------- helpers ---------- */

  const stripBrackets = (s) => (s || "").trim().replace(/^\[\s*|\s*\]$/g, "");

  function pageButtons() {
    return Array.from(document.querySelectorAll(".pagination-button"));
  }
  function nextBtn() {
    return pageButtons().find((b) => /^next$/i.test((b.textContent || "").trim()));
  }
  function rows() {
    return Array.from(document.querySelectorAll("button.record-row"));
  }

  /* ---------- URL capture ---------- */
  // The modal's Download <button> doesn't synthesize an <a href> we can
  // intercept — it goes via window.open or assigns window.location.href.
  // So we install global hooks for the duration of the scrape that record
  // whatever URL the page tries to navigate to, and prevent the actual
  // navigation/download.

  let _captured_url = null;

  const _origOpen = window.open;
  window.open = function (url, ...rest) {
    if (url) _captured_url = String(url);
    return null; // don't actually open
  };

  // Hook assignments to window.location.assign / replace / href
  const _origAssign = window.location.assign.bind(window.location);
  const _origReplace = window.location.replace.bind(window.location);
  window.location.assign = (url) => { if (url) _captured_url = String(url); };
  window.location.replace = (url) => { if (url) _captured_url = String(url); };
  // location.href setter is harder to hook reliably; capture via Object.defineProperty on document
  // (best-effort; some browsers won't allow it)
  try {
    const _hrefSetter = Object.getOwnPropertyDescriptor(Location.prototype, "href").set;
    Object.defineProperty(Location.prototype, "href", {
      set(v) {
        if (v) _captured_url = String(v);
        // intentionally do not call _hrefSetter — would actually navigate
      },
      configurable: true,
    });
  } catch (e) {
    log("could not hook Location.href setter:", e.message);
  }

  // Also catch synthesized anchor clicks (older / alternate site code paths)
  const _onDocClick = (e) => {
    const a = e.target.closest && e.target.closest("a[href]");
    if (a && a.href) {
      // Allow row clicks, pagination clicks etc. to proceed.
      // Only intercept if href looks like a file download.
      if (/\/medialink\/ufo\/|\.(pdf|jpg|jpeg|png|mp4|mov|zip)$/i.test(a.href)) {
        _captured_url = a.href;
        e.preventDefault();
        e.stopPropagation();
        e.stopImmediatePropagation();
      }
    }
  };
  document.addEventListener("click", _onDocClick, true);

  // Restore hooks on script end (best-effort)
  function _restoreHooks() {
    window.open = _origOpen;
    try {
      window.location.assign = _origAssign;
      window.location.replace = _origReplace;
    } catch (e) {}
    document.removeEventListener("click", _onDocClick, true);
  }

  /* ---------- single row scrape ---------- */

  async function scrapeRow(rowEl) {
    // Capture the release straight from the row's RELEASE cell BEFORE opening
    // the modal. war.gov v4 (2026-07) moved the release out of the modal's
    // fact list and into the table column, formatted "[7/10/26 - RELEASE 04]".
    // Every row (including video/audio, whose download URL is only a #fragment)
    // carries it here, so this is the one reliable per-file release signal.
    let rowRelease = null; // e.g. { release_no: "04", release: "release_04", release_date_raw: "7/10/26" }
    for (const meta of rowEl.querySelectorAll(".record-meta")) {
      const txt = stripBrackets(meta.textContent || "");
      const m = txt.match(/(\d{1,2}\/\d{1,2}\/\d{2,4})?\s*-?\s*RELEASE\s*0*(\d+)/i);
      if (m) {
        const no = String(m[2]).padStart(2, "0");
        rowRelease = {
          release_no: no,
          release: `release_${no}`,
          release_date_raw: m[1] || null,
        };
        break;
      }
    }

    rowEl.click();

    // Wait for the modal to populate
    let modal = null;
    for (let i = 0; i < 60; i++) {
      modal = document.querySelector("#record-modal");
      if (modal && modal.querySelector("#record-modal-title")?.textContent?.trim()) break;
      await SLEEP(40);
    }
    if (!modal) return null;

    const title = modal.querySelector("#record-modal-title")?.textContent?.trim() || null;
    const description = modal.querySelector("[data-record-modal-copy]")?.textContent?.trim() || null;
    const kind = modal.getAttribute("data-record-kind") || null;

    const facts = {};
    for (const fact of modal.querySelectorAll(".record-modal-fact")) {
      const k = fact.querySelector("dt")?.textContent?.trim();
      const v = fact.querySelector("dd")?.textContent?.trim();
      if (k && v) facts[k] = stripBrackets(v);
    }

    // Strategy 1: iframe / embed / video src already in modal
    let url = null;
    const media = modal.querySelector(
      ".record-media iframe[src], .record-media embed[src], .record-media object[data], " +
      ".record-media video source[src], .record-media video[src], .record-media img[src]"
    );
    if (media) {
      url = media.getAttribute("src") || media.getAttribute("data") || null;
      if (url && url.startsWith("/")) url = new URL(url, location.origin).href;
      // Skip preview thumbnails / data URIs / placeholder strings
      if (url && (url.startsWith("data:") || /thumb/i.test(url))) url = null;
    }
    if (url && !/^https?:\/\//i.test(url)) url = null;

    // Strategy 2: click the Download button and let our window.open /
    // location-assign / location-href hooks capture the URL.
    if (!url) {
      const dlBtn = modal.querySelector(".record-modal-download, [data-record-modal-download]");
      if (dlBtn) {
        _captured_url = null;
        dlBtn.click();
        // Give the site's handler a moment to run
        await SLEEP(700);
        url = _captured_url;
        if (url && !/^https?:\/\//i.test(url)) url = null;
      }
    }

    // Strategy 3: check the download button's data-* after click (some
    // implementations populate it instead of navigating)
    if (!url) {
      const dlBtn = modal.querySelector(".record-modal-download, [data-record-modal-download]");
      if (dlBtn) {
        url = dlBtn.getAttribute("data-record-modal-download") ||
              dlBtn.getAttribute("data-url") ||
              dlBtn.getAttribute("href") || null;
        if (url && !/^https?:\/\//i.test(url)) url = null;
      }
    }

    // Strategy 4: for videos/audio the <video src> is a Blob URL (useless).
    // Fall back to the war.gov record-page URL using the title slug — this
    // matches the hash route the SPA uses internally (e.g.
    // war.gov/UFO/#NASA-UAP-D3A-Gemini-7-Audio-Excerpt-1965). Clicking the
    // "Download" link in our UI then lands the user on the original record
    // page where they can use the site's native Download button.
    let urlIsRecordPage = false;
    if (!url && title) {
      const slug = title.replace(/[,\s]+/g, "-").replace(/-+/g, "-").replace(/^-|-$/g, "");
      if (slug) {
        url = `https://www.war.gov/UFO/#${slug}`;
        urlIsRecordPage = true;
      }
    }

    // Close the modal so the next row's click works cleanly.
    const closeBtn = modal.querySelector(".record-modal-close, [data-record-modal-close]");
    if (closeBtn) closeBtn.click();
    await SLEEP(120);

    return { title, description, kind, facts, url, urlIsRecordPage, rowRelease };
  }

  /* ---------- walk pagination ---------- */

  const seen = new Set();
  const records = [];

  // Go to page 1 if there's an explicit "1" button and it's not active.
  const one = pageButtons().find((b) => (b.textContent || "").trim() === "1");
  if (one && !one.classList.contains("is-active") && !one.getAttribute("aria-current")) {
    one.click();
    await SLEEP(700);
  }

  let pageIndex = 1;
  const SAFETY = 60; // unified multi-release table is larger than a single release
  while (pageIndex <= SAFETY) {
    const pageRows = rows();
    log(`page ${pageIndex}: ${pageRows.length} rows`);
    for (let i = 0; i < pageRows.length; i++) {
      const row = pageRows[i];
      const rid = row.getAttribute("data-record-id") || `row-${pageIndex}-${i}`;
      if (seen.has(rid)) continue;
      seen.add(rid);
      try {
        const data = await scrapeRow(row);
        if (data) records.push({ recordId: rid, ...data });
      } catch (err) {
        log("row scrape error", rid, err);
      }
      if ((i + 1) % 5 === 0) log(`  ${i + 1}/${pageRows.length} on page ${pageIndex}`);
    }

    const nb = nextBtn();
    if (!nb || nb.disabled || nb.getAttribute("aria-disabled") === "true") {
      log(`reached last page (${pageIndex})`);
      break;
    }
    nb.click();
    pageIndex++;
    await SLEEP(700);
  }

  /* ---------- assemble + download ---------- */

  function entryFrom(r) {
    const url = r.url || null;
    const isPageURL = r.urlIsRecordPage === true;
    const filenameFromUrl =
      url && !isPageURL ? decodeURIComponent(url.split("/").pop().split("?")[0]) : null;
    const id = filenameFromUrl ? filenameFromUrl.replace(/\.[a-z0-9]+$/i, "") : r.recordId;
    const docType = (r.facts["Document Type"] || r.kind || "").replace(/^\./, "").toLowerCase() || null;
    // Release: prefer the modal fact if war.gov ever restores it, else the
    // RELEASE column captured from the row (v4). `release`/`release_no` are the
    // stable per-file tab keys; `release_date` keeps the raw war.gov M/D/YY date
    // (merge_release.py converts it to Israeli DD/MM/YY).
    const rr = r.rowRelease || {};
    const entry = {
      id,
      title: r.title || null,
      title_he: null,
      filename: filenameFromUrl,
      agency: r.facts["Agency"] || null,
      agency_he: null,
      type: docType,
      source_url: url,
      release: rr.release || null,
      release_no: rr.release_no || null,
      release_date: r.facts["Release Date"] || rr.release_date_raw || null,
      incident_date: r.facts["Incident Date"] || null,
      incident_location: r.facts["Incident Location"] || null,
      incident_location_he: null,
      summary_en: r.description || null,
      summary_he: null,
      size_bytes: null,
      url_status: null,
      _record_id: r.recordId,
    };
    if (isPageURL) entry._url_is_record_page = true;
    return entry;
  }

  const files = records.map(entryFrom);

  // Summarize the releases present in the scraped set (data-driven, so the
  // manifest is correct whether war.gov is showing one release or several).
  const releaseCounts = {};
  for (const f of files) {
    const r = f.release || "unknown";
    releaseCounts[r] = (releaseCounts[r] || 0) + 1;
  }
  const releases = Object.entries(releaseCounts)
    .map(([label, count]) => ({ label, count }))
    .sort((a, b) => a.label.localeCompare(b.label));

  const manifest = {
    release_id: releases.length > 1 ? "combined" : "release_01",
    release_date: releases.length === 1 ? (files[0] && files[0].release_date) || null : null,
    source_page_url: "https://www.war.gov/UFO/",
    total_files: files.length,
    releases,
    generated_at: new Date().toISOString(),
    _scraped_by: "browser_scrape.js v4 (DevTools console, per-release tabs)",
    _note:
      "Hebrew translation fields (title_he, agency_he, incident_location_he, summary_he) are added separately by a Claude Code session.",
    files,
  };

  log("=== SUMMARY ===");
  log(`  total records: ${files.length}`);
  log(`  releases:      ${releases.map((r) => `${r.label} (${r.count})`).join(" | ")}`);
  log(`  with URL:      ${files.filter((e) => e.source_url).length}`);
  log(`  with summary:  ${files.filter((e) => e.summary_en).length}`);
  log(`  agencies:      ${[...new Set(files.map((e) => e.agency).filter(Boolean))].join(", ")}`);
  log(`  locations:     ${[...new Set(files.map((e) => e.incident_location).filter(Boolean))].join(", ")}`);
  log("=== /SUMMARY ===");

  // Restore navigation hooks BEFORE triggering our own download (otherwise our
  // download anchor click would itself be captured by the hooks).
  _restoreHooks();

  const blob = new Blob([JSON.stringify(manifest, null, 2)], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "manifest.json";
  document.body.appendChild(a);
  a.click();
  a.remove();

  log("✓ downloaded manifest.json — save it to data/manifest.json in the repo");
})();
