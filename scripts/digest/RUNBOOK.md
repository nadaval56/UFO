# Runbook: one scheduled batch of extended Hebrew summaries

This is what a scheduled session does, start to finish, with no one watching. The repository owner approved the whole flow on 2026-10-25, **including merging each batch's PR into `main` yourself** once the checks below pass. Background and decisions: the 2026-10-25 entries in `CLAUDE.md`.

The scheduled prompt names a **mode**:
- `day`: one cycle with a budget of 1,700,000 OCR characters (the owner doubled it after the first run: 850,000 measured at ~12% of a 5-hour window).
- `night`: repeat cycles of 1,700,000 until it is 05:30 in Israel (`TZ=Asia/Jerusalem date +%H%M` is 0530 or later) or a cycle hits the usage limit.

## 0. Setup

- Work in the repository checkout (clone `https://github.com/nadaval56/UFO` if it isn't there). `git fetch origin main`, then start your branch from `origin/main`. Use the branch your session was told to develop on; if none, `digest/<UTC timestamp>`.
- Pick a scratch directory, `WORK`, outside the repository.
- `python3 scripts/digest/plan_batch.py --status` and note the "done" count.

## 1. Plan

`python3 scripts/digest/plan_batch.py --budget 1700000 --work "$WORK/cycle<N>"` writes `plan.json`.
- If it prints that the queue is empty: the project is finished. Disable every scheduled task whose name starts with `PURSUE digest` (`update_trigger` with `enabled: false`), say so in your final message, and stop.

## 2. Run the agent tasks (in parallel)

For each entry of `plan.json` `tasks`, write its JSON to `$WORK/cycle<N>/task<k>.json` and launch one `general-purpose` agent, all of them in a single message so they run concurrently:
- `kind: docs`: the task file holds `records` (each with `ocr_file` and `out_file`). Prompt: "Read `<repo>/scripts/digest/BRIEF.md` and follow it exactly. Your batch file: `<task file>`. Write the Hebrew yourself (do not call any API)."
- `kind: part`: the task file holds one part (`record`, `part`, `of`, `part_file`, `notes_file`). Prompt: "Read `<repo>/scripts/digest/BRIEF.md`, then `<repo>/scripts/digest/PART_BRIEF.md`, and follow them. Your task file: `<task file>`. Write the Hebrew yourself (do not call any API)."

Wait for all of them. Then, for each entry of `merges`, write it to `$WORK/cycle<N>/merge<k>.json` and launch one agent (again all at once): "Read `<repo>/scripts/digest/BRIEF.md`, then `<repo>/scripts/digest/MERGE_BRIEF.md`, and follow them. Your task file: `<merge file>`. Write the Hebrew yourself (do not call any API)." Skip a merge whose notes files are not all present.

If agents fail because the usage limit was reached, stop launching new ones and go straight to step 3 with whatever was written.

## 3. Validate

`python3 scripts/digest/check.py "$WORK"/cycle<N>/digest/*.md`
- For each FAIL, launch one agent to fix that file in place, giving it the error line and the path to `BRIEF.md`; re-check. A file still failing after one fix is left out of this batch (its document stays pending and is retried by a later run).
- Read two of the summaries yourself, start to finish. If one is wrong in a way the checker cannot see (not about the document, invented facts, translationese, English left in), leave it out too and say so in your final message.

## 4. Publish

1. Copy the passing files into `data/digest/`.
2. `python3 scripts/build_sitemap.py` (rebuilds `doc/*.html`, `archive.html`, `sitemap.xml`, `feed.xml`, `llms.txt`).
3. Commit everything with a message like `Extended summaries: <n> documents (<first ids>...)`, push, open a PR to `main` (not a draft), and merge it (squash). No PR template is needed.
4. If the merge is refused because `main` moved (another batch landed first): `git fetch origin main`, reset your branch to `origin/main`, copy your digest files in again, rebuild, commit, force-push your own branch, and merge. Try at most three times.

Never edit anything except `data/digest/` and the files `build_sitemap.py` generates. Never touch another batch's digest files.

## 5. Next cycle or finish

- `night` mode: if it is still before 05:30 in Israel and nothing hit the usage limit, go back to step 1 with `cycle<N+1>`, starting from a fresh `origin/main`.
- Otherwise finish. Final message: the documents published (count and ids), any left out and why, and the new `plan_batch.py --status` line.
