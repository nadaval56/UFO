#!/usr/bin/env python3
"""
sister_sites.py - the thin "עוד אתרים שלי" strip at the bottom of every page.

The same strip runs on the owner's other sites (geniza-explorer's
sister_sites.py, which in turn copied dronexam.co.il). Here the PURSUE entry
is left out, since this is PURSUE.

Links only: nothing is loaded from these sites - no favicon, no script - so the
privacy policy's "no third-party code" still holds.

The list is written twice. The second copy exists only so that the slow scroll
in assets/js/sister.js can loop without a seam; it is aria-hidden and taken out
of the tab order, and CSS hides it altogether under reduced motion (and under
the accessibility menu's "stop animations").

Each page carries the markup between two markers:

    <!-- sister:start -->  ...  <!-- sister:end -->

After changing SITES, run:

    python3 scripts/sister_sites.py        # rewrites the marked blocks
    python3 scripts/build_sitemap.py       # doc/*.html (from file.html) and archive.html
"""
from __future__ import annotations

import re
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# page -> prefix for the script URL. doc/*.html get the strip from file.html
# (via build_static_pages.py), and archive.html from build_sitemap.py.
PAGES = {
    "index.html": "",
    "file.html": "",
    "404.html": "/",
    "privacy/index.html": "../",
    "accessibility/index.html": "../",
}

# (emoji, url, linked text, trailing unlinked text)
# "מייקינג · יצירה טכנולוגית" is the one entry where only the name is a link -
# the same split as on the other sites.
# The first entry is an invite to the owner's WhatsApp group, not a site; it is
# highlighted (class "sister-invite" in assets/css/styles.css).
INVITE = "https://chat.whatsapp.com/JPkp1hyk4J938apVTFu6J1"
SITES = [
    ("🔭", INVITE, "קבוצת ווטסאפ · עדכוני אסטרונומיה יומיים (קבוצה שקטה)", ""),
    ("🩻", "https://roentgen.co.il/", "רנטגן · לראות מבפנים", ""),
    ("☀️", "https://sunspots.co.il/", "השמש היום · כתמי שמש בזמן אמת", ""),
    ("📜", "https://geniza.co.il/", "הגניזה הקהירית", ""),
    ("🛠️", "https://making-il.co.il/", "מייקינג", " · יצירה טכנולוגית"),
    ("💶", "https://banknote.co.il/", "Banknote · שטרות ומטבעות", ""),
    ("🛩️", "https://dronexam.co.il/", 'לעוף לשמיים · מבחן רת"א לרחפנים', ""),
    ("🌱", "https://holisticcenter.co.il/", "מעט צרי · רפואה משלימה", ""),
    ("🌍", "https://quake.co.il/", "רעידת אדמה · רעידות היסטוריות", ""),
    ("📅", "https://heb-cal.co.il/", "לוח עברי", ""),
]

MARK = re.compile(r"([ \t]*)<!-- sister:start -->.*?<!-- sister:end -->", re.S)


def _items(clone: bool, ind: str) -> str:
    tab = ' tabindex="-1"' if clone else ""
    out = []
    for emoji, url, text, tail in SITES:
        icon = f'<span aria-hidden="true">{emoji}</span>'
        if tail:
            out.append(f'{ind}<span class="sister-item">{icon} '
                       f'<a href="{escape(url)}" rel="noopener"{tab}>{escape(text)}</a>'
                       f'{escape(tail)}</span>')
        else:
            cls = ' class="sister-invite"' if url == INVITE else ""
            out.append(f'{ind}<a href="{escape(url)}" rel="noopener"{cls}{tab}>'
                       f'{icon} {escape(text)}</a>')
    return "\n".join(out)


def nav(root: str = "", ind: str = "    ") -> str:
    i2, i4, i6, i8 = (ind + "  " * n for n in (1, 2, 3, 4))
    return f"""{ind}<!-- sister:start -->
{ind}<nav class="sister" aria-label="האתרים הנוספים שלי">
{i2}<span class="sister-lbl">עוד אתרים שלי</span>
{i2}<div class="sister-view">
{i4}<div class="sister-track">
{i6}<div class="sister-set">
{_items(False, i8)}
{i6}</div>
{i6}<div class="sister-set sister-clone" aria-hidden="true">
{_items(True, i8)}
{i6}</div>
{i4}</div>
{i2}</div>
{ind}</nav>
{ind}<script src="{root}assets/js/sister.js" defer></script>
{ind}<!-- sister:end -->"""


def main() -> None:
    for page, root in PAGES.items():
        path = ROOT / page
        s = path.read_text(encoding="utf-8")
        new, n = MARK.subn(lambda m: nav(root, m.group(1)), s)
        if n != 1:
            raise SystemExit(f"{page}: expected one sister block, found {n}")
        if new != s:
            path.write_text(new, encoding="utf-8")
            print(f"updated {page}")


if __name__ == "__main__":
    main()
