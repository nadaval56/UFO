/* ============================================================
   file-detail.js
   Loads manifest.json, finds entry by ?id=..., renders the
   standalone file detail page (gallery + metadata + texts).
   No dependencies — vanilla JS.
   ============================================================ */

(function () {
  "use strict";

  const MANIFEST_URL = "data/manifest.json";

  /* ------------------------- state ------------------------- */

  const state = {
    file: null,
    previews: [],         // [{ page, kind, path }, ...]
    previewsAreFallback: false, // true if showing preview_pages_fallback
    galleryIdx: 0,
  };

  /* ------------------------- elements ------------------------- */

  const el = {
    loading: document.getElementById("file-loading"),
    error: document.getElementById("file-error"),
    article: document.getElementById("file-article"),

    eyebrow: document.getElementById("file-eyebrow"),
    title: document.getElementById("file-title"),
    filename: document.getElementById("file-filename"),

    gallery: document.getElementById("gallery"),
    galleryEmpty: document.getElementById("gallery-empty"),
    galleryImage: document.getElementById("gallery-image"),
    galleryPrev: document.getElementById("gallery-prev"),
    galleryNext: document.getElementById("gallery-next"),
    galleryCounter: document.getElementById("gallery-counter"),
    galleryKind: document.getElementById("gallery-kind"),
    galleryThumbs: document.getElementById("gallery-thumbs"),
    galleryFallbackNote: document.getElementById("gallery-fallback-note"),

    metaAgency: document.getElementById("meta-agency"),
    metaType: document.getElementById("meta-type"),
    metaRelease: document.getElementById("meta-release"),
    metaIncidentDate: document.getElementById("meta-incident-date"),
    metaIncidentLoc: document.getElementById("meta-incident-loc"),
    metaPages: document.getElementById("meta-pages"),
    metaSize: document.getElementById("meta-size"),
    metaKinds: document.getElementById("meta-kinds"),
    metaDownload: document.getElementById("meta-download"),
    metaDownload2: document.getElementById("meta-download-2"),

    narrativeSection: document.getElementById("narrative-section"),
    narrativeBody: document.getElementById("narrative-body"),

    summarySection: document.getElementById("summary-section"),
    summaryHe: document.getElementById("summary-he"),
    summaryEn: document.getElementById("summary-en"),
    summaryEnWrap: document.getElementById("summary-en-wrap"),

    ocrHeSection: document.getElementById("ocr-he-section"),
    ocrHeBody: document.getElementById("ocr-he-body"),
    ocrHeByline: null, // populated below
    ocrEnWrap: document.getElementById("ocr-en-wrap"),
    ocrEnSection: document.getElementById("ocr-en-section"),
    ocrEnBody: document.getElementById("ocr-en-body"),
    ocrFullSection: document.getElementById("ocr-full-section"),
    ocrFullBody: document.getElementById("ocr-full-body"),
  };
  el.ocrHeByline = el.ocrHeSection
    ? el.ocrHeSection.querySelector(".text-block-byline")
    : null;

  /* ------------------------- utils ------------------------- */

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    })[c]);
  }

  function getQueryId() {
    const params = new URLSearchParams(window.location.search);
    return params.get("id");
  }

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

  const KIND_LABEL_HE = {
    photo: "תצלום",
    illustration: "רישום",
    clipping: "קטע עיתונות",
    typewritten: "מודפס",
    handwritten: "כתב יד",
    cover: "כריכה",
    divider: "מפריד",
    blank: "ריק",
    mixed: "מעורב",
  };

  function kindLabelHe(k) {
    return KIND_LABEL_HE[k] || k || "—";
  }

  function showError(msg) {
    el.loading.hidden = true;
    el.article.hidden = true;
    el.error.hidden = false;
    el.error.textContent = msg;
  }

  /* ------------------------- load + dispatch ------------------------- */

  async function load() {
    const id = getQueryId();
    if (!id) {
      showError("חסר מזהה קובץ ב-URL. חזרה לארכיון: index.html#release");
      return;
    }

    let manifest;
    try {
      const res = await fetch(MANIFEST_URL, { cache: "no-cache" });
      if (!res.ok) throw new Error("HTTP " + res.status);
      manifest = await res.json();
    } catch (err) {
      console.error("manifest load failed", err);
      showError("טעינת המאניפסט נכשלה: " + err.message);
      return;
    }

    const file = (manifest.files || []).find((f) => f.id === id);
    if (!file) {
      showError(`לא נמצא קובץ עם המזהה: ${id}`);
      return;
    }

    state.file = file;
    // Prefer curated preview_pages (visually interesting). If empty, fall back
    // to preview_pages_fallback (first non-blank pages of the document).
    const primary = Array.isArray(file.preview_pages) ? file.preview_pages : [];
    const fallback = Array.isArray(file.preview_pages_fallback)
      ? file.preview_pages_fallback
      : [];
    if (primary.length > 0) {
      state.previews = primary;
      state.previewsAreFallback = false;
    } else {
      state.previews = fallback;
      state.previewsAreFallback = fallback.length > 0;
    }

    render();

    el.loading.hidden = true;
    el.article.hidden = false;

    bindGalleryEvents();
    applyHashImage();
  }

  /* ------------------------- render ------------------------- */

  function render() {
    const f = state.file;

    // עדכון title של הדפדפן
    const titleHe = f.title_he || f.title || f.filename || "מסמך";
    document.title = `${titleHe} — PURSUE`;

    // כותרת
    el.eyebrow.textContent = f.agency_he || f.agency || "מסמך";
    el.title.textContent = titleHe;
    el.title.setAttribute("dir", f.title_he ? "rtl" : "ltr");
    if (f.filename) {
      el.filename.textContent = f.filename;
    } else {
      el.filename.hidden = true;
    }

    // מטא-דאטה
    el.metaAgency.textContent = f.agency_he || f.agency || "—";
    el.metaType.textContent = typeLabel(f.type);
    el.metaRelease.textContent = f.release_date || "—";
    el.metaIncidentDate.textContent = f.incident_date_display || f.incident_date || "N/A";
    el.metaIncidentLoc.textContent = f.incident_location_he || f.incident_location || "N/A";
    el.metaPages.textContent = f.page_count != null ? String(f.page_count) : "—";
    el.metaSize.textContent = formatBytes(f.size_bytes);
    el.metaKinds.textContent = (f.content_kinds || []).map(kindLabelHe).join(" · ") || "—";

    // קישור הורדה
    setupDownload(el.metaDownload, f);
    setupDownload(el.metaDownload2, f);

    // גלריה
    if (state.previews.length > 0) {
      el.gallery.hidden = false;
      el.galleryEmpty.hidden = true;
      if (el.galleryFallbackNote) {
        el.galleryFallbackNote.hidden = !state.previewsAreFallback;
      }
      renderThumbs();
      showImage(0);
    } else {
      el.gallery.hidden = true;
      el.galleryEmpty.hidden = false;
    }

    // תיאור ארכאולוגי (Claude)
    if (f.narrative_he) {
      el.narrativeSection.hidden = false;
      el.narrativeBody.innerHTML = paragraphsToHtml(f.narrative_he);
    } else {
      el.narrativeSection.hidden = true;
    }

    // תקציר רשמי
    if (f.summary_he || f.summary_en) {
      el.summarySection.hidden = false;
      if (f.summary_he) {
        el.summaryHe.innerHTML = paragraphsToHtml(f.summary_he);
        el.summaryHe.hidden = false;
      } else {
        el.summaryHe.hidden = true;
      }
      if (f.summary_en) {
        el.summaryEnWrap.hidden = false;
        el.summaryEn.textContent = f.summary_en;
        // כשאין עברית, פותחים אוטומטית
        el.summaryEnWrap.open = !f.summary_he;
      } else {
        el.summaryEnWrap.hidden = true;
      }
    } else {
      el.summarySection.hidden = true;
    }

    // OCR — תרגום עברי (prefer full text_he; fall back to 3000-char text_preview_he)
    const heFull = f.text_he;
    const heExcerpt = f.text_preview_he;
    const heText = heFull || heExcerpt;
    if (heText) {
      el.ocrHeSection.hidden = false;
      el.ocrHeBody.innerHTML = paragraphsToHtml(heText);
      if (el.ocrHeByline) {
        el.ocrHeByline.textContent = heFull
          ? "תרגום עברי מלא של ה-OCR."
          : "תרגום עברי של ~3,000 התווים הראשונים מתוך ה-OCR (תרגום מלא בעבודה).";
      }
    } else {
      el.ocrHeSection.hidden = true;
    }

    // English OCR collapsible — contains both the excerpt and the full text.
    // Show the wrap if either field exists; show each inner sub-section by data.
    const hasEn = !!(f.text_preview_en || f.text_en);
    el.ocrEnWrap.hidden = !hasEn;
    if (f.text_preview_en) {
      el.ocrEnSection.hidden = false;
      el.ocrEnBody.innerHTML = paragraphsToHtml(f.text_preview_en);
    } else {
      el.ocrEnSection.hidden = true;
    }
    if (f.text_en) {
      el.ocrFullSection.hidden = false;
      el.ocrFullBody.textContent = f.text_en;
    } else {
      el.ocrFullSection.hidden = true;
    }
  }

  function paragraphsToHtml(text) {
    return String(text)
      .split(/\n{2,}/)
      .map((p) => p.trim())
      .filter(Boolean)
      .map((p) => `<p>${escapeHtml(p).replace(/\n/g, "<br>")}</p>`)
      .join("");
  }

  function setupDownload(node, f) {
    if (!node) return;
    if (f.source_url) {
      node.href = f.source_url;
      node.removeAttribute("aria-disabled");
      node.classList.remove("btn-disabled");
      node.textContent = f._url_is_record_page
        ? "פתיחת הרשומה באתר המקור ↗"
        : "הורדה מאתר המקור ↗";
    } else {
      node.removeAttribute("href");
      node.setAttribute("aria-disabled", "true");
      node.classList.add("btn-disabled");
      node.textContent = "אין קישור הורדה זמין";
    }
  }

  /* ------------------------- gallery ------------------------- */

  function renderThumbs() {
    el.galleryThumbs.innerHTML = state.previews.map((p, i) => {
      const path = escapeHtml(p.path || "");
      const kind = escapeHtml(kindLabelHe(p.kind));
      const page = p.page;
      return `
        <button type="button" class="gallery-thumb" data-idx="${i}"
                role="tab" aria-label="עמוד ${page} (${kind})">
          <img src="${path}" alt="" loading="lazy">
          <span class="gallery-thumb-page mono">${page}</span>
        </button>`;
    }).join("");

    el.galleryThumbs.querySelectorAll(".gallery-thumb").forEach((btn) => {
      btn.addEventListener("click", () => {
        const i = parseInt(btn.dataset.idx, 10);
        if (Number.isInteger(i)) showImage(i);
      });
    });
  }

  function showImage(idx) {
    const n = state.previews.length;
    if (n === 0) return;
    // wrap-around
    state.galleryIdx = ((idx % n) + n) % n;
    const p = state.previews[state.galleryIdx];
    el.galleryImage.src = p.path;
    el.galleryImage.alt = `תצוגה מקדימה — עמוד ${p.page} (${kindLabelHe(p.kind)})`;
    el.galleryCounter.textContent = `${state.galleryIdx + 1} / ${n} · עמוד ${p.page}`;
    el.galleryKind.textContent = kindLabelHe(p.kind);

    // עדכון רצועת ה-thumbs (active state + גלילה למרכז)
    el.galleryThumbs.querySelectorAll(".gallery-thumb").forEach((btn, i) => {
      const active = i === state.galleryIdx;
      btn.classList.toggle("is-active", active);
      btn.setAttribute("aria-selected", active ? "true" : "false");
      if (active && typeof btn.scrollIntoView === "function") {
        btn.scrollIntoView({ block: "nearest", inline: "center", behavior: "smooth" });
      }
    });

    // עדכון hash בלי לדחוף לhistory
    const newHash = `#page-${p.page}`;
    if (location.hash !== newHash) {
      history.replaceState(null, "", location.pathname + location.search + newHash);
    }
  }

  function applyHashImage() {
    const m = location.hash.match(/^#page-(\d+)$/);
    if (!m) return;
    const page = parseInt(m[1], 10);
    const idx = state.previews.findIndex((p) => p.page === page);
    if (idx >= 0) showImage(idx);
  }

  function bindGalleryEvents() {
    el.galleryPrev.addEventListener("click", () => showImage(state.galleryIdx - 1));
    el.galleryNext.addEventListener("click", () => showImage(state.galleryIdx + 1));

    document.addEventListener("keydown", (e) => {
      // התעלמות כשמקלידים בשדה
      if (e.target.matches("input, textarea, select")) return;
      if (state.previews.length === 0) return;
      // RTL: חץ ימינה = הקודם, חץ שמאלה = הבא (כיוון קריאה עברי)
      if (e.key === "ArrowRight") { e.preventDefault(); showImage(state.galleryIdx - 1); }
      else if (e.key === "ArrowLeft") { e.preventDefault(); showImage(state.galleryIdx + 1); }
    });
  }

  /* ------------------------- go ------------------------- */

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", load);
  } else {
    load();
  }
})();
