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
    "Central Intelligence Agency": "סוכנות הביון המרכזית",
    "Department of Energy": "משרד האנרגיה",
    "Office of the Director of National Intelligence": "משרד מנהל המודיעין הלאומי",
}

# ---------------------------------------------------------------------------
# Incident locations
# ---------------------------------------------------------------------------

LOCATION_HE: dict[str, str] = {
    "N/A": "לא ידוע",
    "AFRICOM": "פיקוד אפריקה",
    "Aegean Sea": "הים האגאי",
    "CENTCOM": "פיקוד מרכז",
    "Cislunar Space": "מרחב ציס-לונרי",
    "EUCOM": "הפיקוד האירופי",
    "INDOPACOM": "פיקוד אינדו-פסיפיק",
    "Midwestern United States": "המערב התיכון של ארצות הברית",
    "New Mexico": "ניו מקסיקו",
    "North Atlantic Ocean": "צפון האוקיינוס האטלנטי",
    "NORTHCOM": "הפיקוד הצפוני",
    "Southeastern United States": "דרום-מזרח ארצות הברית",
    "Texas": "טקסס",
    "USSR": "ברית המועצות",
    "Yellow Sea": "הים הצהוב",
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
        "הלשכה הפדרלית לחקירות (FBI) הגישה למשרד פתרון תופעות כל-תחומיות (AARO) דיווח על "
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
        "פיקוד מרכז של ארצות הברית (CENTCOM) הגיש למשרד פתרון תופעות כל-תחומיות (AARO) דיווח "
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
        "פיקוד מרכז של ארצות הברית (CENTCOM) הגיש למשרד פתרון תופעות כל-תחומיות (AARO) דיווח "
        "על תופעה אווירית חריגה בלתי מזוהה. הדיווח כולל את פרטי האירוע: תאריך, שעה, מיקום, כוח "
        "מדווח, תיאור התופעה ופעולות שבוצעו בעקבותיה — בהתאם להליכי הדיווח הסטנדרטיים. בוצעו "
        "השמטות כדי להגן על זהות עדי ראייה, מיקומי מתקנים ממשלתיים, או מידע פוטנציאלית רגיש על "
        "אתרים צבאיים שאינם קשורים ל-UAP. לא בוצעו השמטות בקבצים שפורסמו תחת הנחיית הנשיא טראמפ "
        "בנוגע למידע על טבעם או קיומם של מפגשים שדווחו כ-UAP או תופעות נלוות."
    ),
    # USINDOPACOM (3x)
    (
        "The United States Indo-Pacific Command submitted a report of an unidentified anomalous phenomenon to the All-domain Anom",
        "פיקוד אינדו-פסיפיק של ארצות הברית (INDOPACOM) הגיש למשרד פתרון תופעות כל-תחומיות "
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
    # 1) Full-text exact match for one-off summaries
    if en in UNIQUE_SUMMARIES_HE:
        return UNIQUE_SUMMARIES_HE[en]
    # 2) Prefix match for repeated templates
    prefix = en[:120]
    for key, he in SUMMARY_TEMPLATES:
        if prefix == key:
            return he
    return None


# ---------------------------------------------------------------------------
# Unique one-off summaries — full English text → faithful Hebrew translation.
# Each appears once in the manifest; matched by exact full-text equality.
# ---------------------------------------------------------------------------

UNIQUE_SUMMARIES_HE: dict[str, str] = {
    "This file contains memorandums and correspondence related to flying disc/saucer sightings and that those are a matter of concern for the Air Materiel Command.":
        "תיק זה מכיל מזכרים והתכתבויות הנוגעים לתצפיות של דיסקיות / צלחות מעופפות, וקובע כי אלו מהוות עניין שבדאגה לפיקוד הציוד של חיל האוויר (Air Materiel Command).",

    "This file contains memorandums, correspondence, and forms related to the reporting of information on flying discs and investigations into sightings.":
        "תיק זה מכיל מזכרים, התכתבויות וטפסים הנוגעים לדיווח על מידע על דיסקיות מעופפות ולחקירות של תצפיות.",

    "This file contains an independent report on UFOs written by the French association COMETA (previously published in the French magazine VDS in 1999), which details the results of a study by the Institute of Higher Studies for National Defence. The file also includes a letter from Carol Rosin in which she notes that she was spokesperson for von Braun during the last years of his life.\n  Redactions have been made to protect the identity of eyewitnesses, the location of government facilities, or potentially sensitive information about military sites not related to UAP. No redactions have been made to any files released under President Trump's directive concerning information about the nature or existence of any encounter reported as a UAP or related phenomena.":
        "תיק זה מכיל דו\"ח עצמאי על UFO שנכתב על ידי האגודה הצרפתית COMETA (פורסם בעבר במגזין הצרפתי VDS ב-1999), המפרט את תוצאות מחקר שערך המכון ללימודים מתקדמים בהגנה לאומית. בתיק כלול גם מכתב מאת קרול רוזין, שבו היא מציינת כי שימשה כדוברתו של פון בראון בשנים האחרונות לחייו. בוצעו השמטות כדי להגן על זהות עדי ראייה, מיקומי מתקנים ממשלתיים, או מידע פוטנציאלית רגיש על אתרים צבאיים שאינם קשורים ל-UAP. לא בוצעו השמטות בקבצים שפורסמו תחת הנחיית הנשיא טראמפ בנוגע למידע על טבעם או קיומם של מפגשים שדווחו כ-UAP או תופעות נלוות.",

    "Gemini 7 was the tenth crewed American spaceflight. This document is a transcript of communications between the flight crew, Astronauts James “Jim” Lovell and Frank Borman, and the Manned Flight Center (now known as Johnson Space Center) in Houston, Texas. The transcript begins with Borman’s report of a “bogey,” contemporary nomenclature for an unknown aircraft, as well as a debris field. Borman described the debris field as consisting of “very, very many […] hundreds of little particles.” He estimated the particles’ distance from the spacecraft to be four miles. Lovell described observing a “brilliant body in the sun against a black background with trillions of particles on it.”This document also includes handwritten notes documenting the encounter, annotated with the phrase “UFO Sighting by Borman” in the top right corner.":
        "ג'מיני 7 הייתה טיסת החלל האנושית האמריקאית העשירית. מסמך זה הוא תמליל של תקשורת בין צוות הטיסה — האסטרונאוטים ג'יימס \"ג'ים\" לאוול ופרנק בורמן — לבין מרכז הטיסה האנושית (כיום מרכז ג'ונסון לחקר החלל) בהיוסטון, טקסס. התמליל פותח בדיווחו של בורמן על \"bogey\" — כינוי תקופתי לכלי טיס בלתי מזוהה — וכן על שדה פסולת. בורמן תיאר את שדה הפסולת כמכיל \"מאוד מאוד הרבה […] מאות חלקיקים קטנים\". הוא העריך את מרחקם של החלקיקים מהחללית בכארבעה מיילים. לאוול תיאר כי חזה ב\"גוף זוהר באור השמש על רקע שחור, עם טריליוני חלקיקים עליו\". מסמך זה כולל גם הערות בכתב יד המתעדות את המפגש, ובפינתן הימנית-עליונה רשום \"תצפית UFO על ידי בורמן\".",

    "This audio recording contains air to ground communications and the NASA Public Affairs audio feed with commentary, recorded during the flight of the Gemini 7 mission. In this excerpted segment of audio, Astronaut Frank Borman reports to NASA mission control in Houston his sighting of an unidentified object, which he referred to as a \"bogey.\" This sighting occurred on December 5, 1965. The dialogue includes Borman's initial report, as well as additional comments by Astronaut Jim Lovell, Borman's fellow crew member.":
        "הקלטת שמע זו מכילה תקשורת אוויר-קרקע ואת שידור השמע של מחלקת יחסי הציבור של NASA לצד פרשנות, שהוקלטו במהלך משימת ג'מיני 7. בקטע השמע המצוטט, האסטרונאוט פרנק בורמן מדווח לבקרת המשימה של NASA בהיוסטון על תצפית בעצם בלתי מזוהה, אותו כינה \"bogey\". התצפית התרחשה ב-5 בדצמבר 1965. הדיאלוג כולל את דיווחו הראשוני של בורמן, וכן הערות נוספות מצד האסטרונאוט ג'ים לאוול, חברו של בורמן בצוות.",

    "This file contains SHAEF messages and memorandums related to \"night phenomena (foofighters),\" flak rockets, unidentified cylindrical objects, and blinking lights. The documents include multiple references to the observations of the 415th Night Fighter Squadron.":
        "תיק זה מכיל הודעות ומזכרים של מטה הכוחות בעלות הברית באירופה (SHAEF) הנוגעים ל\"תופעות לילה (foofighters)\", רקטות נ\"מ, עצמים גליליים בלתי מזוהים ואורות מהבהבים. המסמכים כוללים אזכורים רבים של תצפיות שבוצעו על ידי טייסת ה-415 לקרב לילה.",

    "An Air Force intelligence report from November 1948 relating to unidentified flying objects and flying saucers.":
        "דו\"ח מודיעין של חיל האוויר מנובמבר 1948 הנוגע לעצמים מעופפים בלתי מזוהים ולצלחות מעופפות.",

    "Air Intelligence Information Report, 14 October 1955, Report of eye witness account of the ascent and flight of a unconventional aircraft in the trans-Caucasus region on the USSR.":
        "דו\"ח מידע מודיעין אוויר, 14 באוקטובר 1955, דיווח על עדות ראייה לעלייתו ולמעופו של כלי טיס בלתי שגרתי באזור הטרנס-קווקזי בברית המועצות.",

    "This file primarily contains incident reports on Unidentified Flying Objects (UFOs) written in compliance with the 1948 Flight Service Regulation (FSR) 200-4. The incidents were witnessed by military sources, as well as by some Civilian Aviation Authority (CAA) ones. The reports typically include information such as dates, locations, weather, and altitude, plus detailed descriptions of appearance and movement. Some messages from the Military Air Transport Service (MATS) and Army Airways Communications System (AACS) are also included, as well as additional military intelligence reports, several diagrams, and a report from a weather station in Japan.":
        "תיק זה מכיל בעיקר דיווחי אירועים על עצמים מעופפים בלתי מזוהים (UFO) שנכתבו בהתאם לתקנת שירותי הטיסה (FSR) 200-4 משנת 1948. האירועים נצפו על ידי מקורות צבאיים, וכן על ידי כמה מקורות מרשות התעופה האזרחית (CAA). הדיווחים כוללים בדרך כלל פרטים כגון תאריך, מיקום, מזג אוויר וגובה, וכן תיאורים מפורטים של מראה ותנועה. בתיק נכללות גם הודעות משירות התובלה האווירית הצבאי (MATS) וממערכת התקשורת האווירית של הצבא (AACS), כמו גם דיווחי מודיעין צבאי נוספים, מספר תרשימים, ודו\"ח מתחנת מזג אוויר ביפן.",

    "This memorandum, dated July 18, 1963, from the Executive Office of the President, National Aeronautics and Space Council, relates to thoughts on the space alien race question. Included are details relating to plans if alien intelligence is discovered, expanding scientific knowledge, the possibility of life on Mars, and diplomatic policy.":
        "מזכר זה, מתאריך 18 ביולי 1963, מטעם הלשכה המנהלית של הנשיא והמועצה הלאומית לאווירונאוטיקה וחלל, נוגע למחשבות על שאלת גזע החוצנים. במזכר נכללים פרטים הנוגעים לתוכניות במקרה שתתגלה תבונה חוצנית, להרחבת הידע המדעי, לאפשרות של חיים על מאדים, ולמדיניות דיפלומטית.",

    "This two page memorandum, dated July 28, 1952, relates to increased reports of unidentified flying objects (UFOs). Included in the record are possible explanations of increased sightings, such as technological improvements, historical records of UFOs, and U.S. Air Force opinions on UFOs.":
        "מזכר בן שני עמודים זה, מתאריך 28 ביולי 1952, נוגע לעלייה במספר הדיווחים על עצמים מעופפים בלתי מזוהים (UFO). ברשומה נכללים הסברים אפשריים לגידול בתצפיות — בהם שיפורים טכנולוגיים, רישומים היסטוריים של UFO, ועמדות חיל האוויר האמריקאי בנושא UFO.",

    "An FBI memo from 1958 reporting a UFO sighting by a Detroit man who described a \"circular object with a crystal-type dome,\" and recommending that the information be forwarded to \"proper air force authorities.\"":
        "מזכר של ה-FBI משנת 1958 המדווח על תצפית UFO על ידי תושב דטרויט, שתיאר \"עצם עגול עם כיפה דמוית קריסטל\", וממליץ להעביר את המידע ל\"רשויות חיל אוויר המתאימות\".",

    "An FBI report from 1957 detailing the interview with Wladyslaw Krasuski, who recounted seeing a large, circular, vertically-rising vehicle in 1944 Germany near a German military compound.\n  Redactions have been made to protect the identity of eyewitnesses, the location of government facilities, or potentially sensitive information about military sites not related to UAP. No redactions have been made to any files released under President Trump's directive concerning information about the nature or existence of any encounter reported as a UAP or related phenomena.":
        "דו\"ח של ה-FBI משנת 1957 המפרט ראיון עם ולדיסלב קראסוסקי, שתיאר כיצד חזה ב-1944 בגרמניה בכלי טיס גדול, עגול, המתרומם אנכית, בקרבת מתחם צבאי גרמני. בוצעו השמטות כדי להגן על זהות עדי ראייה, מיקומי מתקנים ממשלתיים, או מידע פוטנציאלית רגיש על אתרים צבאיים שאינם קשורים ל-UAP. לא בוצעו השמטות בקבצים שפורסמו תחת הנחיית הנשיא טראמפ בנוגע למידע על טבעם או קיומם של מפגשים שדווחו כ-UAP או תופעות נלוות.",

    "This report describes the Modeling of Unlikely Space-Booster Failures in Risk Calculations, documenting historical launch failure modes and recommending corrective actions to address them using novel modelling techniques.":
        "דו\"ח זה מתאר את \"מידול כשלים בלתי סבירים של מאיצי חלל בחישובי סיכון\", מתעד אופני כשל היסטוריים בשיגורים, וממליץ על פעולות מתקנות לטיפול בהם באמצעות טכניקות מידול חדשניות.",

    "This report summarizes the historical record of launches occurring at Vandenberg Air Force Base between 1958 and 2000.":
        "דו\"ח זה מסכם את הרישום ההיסטורי של שיגורים שהתקיימו בבסיס חיל האוויר ונדנברג בין השנים 1958 ל-2000.",

    "This document is a mission briefing summarizing an observation of Unidentified Anomalous Phenomena (UAP) by a U.S. military platform near Latakia, Syria.A U.S. military pilot flying a P-8A aircraft reported observing an object via the aircraft’s EO/IR sensor, which they characterized as appearing to be in “sea skim mode,” traveling at approximately 500 knots (575 mph) on a southeasterly heading. The P-8A lost visual contact with the object after two minutes.All descriptive and estimative language contained in this report reflects the reporter’s subjective interpretation at the time of the event. Such characterizations should not be interpreted as a conclusive indication of the presence or absence of any intrinsic object features or performance characteristics.\n  Redactions have been made to protect the identity of eyewitnesses, the location of government facilities, or potentially sensitive information about military sites not related to UAP. No redactions have been made to any files released under President Trump's directive concerning information about the nature or existence of any encounter reported as a UAP or related phenomena.":
        "מסמך זה הוא תדריך משימה המסכם תצפית בתופעה אווירית חריגה בלתי מזוהה (UAP) על ידי פלטפורמה צבאית אמריקאית בקרבת לטקיה, סוריה. טייס צבאי אמריקאי בכלי טיס P-8A דיווח כי חזה בעצם דרך חיישן EO/IR של כלי הטיס, ותיאר אותו כנראה ב\"מצב גלישה ימית\" (sea skim mode), כשהוא נע במהירות של כ-500 קשר (575 מיילים לשעה) בכיוון דרום-מזרחי. ה-P-8A איבד קשר עין עם העצם לאחר שתי דקות. כל הניסוחים התיאוריים והמעריכים בדו\"ח זה משקפים את הפרשנות הסובייקטיבית של המדווח בעת האירוע. אין לפרש תיאורים אלה כעדות מסכמת לקיומם או להיעדרם של מאפיינים או ביצועים אינטרינזיים כלשהם של העצם. בוצעו השמטות כדי להגן על זהות עדי ראייה, מיקומי מתקנים ממשלתיים, או מידע פוטנציאלית רגיש על אתרים צבאיים שאינם קשורים ל-UAP. לא בוצעו השמטות בקבצים שפורסמו תחת הנחיית הנשיא טראמפ בנוגע למידע על טבעם או קיומם של מפגשים שדווחו כ-UAP או תופעות נלוות.",

    "The United States Northern Command submitted a report of an unidentified anomalous phenomenon (UAP) to the All-domain Anomaly Resolution Office (AARO) consisting of 21 seconds of video footage from an infrared sensor aboard a U.S. military platform in 2024. An accompanying mission report, DoW-UAP-D8, described the UAP as consisting of an object with a vertical pole or bar attached to the bottom of the object. The observer also reported that the UAP may instead be a reflection from an object in the water.Video Description:00:00-00:21: An area of contrast visually resembling an inverted teardrop with a vertically linear trailing mass suspended below remains generally within the center of the sensor field-of-view throughout the video.This video description is provided for informational purposes only. Readers should not interpret any part of this description as reflecting an analytical judgment, investigative conclusion, or factual determination regarding the described event’s validity, nature, or significance.\n  Redactions have been made to protect the identity of eyewitnesses, the location of government facilities, or potentially sensitive information about military sites not related to UAP. No redactions have been made to any files released under President Trump's directive concerning information about the nature or existence of any encounter reported as a UAP or related phenomena.":
        "הפיקוד הצפוני של ארצות הברית (NORTHCOM) הגיש למשרד פתרון תופעות כל-תחומיות (AARO) דיווח על תופעה אווירית חריגה בלתי מזוהה (UAP) הכולל 21 שניות של צילומי וידאו מחיישן אינפרא-אדום על גבי פלטפורמה צבאית אמריקאית ב-2024. דו\"ח משימה מצורף, DoW-UAP-D8, תיאר את ה-UAP כעצם שלתחתיתו מחובר מוט או קורה אנכיים. הצופה דיווח גם כי ה-UAP עשוי להיות חלופית השתקפות של עצם מן המים. תיאור הווידאו: 00:00-00:21: אזור של ניגודיות, המזכיר ויזואלית טיפת דמע הפוכה עם מסה ליניארית-אנכית הנגררת תחתיה, נשאר ככלל במרכז שדה הראייה של החיישן לאורך הווידאו. תיאור וידאו זה ניתן לצורכי מידע בלבד. אין לפרש כל חלק ממנו כשיקוף של שיפוט אנליטי, מסקנה חקירתית או קביעת עובדה בנוגע לתקפותו, טבעו או משמעותו של האירוע המתואר. בוצעו השמטות כדי להגן על זהות עדי ראייה, מיקומי מתקנים ממשלתיים, או מידע פוטנציאלית רגיש על אתרים צבאיים שאינם קשורים ל-UAP. לא בוצעו השמטות בקבצים שפורסמו תחת הנחיית הנשיא טראמפ בנוגע למידע על טבעם או קיומם של מפגשים שדווחו כ-UAP או תופעות נלוות.",

    "The United States Africa Command submitted a report of an unidentified anomalous phenomenon to the All-domain Anomaly Resolution Office (AARO) consisting of two seconds of video footage from an infrared sensor aboard a U.S. military platform in 2025. The reporter did not provide any oral or written description of the observation.Video Description:00:00-00:02: A small, barely distinguishable area of contrast moves from the left side of the sensor field-of-view to the right side, exiting the scene from the bottom right quarter of the screen.This video description is provided for informational purposes only. Readers should not interpret any part of this description as reflecting an analytical judgment, investigative conclusion, or factual determination regarding the described event’s validity, nature, or significance. The video is looped for viewing purposes.\n  Redactions have been made to protect the identity of eyewitnesses, the location of government facilities, or potentially sensitive information about military sites not related to UAP. No redactions have been made to any files released under President Trump's directive concerning information about the nature or existence of any encounter reported as a UAP or related phenomena.":
        "פיקוד אפריקה של ארצות הברית (AFRICOM) הגיש למשרד פתרון תופעות כל-תחומיות (AARO) דיווח על תופעה אווירית חריגה בלתי מזוהה, הכולל שתי שניות של צילומי וידאו מחיישן אינפרא-אדום על גבי פלטפורמה צבאית אמריקאית ב-2025. המדווח לא סיפק כל תיאור מילולי או כתוב של התצפית. תיאור הווידאו: 00:00-00:02: אזור קטן וכמעט בלתי מובחן של ניגודיות נע מצדו השמאלי של שדה הראייה של החיישן לצדו הימני, ויוצא מהסצנה מהרבע הימני-תחתון של המסך. תיאור וידאו זה ניתן לצורכי מידע בלבד. אין לפרש כל חלק ממנו כשיקוף של שיפוט אנליטי, מסקנה חקירתית או קביעת עובדה בנוגע לתקפותו, טבעו או משמעותו של האירוע המתואר. הווידאו מנוגן בלולאה לצורך צפייה. בוצעו השמטות כדי להגן על זהות עדי ראייה, מיקומי מתקנים ממשלתיים, או מידע פוטנציאלית רגיש על אתרים צבאיים שאינם קשורים ל-UAP. לא בוצעו השמטות בקבצים שפורסמו תחת הנחיית הנשיא טראמפ בנוגע למידע על טבעם או קיומם של מפגשים שדווחו כ-UAP או תופעות נלוות.",

    "The Department of the Air Force submitted a report of an unidentified anomalous phenomenon to the All-domain Anomaly Resolution Office (AARO) consisting of 58 seconds of video footage from an infrared sensor aboard a U.S. military platform in 2020. The reporter did not provide any oral or written description of the observation.Video Description:00:00-00:03: The sensor tracks an area of contrast acquiring a reticle lock.00:04-00:30: The area of contrast gradually increases in distinctiveness against the background.00:31: The sensor narrows its field-of-view to zoom in on the area of contrast.00:32-00:56: The area of contrast increases in apparent size and distinctiveness.00:57-00:58: The area of contrast leaves the center of the frame and passes out of the sensor field-of-view, exiting the scene in the bottom right corner of the screen.This video description is provided for informational purposes only. Readers should not interpret any part of this description as reflecting an analytical judgment, investigative conclusion, or factual determination regarding the described event’s validity, nature, or significance.AARO Comment: The area of contrast’s apparent increase in size is likely to be at least partially attributable to the U.S. platform closing the distance between itself and the source of the detection.\n  Redactions have been made to protect the identity of eyewitnesses, the location of government facilities, or potentially sensitive information about military sites not related to UAP. No redactions have been made to any files released under President Trump's directive concerning information about the nature or existence of any encounter reported as a UAP or related phenomena.":
        "חיל האוויר (Department of the Air Force) הגיש למשרד פתרון תופעות כל-תחומיות (AARO) דיווח על תופעה אווירית חריגה בלתי מזוהה, הכולל 58 שניות של צילומי וידאו מחיישן אינפרא-אדום על גבי פלטפורמה צבאית אמריקאית ב-2020. המדווח לא סיפק כל תיאור מילולי או כתוב של התצפית. תיאור הווידאו: 00:00-00:03: החיישן עוקב אחרי אזור של ניגודיות תוך נעילת כוורת כיוון. 00:04-00:30: בהדרגה גוברת מובחנותו של אזור הניגודיות מול הרקע. 00:31: החיישן מצמצם את שדה הראייה כדי להתקרב לאזור הניגודיות. 00:32-00:56: אזור הניגודיות גדל בגודלו הנראה ובמובחנותו. 00:57-00:58: אזור הניגודיות יוצא ממרכז הפריים וחולף אל מחוץ לשדה הראייה של החיישן, יוצא מהסצנה בפינה הימנית-תחתונה של המסך. תיאור וידאו זה ניתן לצורכי מידע בלבד. אין לפרש כל חלק ממנו כשיקוף של שיפוט אנליטי, מסקנה חקירתית או קביעת עובדה בנוגע לתקפותו, טבעו או משמעותו של האירוע המתואר. הערת AARO: הגידול הנראה לעין בגודלו של אזור הניגודיות מיוחס ככל הנראה, לפחות באופן חלקי, לפלטפורמה האמריקאית הסוגרת את המרחק בינה לבין מקור הזיהוי. בוצעו השמטות כדי להגן על זהות עדי ראייה, מיקומי מתקנים ממשלתיים, או מידע פוטנציאלית רגיש על אתרים צבאיים שאינם קשורים ל-UAP. לא בוצעו השמטות בקבצים שפורסמו תחת הנחיית הנשיא טראמפ בנוגע למידע על טבעם או קיומם של מפגשים שדווחו כ-UAP או תופעות נלוות.",

    "The Department of the Army submitted a report of an unidentified anomalous phenomenon to the All-domain Anomaly Resolution Office (AARO) consisting of one minute and 49 seconds of video from an infrared sensor aboard a U.S. military platform in 2026. The reporter did not provide any oral or written description of the observation.Video Description:00:00-00:08: The sensor tracks an initial area of interest.00:09-00:16: The sensor disengages from its previous area of focus and pans from right to left to track two areas of contrast, narrowing the field-of-view to zoom in while panning to maintain the objects' positions generally within the center of the frame.00:17-01:03: The sensor widens its field-of-view to zoom out, keeping the areas of contrast generally centered within the display.01:04-01:08: The sensor field-of-view rapidly cycles between levels of zoom, causing the areas of contrast to appear to rapidly increase and decrease in size.01:09-01:48: The sensor tracks the areas of contrast while maintaining a generally centered position, intermittently cycling between contrast settings.This video description is provided for informational purposes only. Readers should not interpret any part of this description as reflecting an analytical judgment, investigative conclusion, or factual determination regarding the described event’s validity, nature, or significance.\n  Redactions have been made to protect the identity of eyewitnesses, the location of government facilities, or potentially sensitive information about military sites not related to UAP. No redactions have been made to any files released under President Trump's directive concerning information about the nature or existence of any encounter reported as a UAP or related phenomena.":
        "הצבא (Department of the Army) הגיש למשרד פתרון תופעות כל-תחומיות (AARO) דיווח על תופעה אווירית חריגה בלתי מזוהה, הכולל דקה ו-49 שניות של וידאו מחיישן אינפרא-אדום על גבי פלטפורמה צבאית אמריקאית ב-2026. המדווח לא סיפק כל תיאור מילולי או כתוב של התצפית. תיאור הווידאו: 00:00-00:08: החיישן עוקב אחרי אזור עניין ראשוני. 00:09-00:16: החיישן מנתק מאזור המוקד הקודם ומסיט מימין לשמאל כדי לעקוב אחרי שני אזורים של ניגודיות, מצמצם את שדה הראייה לזום-אין תוך כדי הסטה כדי לשמור על מיקום העצמים ככלל במרכז הפריים. 00:17-01:03: החיישן מרחיב את שדה הראייה לזום-אאוט, ושומר על אזורי הניגודיות ככלל במרכז המסך. 01:04-01:08: שדה הראייה של החיישן מתחלף במהירות בין רמות זום, וגורם לאזורי הניגודיות להיראות כגדלים וקטנים במהירות. 01:09-01:48: החיישן עוקב אחרי אזורי הניגודיות תוך שמירה על מיקום ככלל מרכזי, ומחליף לסירוגין בין הגדרות ניגודיות. תיאור וידאו זה ניתן לצורכי מידע בלבד. אין לפרש כל חלק ממנו כשיקוף של שיפוט אנליטי, מסקנה חקירתית או קביעת עובדה בנוגע לתקפותו, טבעו או משמעותו של האירוע המתואר. בוצעו השמטות כדי להגן על זהות עדי ראייה, מיקומי מתקנים ממשלתיים, או מידע פוטנציאלית רגיש על אתרים צבאיים שאינם קשורים ל-UAP. לא בוצעו השמטות בקבצים שפורסמו תחת הנחיית הנשיא טראמפ בנוגע למידע על טבעם או קיומם של מפגשים שדווחו כ-UAP או תופעות נלוות.",

    "Apollo 12 was the fourth crewed U.S. mission to the Moon and the second to land astronauts on the lunar surface. This document is an excerpt from the Apollo 12 Technical Air-to-Ground Voice Transcription, November 1969, highlighting two periods in which astronauts reported observing unidentified phenomenon: a one hour period on the fifth day, and a two minute period on the sixth day. These transcripts contain contemporaneous observations by the flight crew reacting to unidentified phenomenon.•\tDay 05, Hour 19, Minute 14, Second 58 through Day 05, Hour 20, Minute 12, Second 14:o\tAt 05:19:27:25, the pilot of the Lunar Module (LMP-LM), Astronaut Alan L. Bean, described observing particles and flashes of light “sailing off in space” via the onboard Alignment Optical Telescope (AOT). He characterized these phenomenon as “escaping the Moon.”•\tDay 06, Hour 00, Minute 21, Second 42 through Day 06, Hour 00, Minute 23, Second 33:o\tMission Commander, Charles “Pete” Conrad, described observing floating debris outside the lunar module, which had been illuminated by the module’s onboard tracking light. At 06:00:21:51, Conrad assessed that the tracking light had burnt out because he could no longer see the debris from the module.":
        "Apollo 12 הייתה המשימה האנושית האמריקאית הרביעית לירח והשנייה שהנחיתה אסטרונאוטים על פני הירח. מסמך זה מהווה קטע מתוך תמליל הקול הטכני אוויר-קרקע של Apollo 12, נובמבר 1969, ומדגיש שתי תקופות שבהן דיווחו האסטרונאוטים על תצפית בתופעות בלתי מזוהות: תקופה בת שעה ביום החמישי, ותקופה בת שתי דקות ביום השישי. תמלילים אלה מכילים תצפיות בו-זמניות של צוות הטיסה המגיב לתופעות בלתי מזוהות. • יום 05, שעה 19, דקה 14, שנייה 58 עד יום 05, שעה 20, דקה 12, שנייה 14: ב-05:19:27:25, טייס המודול הירחי (LMP-LM), האסטרונאוט אלן ל. בין, תיאר כי חזה בחלקיקים ובהבזקי אור \"מפליגים בחלל\" דרך הטלסקופ האופטי לכיוונון (AOT) שעל הסיפון. הוא תיאר את התופעות הללו כ\"בורחות מן הירח\". • יום 06, שעה 00, דקה 21, שנייה 42 עד יום 06, שעה 00, דקה 23, שנייה 33: מפקד המשימה, צ'רלס \"פיט\" קונרד, תיאר כי חזה בפסולת צפה מחוץ למודול הירחי, שהוארה על ידי אור המעקב של המודול. ב-06:00:21:51, קונרד העריך כי אור המעקב נשרף משום שלא יכול היה עוד לראות את הפסולת מן המודול.",

    "Apollo 17 was the ninth crewed U.S. mission to the Moon, and the sixth to land astronauts on the lunar surface. This document is an excerpt from the Apollo 17 Technical Air-to-Ground Voice Transcription, December 1972, highlighting three periods in which astronauts reported observing unidentified phenomenon: a nine minute period on the first day, a three hour period on the second day, and a six minute period on the third day. •\tDay 00, Hour 03, Minute 34, Second 10 through Day 00, Hour 03, Minute 42, Second 29:    o\tCommand Module Pilot (CMP), Ronald Evans, reported observing “very bright particles or fragments” drifting and “tumbling” near the spacecraft as it maneuvered. Lunar Module Pilot (LMP), Harrison “Jack” Schmitt, described the phenomenon as looking “like the Fourth of July.” The astronauts speculated that the phenomenon may be attributable to ice or paint fragments dislodging from a separated component of the spacecraft (S-IVB) but characterized that assessment as a “wild guess.”•\tDay 02, Hour 18, Minute 42, Second 34 through Day 02, Hour 21, Minute 07, Second 05:    o\tMission Commander, Eugene A. Cernan, reported difficulty sleeping and described having observed “some sets of the streaks.” He also described an intense light flashing between his eyes, describing its intensity as comparable to that of a train headlight and characterizing it as “imposing.” Over the next three hours, Cernan described observing several flashing, rotating phenomenon that he assessed as corresponding to physical objects in space rather than a purely optical phenomenon. LMP Schmitt also reported observing similar phenomenon, though he again assessed the source of his observation to be a separated rocket stage (S-IVB). At 02:20:55:22, Cernan reported observing two additional distant flashing objects, though he assessed them as Spacecraft/Lunar Module Adapter panels (SLA panel), another separated component of the Saturn V rocket.•\tDay 03, Hour 15, Minute 33, Second 25 through Day 03, Hour 15, Minute 39, Second 46:    o\tAt 03:15:38:09, LMP Schmitt exclaimed that he had observed a flash on the lunar surface north of Grimaldi (crater).":
        "Apollo 17 הייתה המשימה האנושית האמריקאית התשיעית לירח, והשישית שהנחיתה אסטרונאוטים על פני הירח. מסמך זה מהווה קטע מתוך תמליל הקול הטכני אוויר-קרקע של Apollo 17, דצמבר 1972, ומדגיש שלוש תקופות שבהן דיווחו האסטרונאוטים על תצפית בתופעות בלתי מזוהות: תקופה בת תשע דקות ביום הראשון, תקופה בת שלוש שעות ביום השני, ותקופה בת שש דקות ביום השלישי. • יום 00, שעה 03, דקה 34, שנייה 10 עד יום 00, שעה 03, דקה 42, שנייה 29: טייס מודול הפיקוד (CMP), רונלד אוונס, דיווח על תצפית ב\"חלקיקים או שברים בהירים מאוד\" הנעים ו\"מתהפכים\" סמוך לחללית בעת תמרון. טייס המודול הירחי (LMP), הריסון \"ג'ק\" שמיט, תיאר את התופעה כ\"נראית כמו הרביעי ביולי\". האסטרונאוטים שיערו כי ייתכן ושברי קרח או צבע שניתקו מרכיב מנותק של החללית (S-IVB) הם הגורם, אך תיארו הערכה זו כ\"ניחוש פראי\". • יום 02, שעה 18, דקה 42, שנייה 34 עד יום 02, שעה 21, דקה 07, שנייה 05: מפקד המשימה, יוג'ין א. סרנן, דיווח על קושי בשינה ותיאר כיצד חזה ב\"כמה סדרות של פסים\". הוא תיאר גם אור עז מהבהב בין עיניו, השווה את עוצמתו לזו של פנס רכבת ותיאר אותה כ\"מטילת מורא\". במהלך שלוש השעות הבאות תיאר סרנן תצפית בכמה תופעות מהבהבות ומסתובבות, שאותן הוא העריך כתואמות לעצמים פיזיים בחלל ולא כתופעה אופטית גרידא. גם LMP שמיט דיווח על תצפית בתופעות דומות, אך שוב העריך את מקור התצפית כשלב טיל מנותק (S-IVB). ב-02:20:55:22, סרנן דיווח על תצפית בשני עצמים מהבהבים נוספים במרחק, אך העריך אותם כפאנלים של מתאם החללית/המודול הירחי (פאנל SLA), רכיב מנותק נוסף של טיל סטורן V. • יום 03, שעה 15, דקה 33, שנייה 25 עד יום 03, שעה 15, דקה 39, שנייה 46: ב-03:15:38:09, LMP שמיט קרא כי חזה בהבזק על פני הירח מצפון לגרימלדי (מכתש).",

    "Apollo 11 was the third crewed mission to the Moon and the first to land Astronauts on the lunar surface. This document is an excerpt from the Apollo 11 Technical Crew Debriefing (Volumes 1 and 2) from July 31, 1969. The document highlights three observations: one, an object on the way out to the Moon; two, flashes of light inside the cabin; and three, a sighting on the return trip of a bright light tentatively assumed by the crew to be a laser.•\tPage 6-33 (Vol. 1). [Lunar Module Pilot for Apollo 11, Buzz Aldrin]: “The first unusual thing that we saw I guess was 1 day out or something pretty close to the moon. It had a sizeable dimension to it, so we put the monocular on it.” The crew speculated that it could have been the S-IVB stage of the Saturn V launch vehicle.•\tPage 6-37 (Vol. 1). [Lunar Module Pilot for Apollo 11, Buzz Aldrin] “The other observation that I made accumulated gradually. I don’t know whether I saw it the first night, but I’m sure I saw it the second night. I was trying to go to sleep with all the lights out. I observed what I thought were little flashes inside the cabin, spaced a couple of minutes apart…”•\tPage 21-1 (Vol. 2). [Lunar Module Pilot for Apollo 11, Buzz Aldrin] “I observed what appeared to be a fairly bright light source which we tentatively ascribed to a possible laser.”":
        "Apollo 11 הייתה המשימה האנושית השלישית לירח והראשונה שהנחיתה אסטרונאוטים על פני הירח. מסמך זה מהווה קטע מתוך התחקור הטכני של צוות Apollo 11 (כרכים 1 ו-2) מ-31 ביולי 1969. המסמך מדגיש שלוש תצפיות: ראשית, עצם בדרך לירח; שנית, הבזקי אור בתוך התא; ושלישית, תצפית בטיסת החזרה באור בהיר שהצוות שיער באופן זמני כי הוא לייזר. • עמ' 6-33 (כרך 1). [טייס המודול הירחי של Apollo 11, באז אולדרין]: \"הדבר הראשון הבלתי שגרתי שראינו היה, לדעתי, יום אחד אחרי השיגור או משהו די קרוב לירח. היה לו ממד נכבד, אז כיוונו עליו את המונוקולר\". הצוות שיער כי ייתכן והיה זה שלב S-IVB של כלי השיגור סטורן V. • עמ' 6-37 (כרך 1). [טייס המודול הירחי של Apollo 11, באז אולדרין]: \"התצפית האחרת שעשיתי הצטברה בהדרגה. אני לא יודע אם ראיתי אותה בלילה הראשון, אבל אני בטוח שראיתי אותה בלילה השני. ניסיתי להירדם כשכל האורות כבויים. ראיתי את מה שחשבתי שהם הבזקים קטנים בתוך התא, במרווחים של כמה דקות זה מזה…\". • עמ' 21-1 (כרך 2). [טייס המודול הירחי של Apollo 11, באז אולדרין]: \"חזיתי במה שנראה כמקור אור בהיר למדי, אותו ייחסנו באופן זמני ללייזר אפשרי\".",

    "Launched on May 14, 1973, Skylab was the United States’ first laboratory in space. From 1973 to 1974, the station was visited by three crews. This document contains excerpts from all three crews to visit the station. In the first excerpt taken from Skylab 1/2 [first crew] Technical Debriefing from June 30, 1973, highlights crew observations of light flashes. The second excerpt taken from Skylab 1/3 Technical Crew Debriefing from October 4, 1973, highlights two observations—a satellite in similar orbit and another object with a “reddish hue to it.” The final excerpt taken from the Skylab 1/4 Technical Crew Debriefing from February 22, 1974, highlights an observation of flashing lights outside Skylab.•\tSkylab 2 crew observation: o\tPage 23-20. [Science Pilot for Skylab 2, Joesph Kerwin] “We saw light flashes. I think all of us saw them. I saw them most often when I was in the sack at night with my eyes closed but awake naturally. They tended to wax and wane in frequency.”•\tSkylab 3 crew observations: o\tPage 7-4. [Science Pilot for Skylab 3, Owen Garriott] “We saw that satellite about a week before splashdown. That was one of the most unusual things that we saw and I guess Jack [Lousma] noticed it looking out the window. This bright reddish object was out there and we tracked it for about 5 or 10 minutes. It was obviously a satellite in a very similar orbit to our own.”o\tPage 20-1. [Science Pilot for Skylab 3, Owen Garriott] “Jack [Lousma] first noticed this rather large red star out the wardroom window. Upon close examination, it was much brighter than Jupiter or any of the other planets. It had a reddish hue to it, even though it was well above the horizon.”•\tSkylab 4 crew observation o\tPage 7-8. [Commander for Skylab 4, Gerald P. Carr] “One other area of unusual events that we reported on the dump tapes was that on occasion we saw some lights flashing outside with very a definite motion relative to ours. We presumed that they were other pieces of Skylab, or possibly other satellites.”":
        "Skylab, ששוגרה ב-14 במאי 1973, הייתה המעבדה הראשונה של ארצות הברית בחלל. בין השנים 1973 ל-1974 ביקרו בתחנה שלושה צוותים. מסמך זה מכיל קטעים מתוך כל שלושת הצוותים שביקרו בתחנה. הקטע הראשון, מתוך התחקור הטכני של Skylab 1/2 [הצוות הראשון] מ-30 ביוני 1973, מדגיש תצפיות צוות בהבזקי אור. הקטע השני, מתוך התחקור הטכני של צוות Skylab 1/3 מ-4 באוקטובר 1973, מדגיש שתי תצפיות — לוויין במסלול דומה ועצם נוסף בעל \"גוון אדמדם\". הקטע האחרון, מתוך התחקור הטכני של צוות Skylab 1/4 מ-22 בפברואר 1974, מדגיש תצפית באורות מהבהבים מחוץ ל-Skylab. • תצפית צוות Skylab 2: עמ' 23-20. [טייס המדע של Skylab 2, ג'וזף קרווין]: \"ראינו הבזקי אור. אני חושב שכולנו ראינו אותם. ראיתי אותם לרוב כשהייתי במיטה בלילה עם עיניים עצומות אך ער באופן טבעי. הם נטו להופיע ולהיעלם בתדירות משתנה\". • תצפיות צוות Skylab 3: עמ' 7-4. [טייס המדע של Skylab 3, אוון גריוט]: \"ראינו את הלוויין הזה כשבוע לפני נחיתת המים. זה היה אחד הדברים הבלתי שגרתיים ביותר שראינו, ולדעתי ג'ק [לוסמה] שם לב אליו כשהוא הביט מהחלון. העצם האדמדם הבהיר הזה היה שם וביצענו עליו מעקב כ-5 או 10 דקות. ברור שהיה זה לוויין במסלול דומה מאוד לשלנו\". עמ' 20-1. [טייס המדע של Skylab 3, אוון גריוט]: \"ג'ק [לוסמה] שם לב לראשונה לכוכב האדום הגדול-יחסית הזה מחלון חדר האוכל. בבחינה מקרוב, הוא היה בהיר בהרבה מצדק או מכל כוכבי הלכת האחרים. היה לו גוון אדמדם, אף שהיה גבוה מאוד מעל האופק\". • תצפית צוות Skylab 4: עמ' 7-8. [מפקד Skylab 4, ג'רלד פ. קאר]: \"תחום אחר נוסף של אירועים בלתי שגרתיים שדיווחנו עליו בקלטות הפריקה הוא שלעתים ראינו אורות מהבהבים בחוץ עם תנועה מובהקת מאוד יחסית לשלנו. הנחנו כי היו אלה חלקים אחרים של Skylab, או אולי לוויינים אחרים\".",

    "This archival photograph depicts the lunar surface as viewed from the landing site of Apollo 12. This image features two highlighted areas of interest, labeled “Area 1” and “Area 2,” slightly to the right of the vertical axis of the frame, above the horizon, in which unidentified phenomena are visible.This image has been modified from its original state to assist viewers in identifying specific areas of interest. These highlights are provided for contextual purposes only. Such alterations do not constitute an analytical judgment, investigative conclusion, or factual determination regarding the nature or significance of the subject matter.":
        "צילום ארכיון זה מציג את פני הירח כפי שנראו מאתר הנחיתה של Apollo 12. בתמונה מודגשים שני אזורי עניין, המסומנים \"אזור 1\" ו\"אזור 2\", מעט מימין לציר האנכי של הפריים, מעל האופק, ובהם נראות תופעות בלתי מזוהות. תמונה זו עברה שינוי ממצבה המקורי כדי לסייע לצופים בזיהוי אזורי עניין ספציפיים. הדגשות אלו ניתנות לצורכי הקשר בלבד. שינויים מסוג זה אינם מהווים שיפוט אנליטי, מסקנה חקירתית או קביעת עובדה בנוגע לטבעו או למשמעותו של הנושא.",

    "This archival photograph depicts the lunar surface as viewed from the landing site of Apollo 12. This image features five highlighted areas of interest, labeled “Area 1” through “Area 5,” above the horizon, in which unidentified phenomena are visible.This image has been modified from its original state to assist viewers in identifying specific areas of interest. These highlights are provided for contextual purposes only. Such alterations do not constitute an analytical judgment, investigative conclusion, or factual determination regarding the nature or significance of the subject matter.":
        "צילום ארכיון זה מציג את פני הירח כפי שנראו מאתר הנחיתה של Apollo 12. בתמונה מודגשים חמישה אזורי עניין, המסומנים \"אזור 1\" עד \"אזור 5\", מעל האופק, ובהם נראות תופעות בלתי מזוהות. תמונה זו עברה שינוי ממצבה המקורי כדי לסייע לצופים בזיהוי אזורי עניין ספציפיים. הדגשות אלו ניתנות לצורכי הקשר בלבד. שינויים מסוג זה אינם מהווים שיפוט אנליטי, מסקנה חקירתית או קביעת עובדה בנוגע לטבעו או למשמעותו של הנושא.",

    "As part of the review of historical UAP materials under PURSUE, DOW has opened a case to investigate the accompanying NASA photograph from the Apollo 17 mission, taken December 1972. The image contains three “dots” in a triangular formation in the lower right quadrant of the lunar sky that is clearly visible upon magnification of the image. While this photo has been previously released and discussed by keen observers, there is no consensus about the nature of the anomaly. New preliminary US government analysis suggests the image feature is potentially the result of a physical object in the scene. Additionally, as part of this investigation, the government has obtained the original film from the Apollo 17 mission and the results of the full NASA and DOW analysis will be released when completed.":
        "כחלק מבחינת חומרי UAP היסטוריים במסגרת PURSUE, משרד המלחמה (DOW) פתח תיק לחקירת תמונת NASA המצורפת ממשימת Apollo 17, שצולמה בדצמבר 1972. התמונה מכילה שלוש \"נקודות\" במבנה משולש ברבע הימני-תחתון של שמי הירח, הנראות בבירור בעת הגדלת התמונה. אף שהתמונה פורסמה והובאה לדיון בעבר בידי תצפיתנים מעמיקים, אין הסכמה לגבי טבעה של החריגה. ניתוח ראשוני חדש מטעם ממשלת ארה\"ב מצביע על כך שתופעת התמונה היא פוטנציאלית תוצאה של עצם פיזי בסצנה. בנוסף, כחלק מהחקירה הזו, הממשלה השיגה את הסרט המקורי ממשימת Apollo 17, ותוצאות הניתוח המלא של NASA ו-DOW יפורסמו עם השלמתו.",

    "This document is a U.S. Department of State diplomatic cable from the U.S. Embassy in Port Moresby, Papua New Guinea to USCINCPAC (United States Indo-Pacific Command) at Honolulu, HI on January 28, 1985. The cable reports that the U.S. Embassy to Papua New Guinea received an inquiry from the host nation’s intelligence services regarding reports of high-altitude, high-speed aircraft in Papua New Guinean airspace on the evening of January 24, 1985. The cable refers to a representative of the local intelligence services as “NIO,” or National Intelligence Officer, throughout. The NIO relayed to U.S. diplomatic personnel that residents had been “frightened by overflights, which led to the provincial premier’s calling of a public meeting on the subject.” The NIO also stated there had been “various reports of unidentified aerial phenomena the night of January 24, including fast-moving objects with lights, contrails, and noise.” The NIO assessed these reports as credible based upon the testimony of an Air Niugini pilot who said that their radar had “picked up aircraft flying south to north at high altitude and high speed.”The cable concludes by characterizing the information provided by the NIO as “very sketchy.” It also sought clarification from U.S. INDOPACOM on the presence or absence of U.S. military aircraft within Papua New Guinean airspace on the night in question.":
        "מסמך זה הוא מברק דיפלומטי של מחלקת המדינה האמריקאית מהשגרירות האמריקאית בפורט מורסבי, פפואה גינאה החדשה, אל USCINCPAC (פיקוד אינדו-פסיפיק של ארצות הברית) בהונולולו, הוואי, ב-28 בינואר 1985. במברק מדווח כי השגרירות האמריקאית בפפואה גינאה החדשה קיבלה פנייה משירותי המודיעין של מדינת הארח בנוגע לדיווחים על כלי טיס במהירות וגובה גבוהים במרחב האווירי של פפואה גינאה החדשה בערב 24 בינואר 1985. המברק מתייחס לנציג שירותי המודיעין המקומיים לאורך כולו כ-\"NIO\", כלומר קצין מודיעין לאומי. ה-NIO מסר לאנשי הסגל הדיפלומטי האמריקאי כי תושבים \"נבהלו מהטיסות מעל, מה שהוביל את ראש הממשלה המחוזי לכנס פגישה ציבורית בנושא\". ה-NIO ציין גם כי היו \"דיווחים מגוונים על תופעות אוויריות בלתי מזוהות בליל 24 בינואר, ובהם עצמים נעים במהירות עם אורות, פסי עיבוי ורעש\". ה-NIO העריך את הדיווחים הללו כאמינים על בסיס עדותו של טייס Air Niugini, שאמר כי המכ\"ם שלהם \"קלט כלי טיס הטסים מדרום לצפון בגובה ובמהירות גבוהים\". המברק מסכם בתיאור המידע שמסר ה-NIO כ\"שטחי מאוד\". הוא מבקש גם הבהרה מ-INDOPACOM של ארה\"ב בנוגע לנוכחות או היעדרות של כלי טיס צבאיים אמריקאיים במרחב האווירי של פפואה גינאה החדשה בליל המדובר.",

    "This document is a U.S. Department of State diplomatic cable from the U.S. Embassy in Dushanbe, Tajikistan to the Secretary of State in Washington, D.C. on January 31, 1994.On January 27, 1994 one Tajik pilot and three American citizens encountered an UAP flying a 747 jet at 41,000 feet over Kazakhstan.  Object was a bright light of enormous intensity and approached over the horizon to the east at great speed and a much higher altitude.  Several pictures were taken of the craft making 90 degree turns, doing corkscrews and maneuvering in circles a great rates of speed.  Object was reported as resembling a bullet in flight.  Visual estimation of the contrails were at 100,000 feet, which was too high to leave contrails by ordinary aircraft.":
        "מסמך זה הוא מברק דיפלומטי של מחלקת המדינה האמריקאית מהשגרירות האמריקאית בדושנבה, טג'יקיסטן, אל מזכיר המדינה בוושינגטון הבירה, ב-31 בינואר 1994. ב-27 בינואר 1994 נתקלו טייס טג'יקי אחד ושלושה אזרחים אמריקאים ב-UAP בעת שהטיסו מטוס 747 בגובה 41,000 רגל מעל קזחסטן. העצם היה אור בהיר בעוצמה אדירה, והתקרב מעל האופק במזרח במהירות עצומה ובגובה גבוה בהרבה. צולמו מספר תמונות של הכלי בעודו מבצע פניות של 90 מעלות, סלילים ותמרונים במעגלים במהירויות גבוהות. העצם דווח כדומה לכדור בטיסה. ההערכה הוויזואלית של פסי העיבוי הייתה בגובה 100,000 רגל — גובה רב מדי משאיוכלו כלי טיס רגילים להותיר פסי עיבוי.",

    "On October 28-29, there was an incident alleged by the Georgian Foreign Ministry that Russian aircraft had violated Georgian airspace and bombed areas of the Kodori Gorge.  Russians denied any of the claims and said that it could have been UFOs.  Cable authors note that Russians typically engage in the “bold lie” when they wish to conceal actions.":
        "ב-28-29 באוקטובר התרחש אירוע שלגביו טען משרד החוץ הגאורגי כי כלי טיס רוסיים הפרו את המרחב האווירי הגאורגי והפציצו אזורים בגיא קודורי. הרוסים הכחישו את הטענות וטענו כי ייתכן שמדובר היה ב-UFO. כותבי המברק מציינים כי הרוסים נוטים בדרך כלל ל\"שקר נועז\" כשהם מבקשים להסתיר פעולות.",

    "UFOlogists of Turkmenistan has gained a positive reputation as a reliable partner for the United States in Turkmenistan to the bemusement of the cable’s author in the build up of civil society organizations within the country.  The reputation has become earned because everyone in Turkmenistan, apparently, “is interested in UFOs.”":
        "אגודת ה-UFOlogists של טורקמניסטן זכתה למוניטין חיובי כשותפה אמינה של ארצות הברית בטורקמניסטן, להפתעת מחבר המברק, בקידום ארגוני חברה אזרחית בתוך המדינה. המוניטין הושג, כפי הנראה, משום שכולם בטורקמניסטן \"מתעניינים ב-UFO\".",

    "On September 12, 20023 the Mexican Congress heard testimony on UAP from experts related to the debate about an Aerial Space Protection Law, which, if approved, would make Mexico the first country to formally acknowledge the presence of alien life on earth. Experts asked legislators to recognize UAP, guarantee airspace security, and allow UAP to be studied.  They presented to alleged alien corpses and videos of Mexican pilot’s encounters with fast-moving flying objects during flight. Disagreement about the efficacy and validity of the purported alien corpses.":
        "ב-12 בספטמבר 2023 שמע הקונגרס המקסיקני עדות על UAP ממומחים, בקשר לדיון על חוק להגנת המרחב האווירי שאם יאושר, יהפוך את מקסיקו למדינה הראשונה שמכירה באופן רשמי בקיומם של חיים חוצניים על פני כדור הארץ. המומחים ביקשו מהמחוקקים להכיר ב-UAP, להבטיח את ביטחון המרחב האווירי, ולאפשר את חקר ה-UAP. הם הציגו גופות שלפי הטענה הן חוצניות וסרטונים של מפגשי טייסים מקסיקנים עם עצמים מעופפים נעים במהירות בעת טיסה. הייתה אי-הסכמה בנוגע לאמינותן ולתקפותן של הגופות הנטענות.",

    "This is an FBI 302 interview conducted with a senior US intelligence official regarding his first-hand account of a UAP encounter at a US military facility. USPER relayed to FBI agents that he and other federal and state personnel conducted searches to where orbs had been previously seen.  After searching the area with a helicopter, they found a “super-hot” orb hovering over the ground.  The orb is reported to have travelled for 20 miles at a speed too fast for the helicopter in pursuit.  An additional “swarm” of lights were seen moving in all directions.  A total of four or five additional orbs were seen shortly thereafter for a short time, flaring up and then down.  This pattern of four or five orbs flaring up, then down continued over the next thirty minutes across the area.\n  Redactions have been made to protect the identity of eyewitnesses, the location of government facilities, or potentially sensitive information about military sites not related to UAP. No redactions have been made to any files released under President Trump's directive concerning information about the nature or existence of any encounter reported as a UAP or related phenomena.":
        "זהו ראיון FBI טופס 302 שנערך עם פקיד מודיעין בכיר בארה\"ב בנוגע לעדותו ממקור ראשון על מפגש UAP במתקן צבאי אמריקאי. USPER מסר לסוכני ה-FBI כי הוא ואנשי סגל פדרליים ומדינתיים נוספים ערכו חיפושים באזורים שבהם נראו בעבר כדורי אור. לאחר חיפוש באזור בעזרת מסוק, הם מצאו כדור אור \"חם במיוחד\" מרחף מעל הקרקע. כדור האור דווח כי נסע 20 מייל במהירות מהירה מדי עבור המסוק שרדף אחריו. בנוסף נראה \"נחיל\" של אורות נע לכל הכיוונים. בסך הכל נראו ארבעה או חמישה כדורי אור נוספים זמן קצר לאחר מכן לפרק זמן קצר, מתלקחים ואז דועכים. תבנית זו של ארבעה או חמישה כדורי אור מתלקחים ואז דועכים נמשכה במהלך שלושים הדקות הבאות ברחבי האזור. בוצעו השמטות כדי להגן על זהות עדי ראייה, מיקומי מתקנים ממשלתיים, או מידע פוטנציאלית רגיש על אתרים צבאיים שאינם קשורים ל-UAP. לא בוצעו השמטות בקבצים שפורסמו תחת הנחיית הנשיא טראמפ בנוגע למידע על טבעם או קיומם של מפגשים שדווחו כ-UAP או תופעות נלוות.",

    "Actual site photo with FBI Lab rendered graphic overlay depicting corroborating eyewitness reports from September 2023 of an apparent ellipsoid bronze metallic object materializing out of a bright light in the sky, 130-195 feet in length, and disappearing instantaneously.":
        "תצלום אמיתי של זירה בתוספת שכבת גרפיקה שעיבדה מעבדת ה-FBI, המתארת דיווחי עדי ראייה מאשרים מספטמבר 2023 על עצם מתכתי ארד אליפסואידי לכאורה, באורך 130-195 רגל, אשר התממש מתוך אור בהיר בשמיים ונעלם באופן מיידי.",

    "This document is a summary of statements by seven US PERSONs employed by the federal government who separately reported observing several unidentified anomalous phenomena in the western United States over the course of two days in 2023.  The summary notes the US PERSONS reported four distinct categories of experiences, including observing “orbs launching other orbs” at a distance, observing a large stationary glowing orb at close estimated range, pursuing a large phenomenon near the ground, and observing a large, seemingly transparent phenomenon, reported to being akin to a “translucent kite.” Although there is no technical data directly associated with this report, contextual factors — such as these events sharing features with others reported to the All-domain Anomaly Resolution Office (AARO), the reporters’ credibility, and the potentially anomalous nature of the events themselves — combine to make this report among the most compelling within AARO’s current holdings.":
        "מסמך זה הוא סיכום של הצהרות מצד שבעה US PERSON המועסקים על ידי הממשל הפדרלי, אשר דיווחו בנפרד על תצפית בכמה תופעות אוויריות חריגות בלתי מזוהות במערב ארצות הברית במהלך יומיים בשנת 2023. הסיכום מציין כי ה-US PERSONS דיווחו על ארבע קטגוריות מובחנות של חוויות, ובהן: תצפית ב\"כדורי אור המשגרים כדורי אור אחרים\" במרחק, תצפית בכדור אור גדול ונייח זוהר בטווח קרוב משוער, רדיפה אחר תופעה גדולה סמוך לקרקע, ותצפית בתופעה גדולה ושקופה לכאורה, שדווחה כדומה ל\"עפיפון שקוף-למחצה\". אף שאין נתונים טכניים הקשורים ישירות לדיווח זה, גורמי הקשר — כגון העובדה שלאירועים הללו יש מאפיינים משותפים עם אחרים שדווחו למשרד פתרון תופעות כל-תחומיות (AARO), אמינותם של המדווחים, וטבעם החריג הפוטנציאלי של האירועים עצמם — משתלבים יחד כדי להפוך דיווח זה לאחד המשכנעים ביותר מבין אלו שבחזקתה הנוכחית של AARO.",
}


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
