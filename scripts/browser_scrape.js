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
  // The modal's Download button programmatically creates an <a href="...pdf" download>
  // and clicks it. We listen for clicks in the capture phase, grab the URL,
  // and stop the actual navigation. This works without disturbing other links
  // because we only attach the listener while waiting for the click.

  function captureNextDownloadURL(timeoutMs = 1200) {
    return new Promise((resolve) => {
      let resolved = false;
      const onClick = (e) => {
        const a = e.target.closest && e.target.closest("a[href]");
        if (a && a.href) {
          e.preventDefault();
          e.stopPropagation();
          e.stopImmediatePropagation();
          document.removeEventListener("click", onClick, true);
          resolved = true;
          resolve(a.href);
        }
      };
      document.addEventListener("click", onClick, true);
      setTimeout(() => {
        if (resolved) return;
        document.removeEventListener("click", onClick, true);
        resolve(null);
      }, timeoutMs);
    });
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

    // Try iframe src first (cheap), then fall back to clicking download.
    let url = null;
    const iframe = modal.querySelector("iframe[src], embed[src], object[data]");
    if (iframe) {
      url = iframe.getAttribute("src") || iframe.getAttribute("data") || null;
      if (url && url.startsWith("/")) url = new URL(url, location.origin).href;
    }
    if (!url) {
      const dlBtn = modal.querySelector(".record-modal-download, [data-record-modal-download]");
      if (dlBtn) {
        const urlPromise = captureNextDownloadURL();
        dlBtn.click();
        url = await urlPromise;
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

  const blob = new Blob([JSON.stringify(manifest, null, 2)], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "manifest.json";
  document.body.appendChild(a);
  // Click directly via descriptor to bypass any listeners we may have registered.
  HTMLElement.prototype.click.call(a);
  a.remove();

  log("✓ downloaded manifest.json — save it to data/manifest.json in the repo");
})();
