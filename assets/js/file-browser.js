/* ============================================================
   file-browser.js
   Drives the archive browser across every PURSUE release: loads
   manifest.json, renders cards, handles pagination, filters, and search.
   Cards link to the standalone file.html?id=... page.
   No dependencies — vanilla JS.
   ============================================================ */

(function () {
  "use strict";

  const MANIFEST_URL = "data/manifest.json";
  const PENDING_URL = "data/pending.json";
  const PAGE_SIZE = 10;

  /* ------------------------- state ------------------------- */

  const state = {
    files: [],
    filtered: [],
    page: 1,
    filters: {
      agency: "",
      release: "",
      incidentDate: "",
      incidentLocation: "",
      type: "",
      search: "",
    },
  };

  /* ------------------------- elements ------------------------- */

  const el = {
    list: document.getElementById("file-list"),
    empty: document.getElementById("file-list-empty"),
    emptyReset: document.getElementById("file-list-empty-reset"),
    pagination: document.getElementById("pagination"),
    countNum: document.getElementById("file-count-num"),
    tabs: document.getElementById("release-tabs"),
    releaseTitle: document.getElementById("release-title"),
    releaseEyebrow: document.getElementById("release-eyebrow"),
    latestReleaseDate: document.getElementById("latest-release-date"),
    agencyList: document.getElementById("directive-agencies"),
    pending: document.getElementById("pending-release"),
    agency: document.getElementById("filter-agency"),
    releaseSelect: document.getElementById("filter-release"),
    incidentDate: document.getElementById("filter-incident-date"),
    incidentLocation: document.getElementById("filter-incident-location"),
    type: document.getElementById("filter-type"),
    search: document.getElementById("filter-search"),
    reset: document.getElementById("filter-reset"),
    filtersToggle: document.getElementById("filters-toggle"),
    filtersPanel: document.getElementById("filters"),
    filtersCount: document.getElementById("filters-toggle-count"),
  };

  /* ------------------------- utilities ------------------------- */

  function typeLabel(t) {
    const map = { pdf: "PDF", img: "תמונה", vid: "וידאו", doc: "מסמך", txt: "טקסט" };
    return map[t] || (t ? t.toUpperCase() : "—");
  }

  function fileTitleHe(f) {
    return f.title_he || f.title || f.filename || "—";
  }

  function agencyDisplayHe(f) {
    return f.agency_he || f.agency || "—";
  }

  /** First sentence of a Hebrew narrative, capped at maxChars. */
  function narrativeBlurb(text, maxChars = 200) {
    if (!text) return "";
    const trimmed = String(text).trim();
    // Split on Hebrew/Latin sentence enders. The first "chunk" is the blurb.
    const m = trimmed.match(/^([^.!?]*[.!?])\s/);
    let first = m ? m[1] : trimmed;
    if (first.length > maxChars) {
      // Back up to the last space within budget
      const cut = first.slice(0, maxChars);
      const sp = cut.lastIndexOf(" ");
      first = (sp > 100 ? cut.slice(0, sp) : cut) + "…";
    }
    return first;
  }

  /** Human-readable card headline. Prefers title_he, then the first
   *  phrase of narrative_he (before em-dash or first sentence end).
   *  If the first em-dash segment is too short (e.g. just a year),
   *  promotes to the next segment to get a meaningful title. */
  function cardHeadline(f) {
    if (f.title_he) return f.title_he;
    const n = (f.narrative_he || "").trim();
    if (!n) return f.title || f.filename || "(ללא כותרת)";

    const dashIdx = n.indexOf(" — ");
    if (dashIdx >= 4 && dashIdx <= 80) {
      // If the first segment is a short date / context (< 20 chars), expand
      // through the next phrase so the headline carries real meaning.
      if (dashIdx < 20) {
        const budget = 80 - dashIdx - 3;
        const after = n.slice(dashIdx + 3);
        if (after.length <= budget) return (n.slice(0, dashIdx + 3) + after).trim();
        const piece = after.slice(0, budget);
        const lastSp = piece.lastIndexOf(" ");
        const trimmedAfter = (lastSp > 10 ? piece.slice(0, lastSp) : piece).replace(/[,;.]$/, "");
        return (n.slice(0, dashIdx + 3) + trimmedAfter).trim() + "…";
      }
      return n.slice(0, dashIdx).trim();
    }
    // No em-dash: take first ~55 chars, ending at the nearest word boundary
    const limit = 55;
    if (n.length <= limit) return n;
    const cut = n.slice(0, limit);
    const lastBreak = Math.max(cut.lastIndexOf(" "), cut.lastIndexOf(","), cut.lastIndexOf("׳"));
    const trimmed = (lastBreak > 25 ? cut.slice(0, lastBreak) : cut).trim().replace(/[,;.]$/, "");
    return trimmed + "…";
  }

  /** True if the given value is N/A / לא ידוע / blank — shouldn't render. */
  function isBlank(v) {
    if (v == null) return true;
    const s = String(v).trim().toLowerCase();
    return s === "" || s === "n/a" || s === "—" || s === "-" || s === "לא ידוע" || s === "לא רלוונטי";
  }

  /** Card blurb: the rest of narrative_he after the headline is removed. */
  function cardBlurb(f, headline) {
    const n = (f.narrative_he || "").trim();
    if (!n) return "";
    // Strip ellipsis from the headline before prefix-matching so that
    // truncated headlines still consume their matched prefix from n.
    const clean = (headline || "").replace(/…$/, "").trim();
    if (clean && n.startsWith(clean)) {
      const rest = n.slice(clean.length).replace(/^\s*[—\-,;.]\s*/, "").trim();
      if (rest) return narrativeBlurb(rest, 220);
    }
    return narrativeBlurb(n, 220);
  }

  function incidentDateDisplay(f) {
    return f.incident_date_display || f.incident_date || null;
  }

  function incidentLocationDisplayHe(f) {
    return f.incident_location_he || f.incident_location || null;
  }

  function unique(arr) {
    return Array.from(new Set(arr.filter(Boolean))).sort();
  }

  /* ------------------------- release model ------------------------- */
  // Every file carries a stable `release` key ("release_03") produced by the
  // scraper / merge step. The per-release tabs and the "מהדורה" filter are two
  // views of this same dimension and stay in sync.

  function fileRelease(f) {
    return f.release || "";
  }

  function releaseNo(key) {
    const m = /(\d+)/.exec(key || "");
    return m ? String(parseInt(m[1], 10)).padStart(2, "0") : null;
  }

  function releaseLabel(no) {
    return "מהדורה " + (no || "?");
  }

  /** Ordered list of releases present in the data: {key, no, date, count}. */
  function releaseList() {
    const map = new Map();
    state.files.forEach((f) => {
      const key = fileRelease(f);
      if (!key) return;
      if (!map.has(key)) {
        map.set(key, { key, no: releaseNo(key), date: f.release_date || null, count: 0 });
      }
      map.get(key).count += 1;
    });
    return Array.from(map.values()).sort((a, b) => (a.no || "").localeCompare(b.no || ""));
  }

  /** Set the active release (from a tab click or the dropdown) and re-render. */
  function setRelease(key) {
    state.filters.release = key || "";
    if (el.releaseSelect) el.releaseSelect.value = state.filters.release;
    state.page = 1;
    updateTabActive();
    apply();
    writeHash();
  }

  // Hebrew month names for the eyebrow line — release_date is Israeli DD/MM/YY.
  const MONTHS_HE = ["ינואר", "פברואר", "מרץ", "אפריל", "מאי", "יוני", "יולי",
                     "אוגוסט", "ספטמבר", "אוקטובר", "נובמבר", "דצמבר"];

  function parseIlDate(d) {
    const parts = String(d || "").split("/");
    if (parts.length !== 3) return null;
    const day = parseInt(parts[0], 10);
    const month = parseInt(parts[1], 10);
    let year = parseInt(parts[2], 10);
    if (!day || !month || Number.isNaN(year)) return null;
    if (year < 100) year += 2000;
    return { day, month, year };
  }

  // "8 במאי, 22 במאי, 12 ביוני ו-10 ביולי 2026" — the year is stated once when
  // every release shares it, and the last item gets the conjunction, the way
  // the hand-written heading used to read.
  function releaseDatesLine(rels) {
    const parsed = rels.map((r) => parseIlDate(r.date)).filter(Boolean);
    if (!parsed.length) return null;
    const sameYear = parsed.every((p) => p.year === parsed[0].year);
    const parts = parsed.map((p, i) => {
      const base = `${p.day} ב${MONTHS_HE[p.month - 1]}`;
      return sameYear && i < parsed.length - 1 ? base : `${base} ${p.year}`;
    });
    if (parts.length === 1) return parts[0];
    return parts.slice(0, -1).join(", ") + " ו-" + parts[parts.length - 1];
  }

  // The section heading used to name the releases by hand ("מהדורות 01–04"),
  // which silently went stale every time a tranche landed. Derive it instead.
  function renderReleaseHeader() {
    const rels = releaseList();
    if (!rels.length) return;
    const first = rels[0].no, last = rels[rels.length - 1].no;

    if (el.releaseTitle) {
      el.releaseTitle.textContent = rels.length > 1
        ? `ארכיון המסמכים — מהדורות ${first}–${last}`
        : `ארכיון המסמכים — ${releaseLabel(first)}`;
    }
    if (el.releaseEyebrow) {
      const dates = releaseDatesLine(rels);
      el.releaseEyebrow.textContent = dates
        ? `ארכיון פתוח · ${state.files.length} קבצים · שוחרר ב-${dates}`
        : `ארכיון פתוח · ${state.files.length} קבצים`;
    }
    // The directive aside used to name a specific release by hand and froze
    // at 02; take the newest date from the data instead.
    if (el.latestReleaseDate) {
      const p = parseIlDate(rels[rels.length - 1].date);
      if (p) {
        el.latestReleaseDate.textContent =
          `${p.year}-${String(p.month).padStart(2, "0")}-${String(p.day).padStart(2, "0")}`;
      }
    }
  }

  // A tranche announced on war.gov but not yet mirrored. Listing it is the
  // honest alternative to a tab strip that quietly stops at the last release
  // we happened to scrape.
  async function renderPending() {
    if (!el.pending) return;
    let list = [];
    try {
      const res = await fetch(PENDING_URL, { cache: "no-cache" });
      if (!res.ok) throw new Error("HTTP " + res.status);
      const data = await res.json();
      list = Array.isArray(data.pending) ? data.pending : [];
    } catch (err) {
      console.warn("pending.json unavailable", err);
      return;                       // no file, no claim
    }
    if (!list.length) return;       // nothing outstanding

    el.pending.innerHTML = list.map((r) => `
      <div class="pending-release-item">
        <p class="pending-release-head">
          <span class="pending-release-badge mono">${escapeHtml(r.no || "?")}</span>
          <strong>מהדורה ${escapeHtml(r.no || "?")} פורסמה ב-${escapeHtml(r.date_he || "")}</strong>
          <span class="pending-release-count">${r.file_count ? escapeHtml(String(r.file_count)) + " קבצים" : ""}</span>
        </p>
        ${r.headline_he ? `<p class="pending-release-body">${escapeHtml(r.headline_he)}</p>` : ""}
        <p class="pending-release-foot">
          החומרים טרם שוקפו לעברית — war.gov חוסם סריקה משרתים, והרענון מתבצע ידנית מהדפדפן.
          ${r.announcement_url ? `<a href="${escapeHtml(r.announcement_url)}" target="_blank" rel="noopener">ההודעה הרשמית ↗</a>` : ""}
        </p>
        ${renderPendingBundles(r)}
      </div>`).join("");
    el.pending.hidden = false;
  }

  function renderPendingBundles(r) {
    const bundles = (r.bundles || []).filter((b) => b && b.url);
    if (!bundles.length) return "";
    return `
      <div class="pending-release-bundles">
        <span class="pending-release-bundles-label">הורדה ישירה מהמקור:</span>
        ${bundles.map((b) => `
          <a class="pending-release-bundle" href="${escapeHtml(b.url)}" target="_blank" rel="noopener">
            <span>${escapeHtml(b.label_he || "חבילה")}</span>
            <span class="mono">${escapeHtml(b.filename || "")}</span>
          </a>`).join("")}
      </div>`;
  }

  /* ------------------------- mobile filter collapse ------------------------- */
  // `release` is deliberately excluded from the count: picking a release is
  // done from the tab strip, which stays visible and shows its own active
  // state, so counting it here would report the same thing twice.
  const COUNTED_FILTERS = ["agency", "incidentDate", "incidentLocation", "type", "search"];

  function activeFilterCount() {
    return COUNTED_FILTERS.filter((k) => state.filters[k]).length;
  }

  function setFiltersExpanded(open) {
    if (!el.filtersToggle || !el.filtersPanel) return;
    el.filtersToggle.setAttribute("aria-expanded", open ? "true" : "false");
    el.filtersPanel.classList.toggle("is-collapsed", !open);
  }

  function updateFilterChrome() {
    if (!el.filtersCount) return;
    const n = activeFilterCount();
    el.filtersCount.textContent = n ? String(n) : "";
    el.filtersCount.hidden = n === 0;
  }

  function initFilterCollapse() {
    if (!el.filtersToggle || !el.filtersPanel) return;
    const mobile = window.matchMedia("(max-width: 768px)");

    function syncToBreakpoint() {
      // Above the breakpoint the CSS ignores .is-collapsed entirely. Below it,
      // start closed — unless a filter is already active (a deep link), in
      // which case hiding the controls that caused it would be baffling.
      setFiltersExpanded(!mobile.matches || activeFilterCount() > 0);
    }

    syncToBreakpoint();
    el.filtersToggle.addEventListener("click", () => {
      setFiltersExpanded(el.filtersToggle.getAttribute("aria-expanded") !== "true");
    });
    mobile.addEventListener("change", syncToBreakpoint);
  }

  // The directive section used to name four agencies by hand. That list was
  // written for Release 01 and never revisited: by Release 05 it still said
  // AARO (0 files) and ODNI (1), while omitting NASA (40), CIA, State, DOE
  // and the Executive Office of the President entirely. Build it from the
  // data instead, with counts, and make each one filter the archive.
  function renderAgencies() {
    if (!el.agencyList) return;
    const counts = new Map();
    state.files.forEach((f) => {
      const key = f.agency;
      if (!key) return;
      if (!counts.has(key)) counts.set(key, { agency: key, he: f.agency_he || key, n: 0 });
      counts.get(key).n += 1;
    });
    const rows = [...counts.values()].sort((a, b) => b.n - a.n);
    if (!rows.length) return;

    // war.gov's agency values have a long tail of one-file entries with long
    // Hebrew names — showing all eleven at once is taller than the four
    // hardcoded rows this replaces. Lead with the substantial ones and put
    // the rest behind a chip, so nothing is hidden permanently.
    const LEAD = 6;
    const chip = (r) => `
      <li>
        <button type="button" class="agency-chip" data-agency="${escapeHtml(r.agency)}"
                title="סינון הארכיון לפי ${escapeHtml(r.he)}">
          <span class="agency-chip-name">${escapeHtml(r.he)}</span>
          <span class="agency-chip-count mono">${r.n}</span>
        </button>
      </li>`;

    const lead = rows.slice(0, LEAD);
    const tail = rows.slice(LEAD);
    el.agencyList.innerHTML =
      lead.map(chip).join("") +
      tail.map((r) => chip(r).replace("<li>", '<li class="agency-tail" hidden>')).join("") +
      (tail.length
        ? `<li><button type="button" class="agency-chip agency-chip-more" id="agency-more">
             +${tail.length} נוספות</button></li>`
        : "");

    const more = el.agencyList.querySelector("#agency-more");
    if (more) {
      more.addEventListener("click", () => {
        el.agencyList.querySelectorAll(".agency-tail").forEach((li) => { li.hidden = false; });
        more.parentElement.remove();
      });
    }

    el.agencyList.querySelectorAll("[data-agency]").forEach((b) => {
      b.addEventListener("click", () => {
        state.filters.agency = b.dataset.agency;
        state.page = 1;
        if (el.agency) el.agency.value = state.filters.agency;
        apply();
        writeHash();
        document.getElementById("release").scrollIntoView({ behavior: "smooth", block: "start" });
      });
    });
  }

  function renderTabs() {
    if (!el.tabs) return;
    const rels = releaseList();
    if (!rels.length) { el.tabs.innerHTML = ""; return; }
    const active = state.filters.release || "";

    const tabBtn = (key, label, count) => {
      const on = key === active;
      return `<button type="button" role="tab" class="release-tab${on ? " is-active" : ""}"` +
        ` aria-selected="${on ? "true" : "false"}" data-release="${escapeHtml(key)}">` +
        `<span class="release-tab-label">${escapeHtml(label)}</span>` +
        `<span class="release-tab-count mono">${count}</span></button>`;
    };

    const html = [tabBtn("", "הכול", state.files.length)];
    rels.forEach((r) => html.push(tabBtn(r.key, releaseLabel(r.no), r.count)));
    el.tabs.innerHTML = html.join("");

    el.tabs.querySelectorAll("[data-release]").forEach((b) => {
      b.addEventListener("click", () => setRelease(b.dataset.release));
    });
  }

  function updateTabActive() {
    if (!el.tabs) return;
    const active = state.filters.release || "";
    el.tabs.querySelectorAll("[data-release]").forEach((b) => {
      const on = b.dataset.release === active;
      b.classList.toggle("is-active", on);
      b.setAttribute("aria-selected", on ? "true" : "false");
    });
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    })[c]);
  }

  function truncate(s, n) {
    return s.length > n ? s.slice(0, n - 1).trimEnd() + "…" : s;
  }

  function showPlaceholderBanner(n) {
    const wrap = document.querySelector("#release .container");
    if (!wrap) return;
    const note = document.createElement("div");
    note.className = "placeholder-banner";
    note.innerHTML = `
      <strong>// המאניפסט ממתין לסריקה</strong>
      <p>מוצגות ${n} רשומות בלבד. war.gov חוסם בוטים — הסריקה מתבצעת מהדפדפן שלך. הוראות מלאות:
      <a href="https://github.com/nadaval56/UFO#איך-מרעננים-את-ה-manifest-חובה-ידנית" target="_blank" rel="noopener">README → איך מרעננים</a>.</p>`;
    const downloads = wrap.querySelector(".release-downloads");
    if (downloads) downloads.parentNode.insertBefore(note, downloads);
  }

  /* ------------------------- load ------------------------- */

  async function load() {
    try {
      const res = await fetch(MANIFEST_URL, { cache: "no-cache" });
      if (!res.ok) throw new Error("HTTP " + res.status);
      const data = await res.json();
      state.files = Array.isArray(data.files) ? data.files : [];
      // If the manifest is the seeded placeholder, show a notice.
      if (data._note && data.total_files < 10) {
        showPlaceholderBanner(data.total_files);
      }
    } catch (err) {
      console.error("manifest load failed", err);
      el.list.innerHTML = `
        <div class="file-list-empty" style="margin:0">
          <p>טעינת המאניפסט נכשלה: ${escapeHtml(err.message)}</p>
          <p style="font-size:.85rem;color:var(--text-dim)">
            ודא ש-<code class="mono">data/manifest.json</code> קיים. לקבלת קובץ אמיתי הרץ
            <code class="mono">python scripts/build_manifest.py</code>.
          </p>
        </div>`;
      el.countNum.textContent = "0";
      return;
    }

    initFilters();
    renderAgencies();
    renderReleaseHeader();
    renderPending();
    applyHash();
    // After applyHash: the collapse decision reads the filter state, and on a
    // deep link that state only exists once the hash has been parsed. Running
    // it earlier left a shared ?type=... link collapsed with an active badge
    // and no visible controls.
    initFilterCollapse();
    bindEvents();
    apply();
  }

  /* ------------------------- filters ------------------------- */

  function initFilters() {
    const agencies = unique(state.files.map((f) => f.agency));
    const types = unique(state.files.map((f) => f.type));

    // Incident dates: prefer display form (matches what the user sees)
    const incidentDates = unique(state.files.map((f) => incidentDateDisplay(f)));
    const incidentLocations = unique(state.files.map((f) => f.incident_location));

    // Release: the dropdown and the tabs are two views of the same dimension.
    // Options carry the stable release key as value, with a "מהדורה NN · date"
    // label; apply() compares against fileRelease(f).
    const rels = releaseList();
    fillSelect(
      el.releaseSelect,
      rels.map((r) => r.key),
      (key) => {
        const r = rels.find((x) => x.key === key);
        return r ? releaseLabel(r.no) + (r.date ? " · " + r.date : "") : key;
      }
    );
    renderTabs();

    // Show the Hebrew agency label the cards use; keep the English in parens
    // since the document codes (DOW-, FBI-, DOS-, EOP-) are English too.
    fillSelect(el.agency, agencies, (v) => {
      const f = state.files.find((x) => x.agency === v);
      const he = f && f.agency_he;
      return he && he !== v ? `${he} (${v})` : v;
    });
    fillSelect(el.type, types, typeLabel);
    fillSelect(el.incidentDate, incidentDates);
    fillSelect(el.incidentLocation, incidentLocations, (v) => {
      const f = state.files.find((x) => x.incident_location === v);
      return f && f.incident_location_he ? `${f.incident_location_he} (${v})` : v;
    });
  }

  function fillSelect(select, values, labelFn) {
    if (!select) return;
    const current = select.value;
    while (select.options.length > 1) select.remove(1);
    values.forEach((v) => {
      const opt = document.createElement("option");
      opt.value = v;
      opt.textContent = labelFn ? labelFn(v) : v;
      select.appendChild(opt);
    });
    if (values.includes(current)) select.value = current;
  }

  /* ------------------------- events ------------------------- */

  function bindFilter(elem, key) {
    if (!elem) return;
    elem.addEventListener("change", () => {
      state.filters[key] = elem.value;
      state.page = 1;
      apply();
      writeHash();
    });
  }

  function bindEvents() {
    bindFilter(el.agency, "agency");
    // Release select drives the same state as the tabs — route through setRelease
    // so the two controls stay visually in sync.
    if (el.releaseSelect) {
      el.releaseSelect.addEventListener("change", () => setRelease(el.releaseSelect.value));
    }
    bindFilter(el.incidentDate, "incidentDate");
    bindFilter(el.incidentLocation, "incidentLocation");
    bindFilter(el.type, "type");

    let searchDebounce;
    el.search.addEventListener("input", () => {
      clearTimeout(searchDebounce);
      searchDebounce = setTimeout(() => {
        state.filters.search = el.search.value.trim().toLowerCase();
        state.page = 1;
        apply();
        writeHash();
      }, 150);
    });

    el.reset.addEventListener("click", resetFilters);
    if (el.emptyReset) el.emptyReset.addEventListener("click", resetFilters);

    window.addEventListener("hashchange", () => {
      applyHash();
      apply();
    });
  }

  function resetFilters() {
    state.filters = {
      agency: "", release: "", incidentDate: "",
      incidentLocation: "", type: "", search: "",
    };
    state.page = 1;
    if (el.agency) el.agency.value = "";
    if (el.releaseSelect) el.releaseSelect.value = "";
    if (el.incidentDate) el.incidentDate.value = "";
    if (el.incidentLocation) el.incidentLocation.value = "";
    if (el.type) el.type.value = "";
    if (el.search) el.search.value = "";
    updateTabActive();
    apply();
    writeHash();
  }

  /* ------------------------- hash routing ------------------------- */

  function applyHash() {
    const hash = decodeURIComponent(location.hash.replace(/^#/, ""));
    if (!hash.startsWith("release")) return;

    const [pathPart, queryPart] = hash.split("?");
    const segments = pathPart.split("/");
    const pageIdx = segments.indexOf("page");
    if (pageIdx !== -1 && segments[pageIdx + 1]) {
      const n = parseInt(segments[pageIdx + 1], 10);
      if (Number.isInteger(n) && n > 0) state.page = n;
    }
    if (queryPart) {
      const params = new URLSearchParams(queryPart);
      state.filters.agency = params.get("agency") || "";
      state.filters.release = params.get("release") || "";
      state.filters.incidentDate = params.get("incident_date") || "";
      state.filters.incidentLocation = params.get("location") || "";
      state.filters.type = params.get("type") || "";
      state.filters.search = (params.get("q") || "").toLowerCase();

      if (el.agency) el.agency.value = state.filters.agency;
      if (el.releaseSelect) el.releaseSelect.value = state.filters.release;
      updateTabActive();
      if (el.incidentDate) el.incidentDate.value = state.filters.incidentDate;
      if (el.incidentLocation) el.incidentLocation.value = state.filters.incidentLocation;
      if (el.type) el.type.value = state.filters.type;
      if (el.search) el.search.value = state.filters.search;
    }
  }

  function writeHash() {
    const params = new URLSearchParams();
    if (state.filters.agency) params.set("agency", state.filters.agency);
    if (state.filters.release) params.set("release", state.filters.release);
    if (state.filters.incidentDate) params.set("incident_date", state.filters.incidentDate);
    if (state.filters.incidentLocation) params.set("location", state.filters.incidentLocation);
    if (state.filters.type) params.set("type", state.filters.type);
    if (state.filters.search) params.set("q", state.filters.search);
    const q = params.toString();
    const hash = `release/page/${state.page}` + (q ? `?${q}` : "");
    history.replaceState(null, "", "#" + hash);
  }

  /* ------------------------- filter + render ------------------------- */

  function apply() {
    const { agency, release, incidentDate, incidentLocation, type, search } = state.filters;

    state.filtered = state.files.filter((f) => {
      if (agency && f.agency !== agency) return false;
      if (type && f.type !== type) return false;
      if (release && fileRelease(f) !== release) return false;
      if (incidentDate && incidentDateDisplay(f) !== incidentDate) return false;
      if (incidentLocation && f.incident_location !== incidentLocation) return false;
      if (search) {
        const hay = [
          f.title, f.title_he, f.filename, f.id,
          f.agency, f.agency_he,
          f.incident_location, f.incident_location_he,
          f.summary_he, f.narrative_he,
        ].filter(Boolean).join(" ").toLowerCase();
        if (!hay.includes(search)) return false;
      }
      return true;
    });

    const totalPages = Math.max(1, Math.ceil(state.filtered.length / PAGE_SIZE));
    if (state.page > totalPages) state.page = totalPages;
    if (state.page < 1) state.page = 1;

    el.countNum.textContent = String(state.filtered.length);

    updateFilterChrome();
    renderList();
    renderPagination(totalPages);
  }

  function renderList() {
    if (!state.filtered.length) {
      el.list.innerHTML = "";
      el.empty.hidden = false;
      return;
    }
    el.empty.hidden = true;

    const start = (state.page - 1) * PAGE_SIZE;
    const slice = state.filtered.slice(start, start + PAGE_SIZE);

    el.list.innerHTML = slice.map((f, idx) => {
      const headline = cardHeadline(f);
      const headlineSafe = escapeHtml(headline);
      const blurb = escapeHtml(cardBlurb(f, headline));
      const rawName = escapeHtml(f.filename || f.id || "");
      const safeType = escapeHtml(typeLabel(f.type));
      const idAttr = escapeHtml(f.id || f.filename || "");
      const isCodeHeadline = !f.title_he && /^[\d_A-Z\-]+(\.pdf)?$/i.test(headline);

      // Build metadata items, skipping empty ones entirely
      const agency = f.agency_he || f.agency;
      const incDate = incidentDateDisplay(f);
      const incLoc = incidentLocationDisplayHe(f);
      const metaItems = [];
      if (!isBlank(agency)) metaItems.push({ icon: "🏛", label: "סוכנות", value: agency });
      if (!isBlank(f.release_date)) metaItems.push({ icon: "📅", label: "שחרור", value: f.release_date });
      if (!isBlank(incDate)) metaItems.push({ icon: "🕰", label: "אירוע", value: incDate });
      if (!isBlank(incLoc)) metaItems.push({ icon: "📍", label: "מיקום", value: incLoc });

      const metaHtml = metaItems.map((it) => `
        <li class="file-card-meta-item">
          <span class="meta-icon" aria-hidden="true">${it.icon}</span>
          <span class="meta-label">${escapeHtml(it.label)}</span>
          <span class="meta-value">${escapeHtml(it.value)}</span>
        </li>`).join("");

      const downloadHtml = f.source_url
        ? (f._url_is_record_page
            ? `<a class="file-card-download file-card-download-page" href="${escapeHtml(f.source_url)}" target="_blank" rel="noopener" data-stop-card title="פתיחה בעמוד הקובץ באתר המקור">פתח ↗</a>`
            : `<a class="file-card-download" href="${escapeHtml(f.source_url)}" target="_blank" rel="noopener" data-stop-card>הורדה ↓</a>`)
        : `<span class="file-card-download file-card-download-disabled" data-stop-card>אין קישור</span>`;

      return `
        <article class="file-card" tabindex="0" data-id="${idAttr}" data-index="${start + idx}" role="button" aria-label="פתח פרטים עבור ${headlineSafe}">
          <header class="file-card-head">
            <h3 class="file-card-title${isCodeHeadline ? " code-title" : ""}" dir="${isCodeHeadline ? "ltr" : "rtl"}">${headlineSafe}</h3>
            <span class="file-card-type-badge mono">.${safeType}</span>
          </header>
          ${blurb ? `<p class="file-card-blurb">${blurb}</p>` : ""}
          ${metaItems.length ? `<ul class="file-card-meta">${metaHtml}</ul>` : ""}
          <div class="file-card-footer">
            ${downloadHtml}
            <p class="file-card-filename mono" title="${rawName}">${rawName}</p>
          </div>
        </article>
      `;
    }).join("");

    el.list.querySelectorAll(".file-card").forEach((card) => {
      card.addEventListener("click", (e) => {
        if (e.target.closest("[data-stop-card]")) return;
        const idx = parseInt(card.dataset.index, 10);
        openFile(state.filtered[idx]);
      });
      card.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          const idx = parseInt(card.dataset.index, 10);
          openFile(state.filtered[idx]);
        }
      });
    });
  }

  function openFile(file) {
    if (!file || !file.id) return;
    window.location.href = "file.html?id=" + encodeURIComponent(file.id);
  }

  /* ------------------------- pagination ------------------------- */

  function renderPagination(totalPages) {
    if (totalPages <= 1) { el.pagination.innerHTML = ""; return; }

    const current = state.page;
    const html = [];

    html.push(`<button type="button" data-page="${current - 1}" ${current === 1 ? "disabled" : ""} aria-label="עמוד קודם">PREV</button>`);

    const pagesToShow = buildPageList(current, totalPages);
    pagesToShow.forEach((p) => {
      if (p === "…") {
        html.push(`<span class="page-ellipsis">…</span>`);
      } else {
        html.push(`<button type="button" data-page="${p}" ${p === current ? 'aria-current="page"' : ""}>${p}</button>`);
      }
    });

    html.push(`<button type="button" data-page="${current + 1}" ${current === totalPages ? "disabled" : ""} aria-label="עמוד הבא">NEXT</button>`);

    el.pagination.innerHTML = html.join("");

    el.pagination.querySelectorAll("button[data-page]").forEach((b) => {
      b.addEventListener("click", () => {
        const p = parseInt(b.dataset.page, 10);
        if (!Number.isInteger(p) || p < 1 || p > totalPages) return;
        state.page = p;
        apply();
        writeHash();
        document.getElementById("release").scrollIntoView({ behavior: "smooth", block: "start" });
      });
    });
  }

  function buildPageList(current, total) {
    const pages = new Set([1, total, current, current - 1, current + 1]);
    const list = [...pages].filter((p) => p >= 1 && p <= total).sort((a, b) => a - b);
    const out = [];
    for (let i = 0; i < list.length; i++) {
      out.push(list[i]);
      if (i < list.length - 1 && list[i + 1] - list[i] > 1) out.push("…");
    }
    return out;
  }

  /* ------------------------- go ------------------------- */

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", load);
  } else {
    load();
  }
})();
