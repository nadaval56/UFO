# PURSUE — מראה עברית

מראה עברית בלתי רשמית של עמוד **PURSUE** (Presidential Unsealing and Reporting System for UAP Encounters) של משרד המלחמה האמריקאי.

> **כתב ויתור:** תרגום קהילתי בלתי רשמי. לא מסונף לממשלת ארה"ב. למקור הרשמי באנגלית: [war.gov/UFO](https://www.war.gov/UFO/)

## אודות

הפרויקט הוא שיכפול 1:1 של עמוד הנחיתה, מתורגם לעברית RTL, כולל דפדפן מסמכים פעיל עם סינון, חיפוש וחלוקה לעמודים.

הפרויקט סטטי לחלוטין — HTML/CSS/JS ללא תלות בשרת. נארח ב-GitHub Pages.

## הפעלה מקומית

```bash
# שרת סטטי כלשהו, למשל:
python3 -m http.server 8000
# ואז פתח http://localhost:8000
```

## בניית מאניפסט הקבצים

```bash
cd scripts
pip install -r requirements.txt
python build_manifest.py
```

הסקריפט מוריד את `Release_1.zip` מ-war.gov, מחלץ אותו, מנתח את שמות הקבצים ומפיק `data/manifest.json`.

## מבנה הפרויקט

```
/
├── index.html
├── CLAUDE.md
├── README.md
├── LICENSE
├── data/
│   ├── manifest.json
│   └── README.md
├── scripts/
│   ├── build_manifest.py
│   └── requirements.txt
├── assets/
│   ├── css/styles.css
│   ├── js/main.js
│   ├── js/file-browser.js
│   ├── images/
│   └── fonts/
└── .github/workflows/deploy.yml
```

## רישיון

תוכן המקור שייך לציבור (יצירה של ממשלת ארה"ב, 17 U.S.C. § 105). הקוד של פרויקט זה משוחרר תחת MIT — ראה [LICENSE](./LICENSE).

## תרומה

ראה [CLAUDE.md](./CLAUDE.md) למפת הדרכים והנחיות פיתוח.
