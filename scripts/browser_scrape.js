/* ============================================================================
 * PURSUE Hebrew Mirror — Browser-side manifest scraper v2
 *
 * Paste into the DevTools Console on https://www.war.gov/UFO/.
 * Downloads `manifest.json` describing every file in the release.
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
      // Skip preview thumbnails / data URIs
      if (url && (url.startsWith("data:") || /thumb/i.test(url))) url = null;
    }

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
      }
    }

    // Close the modal so the next row's click works cleanly.
    const closeBtn = modal.querySelector(".record-modal-close, [data-record-modal-close]");
    if (closeBtn) closeBtn.click();
    await SLEEP(120);

    return { title, description, kind, facts, url };
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
  const SAFETY = 30;
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
    const filenameFromUrl = url ? decodeURIComponent(url.split("/").pop().split("?")[0]) : null;
    const id = filenameFromUrl ? filenameFromUrl.replace(/\.[a-z0-9]+$/i, "") : r.recordId;
    const docType = (r.facts["Document Type"] || r.kind || "").replace(/^\./, "").toLowerCase() || null;
    return {
      id,
      title: r.title || null,
      title_he: null,
      filename: filenameFromUrl,
      agency: r.facts["Agency"] || null,
      agency_he: null,
      type: docType,
      source_url: url,
      release_date: r.facts["Release Date"] || null,
      incident_date: r.facts["Incident Date"] || null,
      incident_location: r.facts["Incident Location"] || null,
      incident_location_he: null,
      summary_en: r.description || null,
      summary_he: null,
      size_bytes: null,
      url_status: null,
      _record_id: r.recordId,
    };
  }

  const files = records.map(entryFrom);

  const manifest = {
    release_id: "release_01",
    release_date: "2026-05-08",
    source_page_url: "https://www.war.gov/UFO/",
    total_files: files.length,
    generated_at: new Date().toISOString(),
    _scraped_by: "browser_scrape.js v2 (DevTools console)",
    _note:
      "Hebrew translation fields (title_he, agency_he, incident_location_he, summary_he) are added separately by a Claude Code session.",
    files,
  };

  log("=== SUMMARY ===");
  log(`  total records: ${files.length}`);
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
