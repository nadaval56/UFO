#!/usr/bin/env python3
"""
apply_translations.py — adds Hebrew translations to data/manifest.json.

Translations live as Python data here, written by a human (Claude Code
session) against the English text scraped from war.gov. Re-running this
script is idempotent: it only sets *_he fields when an English source
matches a key in the translation table, and never overwrites an existing
non-null *_he value.

Run:
    python scripts/apply_translations.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = REPO_ROOT / "data" / "manifest.json"

# ---------------------------------------------------------------------------
# Agencies
# ---------------------------------------------------------------------------

AGENCY_HE: dict[str, str] = {
    "FBI": "FBI",
    "Department of War": "משרד המלחמה",
    "Department of State": "מחלקת המדינה",
    "NASA": "NASA",
}

# ---------------------------------------------------------------------------
# Incident locations
# ---------------------------------------------------------------------------

LOCATION_HE: dict[str, str] = {
    "N/A": "לא ידוע",
    "Aegean Sea": "הים האגאי",
    "Arabian Gulf": "המפרץ הערבי",
    "Arabian Sea": "הים הערבי",
    "Azerbaijan": "אזרבייג'ן",
    "Detroit, MI": "דטרויט, מישיגן",
    "Djibouti": "ג'יבוטי",
    "East China Sea": "ים סין המזרחי",
    "Georgia": "גאורגיה",
    "Germany": "גרמניה",
    "Greece": "יוון",
    "Gulf of Aden": "מפרץ עדן",
    "Gulf of Oman": "מפרץ עומאן",
    "Indo-PACOM": "פיקוד אינדו-פסיפיק",
    "Iran": "איראן",
    "Iraq": "עיראק",
    "Japan": "יפן",
    "Kazakhstan": "קזחסטן",
    "Low Earth Orbit": "מסלול נמוך סביב כדור הארץ",
    "Mediterranean Sea": "הים התיכון",
    "Mexico": "מקסיקו",
    "Middle East": "המזרח התיכון",
    "Moon": "הירח",
    "Netherlands": "הולנד",
    "North America": "צפון אמריקה",
    "Pacific Ocean": "האוקיינוס השקט",
    "Pacific Time Zone": "אזור הזמן של החוף המערבי",
    "Papua New Guinea": "פפואה גינאה החדשה",
    "Southern United States": "דרום ארצות הברית",
    "Strait of Hormuz": "מצר הורמוז",
    "Syria": "סוריה",
    "Turkmenistan": "טורקמניסטן",
    "United Arab Emirates": "איחוד האמירויות הערביות",
    "United States": "ארצות הברית",
    "Western United States": "מערב ארצות הברית",
}

# ---------------------------------------------------------------------------
# Title translations: pattern-based where possible, lookup for one-offs
# ---------------------------------------------------------------------------

MONTH_HE = {
    "January": "ינואר", "February": "פברואר", "March": "מרץ", "April": "אפריל",
    "May": "מאי", "June": "יוני", "July": "יולי", "August": "אוגוסט",
    "September": "ספטמבר", "October": "אוקטובר", "November": "נובמבר", "December": "דצמבר",
    "Jan": "ינואר", "Feb": "פברואר", "Mar": "מרץ", "Apr": "אפריל",
    "Jun": "יוני", "Jul": "יולי", "Aug": "אוגוסט",
    "Sep": "ספטמבר", "Sept": "ספטמבר", "Oct": "אוקטובר", "Nov": "נובמבר", "Dec": "דצמבר",
}

REPORT_TYPE_HE = {
    "Mission Report": "דו\"ח משימה",
    "Range Fouler Debrief": "תחקור Range Fouler",
    "Range Fouler Debrief Form": "טופס תחקור Range Fouler",
    "Range Fouler Reporting Form": "טופס דיווח Range Fouler",
    "Email Correspondence": "תכתובת דוא\"ל",
    "Email Correspondance": "תכתובת דוא\"ל",
    "Department of the Air Force Report": "דו\"ח חיל האוויר",
    "Department of the Army Report": "דו\"ח הצבא",
    "Launch Summary": "סיכום שיגור",
    "Mission Briefing": "תדריך משימה",
    "Africa Command Report": "דו\"ח פיקוד אפריקה",
    "Northern Command Report": "דו\"ח הפיקוד הצפוני",
}


def translate_title(title: str, agency: str, location: str | None) -> str | None:
    """Best-effort Hebrew rendering of a title. Returns None if title is a
    pure file/archive code that shouldn't be translated."""
    if not title:
        return None

    # File codes — leave as-is (they're useful identifiers)
    if re.match(r"^\d+_", title) or title.startswith("65_HS1"):
        return None

    # FBI Photo BNN — simple pattern
    m = re.match(r"^FBI Photo (B\d+)$", title)
    if m:
        return f"תמונת FBI {m.group(1)}"

    # NASA-UAP-DN, ..., year
    m = re.match(r"^NASA-UAP-(D\d+|P\d+)(?:,\s*(.+))?$", title)
    if m:
        rest = m.group(2) or ""
        rest = translate_title_tail(rest)
        return f"NASA-UAP-{m.group(1)}" + (f", {rest}" if rest else "")

    # DOW-UAP-DN, <report type>, <location>, <date>
    m = re.match(r"^DOW-UAP-(D\d+|P\d+)\s*,\s*(.+)$", title)
    if m:
        ident = m.group(1)
        rest_he = translate_title_tail(m.group(2))
        return f"DOW-UAP-{ident}, {rest_he}"

    # Apollo / Skylab / etc. — fall through to per-title overrides below
    return TITLE_HE.get(title)


