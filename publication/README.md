# Publication workspace — DJSCE Institutional Brain

Everything for the **academic side** of the project lives here: the mentor brief, the
IPD report, the AVINYA poster, presentations, a research paper and meeting notes.
The **software** lives in the rest of the repository (`backend/`, `frontend/`,
`docs/`). Keep the two separate: nothing in this folder is imported or deployed.

| Folder | What goes in it | Status |
|---|---|---|
| [`00_project_brief/`](00_project_brief/) | One-document explanation of the project for the mentor/guide | ✅ first draft |
| [`01_ipd_report/`](01_ipd_report/) | IPD report, chapter by chapter, following the department format | 🟡 outline + draft content |
| [`02_poster/`](02_poster/) | AVINYA poster content (and the final PDF/PNG export) | 🟡 content draft |
| [`03_presentation/`](03_presentation/) | Review / viva slide decks | ⬜ not started |
| [`04_research_paper/`](04_research_paper/) | Conference/journal paper draft | ⬜ not started |
| [`05_meetings_with_guide/`](05_meetings_with_guide/) | Dated notes of every guide meeting, decisions and action items | ⬜ template only |
| [`references/`](references/) | Seniors' sample report and posters, papers we cite | ✅ samples added |

## Working rules for the team

1. **Write in Markdown first** (`.md`), so changes are reviewable in git diffs and pull
   requests. Convert to Word/PDF only for the final submission and commit that export
   next to its source (for example `01_ipd_report/IPD_Report_v1.pdf`).
2. **Never invent numbers.** Every metric in the report or poster must come from a
   run we can reproduce. Put `TBD` until then, and note where the number came from.
3. **Data is mixed: synthetic + public website.** Meetings, people and internal procedures
   are fictional — say so in every document and never present them as official DJSCE records.
   Public knowledge in `djsce_public_data/` is authentic information published on https://www.djsce.ac.in;
   cite it by URL and retrieval date, call it "published on the public website" (not official
   policy), and acknowledge use of public website content.
4. **Figures** go in `01_ipd_report/figures/` with a source file (diagram code,
   screenshot date) so anyone can regenerate them.
5. **Pull before you write, commit small, push often.** One topic per commit, for
   example `report: draft chapter 4 problem formulation`.
6. Keep binary files (PDF/PPTX/images) small; large raw recordings belong in a
   shared drive, with only the link committed here.

## Reference samples from seniors

`references/senior_samples/` holds the structure we follow:

- `AgriScan_IPD3_Report_Sem5.pdf` — a complete IPD-III report (front matter + 9 chapters).
- `poster_avinya2026_*.jpeg` — three AVINYA 2026 posters (Introduction · Contributions ·
  Architecture · Workflow · Results · Conclusion/Future scope · team, guide, QR to GitHub).

These belong to their authors and are kept only as format references; this repository
is private. Do not copy their text.
