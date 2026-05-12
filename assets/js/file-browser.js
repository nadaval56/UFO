/* ============================================================
   file-browser.js
   Drives the Release 01 file browser: loads manifest.json,
   renders cards, handles pagination, filters, search and modal.
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
    filters: { agency: "", releaseDate: "", type: "", search: "" },
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
    type: document.getElementById("filter-type"),
    search: document.getElementById("filter-search"),
    reset: document.getElementById("filter-reset"),
    modal: document.getElementById("file-modal"),
    modalTitle: document.getElementById("file-modal-title"),
    modalAgency: document.getElementById("modal-agency"),
    modalType: document.getElementById("modal-type"),
    modalReleaseDate: document.getElementById("modal-release-date"),
    modalIncidentDate: document.getElementById("modal-incident-date"),
    modalIncidentLocation: document.getElementById("modal-incident-location"),
    modalSize: document.getElementById("modal-size"),
    modalSummaryHe: document.getElementById("modal-summary-he"),
    modalSummaryHeWrap: document.getElementById("modal-summary-he-wrap"),
    modalSummaryEn: document.getElementById("modal-summary-en"),
    modalSummaryEnWrap: document.getElementById("modal-summary-en-wrap"),
    modalDownload: document.getElementById("modal-download"),
  };

  /* ------------------------- utilities ------------------------- */

  function formatBytes(bytes) {
    if (bytes == null || isNaN(bytes)) return "—";
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
    if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + " MB";
    return (bytes / (1024 * 1024 * 1024)).toFixed(2) + " GB";
  }

  function typeLabel(t) {
    const map = { pdf: "PDF", img: "תמונה", vid: "וידאו", doc: "מסמך", txt: "טקסט" };
    return map[t] || (t ? t.toUpperCase() : "—");
  }

  function agencyLabel(a) {
    return a || "—";
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

  /* ------------------------- load ------------------------- */

  async function load() {
    try {
      const res = await fetch(MANIFEST_URL, { cache: "no-cache" });
      if (!res.ok) throw new Error("HTTP " + res.status);
      const data = await res.json();
      state.files = Array.isArray(data.files) ? data.files : [];
      state.releaseDateGlobal = data.release_date || null;
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

    fillSelect(el.agency, agencies);
    fillSelect(el.type, types, typeLabel);
    fillSelect(el.releaseDate, releaseDates);
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

  function bindEvents() {
    el.agency.addEventListener("change", () => { state.filters.agency = el.agency.value; state.page = 1; apply(); writeHash(); });
    el.releaseDate.addEventListener("change", () => { state.filters.releaseDate = el.releaseDate.value; state.page = 1; apply(); writeHash(); });
    el.type.addEventListener("change", () => { state.filters.type = el.type.value; state.page = 1; apply(); writeHash(); });

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

    document.querySelectorAll("[data-close-modal]").forEach((n) =>
      n.addEventListener("click", closeModal)
    );
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && !el.modal.hidden) closeModal();
    });

    window.addEventListener("hashchange", () => {
      applyHash();
      apply();
    });
  }

  function resetFilters() {
    state.filters = { agency: "", releaseDate: "", type: "", search: "" };
    state.page = 1;
    el.agency.value = "";
    el.releaseDate.value = "";
    el.type.value = "";
    el.search.value = "";
    apply();
    writeHash();
  }

  /* ------------------------- hash routing ------------------------- */

  function applyHash() {
    // accepted forms:
    //   #release/page/3
    //   #release/page/3?agency=FBI&type=pdf&q=serial_130
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
      state.filters.type = params.get("type") || "";
      state.filters.search = (params.get("q") || "").toLowerCase();

      // reflect in inputs
      if (el.agency) el.agency.value = state.filters.agency;
      if (el.releaseDate) el.releaseDate.value = state.filters.releaseDate;
      if (el.type) el.type.value = state.filters.type;
      if (el.search) el.search.value = state.filters.search;
    }
  }

  function writeHash() {
    const params = new URLSearchParams();
    if (state.filters.agency) params.set("agency", state.filters.agency);
    if (state.filters.releaseDate) params.set("release", state.filters.releaseDate);
    if (state.filters.type) params.set("type", state.filters.type);
    if (state.filters.search) params.set("q", state.filters.search);
    const q = params.toString();
    const hash = `release/page/${state.page}` + (q ? `?${q}` : "");
    // avoid scroll jump
    history.replaceState(null, "", "#" + hash);
  }

  /* ------------------------- filter + render ------------------------- */

  function apply() {
    const { agency, releaseDate, type, search } = state.filters;

    state.filtered = state.files.filter((f) => {
      if (agency && f.agency !== agency) return false;
      if (type && f.type !== type) return false;
      if (releaseDate && (f.release_date || state.releaseDateGlobal) !== releaseDate) return false;
      if (search) {
        const hay = (f.filename + " " + (f.id || "")).toLowerCase();
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
      const safeName = escapeHtml(f.filename);
      const safeAgency = escapeHtml(agencyLabel(f.agency));
      const safeType = escapeHtml(typeLabel(f.type));
      const idAttr = escapeHtml(f.id || f.filename);
      const summary = (f.summary_he || f.summary_en || "").trim();
      const snippet = summary ? escapeHtml(truncate(summary, 180)) : "";
      const summaryHtml = snippet
        ? `<p class="file-card-summary" dir="${f.summary_he ? "rtl" : "ltr"}">${snippet}</p>`
        : "";
      return `
        <article class="file-card" tabindex="0" data-id="${idAttr}" data-index="${start + idx}" role="button" aria-label="פתח פרטים עבור ${safeName}">
          <div class="file-card-main">
            <div class="file-card-name">${safeName}</div>
            ${summaryHtml}
          </div>
          <div class="file-card-field">
            <span class="file-card-field-label">סוכנות</span>
            <span class="file-card-field-value">${safeAgency}</span>
          </div>
          <div class="file-card-field">
            <span class="file-card-field-label">סוג</span>
            <span class="file-card-field-value">${safeType}</span>
          </div>
          <a class="file-card-download" href="${escapeHtml(f.source_url || "#")}" target="_blank" rel="noopener" data-stop-card>הורדה ↓</a>
        </article>
      `;
    }).join("");

    el.list.querySelectorAll(".file-card").forEach((card) => {
      card.addEventListener("click", (e) => {
        if (e.target.closest("[data-stop-card]")) return;
        const idx = parseInt(card.dataset.index, 10);
        openModal(state.filtered[idx]);
      });
      card.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          const idx = parseInt(card.dataset.index, 10);
          openModal(state.filtered[idx]);
        }
      });
    });
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
    // Always show first, last, current, neighbours, with "…" gaps.
    const pages = new Set([1, total, current, current - 1, current + 1]);
    const list = [...pages].filter((p) => p >= 1 && p <= total).sort((a, b) => a - b);
    const out = [];
    for (let i = 0; i < list.length; i++) {
      out.push(list[i]);
      if (i < list.length - 1 && list[i + 1] - list[i] > 1) out.push("…");
    }
    return out;
  }

  /* ------------------------- modal ------------------------- */

  function openModal(file) {
    if (!file) return;
    el.modalTitle.textContent = file.filename;
    el.modalAgency.textContent = agencyLabel(file.agency);
    el.modalType.textContent = typeLabel(file.type);
    el.modalReleaseDate.textContent = file.release_date || state.releaseDateGlobal || "—";
    if (el.modalIncidentDate) el.modalIncidentDate.textContent = file.incident_date || "לא ידוע";
    if (el.modalIncidentLocation) el.modalIncidentLocation.textContent = file.incident_location || "לא ידוע";
    el.modalSize.textContent = formatBytes(file.size_bytes);
    el.modalDownload.href = file.source_url || "#";

    if (file.summary_he) {
      el.modalSummaryHe.textContent = file.summary_he;
      el.modalSummaryHeWrap.hidden = false;
    } else {
      el.modalSummaryHeWrap.hidden = true;
    }
    if (file.summary_en) {
      el.modalSummaryEn.textContent = file.summary_en;
      el.modalSummaryEnWrap.hidden = false;
      el.modalSummaryEnWrap.open = !file.summary_he;
    } else {
      el.modalSummaryEnWrap.hidden = true;
    }

    el.modal.hidden = false;
    el.modal.setAttribute("aria-hidden", "false");
    document.body.style.overflow = "hidden";
  }

  function closeModal() {
    el.modal.hidden = true;
    el.modal.setAttribute("aria-hidden", "true");
    document.body.style.overflow = "";
  }

  /* ------------------------- go ------------------------- */

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", load);
  } else {
    load();
  }
})();