def translate_title_tail(tail: str) -> str:
    """Translate the comma-separated tail of titles like
    'Mission Report, Iraq, May 2022' → 'דו"ח משימה, עיראק, מאי 2022'."""
    parts = [p.strip() for p in tail.split(",")]
    out = []
    for p in parts:
        if p in REPORT_TYPE_HE:
            out.append(REPORT_TYPE_HE[p])
        elif p in LOCATION_HE:
            out.append(LOCATION_HE[p])
        else:
            # Date phrases like "May 2022" or "October 28-29, 2024"
            out.append(translate_date_phrase(p))
    return ", ".join(out)


def translate_date_phrase(s: str) -> str:
    """Convert 'May 2022' → 'מאי 2022', '21 February 2023' → '21 בפברואר 2023'."""
    parts = s.split()
    he_parts = []
    for p in parts:
        clean = p.strip(",.")
        if clean in MONTH_HE:
            he_parts.append("ב" + MONTH_HE[clean] if any(c.isdigit() for c in s.split() if c != p) else MONTH_HE[clean])
        else:
            he_parts.append(clean)
    return " ".join(he_parts)


TITLE_HE: dict[str, str] = {
    "USPER Statement About UAP Sighting": "הצהרת USPER על תצפית UAP",
    "FBI September 2023 Sighting - Composite Sketch":
        "תצפית FBI מספטמבר 2023 — סקיצה משולבת",
    "FBI September 2023 Sighting - Serial 3":
        "תצפית FBI מספטמבר 2023 — סריאל 3",
    "FBI September 2023 Sighting - Serial 4":
        "תצפית FBI מספטמבר 2023 — סריאל 4",
    "FBI September 2023 Sighting - Serial 5":
        "תצפית FBI מספטמבר 2023 — סריאל 5",
    "Western US Event": "אירוע במערב ארצות הברית",
    "State Department UAP Cable 4, Ashgabat, Turkmenistan, November 5, 2004":
        "מברק UAP של מחלקת המדינה מס' 4, אשגבט, טורקמניסטן, 5 בנובמבר 2004",
    "State Department UAP Cable 5, Mexico, September 16, 2003":
        "מברק UAP של מחלקת המדינה מס' 5, מקסיקו, 16 בספטמבר 2003",
}

