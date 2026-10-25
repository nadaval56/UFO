# Brief: Hebrew extended summaries (סיכום מורחב) for pursue.co.il

> Used by `RUNBOOK.md`. Agents get this file plus a JSON list of records. Proven on the 19-document pilot (2026-10-25).

pursue.co.il is an unofficial Hebrew mirror of war.gov/UFO, the U.S. Department of War's archive of declassified UAP/UFO documents. Every document has its own page. You write the **extended summary** for some of those pages. It is the longest Hebrew text on the page and the main reason a reader (and Google) finds the page worth visiting. The page already shows the official war.gov summary translated (`summary_he`) and a Hebrew translation of the first ~3,000 OCR characters. Your summary must cover **the whole document** and add real value beyond those.

## Input
Your batch file is a JSON list. Each record gives metadata, the official summary in English and Hebrew, `ocr_file` (the full OCR text of the whole document; read ALL of it, in chunks if it is long), and `out_file` (where you write the result).

The OCR is noisy: broken lines, garbled words, redaction marks, repeated cover pages. Read through the noise. Do not translate noise, and do not guess at illegible words.

## Output
One UTF-8 file per record at `out_file`, in this tiny format (nothing else of Markdown is supported):
- A line starting with `### ` is a section heading.
- Blocks are separated by a blank line. A block whose every line starts with `- ` is a bullet list. Anything else is a paragraph.
- No `#`/`##`, no bold/italics, no links, no tables, no code.

## Structure
1. **Opening paragraph, no heading** (2-4 sentences): what the document is, who produced it and for whom, when, and what it is about. It must stand alone: Google may show it as the snippet, and a reader who stops there should already know what the document is.
2. `### רקע` - the setting needed to understand the document: the program, unit, form or regulation, as the document and the official summary describe them. You may add widely established general facts (for example what Project Blue Book or AFR 200-2 was) only when you are certain. No speculation and no outside claims about the incident itself.
3. `### מה כתוב במסמך` - the core section, always present under exactly this heading (part sub-headings, if any, come after it). Walk through the document in its own order: sections, enclosures, attachments, letters in the file. Be concrete: dates, times, places, units, aircraft, durations, distances, colours, shapes, the witnesses' own descriptions (as short quotes in Hebrew translation), the conclusions and recommendations, and who signed or forwarded what. For a long document use extra `### ` sub-headings named after its parts (for example `### נספח א - ראיונות עם תושבים`).
4. `### פרטים בולטים` - a bullet list of 4-8 specific, checkable details a reader would find most interesting.
5. `### מה לא נמצא במסמך` - redactions (what kind and where, in general terms), pages that are illegible, missing or handwritten, and questions the document leaves open. Short.
6. Optional `### מונחים` - bullets explaining acronyms and terms that appear (AIIR, BAASS, ACWRON...), only when there are several.

## Length
Scale with the document, and don't pad: every sentence should carry information.
- OCR up to ~5,000 characters: 250-450 Hebrew words.
- 5,000-20,000: 400-750 words.
- 20,000-80,000: 900-1,600 words, with sub-headings per part.
- 80,000-300,000: 1,600-2,400 words.
- Over 300,000: 2,000-3,000 words.
Never shorter than needed to cover what the document actually says.

## Rules
- **Faithful.** Everything comes from the OCR or the official summary. Uncertain readings are marked: "(קריאה לא ודאית)". Never invent names, numbers or conclusions.
- **The document wins.** The document is the primary source; war.gov's official summary was written later and sometimes carries copy-paste errors from a neighbouring record. When the summary disagrees with what the document clearly says, write the document's version in the body, and mention the summary's version once, briefly, under `### מה לא נמצא במסמך` (for example "בתיאור הרשמי באתר war.gov נכתב 480 מייל לשעה"). Only where the OCR is illegible on that point may you use the summary's figure, saying that it comes from the official description. Contradictions inside the document itself are stated neutrally and left unresolved.
- **Neutral and serious.** Report what the document says ("לפי הדו"ח", "העד תיאר"), not whether UFOs are real. No hype, no exclamation marks, no rhetorical questions, no first person, no "מסמך מרתק".
- **Do not repeat the official summary.** Build on it. One sentence of overlap in the opening is fine.
- **Private individuals:** medical, financial, family or home-address details about a private person (a witness, a website owner, a resident) are described only in general terms ("המסמך כולל פרטים אישיים על בעל האתר"), never spelled out. This applies even when the document itself is unredacted.
- **Names:** people named in the document are written as they appear, in Hebrew transliteration with the Latin spelling once in parentheses for the main figures. Redacted names stay redacted ("שמו הושחר"), even when the same person is named elsewhere in the document (a DIRD whose title page has "AAP Person 70" but whose body says "the present author (G. Miley)"): use the pseudonym only. Pseudonym labels like "AAP Person 14" stay as they are.
- **Hebrew style:** natural, fluent Hebrew for an educated general reader, not translationese. Dates in words ("18 בינואר 1957"). Military times may stay as written (0614Z). Acronyms in English (FBI, AARO, DIA, BAASS, MUFON), explained once. UFO in prose is עב"ם / עב"מים; UAP is UAP or "תופעה אווירית לא מזוהה".
- **Dashes:** only a plain hyphen `-`. NEVER an em dash (—) or en dash (–), not even in ranges (1953-1955). Check your files for them before finishing.
- **Consistent terms** with the site: Department of War = משרד המלחמה; Air Force = חיל האוויר; AIIR = דו"ח מידע מודיעיני אווירי (AIIR); Flying Objects Report = דו"ח עצמים מעופפים; Air Defense Command = פיקוד ההגנה האווירית; DIA = סוכנות המודיעין הביטחוני; AAWSAP = תוכנית יישומי מערכות נשק תעופתיות-חלליות מתקדמות (AAWSAP); redaction = השחרה/מצונזר; Skinwalker Ranch = חוות סקינווקר.

## Before you finish
Re-read each file against the OCR once: every number, date and name in your text must be in the source. Check: no em/en dashes; every heading line starts with `### `; the file is not empty.

Work only in your batch's out_file paths; do not touch the repository (no edits, no git). Reply with just: the files written, the word count of each, and one line per judgment call you made (conflicts between OCR and summary, uncertain readings).
