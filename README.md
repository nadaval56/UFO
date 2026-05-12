# PURSUE — מראה עברית

מראה עברית בלתי רשמית של עמוד **PURSUE** (Presidential Unsealing and Reporting System for UAP Encounters) של משרד המלחמה האמריקאי.

> **כתב ויתור:** תרגום קהילתי בלתי רשמי. לא מסונף לממשלת ארה"ב. למקור הרשמי באנגלית: [war.gov/UFO](https://www.war.gov/UFO/)

## איך מרעננים את ה-manifest (חובה ידנית)

`war.gov` מוגן ב-Akamai WAF שמחזיר 403 לכל IP של GitHub Actions / AWS / Azure / Google Cloud. אין דרך לסרוק את האתר משרת. **הדפדפן הביתי שלך הוא הסביבה היחידה שעובדת**.

### תהליך הסריקה (פעם בכל מהדורה חדשה — דקה של עבודה)

1. פתח את [https://www.war.gov/UFO/](https://www.war.gov/UFO/) בדפדפן.
2. פתח DevTools (F12) → Console.
3. העתק את כל התוכן של [`scripts/browser_scrape.js`](./scripts/browser_scrape.js), הדבק בקונסול, הקש Enter.
4. הסקריפט יעבור על כל 16 העמודים, יסרוק כל שורה, יכנס לכל פאנל פרטים כדי לקחת את התיאור באנגלית, ויוריד `manifest.json` (אורך הריצה: כ-1-2 דקות בגלל המתנות בין עמודים).
5. החלף את `data/manifest.json` בקובץ שירד.
6. `git add data/manifest.json && git commit -m 'data: refresh manifest from war.gov' && git push`.

GitHub Pages יפרוס את הגרסה החדשה תוך 1-2 דקות.

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
