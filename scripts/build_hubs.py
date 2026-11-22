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


THUMBS = ROOT / "assets" / "thumbs"
CODE_RE = re.compile(r"^([A-Z]{2,5})-UAP-([A-Z]*\d+[A-Za-z]?)")
GLYPH = {"vid": "▶", "aud": "◉", "img": "▣", "pdf": "▤"}


def code_label(f: dict) -> str:
    """Short citation label: 'DOW-UAP-D206, ...' -> 'DOW-D206'."""
    m = CODE_RE.match(f.get("title") or "")
    return f"{m.group(1)}-{m.group(2)}" if m else TYPE_HE.get(f.get("type"), "מסמך")


def year_of(f: dict) -> int | None:
    d = str(f.get("incident_date") or "")
    m = re.search(r"\b(19\d\d|20\d\d)\b", d)
    if m:
        return int(m.group(1))
    m = re.search(r"/(\d\d)$", d)
    if m:
        y = int(m.group(1))
        return 1900 + y if y > 30 else 2000 + y
    m = re.search(r"\b(19\d\d|20\d\d)\b", f.get("title") or "")
    return int(m.group(1)) if m else None


def thumb(f: dict) -> str | None:
    """A 400x300 card thumbnail from the record's first local preview, made
    once into assets/thumbs/ (committed). Videos and audio have no local image."""
    pv = (f.get("preview_pages") or []) + (f.get("preview_pages_fallback") or [])
    if not pv:
        return None
    src = ROOT / pv[0]["path"]
    if not src.exists():
        return None
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", f["id"]).strip("_") + ".jpg"
    out = THUMBS / name
    if not out.exists():
        try:
            from PIL import Image
        except ImportError:
            return None
        THUMBS.mkdir(parents=True, exist_ok=True)
        im = Image.open(src).convert("RGB")
        w = 400
        im = im.resize((w, max(1, round(im.height * w / im.width))))
        # Scans: keep the top (letterhead, title). Photos: centre crop.
        top = 0 if f.get("type") == "pdf" else max(0, (im.height - 300) // 2)
        im.crop((0, top, w, top + 300)).save(out, "JPEG", quality=70, optimize=True, progressive=True)
    return f"assets/thumbs/{name}"


def blurb(f: dict, n: int = 170) -> str:
    t = f.get("narrative_he") or ""
    if " - " in t[:90]:
        t = t.split(" - ", 1)[1]
    return t if len(t) <= n else t[:n].rsplit(" ", 1)[0] + "…"


def body_html(text: str, by_id: dict) -> tuple[str, list[tuple[str, str]]]:
    """digest_html() escapes everything; [[id]] survives escaping unchanged and
    becomes a compact citation chip (the full title is in the cards below and
    in the chip's tooltip). Returns (html, [(anchor, heading)]) for the TOC."""
    out = digest_html(text)

    def link(m):
        rid = html.unescape(m.group(1))
        f = by_id.get(rid)
        if not f:
            raise SystemExit(f"build_hubs: unknown id in [[...]]: {rid!r}")
        return (f'<a class="cite mono" href="{esc(doc_path(rid))}" title="{esc(doc_title(f))}">'
                f'{esc(code_label(f))}</a>')

    # Lazy match + "not followed by ]" so ids that end in "]" (59_214434_sp_16_[7.18.1963]) work.
    out = re.sub(r"\[\[(.+?)\]\](?!\])", link, out)
    toc: list[tuple[str, str]] = []

    def anchor(m):
        a = f"s{len(toc) + 1}"
        toc.append((a, html.unescape(m.group(1))))
        return f'<h2 id="{a}">{m.group(1)}</h2>'

    out = re.sub(r"<h3>(.*?)</h3>", anchor, out)
    return out, toc


def card(f: dict, big: bool = False) -> str:
    th = thumb(f)
    year = year_of(f)
    meta = " · ".join(str(x) for x in (TYPE_HE.get(f.get("type"), ""),
                                      f.get("agency_he") or f.get("agency") or "", year or "") if x)
    img = (f'<img src="{esc(th)}" alt="" loading="lazy" decoding="async" width="400" height="300">' if th
           else f'<span class="doc-glyph" aria-hidden="true">{GLYPH.get(f.get("type"), "▤")}</span>')
    return (f'<li class="doc-card{" doc-card-big" if big else ""}"><a href="{esc(doc_path(f["id"]))}">'
            f'<span class="doc-thumb doc-thumb-{esc(f.get("type") or "pdf")}">{img}'
            f'<span class="doc-code mono">{esc(code_label(f))}</span></span>'
            f'<span class="doc-card-body"><span class="doc-meta mono">{esc(meta)}</span>'
            f'<span class="doc-title">{esc(doc_title(f))}</span>'
            f'<span class="doc-blurb">{esc(blurb(f))}</span></span></a></li>')


def cards(files: list[dict], first: int, label_more: str, big: bool = False) -> str:
    """The first `first` cards, the rest behind a native <details> (no JS; the
    links stay in the HTML for crawlers)."""
    head = "".join(card(f, big) for f in files[:first])
    rest = files[first:]
    s = f'<ul class="doc-grid">{head}</ul>'
    if rest:
        s += (f'<details class="hub-more"><summary><span>{esc(label_more)}</span></summary>'
              f'<ul class="doc-grid">{"".join(card(f) for f in rest)}</ul></details>')
    return s


def stats(files: list[dict]) -> list[str]:
    from collections import Counter
    years = [y for y in (year_of(f) for f in files) if y]
    types = Counter(f.get("type") for f in files)
    plural = {"pdf": "מסמכים", "vid": "סרטונים", "img": "תמונות", "aud": "הקלטות"}
    out = [f"{len(files)} פריטים"]
    if years:
        lo, hi = min(years), max(years)
        out.append(str(lo) if lo == hi else f"{lo}-{hi}")
    one = {"pdf": "מסמך אחד", "vid": "סרטון אחד", "img": "תמונה אחת", "aud": "הקלטה אחת"}
    out += [(one[t] if n == 1 else f"{n} {plural[t]}") for t, n in types.most_common() if t in plural]
    ag = {f.get("agency_he") or f.get("agency") for f in files}
    out.append(f"{len(ag)} סוכנויות" if len(ag) > 1 else next(iter(ag)))
    return out


def chips(items: list[str]) -> str:
    return '<ul class="hub-stats mono">' + "".join(f"<li>{esc(x)}</li>" for x in items) + "</ul>"


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


def hero(crumb: str, eyebrow: str, h1: str, lead: str, stat_items: list[str]) -> str:
    return (f'<section class="hub-hero"><div class="container">'
            f'<nav class="file-crumb" aria-label="פירורי לחם">{crumb}</nav>'
            f'<p class="hub-eyebrow mono">{esc(eyebrow)}</p><h1 class="hub-h1">{esc(h1)}</h1>'
            f'<p class="hub-lead">{esc(lead)}</p>{chips(stat_items)}</div></section>')


def toc_html(toc: list[tuple[str, str]], extra: list[tuple[str, str]]) -> str:
    items = "".join(f'<li><a href="#{a}">{esc(t)}</a></li>' for a, t in toc + extra)
    return f'<ol>{items}</ol>'


def article_layout(body: str, toc: list[tuple[str, str]], extra: list[tuple[str, str]]) -> str:
    t = toc_html(toc, extra)
    return (f'<div class="container hub-layout">'
            f'<aside class="hub-aside"><nav class="hub-toc" aria-label="בדף הזה">'
            f'<p class="hub-toc-label mono">// בדף הזה</p>{t}</nav></aside>'
            f'<article class="hub-prose">'
            f'<details class="hub-toc-mobile"><summary class="mono">// בדף הזה</summary>{t}</details>'
            f'{body}</article></div>')


def section(anchor: str, title: str, inner: str) -> str:
    return (f'<section class="container hub-section" id="{anchor}">'
            f'<h2 class="hub-section-title">{esc(title)}</h2>{inner}</section>')


def main_html(*parts: str) -> str:
    return '<main id="top" class="hub">' + "".join(parts) + "</main>"


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
    crumb = '<a href="index.html#release">הארכיון</a> <span aria-hidden="true">/</span> <a href="topics/">מדריכים</a>'
    rel_date = {r["slug"]: next(f["release_date"] for f in files if f.get("release_no") == r["slug"]) for r in releases}

    rel_slugs = sorted(r["slug"] for r in releases)
    for r in releases:
        slug = r["slug"]
        members = [f for f in files if f.get("release_no") == slug]
        if not members:
            raise SystemExit(f"build_hubs: no records for release {slug}")
        date = rel_date[slug]
        featured = [by_id[i] for i in r["ids"]]
        body, toc = body_html(r["intro"], by_id)
        i = rel_slugs.index(slug)
        pn = []
        if i > 0:
            pn.append(f'<a class="hub-pn hub-pn-prev" href="releases/{rel_slugs[i-1]}.html">'
                      f'<span class="mono">→ המהדורה הקודמת</span><strong>מהדורה {rel_slugs[i-1]}</strong></a>')
        if i < len(rel_slugs) - 1:
            pn.append(f'<a class="hub-pn hub-pn-next" href="releases/{rel_slugs[i+1]}.html">'
                      f'<span class="mono">המהדורה הבאה ←</span><strong>מהדורה {rel_slugs[i+1]}</strong></a>')
        by_type: dict = {}
        for f in members:
            by_type.setdefault(f.get("type"), []).append(f)
        plural = {"pdf": "מסמכים", "vid": "סרטונים", "img": "תמונות", "aud": "הקלטות"}
        all_list = "".join(
            f'<h3 class="hub-subtitle mono">{plural.get(t, t)} ({len(fs)})</h3>'
            f'<ul class="hub-compact">' + "".join(
                f'<li><a href="{esc(doc_path(f["id"]))}">{esc(doc_title(f))}</a>'
                f'<span class="mono">{esc(code_label(f))}</span></li>' for f in fs) + "</ul>"
            for t, fs in sorted(by_type.items(), key=lambda kv: -len(kv[1])))
        main = main_html(
            hero(crumb, f"// מהדורה {slug} · {release_he(date)}", r["h1"], r["description"], stats(members)),
            article_layout(body, toc, [("featured", "מומלץ לקריאה"), ("all", f"כל {len(members)} הקבצים")]),
            section("featured", "מומלץ לקריאה", cards(featured, len(featured), "", big=True)),
            section("all", f"כל {len(members)} הקבצים במהדורה",
                    f'<details class="hub-more hub-more-all"><summary><span>הצגת הרשימה המלאה לפי סוג</span></summary>'
                    f'{all_list}</details>'),
            f'<nav class="container hub-pager" aria-label="מהדורות">{"".join(pn)}</nav>' if pn else "")
        url = f"{BASE}/releases/{slug}.html"
        ld = [{"@context": "https://schema.org", "@type": "Article", "headline": r["h1"],
               "description": r["description"], "inLanguage": "he", "url": url,
               "datePublished": release_iso(date), "image": f"{BASE}/assets/img/og-cover-v2.png",
               "author": {"@type": "Organization", "name": "עב\"מים: כל מה שהותר לפרסום", "url": BASE + "/"},
               "publisher": {"@type": "Organization", "name": "עב\"מים: כל מה שהותר לפרסום", "url": BASE + "/"}},
              crumbs_ld([("עב\"מים", BASE + "/"), ("מדריכים", f"{BASE}/topics/"), (r["h1"], url)])]
        page = shell.page(title=r["title"], desc=r["description"], url=url, og_type="article", ld=ld, main=main)
        (ROOT / "releases" / f"{slug}.html").write_text(page, encoding="utf-8")
        urls.append((url, release_iso(date)))

    for t in topics:
        members = [by_id[i] for i in t["ids"]]
        body, toc = body_html(t["intro"], by_id)
        main = main_html(
            hero(crumb, "// מדריך נושא", t["h1"], t["description"], stats(members)),
            article_layout(body, toc, [("items", f"כל {len(members)} הפריטים")]),
            section("items", f"{len(members)} הפריטים בנושא",
                    cards(members, 12, f"הצגת כל {len(members)} הפריטים")))
        url = f"{BASE}/topics/{t['slug']}.html"
        ld = [{"@context": "https://schema.org", "@type": "CollectionPage", "name": t["h1"],
               "description": t["description"], "inLanguage": "he", "url": url,
               "mainEntity": {"@type": "ItemList", "numberOfItems": len(members), "itemListElement": [
                   {"@type": "ListItem", "position": k + 1, "url": f"{BASE}/{doc_path(f['id'])}", "name": doc_title(f)}
                   for k, f in enumerate(members)]}},
              crumbs_ld([("עב\"מים", BASE + "/"), ("מדריכים", f"{BASE}/topics/"), (t["h1"], url)])]
        page = shell.page(title=t["title"], desc=t["description"], url=url, og_type="website", ld=ld, main=main)
        (ROOT / "topics" / f"{t['slug']}.html").write_text(page, encoding="utf-8")
        urls.append((url, max(release_iso(f["release_date"]) for f in members)))

    # ---- topics/index.html ----
    def cover(members: list[dict]) -> str:
        imgs = [x for x in (thumb(f) for f in members) if x][:3]
        if not imgs:
            g = GLYPH.get(members[0].get("type"), "▤")
            return f'<span class="topic-cover topic-cover-empty" aria-hidden="true"><span>{g}</span></span>'
        return ('<span class="topic-cover" aria-hidden="true">'
                + "".join(f'<img src="{esc(x)}" alt="" loading="lazy" decoding="async" width="400" height="300">' for x in imgs)
                + "</span>")

    t_cards = "".join(
        f'<li class="topic-card"><a href="topics/{esc(t["slug"])}.html">{cover([by_id[i] for i in t["ids"]])}'
        f'<span class="topic-body"><span class="topic-count mono">{len(t["ids"])} פריטים</span>'
        f'<span class="topic-title">{esc(t["h1"])}</span>'
        f'<span class="topic-desc">{esc(t["description"])}</span>'
        f'<span class="topic-go mono">לקריאה ←</span></span></a></li>'
        for t in sorted(topics, key=lambda t: -len(t["ids"])))
    r_cards = "".join(
        f'<li class="rel-card"><a href="releases/{esc(r["slug"])}.html">'
        f'<span class="rel-no mono">{esc(r["slug"])}</span>'
        f'<span class="rel-date mono">{esc(release_he(rel_date[r["slug"]]))} · '
        f'{sum(1 for f in files if f.get("release_no") == r["slug"])} קבצים</span>'
        f'<span class="rel-title">{esc(r["h1"])}</span>'
        f'<span class="rel-desc">{esc(r["description"])}</span></a></li>'
        for r in sorted(releases, key=lambda r: r["slug"], reverse=True))
    title = 'מדריכים לקבצי העב"מים: לפי נושא ולפי מהדורה'
    desc = 'מדריכים בעברית לארכיון העב"מים של ממשל ארה"ב: AAWSAP, Blue Book, נאס"א, ה-CIA, ה-FBI, סרטוני הפנטגון ומה פורסם בכל מהדורה.'
    lead = ('מאות המסמכים, התמונות והסרטונים שממשל ארה"ב פרסם על עב"מים, מסודרים לפי נושא ולפי מהדורה. '
            'כל מדריך מספר בעברית את הסיפור שעולה מהמסמכים ומקשר לכל אחד מהם.')
    url = f"{BASE}/topics/"
    main = main_html(
        hero('<a href="index.html#release">הארכיון</a>', "// מדריכים", 'מדריכים לקבצי העב"מים', lead,
             [f"{len(files)} פריטים בארכיון", f"{len(topics)} נושאים", f"{len(releases)} מהדורות"]),
        section("topics", "לפי נושא", f'<ul class="topic-grid">{t_cards}</ul>'),
        section("releases", "לפי מהדורה", f'<ol class="rel-grid">{r_cards}</ol>'),
        '<section class="container hub-section hub-also"><p>מחפשים משהו אחר? '
        '<a href="index.html#release">לדפדפן הארכיון עם חיפוש וסינון</a>, או '
        '<a href="archive.html">לאינדקס המלא של כל המסמכים</a>.</p></section>')
    page = shell.page(title=title, desc=desc, url=url, og_type="website",
                      ld=[crumbs_ld([("עב\"מים", BASE + "/"), ("מדריכים", url)])], main=main)
    (ROOT / "topics" / "index.html").write_text(page, encoding="utf-8")
    urls.insert(0, (url, latest))
    print(f"build_hubs: {len(releases)} release pages, {len(topics)} topic pages, topics/index.html")
    return urls


if __name__ == "__main__":
    build()
