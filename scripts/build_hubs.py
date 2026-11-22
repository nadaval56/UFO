#!/usr/bin/env python3
"""Hub pages: one Hebrew explainer per release and one page per topic.

  releases/<NN>.html   "what is in release NN" (data/hubs/releases/<NN>.json)
  topics/<slug>.html   a topic across the archive (data/hubs/topics/<slug>.json)
  topics/index.html    the list of both

Content JSON (written by Claude agents, reviewed, committed):
  {"slug", "h1", "title", "description", "intro", "ids": [...]}
`intro` uses the same tiny Markdown subset as data/digest/*.md (paragraphs,
`### ` headings, `- ` lists) plus `[[<record id>]]`, which renders as a link to
that document titled by its seo_title_he. For a release, `ids` are the featured
records; every record of the release is listed below them anyway. For a topic,
`ids` are its members.

Pages are built from the file.html template (same header, footer, privacy and
accessibility scripts) with <base href="/">, like doc/*.html. Run through
build_sitemap.py, which also lists them in sitemap.xml; never hand-edit the
output. topic_memberships() is used by build_static_pages.py to link each
document page back to its topics and release article.
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

from build_static_pages import doc_path, digest_html

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "data" / "manifest.json"
TEMPLATE = ROOT / "file.html"
HUBS = ROOT / "data" / "hubs"
BASE = "https://pursue.co.il"
SITE = 'עב"מים'
TYPE_HE = {"pdf": "מסמך", "vid": "סרטון", "img": "תמונה", "aud": "הקלטה"}
MONTHS = ["ינואר", "פברואר", "מרץ", "אפריל", "מאי", "יוני", "יולי", "אוגוסט",
          "ספטמבר", "אוקטובר", "נובמבר", "דצמבר"]


def esc(v) -> str:
    return html.escape(str(v if v is not None else ""), quote=True)


def load(kind: str) -> list[dict]:
    d = HUBS / kind
    if not d.exists():
        return []
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(d.glob("*.json"))]


def release_iso(d: str) -> str:
    """'20/11/26' (D/M/YY, as the manifest stores release_date) -> '2026-11-20'."""
    day, month, year = (int(x) for x in d.split("/"))
    return f"{2000 + year:04d}-{month:02d}-{day:02d}"


def release_he(d: str) -> str:
    day, month, year = (int(x) for x in d.split("/"))
    return f"{day} ב{MONTHS[month - 1]} {2000 + year}"


def doc_title(f: dict) -> str:
    return f.get("seo_title_he") or f.get("title_he") or f.get("title") or f["id"]


def body_html(text: str, by_id: dict) -> str:
    """digest_html() escapes everything; [[id]] survives escaping unchanged
    (ids contain no HTML-special characters) and is then turned into a link."""
    out = digest_html(text)

    def link(m):
        rid = html.unescape(m.group(1))
        f = by_id.get(rid)
        if not f:
            raise SystemExit(f"build_hubs: unknown id in [[...]]: {rid!r}")
        return f'<a href="{esc(doc_path(rid))}">{esc(doc_title(f))}</a>'

    # Lazy match + "not followed by ]" so ids that end in "]" (59_214434_sp_16_[7.18.1963]) work.
    return re.sub(r"\[\[(.+?)\]\](?!\])", link, out)


def item_html(f: dict, blurb: bool) -> str:
    meta = " · ".join(x for x in (
        TYPE_HE.get(f.get("type"), ""), f.get("agency_he") or f.get("agency") or "",
        (f.get("incident_location_he") or "") if f.get("incident_location_he") not in ("לא ידוע", "N/A") else "",
    ) if x)
    s = (f'<li><a href="{esc(doc_path(f["id"]))}">{esc(doc_title(f))}</a>'
         f'<span class="related-meta">{esc(meta)}</span>')
    if blurb and f.get("narrative_he"):
        n = f["narrative_he"]
        n = n if len(n) <= 260 else n[:260].rsplit(" ", 1)[0] + "…"
        s += f'<p class="hub-blurb">{esc(n)}</p>'
    return s + "</li>"


def list_block(label: str, files: list[dict], blurb: bool) -> str:
    return ('<section class="text-block">\n'
            f'          <header class="text-block-head"><p class="text-block-label mono">{esc(label)}</p></header>\n'
            f'          <ul class="related-list hub-list">{"".join(item_html(f, blurb) for f in files)}</ul>\n'
            '        </section>\n')


class Shell:
    """file.html cut into head / header and footer, with the document-only
    parts (noindex, file-detail.js) removed."""

    def __init__(self):
        t = TEMPLATE.read_text(encoding="utf-8")
        t = re.sub(r"\s*<!-- Legacy route:.*?-->\s*<meta name=\"robots\"[^>]*>", "", t, count=1, flags=re.S)
        t = t.replace('<meta charset="UTF-8">', '<meta charset="UTF-8">\n  <base href="/">', 1)
        t = re.sub(r'\s*<script src="assets/js/file-detail.js" defer></script>', "", t, count=1)
        start, end = t.index("<main"), t.index("</main>") + len("</main>")
        self.head, self.tail = t[:start], t[end:]

    def page(self, *, title, desc, url, og_type, main, ld) -> str:
        h = self.head
        full = f"{title} | {SITE}"

        def attr(pattern, name, value):
            nonlocal h
            h = re.sub(pattern, lambda m: re.sub(rf'{name}="[^"]*"', f'{name}="{esc(value)}"', m.group(0)), h, count=1)

        h = re.sub(r"<title>.*?</title>", f"<title>{esc(full)}</title>", h, count=1)
        attr(r'<meta name="description"[^>]*>', "content", desc)
        attr(r'<link rel="canonical"[^>]*>', "href", url)
        attr(r'<meta property="og:type"[^>]*>', "content", og_type)
        attr(r'<meta property="og:title"[^>]*>', "content", full)
        attr(r'<meta property="og:description"[^>]*>', "content", desc)
        attr(r'<meta property="og:url"[^>]*>', "content", url)
        attr(r'<meta name="twitter:title"[^>]*>', "content", full)
        attr(r'<meta name="twitter:description"[^>]*>', "content", desc)
        lds = "".join(
            '\n  <script type="application/ld+json">'
            + json.dumps(x, ensure_ascii=False).replace("</", "<\\/") + "</script>" for x in ld)
        h = h.replace("</head>", lds + "\n</head>", 1)
        return h + main + self.tail


def crumbs_ld(items: list[tuple[str, str]]) -> dict:
    return {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": i + 1, "name": n, "item": u} for i, (n, u) in enumerate(items)]}


def main_html(crumb: str, eyebrow: str, h1: str, intro: str, blocks: str) -> str:
    return f"""<main id="top">
    <div class="container file-page hub-page">
      <nav class="file-crumb" aria-label="פירורי לחם">{crumb}</nav>
      <article class="file-article">
        <header class="file-head">
          <p class="file-eyebrow mono">{esc(eyebrow)}</p>
          <h1 class="file-title">{esc(h1)}</h1>
        </header>
        <section class="text-block text-block-digest">
          <div class="text-block-body">{intro}</div>
        </section>
        {blocks}
      </article>
    </div>
  </main>"""


def topic_memberships() -> dict[str, list[dict]]:
    """record id -> [{"href", "title"}] of the topic pages it belongs to."""
    out: dict[str, list[dict]] = {}
    for t in load("topics"):
        for rid in t["ids"]:
            out.setdefault(rid, []).append({"href": f"topics/{t['slug']}.html", "title": t["h1"]})
    return out


def build() -> list[tuple[str, str]]:
    """Write every hub page; return [(url, lastmod)] for the sitemap."""
    m = json.loads(MANIFEST.read_text(encoding="utf-8"))
    files = m["files"]
    by_id = {f["id"]: f for f in files}
    shell = Shell()
    releases, topics = load("releases"), load("topics")
    latest = max(release_iso(f["release_date"]) for f in files if f.get("release_date"))
    urls: list[tuple[str, str]] = []
    (ROOT / "releases").mkdir(exist_ok=True)
    (ROOT / "topics").mkdir(exist_ok=True)
    index_crumb = '<a href="index.html#release">← לארכיון</a> · <a href="topics/">כל הנושאים</a>'

    rel_slugs = sorted(r["slug"] for r in releases)
    for r in releases:
        slug = r["slug"]
        members = [f for f in files if f.get("release_no") == slug]
        if not members:
            raise SystemExit(f"build_hubs: no records for release {slug}")
        date = members[0]["release_date"]
        featured = [by_id[i] for i in r["ids"]]
        nav = []
        i = rel_slugs.index(slug)
        if i > 0:
            nav.append(f'<a href="releases/{rel_slugs[i-1]}.html">→ מהדורה {rel_slugs[i-1]}</a>')
        if i < len(rel_slugs) - 1:
            nav.append(f'<a href="releases/{rel_slugs[i+1]}.html">מהדורה {rel_slugs[i+1]} ←</a>')
        blocks = (list_block("// מומלץ לקריאה", featured, True)
                  + list_block(f"// כל {len(members)} הקבצים במהדורה", members, False)
                  + (f'<p class="hub-nav">{" · ".join(nav)}</p>' if nav else ""))
        url = f"{BASE}/releases/{slug}.html"
        ld = [{"@context": "https://schema.org", "@type": "Article", "headline": r["h1"],
               "description": r["description"], "inLanguage": "he", "url": url,
               "datePublished": release_iso(date), "image": f"{BASE}/assets/img/og-cover-v2.png",
               "author": {"@type": "Organization", "name": "עב\"מים: כל מה שהותר לפרסום", "url": BASE + "/"},
               "publisher": {"@type": "Organization", "name": "עב\"מים: כל מה שהותר לפרסום", "url": BASE + "/"}},
              crumbs_ld([("עב\"מים", BASE + "/"), ("נושאים ומהדורות", f"{BASE}/topics/"), (r["h1"], url)])]
        page = shell.page(title=r["title"], desc=r["description"], url=url, og_type="article", ld=ld,
                          main=main_html(index_crumb, f"// מהדורה {slug} · {release_he(date)} · {len(members)} קבצים",
                                         r["h1"], body_html(r["intro"], by_id), blocks))
        (ROOT / "releases" / f"{slug}.html").write_text(page, encoding="utf-8")
        urls.append((url, release_iso(date)))

    for t in topics:
        members = [by_id[i] for i in t["ids"]]
        url = f"{BASE}/topics/{t['slug']}.html"
        ld = [{"@context": "https://schema.org", "@type": "CollectionPage", "name": t["h1"],
               "description": t["description"], "inLanguage": "he", "url": url,
               "mainEntity": {"@type": "ItemList", "numberOfItems": len(members), "itemListElement": [
                   {"@type": "ListItem", "position": k + 1, "url": f"{BASE}/{doc_path(f['id'])}", "name": doc_title(f)}
                   for k, f in enumerate(members)]}},
              crumbs_ld([("עב\"מים", BASE + "/"), ("נושאים ומהדורות", f"{BASE}/topics/"), (t["h1"], url)])]
        page = shell.page(title=t["title"], desc=t["description"], url=url, og_type="website", ld=ld,
                          main=main_html(index_crumb, f"// נושא · {len(members)} פריטים בארכיון", t["h1"],
                                         body_html(t["intro"], by_id),
                                         list_block(f"// {len(members)} הפריטים בנושא", members, True)))
        (ROOT / "topics" / f"{t['slug']}.html").write_text(page, encoding="utf-8")
        urls.append((url, max(release_iso(f["release_date"]) for f in members)))

    # topics/index.html
    t_items = "".join(
        f'<li><a href="topics/{esc(t["slug"])}.html">{esc(t["h1"])}</a>'
        f'<span class="related-meta">{len(t["ids"])} פריטים</span><p class="hub-blurb">{esc(t["description"])}</p></li>'
        for t in topics)
    r_items = "".join(
        f'<li><a href="releases/{esc(r["slug"])}.html">{esc(r["h1"])}</a>'
        f'<span class="related-meta">{esc(release_he(next(f["release_date"] for f in files if f.get("release_no") == r["slug"])))}</span>'
        f'<p class="hub-blurb">{esc(r["description"])}</p></li>'
        for r in sorted(releases, key=lambda r: r["slug"], reverse=True))
    intro = ("<p>המדריכים כאן מסדרים את מאות המסמכים, התמונות והסרטונים שממשל ארה\"ב פרסם על עב\"מים לפי נושא ולפי מהדורה. "
             "כל דף מסביר בעברית מה יש בארכיון על הנושא ומקשר לכל מסמך, עם הקישור למקור הרשמי. "
             "לחיפוש חופשי וסינון: <a href=\"index.html#release\">דפדפן הארכיון</a>. "
             "לרשימה המלאה: <a href=\"archive.html\">אינדקס כל המסמכים</a>.</p>")
    blocks = ('<section class="text-block">\n          <header class="text-block-head"><p class="text-block-label mono">// נושאים</p></header>\n'
              f'          <ul class="related-list hub-list">{t_items}</ul>\n        </section>\n'
              '<section class="text-block">\n          <header class="text-block-head"><p class="text-block-label mono">// מה יש בכל מהדורה</p></header>\n'
              f'          <ul class="related-list hub-list">{r_items}</ul>\n        </section>\n')
    url = f"{BASE}/topics/"
    title = 'מדריכים לקבצי העב"מים: לפי נושא ולפי מהדורה'
    desc = 'מדריכים בעברית לארכיון העב"מים של ממשל ארה"ב: AAWSAP, Blue Book, נאס"א, ה-CIA, ה-FBI, סרטוני הפנטגון ומה פורסם בכל מהדורה.'
    page = shell.page(title=title, desc=desc, url=url, og_type="website",
                      ld=[crumbs_ld([("עב\"מים", BASE + "/"), ("נושאים ומהדורות", url)])],
                      main=main_html('<a href="index.html#release">← לארכיון</a>', "// מדריכים",
                                     title, intro, blocks))
    (ROOT / "topics" / "index.html").write_text(page, encoding="utf-8")
    urls.insert(0, (url, latest))
    print(f"build_hubs: {len(releases)} release pages, {len(topics)} topic pages, topics/index.html")
    return urls


if __name__ == "__main__":
    build()
