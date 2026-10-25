# Brief: notes on one part of a long document (step 1 of 2)

> Used by `RUNBOOK.md` for documents too long for one agent. Read `BRIEF.md` first: its rules on faithfulness, names, redactions, Hebrew style, terms and dashes all apply here.

The document was split into consecutive parts; you get **one** part (`part_file`, "part N of M") plus the record's metadata and official summary. A later merge step writes the final summary from the notes of all parts, without reading the OCR again, so **your notes are its only source**: anything you leave out is lost.

## Output
Write `notes_file` (UTF-8), in Hebrew, in the same tiny format as the final summary (`### ` headings, `- ` lists, paragraphs; no other Markdown). Target 600-1,200 words for a ~100,000-character part; less if the part is thin (forms, tables, noise).

## Content
1. `### מבנה החלק` - what this part contains, in order: which reports, letters, enclosures, tables, appendices; where each begins (quote its own title or heading); and anything that clearly continues from the previous part or into the next.
2. `### תוכן` - the substance, item by item in document order: dates, times, places, units, people (as written, with Latin spelling once for main figures), numbers, descriptions (short translated quotes), findings, conclusions, recommendations, who signed or forwarded what.
3. `### הערות קריאה` - redactions, illegible stretches, uncertain readings (with the reading you chose), and contradictions inside the part or with the official summary.

No opening paragraph is needed and no `פרטים בולטים`: these are working notes, not a page. Don't summarise the whole document from the official summary; describe only what is in **your** part.

Reply with just: the file written, its word count, and one line per judgment call.
