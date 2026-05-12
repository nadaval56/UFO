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

  // Bump the auto year in the footer if present.
  const yearEl = document.querySelector("[data-year]");
  if (yearEl) yearEl.textContent = new Date().getFullYear();
})();