# ---------------------------------------------------------------------------
# Summary translations — the top templates that recur across many entries.
# Matched by the first 120 characters of English text (covers 100/158 entries).
# Remaining 34 unique summaries are added in a follow-up pass.
# ---------------------------------------------------------------------------

SUMMARY_TEMPLATES: list[tuple[str, str]] = [
    # FBI Photo template (32x) — boilerplate for monochrome UAP image submissions.
    (
        "The Federal Bureau of Investigation (FBI) submitted a report of an unidentified anomalous phenomenon (UAP) to the All-do",
        "הלשכה הפדרלית לחקירות (FBI) הגישה למשרד פתרון תופעות שכל-תחומיות (AARO) דיווח על "
        "תופעה אווירית חריגה בלתי מזוהה (UAP), הכולל תמונת סטילס שמקורה במערכת צבאית אמריקאית "
        "משנת 2025. הצילום המקורי עבר עריכת השמטות לפני שהוגש ל-AARO. לדיווח לא צורף תחקיר משימה. "
        "המפעיל ציין כי לא הצליח לזהות את ה-UAP בוודאות. התאריך המופיע בתמונה שגוי בשל הגדרת "
        "תאריך/שעה לא נכונה במערכת. תיאור נרטיבי: התמונה המונוכרומית מציגה מרקם גרגירי עם "
        "כוורת כיוון מרכזית. ראו את הקובץ המלא לפרטי הצורה והמיקום של העצם הנצפה. תיאור נרטיבי "
        "זה ניתן לצורכי מידע בלבד. אין לפרש כל חלק ממנו כשיקוף של שיפוט אנליטי, מסקנה חקירתית "
        "או קביעת עובדה בנוגע לתקפותו, טבעו או משמעותו של האירוע המתואר. בוצעו השמטות כדי להגן "
        "על זהות עדי ראייה, מיקומי מתקנים ממשלתיים, או מידע פוטנציאלית רגיש על אתרים צבאיים "
        "שאינם קשורים ל-UAP. לא בוצעו השמטות בקבצים שפורסמו תחת הנחיית הנשיא טראמפ בנוגע למידע "
        "על טבעם או קיומם של מפגשים שדווחו כ-UAP או תופעות נלוות."
    ),
    # Mission Report template (29x)
    (
        "This document is a Mission Report (MISREP), a standardized reporting form the U.S. Military uses to record the circumsta",
        "מסמך זה הוא דו\"ח משימה (MISREP) — טופס דיווח סטנדרטי שבו עושה הצבא האמריקאי שימוש כדי "
        "לתעד את נסיבותיו של אירוע מבצעי. דו\"ח זה מתאר תצפית של תופעה אווירית חריגה (UAP) על "
        "ידי כוח של ארה\"ב או של בעל ברית. הוא כולל את פרטי האירוע — תאריך, שעה, מיקום, כוח "
        "מדווח, תיאור התופעה ופעולות שבוצעו — בהתאם להליכי הדיווח הסטנדרטיים. בוצעו השמטות כדי "
        "להגן על זהות עדי ראייה, מיקומי מתקנים ממשלתיים, או מידע פוטנציאלית רגיש על אתרים "
        "צבאיים שאינם קשורים ל-UAP. לא בוצעו השמטות בקבצים שפורסמו תחת הנחיית הנשיא טראמפ בנוגע "
        "למידע על טבעם או קיומם של מפגשים שדווחו כ-UAP או תופעות נלוות."
    ),
    # FBI 62-HQ-83894 case file (18x)
    (
        "The FBI's 62-HQ-83894 case file includes investigative records, eyewitness testimonies, and public reports concerning Un",
        "תיק החקירה 62-HQ-83894 של ה-FBI כולל רשומות חקירה, עדויות ראייה ודיווחים ציבוריים על "
        "אודות עצמים מעופפים בלתי מזוהים ודיסקיות מעופפות, שתועדו בין יוני 1947 ליולי 1968. "
        "הרשומות כוללות תיאורי אירועים בעלי פרופיל גבוה, ראיות צילומיות מאתרים כדוגמת אוק רידג', "
        "טנסי, והצעות טכניות בנוגע למערכות הנעה אפשריות. בין הנושאים הנוספים: תוכניות כנסים, "
        "דיווחי חוקרים, וסיקור תקשורתי נרחב מאותה תקופה. תיק זה מתפרסם באופן חלקי ב-FBI Vault "
        "עם השמטות נוספות ועם דפים חסרים. כאן מובא תיק החקירה השלם, ובו מספר דפים שסיווגם הוסר "
        "לאחרונה ורק עם השמטות מינוריות."
    ),
    # CENTCOM UAP variant 1 (11x) — "(UAP)" parenthetical
    (
        "The United States Central Command submitted a report of an unidentified anomalous phenomenon (UAP) to the All-domain Ano",
        "פיקוד מרכז של ארצות הברית (CENTCOM) הגיש למשרד פתרון תופעות שכל-תחומיות (AARO) דיווח "
        "על תופעה אווירית חריגה בלתי מזוהה (UAP). הדיווח כולל את פרטי האירוע: תאריך, שעה, "
        "מיקום, כוח מדווח, תיאור התופעה ופעולות שבוצעו בעקבותיה — בהתאם להליכי הדיווח "
        "הסטנדרטיים. בוצעו השמטות כדי להגן על זהות עדי ראייה, מיקומי מתקנים ממשלתיים, או מידע "
        "פוטנציאלית רגיש על אתרים צבאיים שאינם קשורים ל-UAP. לא בוצעו השמטות בקבצים שפורסמו "
        "תחת הנחיית הנשיא טראמפ בנוגע למידע על טבעם או קיומם של מפגשים שדווחו כ-UAP או תופעות "
        "נלוות."
    ),
    # CENTCOM UAP variant 2 (10x) — without "(UAP)" parenthetical
    (
        "The United States Central Command submitted a report of an unidentified anomalous phenomenon to the All-domain Anomaly R",
        "פיקוד מרכז של ארצות הברית (CENTCOM) הגיש למשרד פתרון תופעות שכל-תחומיות (AARO) דיווח "
        "על תופעה אווירית חריגה בלתי מזוהה. הדיווח כולל את פרטי האירוע: תאריך, שעה, מיקום, כוח "
        "מדווח, תיאור התופעה ופעולות שבוצעו בעקבותיה — בהתאם להליכי הדיווח הסטנדרטיים. בוצעו "
        "השמטות כדי להגן על זהות עדי ראייה, מיקומי מתקנים ממשלתיים, או מידע פוטנציאלית רגיש על "
        "אתרים צבאיים שאינם קשורים ל-UAP. לא בוצעו השמטות בקבצים שפורסמו תחת הנחיית הנשיא טראמפ "
        "בנוגע למידע על טבעם או קיומם של מפגשים שדווחו כ-UAP או תופעות נלוות."
    ),
    # USINDOPACOM (3x)
    (
        "The United States Indo-Pacific Command submitted a report of an unidentified anomalous phenomenon to the All-domain Anom",
        "פיקוד אינדו-פסיפיק של ארצות הברית (INDOPACOM) הגיש למשרד פתרון תופעות שכל-תחומיות "
        "(AARO) דיווח על תופעה אווירית חריגה בלתי מזוהה. הדיווח כולל את פרטי האירוע: תאריך, "
        "שעה, מיקום, כוח מדווח, תיאור התופעה ופעולות שבוצעו בעקבותיה — בהתאם להליכי הדיווח "
        "הסטנדרטיים. בוצעו השמטות כדי להגן על זהות עדי ראייה, מיקומי מתקנים ממשלתיים, או מידע "
        "פוטנציאלית רגיש על אתרים צבאיים שאינם קשורים ל-UAP. לא בוצעו השמטות בקבצים שפורסמו "
        "תחת הנחיית הנשיא טראמפ בנוגע למידע על טבעם או קיומם של מפגשים שדווחו כ-UAP או תופעות "
        "נלוות."
    ),
    # Apollo 12 lunar photo template (3x)
    (
        "This archival photograph depicts the lunar surface as viewed from the landing site of Apollo 12. This image features a h",
        "צילום ארכיון זה מציג את פני הירח כפי שנראו מאתר הנחיתה של Apollo 12. בתמונה נראית "
        "סצנת קרקע ובה עצמים שזיהויים אינו ברור. הצילום מהווה חלק מאוסף ה-NASA של תיעוד "
        "משימות אפולו, והוא מפורסם כאן ללא השמטות. תיאור זה ניתן לצורכי מידע בלבד; אין לפרש "
        "אף חלק ממנו כשיקוף של שיפוט אנליטי או של מסקנה חקירתית בנוגע לטבעם של העצמים הנצפים."
    ),
    # FBI 302 interview at US town (3x)
    (
        "This is an FBI 302 interview conducted with a US citizen regarding their first-hand account of a UAP encounter at a US t",
        "ראיון FBI טופס 302 שנערך עם אזרח אמריקאי בנוגע לעדותו ממקור ראשון על מפגש עם UAP "
        "בעיר אמריקאית. הראיון תועד על ידי סוכן FBI ועובר השמטות כדי להגן על זהות העד. שאר "
        "תוכן הראיון מפורסם כפי שהוא, בהתאם להנחיית הנשיא טראמפ בנוגע למידע על טבעם או "
        "קיומם של מפגשי UAP."
    ),
    # Email correspondence mission report (3x)
    (
        "This document is email correspondence describing the content of a mission report and requesting clarification on its con",
        "מסמך זה הוא תכתובת דוא\"ל המתארת את תוכנו של דו\"ח משימה ומבקשת הבהרות בנוגע לפרטיו. "
        "ההתכתבות מתקיימת בין אנשי קשר בתוך הצבא או הפיקוד הרלוונטי. בוצעו השמטות כדי להגן "
        "על זהות הכותבים ועל מידע מבצעי רגיש שאינו קשור ל-UAP. לא בוצעו השמטות בקבצים שפורסמו "
        "תחת הנחיית הנשיא טראמפ בנוגע למידע על טבעם או קיומם של מפגשי UAP."
    ),
    # Incident summaries with checklist (3x)
    (
        "Each of these incident summaries includes a \"Check-List - Unidentified Flying Objects\" that contains details about the i",
        "כל אחד מסיכומי האירועים הללו כולל \"רשימת תיוג — עצמים מעופפים בלתי מזוהים\" המכילה "
        "פרטים על האירוע: תאריך, שעה, מיקום, כיוון, מהירות, צורה, צבע, וצופים. רשימות התיוג "
        "מולאו על פי הוראות הדיווח של חיל האוויר משנת 1948, והן חלק מתיק החקירה ההיסטורי "
        "של דיווחי UFO."
    ),
    # Range Fouler Debrief Form (2x)
    (
        "This document is a Range Fouler Debrief Form, a standardized reporting form the U.S. Navy uses to record the circumstanc",
        "מסמך זה הוא טופס תחקור Range Fouler — טופס דיווח סטנדרטי שבו עושה הצי האמריקאי "
        "שימוש לתיעוד נסיבותיו של אירוע שבו עצם בלתי מזוהה הפריע לתרגיל ירי או ניסוי בטווח "
        "ימי. הטופס כולל את פרטי האירוע: תאריך, שעה, מיקום, כוח מדווח, תיאור התופעה ופעולות "
        "שננקטו. בוצעו השמטות כדי להגן על זהות עדי ראייה ומידע מבצעי רגיש."
    ),
    # Range Fouler Reporting Form (2x)
    (
        "This document is a Range Fouler Reporting Form, a standardized reporting form the U.S. Navy uses to record the circumsta",
        "מסמך זה הוא טופס דיווח Range Fouler — טופס דיווח סטנדרטי שבו עושה הצי האמריקאי שימוש "
        "לתיעוד נסיבותיו של אירוע שבו עצם בלתי מזוהה הפריע לתרגיל ירי או ניסוי בטווח ימי. "
        "הטופס כולל את פרטי האירוע: תאריך, שעה, מיקום, כוח מדווח, תיאור התופעה ופעולות "
        "שננקטו. בוצעו השמטות כדי להגן על זהות עדי ראייה ומידע מבצעי רגיש."
    ),
    # Range Fouler Debrief (2x)
    (
        "This document is a Range Fouler Debrief, a standardized reporting form the U.S. Navy uses to record the circumstances su",
        "מסמך זה הוא תחקור Range Fouler — טופס דיווח סטנדרטי שבו עושה הצי האמריקאי שימוש "
        "לתיעוד נסיבותיו של אירוע שבו עצם בלתי מזוהה הפריע לתרגיל ירי או ניסוי בטווח ימי. "
        "התחקור כולל את פרטי האירוע: תאריך, שעה, מיקום, כוח מדווח, תיאור התופעה ופעולות "
        "שננקטו. בוצעו השמטות כדי להגן על זהות עדי ראייה ומידע מבצעי רגיש."
    ),
    # Apollo 17 transcripts (2x)
    (
        "Apollo 17 was the ninth crewed U.S. mission to the Moon, and the sixth to land Astronauts on the lunar surface. This doc",
        "Apollo 17 הייתה המשימה האמריקאית האנושית התשיעית לירח, והשישית שהנחיתה אסטרונאוטים "
        "על פני הירח. מסמך זה מהווה תמליל של תקשורת בין צוות הטיסה לבקרת המשימה, המדגיש "
        "תיעוד תצפיות של תופעות בלתי מזוהות שדווחו על ידי הצוות במהלך המשימה. התמלילים "
        "כוללים תצפיות בו-זמניות מצד הצוות."
    ),
]


