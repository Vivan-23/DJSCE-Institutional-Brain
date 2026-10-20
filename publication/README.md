# Publication workspace — DJSCE Institutional Brain

Everything for the **academic side** of the project lives here: the mentor brief, the
IPD report, the AVINYA poster, presentations, a research paper and meeting notes.
The **software** lives in the rest of the repository (`backend/`, `frontend/`,
`docs/`). Keep the two separate: nothing in this folder is imported or deployed.

| Folder | What goes in it | Status |
|---|---|---|
| [`00_project_brief/`](00_project_brief/) | One-document explanation of the project for the mentor/guide | ✅ updated with final results |
| [`01_ipd_report/`](01_ipd_report/) | IPD report, chapter by chapter, following the department format | ✅ final draft: **`IPD_Report_final.pdf`** (43 pages, typeset from `IPD_Report_final.html`), plus `REPORT_DRAFT.md` + `IPD_Report_final_draft.docx`, 16 figures, 20 verified references |
| [`02_poster/`](02_poster/) | AVINYA poster content (and the final PDF/PNG export) | ✅ final content; visual layout to do |
| [`03_presentation/`](03_presentation/) | Review / viva slide decks | 🟡 12-slide outline + demo script; deck to build |
| [`04_research_paper/`](04_research_paper/) | Conference/journal paper draft | 🟡 structured draft with results |
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

## What only the team can finish

- Names, SAP IDs, guide, course number and academic year (every `⟨…⟩` placeholder).
- Certificate, approval and declaration pages with signatures.
- Two or three real products per column of the existing-systems table (report §2.2), each with a source.
- Guide's confirmation of the objective targets (report §4.2) and written OK to use public djsce.ac.in content.
- Poster visual layout (AVINYA template, logos, QR) and the slide deck itself.

Numbers come from `01_ipd_report/results/RESULTS.md` (final run 19 Oct 2026). If you rerun the evaluation,
update the report, poster, slides, paper and brief together, then re-export the Word file with
`python evaluation/publication_tools/export_report_docx.py`.

## Reference samples from seniors

`references/senior_samples/` holds the structure we follow:

- `AgriScan_IPD3_Report_Sem5.pdf` — a complete IPD-III report (front matter + 9 chapters).
- `poster_avinya2026_*.jpeg` — three AVINYA 2026 posters (Introduction · Contributions ·
  Architecture · Workflow · Results · Conclusion/Future scope · team, guide, QR to GitHub).

These belong to their authors and are kept only as format references; this repository
is private. Do not copy their text.
