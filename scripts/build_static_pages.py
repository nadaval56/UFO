#!/usr/bin/env python3
"""
build_static_pages.py — pre-render one static HTML page per document, at
doc/<name>.html, from file.html and data/manifest.json.

Why: file.html renders everything in JavaScript from the manifest, so a crawler
first sees "טוען…" and an empty article, and every one of the 450 documents
shares a single URL path distinguished only by ?id=. Here each document gets
its own real page with the title, description, canonical URL, JSON-LD,
metadata, summaries, Hebrew OCR translation and first preview image already
in the HTML. file-detail.js still runs on top (gallery, video player, lazy
full OCR); it reads the id from <meta name="doc-id">.

The page file name must match `docPath()` in assets/js/file-detail.js and
file-browser.js: non [A-Za-z0-9._-] runs become "_", trimmed.

Generated output — never hand-edit doc/*.html. Run via build_sitemap.py (which
calls this first) after every manifest change.
"""
from __future__ import annotations

import html
import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "data" / "manifest.json"
TEMPLATE = ROOT / "file.html"
OUT_DIR = ROOT / "doc"
BASE = "https://pursue.co.il"
SITE = 'עב"מים'

KIND_LABEL_HE = {
    "photo": "תצלום", "illustration": "רישום", "clipping": "קטע עיתונות",
    "typewritten": "מודפס", "handwritten": "כתב יד", "cover": "כריכה",
    "divider": "מפריד", "blank": "ריק", "mixed": "מעורב",
}
TYPE_LABEL = {"pdf": "PDF", "img": "תמונה", "vid": "וידאו", "aud": "שמע", "doc": "מסמך", "txt": "טקסט"}


