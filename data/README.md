# `/data` — מקור הנתונים של דפדפן הקבצים

קובץ `manifest.json` הוא מקור האמת היחיד עבור דפדפן הקבצים בעמוד `index.html`.
הוא נטען ב-client-side ב-`fetch()` ומכיל את כל המסמכים במהדורה.

## סכמה

```jsonc
{
  "release_id": "release_01",          // מזהה המהדורה
  "release_date": "2026-05-08",        // תאריך הפרסום (YYYY-MM-DD)
  "source_bundle_url": "https://www.war.gov/...Release_1.zip",
  "total_files": 156,
  "generated_at": "2026-05-12T10:00:00Z",
  "files": [
    {
      "id": "65_HS1-834228961_62-HQ-83894_SERIAL_130",
      "filename": "65_HS1-834228961_62-HQ-83894_SERIAL_130.pdf",
      "agency": "FBI",                  // FBI | DOW | NASA | ODNI | AARO | Unknown
      "type": "pdf",                    // pdf | img | vid | doc | txt | …
      "size_bytes": 1234567,
      "source_url": "https://www.war.gov/medialink/ufo/files/65_HS1-...SERIAL_130.pdf",
      "sha256": null,                   // אופציונלי
      "incident_date": null,            // Phase 2
      "incident_location": null,        // Phase 2
      "summary_he": null                // Phase 2
    }
  ]
}
```

## הפקה

```bash
cd scripts
pip install -r requirements.txt
python build_manifest.py            # מוריד את ה-ZIP מ-war.gov
python build_manifest.py --skip-download --skip-extract   # אם כבר ירד
python build_manifest.py --with-sha256                    # חישוב hash (איטי)
```

הסקריפט יוצר את `data/manifest.json` במקום הקובץ הקיים.

## פיתוח מקומי ללא הורדה

הקובץ `manifest.json` המצורף למאגר הוא **דוגמה** שמכילה כמה עשרות רשומות סינתטיות
בתבנית FBI, לצורך בדיקת ה-UI לפני שמושכים את החבילה האמיתית. החליפו אותו על ידי
הפעלת הסקריפט.

## אימות

לאחר ההפקה כדאי לבדוק:
- `total_files` תואם למספר הפריטים ב-`files`.
- כל `source_url` נפתח בפועל (Sample 5 רנדומליים).
- ההיסטוגרמה של `agency` ו-`type` הגיונית.
- גודל הקובץ מתחת ל-500KB (אחרת ה-UI ייטען לאט; שקלו דחיסה / lazy loading).
