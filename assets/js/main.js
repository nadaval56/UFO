/* main.js — small UI helpers (smooth-anchor scroll offset, year, etc.).
   File browser logic lives in file-browser.js. */
(function () {
  "use strict";

  // Header offset for anchor navigation (sticky header is ~72px).
  function scrollToAnchor(hash) {
    const target = document.querySelector(hash);
    if (!target) return;
    const headerHeight = document.querySelector(".site-header")?.offsetHeight || 0;
    const y = target.getBoundingClientRect().top + window.pageYOffset - headerHeight - 8;
    window.scrollTo({ top: y, behavior: "smooth" });
  }

  document.querySelectorAll('a[href^="#"]').forEach((a) => {
    a.addEventListener("click", (e) => {
      const href = a.getAttribute("href");
      if (!href || href === "#") return;
      const target = document.querySelector(href);
      if (!target) return;
      e.preventDefault();
      scrollToAnchor(href);
    });
  });

  // Mobile: the ten source-bundle buttons are folded behind one control.
  // Collapse only when the mobile breakpoint is actually active — on desktop
  // the CSS ignores .is-collapsed, but leaving the class off keeps the DOM
  // honest and means a resize into mobile starts closed rather than open.
  const dlToggle = document.getElementById("release-downloads-toggle");
  const dlPanel = document.getElementById("release-downloads");
  if (dlToggle && dlPanel) {
    const mobile = window.matchMedia("(max-width: 768px)");

    function setExpanded(open) {
      dlToggle.setAttribute("aria-expanded", open ? "true" : "false");
      dlPanel.classList.toggle("is-collapsed", !open);
    }

    function syncToBreakpoint() {
      // Above the breakpoint the grid is always visible; below it, start closed.
      setExpanded(!mobile.matches);
    }

    syncToBreakpoint();
    dlToggle.addEventListener("click", () => {
      setExpanded(dlToggle.getAttribute("aria-expanded") !== "true");
    });
    mobile.addEventListener("change", syncToBreakpoint);
  }

  // Bump the auto year in the footer if present.
  const yearEl = document.querySelector("[data-year]");
  if (yearEl) yearEl.textContent = new Date().getFullYear();
})();
