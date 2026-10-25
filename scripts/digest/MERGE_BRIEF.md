# Brief: final summary from part notes (step 2 of 2)

> Used by `RUNBOOK.md` for documents that were split into parts. Read `BRIEF.md` first: the output format, structure, length table and all rules there apply unchanged.

You get the record's metadata and official summary, and `notes_files`: the Hebrew notes written by other agents on each consecutive part of the document, in order. Write the final extended summary to `out_file`, exactly as `BRIEF.md` describes, **from the notes and the official summary only**. Do not read the OCR.

- The notes are in part order, not necessarily in topic order. Organise the summary around the document's own structure (its reports, sections, enclosures), merging items that continue across a part boundary.
- Use the length row of `BRIEF.md` for the whole document's size (`ocr_chars`).
- Carry over every uncertain-reading mark and every contradiction the notes record. Don't resolve what the notes left open, and don't add facts that are in neither the notes nor the official summary.
- `### מה לא נמצא במסמך` draws on all the notes' `הערות קריאה` sections.

Reply with just: the file written, its word count, and one line per judgment call.