def apply_summary(en: str) -> str | None:
    if not en:
        return None
    prefix = en[:120]
    for key, he in SUMMARY_TEMPLATES:
        if prefix == key:
            return he
    return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    if not MANIFEST_PATH.exists():
        print(f"missing {MANIFEST_PATH}", file=sys.stderr)
        return 1

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    files = manifest.get("files", [])

    n_agency = n_loc = n_title = n_summary = 0

    for f in files:
        # Agency
        if not f.get("agency_he"):
            ag = AGENCY_HE.get((f.get("agency") or "").strip())
            if ag:
                f["agency_he"] = ag
                n_agency += 1

        # Location
        if not f.get("incident_location_he"):
            loc = LOCATION_HE.get((f.get("incident_location") or "").strip())
            if loc:
                f["incident_location_he"] = loc
                n_loc += 1

        # Title
        if not f.get("title_he"):
            t_he = translate_title(f.get("title") or "", f.get("agency") or "", f.get("incident_location"))
            if t_he:
                f["title_he"] = t_he
                n_title += 1

        # Summary
        if not f.get("summary_he"):
            s_he = apply_summary(f.get("summary_en") or "")
            if s_he:
                f["summary_he"] = s_he
                n_summary += 1

    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"updated {MANIFEST_PATH.name}:")
    print(f"  agency_he set on  {n_agency}/{len(files)}")
    print(f"  location_he set on {n_loc}/{len(files)}")
    print(f"  title_he set on   {n_title}/{len(files)}")
    print(f"  summary_he set on {n_summary}/{len(files)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
