/* ============================================================
   file-browser.js
   Drives the Release 01 file browser: loads manifest.json,
   renders cards, handles pagination, filters, and search.
   Cards link to the standalone file.html?id=... page.
   No dependencies — vanilla JS.
   ============================================================ */

(function () {
  "use strict";

  const MANIFEST_URL = "data/manifest.json";
  const PAGE_SIZE = 10;

  /* ------------------------- state ------------------------- */

  const state = {
    files: [],
    filtered: [],
    page: 1,
    filters: {
      agency: "",
      releaseDate: "",
      incidentDate: "",
      incidentLocation: "",
      type: "",
      search: "",
    },
    releaseDateGlobal: null,
  };

  /* ------------------------- elements ------------------------- */

  const el = {
    list: document.getElementById("file-list"),
    empty: document.getElementById("file-list-empty"),
    emptyReset: document.getElementById("file-list-empty-reset"),
    pagination: document.getElementById("pagination"),
    countNum: document.getElementById("file-count-num"),
    agency: document.getElementById("filter-agency"),
    releaseDate: document.getElementById("filter-release"),
    incidentDate: document.getElementById("filter-incident-date"),
    incidentLocation: document.getElementById("filter-incident-location"),
    type: document.getElementById("filter-type"),
    search: document.getElementById("filter-search"),
    reset: document.getElementById("filter-reset"),
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

  function incidentDateDisplay(f) {
    return f.incident_date_display || f.incident_date || null;
  }

  function incidentLocationDisplayHe(f) {
    return f.incident_location_he || f.incident_location || null;
  }

  function unique(arr) {
    return Array.from(new Set(arr.filter(Boolean))).sort();
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
      state.releaseDateGlobal = data.release_date || null;
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
    applyHash();
    bindEvents();
    apply();
  }

  /* ------------------------- filters ------------------------- */

  function initFilters() {
    const agencies = unique(state.files.map((f) => f.agency));
    const types = unique(state.files.map((f) => f.type));
    const releaseDates = state.releaseDateGlobal
      ? [state.releaseDateGlobal]
      : unique(state.files.map((f) => f.release_date));

    // Incident dates: prefer display form (matches what the user sees)
    const incidentDates = unique(state.files.map((f) => incidentDateDisplay(f)));
    const incidentLocations = unique(state.files.map((f) => f.incident_location));

    fillSelect(el.agency, agencies);
    fillSelect(el.type, types, typeLabel);
    fillSelect(el.releaseDate, releaseDates);
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
    bindFilter(el.releaseDate, "releaseDate");
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
      agency: "", releaseDate: "", incidentDate: "",
      incidentLocation: "", type: "", search: "",
    };
    state.page = 1;
    if (el.agency) el.agency.value = "";
    if (el.releaseDate) el.releaseDate.value = "";
    if (el.incidentDate) el.incidentDate.value = "";
    if (el.incidentLocation) el.incidentLocation.value = "";
    if (el.type) el.type.value = "";
    if (el.search) el.search.value = "";
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
      state.filters.releaseDate = params.get("release") || "";
      state.filters.incidentDate = params.get("incident_date") || "";
      state.filters.incidentLocation = params.get("location") || "";
      state.filters.type = params.get("type") || "";
      state.filters.search = (params.get("q") || "").toLowerCase();

      if (el.agency) el.agency.value = state.filters.agency;
      if (el.releaseDate) el.releaseDate.value = state.filters.releaseDate;
      if (el.incidentDate) el.incidentDate.value = state.filters.incidentDate;
      if (el.incidentLocation) el.incidentLocation.value = state.filters.incidentLocation;
      if (el.type) el.type.value = state.filters.type;
      if (el.search) el.search.value = state.filters.search;
    }
  }

  function writeHash() {
    const params = new URLSearchParams();
    if (state.filters.agency) params.set("agency", state.filters.agency);
    if (state.filters.releaseDate) params.set("release", state.filters.releaseDate);
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
    const { agency, releaseDate, incidentDate, incidentLocation, type, search } = state.filters;

    state.filtered = state.files.filter((f) => {
      if (agency && f.agency !== agency) return false;
      if (type && f.type !== type) return false;
      if (releaseDate && (f.release_date || state.releaseDateGlobal) !== releaseDate) return false;
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
      const titleHe = escapeHtml(fileTitleHe(f));
      const rawName = escapeHtml(f.filename || f.id || "");
      const safeAgency = escapeHtml(agencyDisplayHe(f));
      const safeType = escapeHtml(typeLabel(f.type));
      const idAttr = escapeHtml(f.id || f.filename || "");
      const incDate = incidentDateDisplay(f);
      const incLoc = incidentLocationDisplayHe(f);

      const isCodeTitle = !f.title_he && (f.title || f.filename || "").match(/^[\d_A-Z\-]+\.pdf$/i);
      const titleClass = isCodeTitle ? "file-card-title mono code-title" : "file-card-title";

      const blurb = escapeHtml(narrativeBlurb(f.narrative_he));
      return `
        <article class="file-card" tabindex="0" data-id="${idAttr}" data-index="${start + idx}" role="button" aria-label="פתח פרטים עבור ${titleHe}">
          <div class="file-card-main">
            <div class="${titleClass}" dir="${f.title_he ? "rtl" : "ltr"}">${titleHe}</div>
            ${isCodeTitle ? "" : `<div class="file-card-filename mono">${rawName}</div>`}
            ${blurb ? `<p class="file-card-blurb">${blurb}</p>` : ""}
          </div>
          <div class="file-card-field">
            <span class="file-card-field-label">סוכנות</span>
            <span class="file-card-field-value">${safeAgency}</span>
          </div>
          <div class="file-card-field">
            <span class="file-card-field-label">תאריך שחרור</span>
            <span class="file-card-field-value">${f.release_date ? escapeHtml(f.release_date) : "—"}</span>
          </div>
          <div class="file-card-field">
            <span class="file-card-field-label">תאריך אירוע</span>
            <span class="file-card-field-value">${incDate ? escapeHtml(incDate) : "N/A"}</span>
          </div>
          <div class="file-card-field">
            <span class="file-card-field-label">מיקום</span>
            <span class="file-card-field-value">${incLoc ? escapeHtml(incLoc) : "N/A"}</span>
          </div>
          <div class="file-card-field">
            <span class="file-card-field-label">סוג</span>
            <span class="file-card-field-value">.${safeType}</span>
          </div>
          ${f.source_url
            ? (f._url_is_record_page
                ? `<a class="file-card-download file-card-download-page" href="${escapeHtml(f.source_url)}" target="_blank" rel="noopener" data-stop-card title="פתיחה בעמוד הקובץ באתר המקור">פתח ↗</a>`
                : `<a class="file-card-download" href="${escapeHtml(f.source_url)}" target="_blank" rel="noopener" data-stop-card>הורדה ↓</a>`)
            : `<span class="file-card-download file-card-download-disabled" data-stop-card>אין קישור</span>`}
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
