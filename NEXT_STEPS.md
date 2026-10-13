# Where we left off — 13 Oct 2026

Pick up from here next session. Development lives in `backend/`, `frontend/`, `docs/`, `evaluation/`;
publication material lives in `publication/`. Everything below is committed on `main`.

## 1. Summary of what was done

**Repository and identity**
- Repo moved to `github.com/Vivan-23/DJSCE-Institutional-Brain` (private); `demo` branch deleted; work on `main` only.
- Rebranded to DJSCE Institutional Brain: `company.yaml` → `institution.yaml`; DB `djsce_brain_db`;
  containers `djsce_*`; Compose project `djsce-brain`.
- Legacy Company-Brain dataset and scripts removed; duplicated code cleaned up (shared date formatting,
  test helpers, Compose environment block).

**Product features**
- **Student role** with enforced access: students see only the Help Desk and public knowledge; every
  internal API refuses them (403). Role names in the UI: Student / Faculty / Committee Coordinator / System Administrator.
- **Visibility labels** (`internal` / `public`) on every indexed excerpt; student search is filtered inside
  the vector query and re-checked.
- **One evidence pipeline**: uploaded documents now feed citations and procedures, same as transcripts.
- **Cited answers**: the assistant lists its sources; ticket drafts too.
- **Student Help Desk**: quick questions, tickets with AI triage (category, priority, owning office), a staff
  queue with an AI draft plus sources, and a human sends the reply.
- **Knowledge graph fixed**: it had 0 links; now people attend meetings, documents and meetings mention
  committees and departments, and noisy entities are filtered out.
- **laya** added as an *optional* triage engine (pinned 0.3.21; the package is under four weeks old).

**Data**
- Synthetic committee records (4 meetings, 3 internal documents, fictional people).
- Mini-project content (60 Computer Engineering FAQs and the IT department overview), contact details removed.
- **26 authentic public files from djsce.ac.in** in `djsce_public_data/kb/`, each citing its source URL and
  retrieval date. An independent fact-check of 22 facts found no wrong values; the gaps it found were fixed.

**Bugs fixed along the way**: startup race on a fresh database; transcript header lines saved as staff
("Date", "Attendees"); Neo4j deadlock that dropped a meeting; transcripts ingested twice by the loader;
backend image build broken by a Debian mirror sync; FAQ answers split across chunks.

**Publication** (`publication/`)
- `00_project_brief/PROJECT_BRIEF.html` (+ `.md`): a standalone page for the guide.
- `01_ipd_report/REPORT_DRAFT.md`: follows the seniors' IPD report structure; results still `TBD`.
- `02_poster/POSTER_CONTENT.md`: AVINYA layout draft.
- `references/senior_samples/`: seniors' report and three posters.

## 2. Evaluation so far

**Run 1, baseline** (`publication/01_ipd_report/results/RESULTS_run1_baseline.md`), before the retrieval fixes:

| Measure | Result |
|---|---|
| Ticket triage accuracy, LLM / keyword / laya | 90.6% / 57.3% / 51.0% |
| Q&A: right source retrieved (top 5) | 100% |
| Q&A: answer correct | 71% |
| Student visibility leaks | 0 of 20 adversarial queries |
| Commitment extraction | 9 of 9 (precision and recall 100%) |

Takeaways: the LLM triage is clearly best, so the default stays `llm,keyword`. laya was less accurate
and took about 1.4 s per query on CPU. The weak answer score came from chunking and missing speaker
names; both are fixed since run 1.

**Run 2** was running when we stopped. If it finished, its results are in `publication/01_ipd_report/results/`
(`RESULTS.md`, `latest.json`). It used data loaded *before* the last fact-check corrections, so treat it as interim.

## 3. Next session — Claude's work

1. Check whether run 2 finished; then reload the corrected data and do the **final run 3**:
   ```bash
   docker compose down -v && docker compose up -d --build
   python ingest_institutional.py --approve
   docker compose --profile eval run --rm evaluator
   ```
2. Put the run 3 numbers into report §7 and the abstract, the poster "Results" box, and the brief's
   results section (`.md` and `.html`); keep run 1 as the before/after comparison.
3. Build per-department access (CE students see CE material), **once you approve it** (item 10 below).

## 4. Your work (only the team can do these)

**This week**
- [ ] **Rotate the Groq API key** at console.groq.com (an earlier key may have been exposed); put the new
      one in `.env`, never commit it, delete the old key.
- [ ] **Fill placeholders** in the brief and report: team names, SAP IDs / roll numbers, guide name,
      semester, IPD course number.
- [ ] **Meet the guide with `PROJECT_BRIEF.html`** and get:
  - [ ] written OK to use public djsce.ac.in content (see `djsce_public_data/README.md`)
  - [ ] confirmation that synthetic committee data plus public website data is acceptable
  - [ ] target numbers for the SMART objectives (report §4.2)
  - [ ] notes saved in `publication/05_meetings_with_guide/YYYY-MM-DD.md` (copy `TEMPLATE.md`)
- [ ] **Click through the demo once** (about 10 minutes): Student → Help Desk → raise a ticket → Faculty →
      Help Desk Queue → reply → Student sees it. All APIs are tested, but the new pages haven't been
      checked in a browser. Note anything that looks wrong.

**Report writing**
- [ ] Literature survey (§3): 15+ real papers on retrieval-augmented question answering, hallucination,
      meeting action-item extraction, access control in AI retrieval, ticket triage. Share links and
      Claude can summarise and format the references; Claude won't invent citations.
- [ ] Existing systems (§2.2): two or three real products per column of the comparison table, each with a source.
- [ ] Screenshots for report Figures 6.x and the poster → `publication/01_ipd_report/figures/`.
- [ ] Poster design (AVINYA template, college logos, team and guide names, QR code), using `POSTER_CONTENT.md`.

**Team**
- [ ] Add colleagues as collaborators on the private GitHub repo; rule: pull before working, small commits, `main` only.
- [ ] Decide: build **per-department access** next? (The roadmap's next item.)

## 5. How to run things

| Task | Command |
|---|---|
| Start everything | `docker compose up -d --build` |
| Load demo data | `python ingest_institutional.py --approve` |
| Open the app | http://localhost:3000 (all demo logins use `demo123`) |
| Demo logins | `admin@example.com` · `aditi.rao@example.com` (coordinator) · `karan.shah@example.com` (faculty) · `aarav.desai@example.com` (student) |
| Run evaluation | `docker compose --profile eval run --rm evaluator` |
| Backend tests | see `CLAUDE.md` (136 passing) |
| Remote demo | `./start_public_share.ps1` (ngrok) |
| Docs | `docs/ARCHITECTURE.md`, `docs/USAGE.md`, `evaluation/README.md` |
