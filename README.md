# PURSUE — מראה עברית

מראה עברית בלתי רשמית של עמוד **PURSUE** (Presidential Unsealing and Reporting System for UAP Encounters) של משרד המלחמה האמריקאי.

> **כתב ויתור:** תרגום קהילתי בלתי רשמי. לא מסונף לממשלת ארה"ב. למקור הרשמי באנגלית: [war.gov/UFO](https://www.war.gov/UFO/)

## איך מרעננים את ה-manifest (חובה ידנית)

`war.gov` מוגן ב-Akamai WAF שמחזיר 403 לכל IP של GitHub Actions / AWS / Azure / Google Cloud. אין דרך לסרוק את האתר משרת. **הדפדפן הביתי שלך הוא הסביבה היחידה שעובדת**.

### תהליך הסריקה (פעם בכל מהדורה חדשה — דקה של עבודה)

1. פתח את [https://www.war.gov/UFO/](https://www.war.gov/UFO/) בדפדפן.
2. **הגדר את פילטרי הטבלה.** הסקרייפר סורק אך ורק את מה שמוצג בטבלה, ולכן יש שתי אפשרויות:
   - **עדכון מצטבר (מומלץ למהדורה חדשה):** הגדר `ALL AGENCIES` + `ALL TYPES`, ואת פילטר ה-RELEASE
     הגדר **למהדורה החדשה בלבד**. תקבל רק את הרשומות החדשות (למשל 41 במקום 375), והסריקה מסתיימת
     תוך פחות מדקה. `merge_release.py` משווה מול המאניפסט הקיים ולא דורש את הסט המלא — סריקה חלקית
     עובדת בדיוק אותו דבר.
   - **סריקה מלאה:** שלושת הפילטרים ל-ALL. נחוצה רק כשצריך למלא אחורה מהדורות חסרות, או כדי לאמת
     מחדש את כל הארכיון (war.gov לעיתים מרפד מחדש קודי מסמכים בין מהדורות).
3. פתח DevTools (F12) → Console.
4. העתק את כל התוכן של [`scripts/browser_scrape.js`](./scripts/browser_scrape.js), הדבק בקונסול, הקש Enter.
5. הסקריפט יעבור על כל העמודים, יסרוק כל שורה (כל שורה מתויגת בתאריך השחרור/המהדורה שלה), יכנס לכל פאנל פרטים כדי לקחת את התיאור באנגלית, ויוריד `manifest.json`. בסיום הוא מדפיס בקונסול פירוט של כמה רשומות נמצאו בכל מהדורה — ודא שהמספר תואם למצופה.
6. **אל תדרוס את `data/manifest.json` בקובץ שירד** — הקובץ הקיים מכיל תרגומים, תצוגות מקדימות,
   OCR והטמעות וידאו שהסריקה אינה מכילה. במקום זאת, מזג רק את הרשומות החדשות:

   ```bash
   cp ~/Downloads/manifest.json ./scrape.json
   python scripts/merge_release.py --new scrape.json --dry-run   # בדיקה: כמה רשומות חדשות?
   python scripts/merge_release.py --new scrape.json             # ביצוע
   ```

   הסקריפט משאיר את הרשומות הקיימות כפי שהן, מוסיף רק מה שבאמת חדש, ומקצה לכל קובץ
   `release` / `release_no` לפי סדר תאריכי השחרור — כך שמהדורה חדשה מקבלת לשונית משלה מעצמה.
7. `git add data/manifest.json && git commit -m 'data: refresh manifest from war.gov' && git push`.

GitHub Pages יפרוס את הגרסה החדשה תוך 1-2 דקות.

### מהדורה חדשה — התהליך המלא

סריקה לבדה מביאה רק את הטבלה. מהדורה חדשה דורשת גם את חבילות ה-ZIP, תצוגות מקדימות, OCR
וסרטוני DVIDS — וכל אלה חסומים מהסביבה הענן. התהליך המלא ארוז כהנחיה אחת להדבקה בסשן
Claude Code **מקומי**:

- מהדורה 05: [`scripts/extract/LOCAL_TASK_R05.md`](./scripts/extract/LOCAL_TASK_R05.md)
- מהדורות 03–04 (לדוגמה): [`scripts/extract/LOCAL_TASK_R03_R04.md`](./scripts/extract/LOCAL_TASK_R03_R04.md)

מהסשן המקומי חוזר zip אחד; הסשן המרוחק מטמיע אותו ומתרגם.

**כל עוד מהדורה פורסמה וטרם שוקפה**, יש לרשום אותה ב-[`data/pending.json`](./data/pending.json).
האתר מציג על סמך זה הודעה גלויה מעל לשוניות המהדורות, כדי שלא ייווצר רושם שהארכיון מלא.
מוחקים את הרשומה משם ברגע שהקבצים מוזגו.

### תרגום לעברית (Claude Code)

הקובץ שירד מהדפדפן מכיל רק אנגלית. כדי להוסיף תרגומים עבריים:

1. פתח Claude Code בריפו.
2. בקש: "תרגם בעברית נאמנה את title, agency, incident_location ו-summary_en של כל הרשומות החדשות ב-data/manifest.json. שמור את התרגומים בשדות `title_he`, `agency_he`, `incident_location_he`, `summary_he`. אל תקצר — שמור על יחס אורך 1:1 ככל האפשר."
3. Claude יקרא את הקובץ, יתרגם, וישכתב אותו.

תרגומים נשמרים בין רענונים: בריצה הבאה של `scripts/build_manifest.py` (אם תרצה לולטדריג את הקובץ ב-validation), כל `*_he` שכבר קיים — נשאר.

### אימות קישורים (אופציונלי)

```bash
python scripts/build_manifest.py            # HEAD-check על כל source_url, סימון url_status
python scripts/build_manifest.py --no-validate
```

## הפעלה מקומית

```bash
python3 -m http.server 8000
# פתח http://localhost:8000
```

## מבנה הפרויקט

```
/
├── index.html                # האתר
├── CLAUDE.md                 # הנחיות פיתוח
├── README.md
├── LICENSE
├── data/
│   ├── manifest.json         # מקור הנתונים של דפדפן הקבצים
│   ├── README.md             # מפרט הסכמה
│   └── TRANSLATIONS.md       # כללי תרגום
├── scripts/
│   ├── browser_scrape.js     # ← הזה — להעתיק לקונסול הדפדפן
│   ├── build_manifest.py     # ולידציה + שימור תרגומים
│   └── requirements.txt
├── assets/
│   ├── css/styles.css
│   ├── js/main.js
│   └── js/file-browser.js
└── .github/workflows/
    └── deploy.yml            # פריסה ל-Pages (האתר סטטי לחלוטין)
```

## רישיון

תוכן המקור שייך לציבור (יצירה של ממשלת ארה"ב, 17 U.S.C. § 105). הקוד של פרויקט זה משוחרר תחת MIT — ראה [LICENSE](./LICENSE).

## תרומה

ראה [CLAUDE.md](./CLAUDE.md) למפת הדרכים והנחיות פיתוח.