def page_name(record_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", record_id).strip("_") + ".html"


def doc_path(record_id: str) -> str:
    return "doc/" + page_name(record_id)


def esc(v) -> str:
    return html.escape(str(v if v is not None else ""), quote=True)


def paragraphs(text: str) -> str:
    parts = [p.strip() for p in re.split(r"\n{2,}", str(text)) if p.strip()]
    return "".join(f"<p>{esc(p).replace(chr(10), '<br>')}</p>" for p in parts)


def fmt_bytes(n) -> str:
    if n is None:
        return "—"
    try:
        n = float(n)
    except (TypeError, ValueError):
        return "—"
    for unit, div in (("GB", 1024 ** 3), ("MB", 1024 ** 2), ("KB", 1024)):
        if n >= div:
            return f"{n / div:.{2 if unit == 'GB' else 1}f} {unit}"
    return f"{int(n)} B"


class Page:
    """Tiny, id-addressed editor over the file.html template. Every target
    element is a leaf in the template (no nested element of the same tag), so
    a non-greedy match on the element's own closing tag is exact."""

    def __init__(self, src: str):
        self.s = src

    def _find(self, el_id: str):
        m = re.search(rf'<(\w+)([^>]*\bid="{re.escape(el_id)}"[^>]*)>', self.s)
        if not m:
            raise KeyError(el_id)
        return m

    def inner(self, el_id: str, content: str) -> None:
        m = self._find(el_id)
        tag = m.group(1)
        close = self.s.index(f"</{tag}>", m.end())
        self.s = self.s[: m.end()] + content + self.s[close:]

    def show(self, el_id: str) -> None:
        m = self._find(el_id)
        attrs = re.sub(r"\s+hidden(?=[\s>]|$)", "", m.group(2))
        self.s = self.s[: m.start()] + f"<{m.group(1)}{attrs}>" + self.s[m.end():]

    def hide(self, el_id: str) -> None:
        m = self._find(el_id)
        if re.search(r"\bhidden\b", m.group(2)):
            return
        self.s = self.s[: m.start()] + f"<{m.group(1)}{m.group(2)} hidden>" + self.s[m.end():]

    def attr(self, el_id: str, name: str, value: str) -> None:
        m = self._find(el_id)
        attrs = m.group(2)
        if re.search(rf'\b{name}="', attrs):
            attrs = re.sub(rf'\b{name}="[^"]*"', f'{name}="{esc(value)}"', attrs)
        else:
            attrs += f' {name}="{esc(value)}"'
        self.s = self.s[: m.start()] + f"<{m.group(1)}{attrs}>" + self.s[m.end():]

    def head_attr(self, selector_re: str, attr: str, value: str) -> None:
        """Set `attr` on the first <meta>/<link> tag matching selector_re."""
        m = re.search(selector_re, self.s)
        if not m:
            raise KeyError(selector_re)
        tag = m.group(0)
        new = re.sub(rf'\b{attr}="[^"]*"', f'{attr}="{esc(value)}"', tag)
        self.s = self.s[: m.start()] + new + self.s[m.end():]


# Nouns for the meta description, where "PDF"/"שמע" read badly in a sentence.
DESC_NOUN = {"pdf": "מסמך", "img": "תמונה", "vid": "סרטון", "aud": "הקלטה"}
DESC_MAX = 155  # roughly what Google shows before it truncates the snippet
DOC_CODE_RE = re.compile(r"[A-Z]+-UAP-[A-Z]*\d+")


def meta_description(f: dict, title_he: str) -> str:
    """Search snippet: type, document code and agency first, then the most
    specific Hebrew text, cut at a word boundary. summary_he opens with
    war.gov's boilerplate on hundreds of records (every INDOPACOM report, all
    37 DIRDs), so leading with it made the first ~155 characters — all Google
    shows — identical across 317 pages. narrative_he is per-document."""
    body = f.get("narrative_he") or f.get("summary_he") or title_he
    code = DOC_CODE_RE.match(f.get("title") or "")
    head = " · ".join(x for x in (
        " ".join(x for x in (DESC_NOUN.get(f.get("type"), "פריט"), code and code.group(0)) if x),
        f.get("agency_he") or f.get("agency")) if x)
    s = re.sub(r"\s+", " ", f"{head} · {body}").strip()
    if len(s) <= DESC_MAX:
        return s
    return s[: DESC_MAX - 1].rsplit(" ", 1)[0].rstrip(",.;:—-־ ") + "…"


def related_for(f: dict, files: list[dict], n: int = 8) -> list[dict]:
    """Neighbours by document code within the same release and agency (so a
    DIRD page links to the DIRDs around it), topped up from the same release."""
    same = sorted((x for x in files if x.get("release") == f.get("release")
                   and x.get("agency") == f.get("agency")), key=lambda x: x["id"])
    i = next((k for k, x in enumerate(same) if x["id"] == f["id"]), 0)
    around = same[max(0, i - n // 2): i] + same[i + 1: i + 1 + n]
    out = around[:n]
    if len(out) < n:
        seen = {x["id"] for x in out} | {f["id"]}
        out += [x for x in files if x.get("release") == f.get("release")
                and x["id"] not in seen][: n - len(out)]
    return out


def render(template: str, f: dict, files: list[dict] | None = None) -> str:
    p = Page(template)
    title_he = f.get("title_he") or f.get("title") or f.get("filename") or "מסמך"
    url = f"{BASE}/{doc_path(f['id'])}"
    desc = meta_description(f, title_he)
    full_title = f"{title_he} — {SITE}"

    # ---- head ----
    # <base href="/"> lets the page live in doc/ while every relative asset,
    # data and navigation URL in the shared template keeps resolving from the
    # site root, exactly as on file.html.
    p.s = p.s.replace('<meta charset="UTF-8">',
                      '<meta charset="UTF-8">\n  <base href="/">\n'
                      f'  <meta name="doc-id" content="{esc(f["id"])}">', 1)
    p.s = re.sub(r"<title>.*?</title>", f"<title>{esc(full_title)}</title>", p.s, count=1)
    p.head_attr(r'<meta name="description"[^>]*>', "content", desc)
    p.head_attr(r'<link rel="canonical"[^>]*>', "href", url)
    p.s = re.sub(r'\s*<!-- Legacy route:.*?-->\s*<meta name="robots"[^>]*>', "", p.s, count=1, flags=re.S)
    p.head_attr(r'<meta property="og:title"[^>]*>', "content", full_title)
    p.head_attr(r'<meta property="og:description"[^>]*>', "content", desc)
    p.head_attr(r'<meta property="og:url"[^>]*>', "content", url)
    p.head_attr(r'<meta name="twitter:title"[^>]*>', "content", full_title)
    p.head_attr(r'<meta name="twitter:description"[^>]*>', "content", desc)

    previews = f.get("preview_pages") or f.get("preview_pages_fallback") or []
    first = previews[0] if previews else None
    if first and first.get("path"):
        img = f"{BASE}/{first['path']}"
        p.head_attr(r'<meta property="og:image"[^>]*>', "content", img)
        p.head_attr(r'<meta name="twitter:image"[^>]*>', "content", img)

    ld = {
        "@context": "https://schema.org", "@type": "CreativeWork",
        "name": title_he, "alternateName": f.get("title"), "description": desc,
        "inLanguage": "he", "url": url, "identifier": f["id"],
        "license": "https://www.usa.gov/government-works", "isAccessibleForFree": True,
        "creditText": f.get("agency_he") or f.get("agency"),
        "isPartOf": {"@type": "Collection", "name": 'עב"מים — כל מה שהותר לפרסום', "url": f"{BASE}/"},
        "publisher": {"@type": "Organization", "name": "U.S. Department of War"},
    }
    if f.get("source_url"):
        ld["sameAs"] = f["source_url"]
    if f.get("incident_date") and f["incident_date"] != "N/A":
        ld["temporalCoverage"] = f["incident_date"]
    if f.get("incident_location_he"):
        ld["contentLocation"] = {"@type": "Place", "name": f["incident_location_he"]}
    if first and first.get("path"):
        ld["image"] = f"{BASE}/{first['path']}"
    ld = {k: v for k, v in ld.items() if v is not None}
    crumbs = {
        "@context": "https://schema.org", "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "הארכיון", "item": f"{BASE}/"},
            {"@type": "ListItem", "position": 2, "name": f"מהדורה {f.get('release_no') or ''}".strip(),
             "item": f"{BASE}/archive.html#{f.get('release') or ''}"},
            {"@type": "ListItem", "position": 3, "name": title_he, "item": url},
        ],
    }

    def script_json(obj) -> str:
        return json.dumps(obj, ensure_ascii=False).replace("</", "<\\/")

    # The page's own record, so file-detail.js needn't fetch the manifest.
    record = {k: v for k, v in f.items() if k != "text_en"}
    p.s = p.s.replace(
        "</head>",
        f'  <script type="application/ld+json">{script_json(ld)}</script>\n'
        f'  <script type="application/ld+json">{script_json(crumbs)}</script>\n'
        f'  <script type="application/json" id="doc-data">{script_json(record)}</script>\n</head>', 1)

    # ---- body ----
    p.hide("file-loading")
    p.show("file-article")
    p.inner("file-eyebrow", esc(f.get("agency_he") or f.get("agency") or "מסמך"))
    p.inner("file-title", esc(title_he))
    p.attr("file-title", "dir", "rtl" if f.get("title_he") else "ltr")
    if f.get("filename"):
        p.inner("file-filename", esc(f["filename"]))
    else:
        p.hide("file-filename")

    rel = (f"מהדורה {f['release_no']}" + (f" · {f['release_date']}" if f.get("release_date") else "")
           if f.get("release_no") else (f.get("release_date") or "—"))
    p.inner("meta-agency", esc(f.get("agency_he") or f.get("agency") or "—"))
    p.inner("meta-type", esc(TYPE_LABEL.get(f.get("type"), (f.get("type") or "—").upper())))
    p.inner("meta-release", esc(rel))
    p.inner("meta-incident-date", esc(f.get("incident_date_display") or f.get("incident_date") or "N/A"))
    p.inner("meta-incident-loc", esc(f.get("incident_location_he") or f.get("incident_location") or "N/A"))
    p.inner("meta-pages", esc(f["page_count"]) if f.get("page_count") is not None else "—")
    p.inner("meta-size", esc(fmt_bytes(f.get("size_bytes"))))
    p.inner("meta-kinds", esc(" · ".join(KIND_LABEL_HE.get(k, k) for k in f.get("content_kinds") or []) or "—"))
    for dl in ("meta-download", "meta-download-2"):
        if f.get("source_url"):
            p.attr(dl, "href", f["source_url"])

    # First preview as a plain image, so the page has a real <img> without JS.
    # The gallery script replaces it with the full carousel.
    if first and first.get("path") and not f.get("media_url"):
        p.show("gallery")
        p.attr("gallery-image", "src", first["path"])
        p.attr("gallery-image", "alt", f"{title_he} — עמוד {first.get('page', 1)}")

    if f.get("narrative_he"):
        p.show("narrative-section")
        p.inner("narrative-body", paragraphs(f["narrative_he"]))
    if f.get("summary_he") or f.get("summary_en"):
        p.show("summary-section")
        if f.get("summary_he"):
            p.inner("summary-he", paragraphs(f["summary_he"]))
        if f.get("summary_en"):
            p.show("summary-en-wrap")
            p.inner("summary-en", esc(f["summary_en"]))
    he_text = f.get("text_he") or f.get("text_preview_he")
    if he_text:
        p.show("ocr-he-section")
        p.inner("ocr-he-body", paragraphs(he_text))
    if f.get("text_preview_en") or f.get("text_en_path") or f.get("text_en"):
        p.show("ocr-en-wrap")
        if f.get("text_preview_en"):
            p.show("ocr-en-section")
            p.inner("ocr-en-body", paragraphs(f["text_preview_en"]))
    rel_docs = related_for(f, files or [])
    if rel_docs:
        items = "".join(
            f'<li><a href="{esc(doc_path(r["id"]))}">{esc(r.get("title_he") or r.get("title") or r["id"])}</a>'
            f'<span class="related-meta">{esc(r.get("agency_he") or r.get("agency") or "")}</span></li>'
            for r in rel_docs)
        block = (
            '<section class="text-block" aria-label="מסמכים קשורים">\n'
            '          <header class="text-block-head"><p class="text-block-label mono">'
            f'// עוד מ{esc("מהדורה " + f["release_no"]) if f.get("release_no") else "הארכיון"}</p></header>\n'
            f'          <ul class="related-list">{items}</ul>\n        </section>\n\n        ')
        p.s = p.s.replace("<!-- footer פעולות -->", block + "<!-- footer פעולות -->", 1)
    return p.s


def build() -> int:
    m = json.loads(MANIFEST.read_text(encoding="utf-8"))
    template = TEMPLATE.read_text(encoding="utf-8")
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)   # drop pages for records that no longer exist
    OUT_DIR.mkdir()
    seen: dict[str, str] = {}
    for f in m["files"]:
        if not f.get("id"):
            continue
        name = page_name(f["id"])
        if name in seen:
            raise SystemExit(f"page-name collision: {f['id']!r} and {seen[name]!r} -> {name}")
        seen[name] = f["id"]
        (OUT_DIR / name).write_text(render(template, f, m["files"]), encoding="utf-8")
    print(f"Wrote {len(seen)} static document pages to {OUT_DIR.relative_to(ROOT)}/")
    return len(seen)


if __name__ == "__main__":
    build()
