# DJSCE Institutional Brain — IPD Report (final draft)

> Structure follows the department's IPD report format (`../references/senior_samples/AgriScan_IPD3_Report_Sem5.pdf`).
> Only `⟨…⟩` placeholders remain: team, guide, course and signature details, which the team must fill.
> Every number in this report comes from the evaluation run recorded in `results/RESULTS.md`
> (19 Oct 2026, 14:55 UTC, model `openai/gpt-oss-120b`) or from the repository at commit time; nothing is estimated.
> **Data disclaimer (repeat in the printed report):** committee meetings, people, commitments and internal
> procedures are synthetic and are not official DJSCE records or policy. Public knowledge is authentic
> information published on https://www.djsce.ac.in, cited per file by URL and retrieval date (13 Oct 2026).

---

## Front matter

1. **Title page.** *DJSCE Institutional Brain: An Evidence-Grounded, Access-Aware Knowledge and Help-Desk
   Platform for Colleges.* "Submitted in partial fulfilment of the requirements of the course Innovative
   Product Development-⟨N⟩, Year ⟨Y⟩, Sem ⟨S⟩, Computer Engineering." Team names and SAP IDs ⟨…⟩; guide
   ⟨name, designation⟩; Dwarkadas J. Sanghvi College of Engineering, University of Mumbai, ⟨academic year⟩.
2. **Certificate** signed by the internal guide, Head of Department and Principal.
3. **Project report approval** with two examiner lines, date and place.
4. **Declaration** of academic integrity, signed by each member.
5. **Acknowledgement** of the guide, the department, and the use of public content from djsce.ac.in.
6. **Abstract**, **Contents**, **List of Figures**, **List of Tables**, **List of Abbreviations** (below).

### Abstract

Colleges take most operational decisions in committee meetings and keep their procedures in scattered
circulars. Action items go untracked, procedures are re-learned every cycle, and students depend on office
visits for routine information. General-purpose chatbots are a poor fit: they cannot cite institutional
sources, may invent policy, and ignore who is allowed to see what. This report presents *DJSCE
Institutional Brain*, a web platform that ingests meeting transcripts and documents, uses a large language
model (LLM) to extract decisions, owner-assigned commitments and step-by-step procedures, and routes every AI
output through human review. All knowledge is stored as citable evidence fragments labelled *internal* or
*public* and tagged with a department; student retrieval is restricted to public evidence inside the vector
query and re-checked afterwards. Students use a Help Desk that answers from public information and
escalates unresolved questions as tickets, which an LLM classifier triages (with a deterministic keyword
fallback) and faculty answer from an AI-drafted, cited reply. The system is built with FastAPI, Next.js,
PostgreSQL, ChromaDB, Neo4j and Celery, deployed with Docker Compose, and covered by 235 automated
backend tests. On synthetic committee records combined with authentic public website content, the LLM
triage reached 90.6 % accuracy against 57.3 % for the keyword baseline; the assistant
retrieved a correct source in the top five for 100 % of 33 questions and answered 91 %
correctly; commitment extraction scored precision 1.00 and recall 1.00; and adversarial
tests found 0 visibility leaks in 20 student queries and 0 department leaks in
10.

**Keywords:** retrieval-augmented generation, access control, meeting action items, help desk, human-in-the-loop.

### List of abbreviations

| Abbr. | Expansion |
|---|---|
| AI | Artificial Intelligence |
| API | Application Programming Interface |
| CE / IT | Computer Engineering / Information Technology (departments) |
| IQAC | Internal Quality Assurance Cell |
| JWT | JSON Web Token |
| KB | Knowledge Base |
| LLM | Large Language Model |
| NBA / NAAC | National Board of Accreditation / National Assessment and Accreditation Council |
| NER | Named-Entity Recognition |
| RAG | Retrieval-Augmented Generation |
| RBAC | Role-Based Access Control |
| SOP | Standard Operating Procedure |

### List of figures

| No. | Title | File (`figures/`) |
|---|---|---|
| 5.1 | Layered system architecture | `fig5_1_architecture.png` |
| 5.2 | Evidence pipeline and access-aware retrieval | `fig5_2_evidence_pipeline.png` |
| 5.3 | Help-desk sequence (student → triage → faculty reply) | `fig5_3_helpdesk_sequence.png` |
| 5.4 | Procedure (skill) lifecycle | `fig5_4_skill_lifecycle.png` |
| 6.1 | Sign-in page with demo-prototype notice | `fig6_01_login.png` |
| 6.2 | Student Help Desk | `fig6_02_student_helpdesk.png` |
| 6.3 | Student answer from public information, with sources | `fig6_03_student_answer.png` |
| 6.4 | Staff overview: insights and upcoming commitments | `fig6_04_overview.png` |
| 6.5 | My Work: commitment with progress and due date | `fig6_05_my_work.png` |
| 6.6 | Ticket review: AI triage and unsent AI draft | `fig6_06_ticket_review.png` |
| 6.7 | Procedure with owner, review date and steps | `fig6_07_procedure_evidence.png` |
| 6.8 | Meetings list | `fig6_08_meetings.png` |
| 6.9 | Knowledge graph | `fig6_09_knowledge_graph.png` |
| 6.10 | Analytics | `fig6_10_analytics.png` |
| 6.11 | Staff assistant answer with citations | `fig6_11_assistant_cited.png` |
| 7.1 | Triage accuracy by engine | `fig7_1_triage.png` |

---

## 1. Introduction

Indian engineering colleges are run through committees: the Academic Council, Boards of Studies, the IQAC,
the Examination Cell, the Training and Placement Cell and department committees. Each meeting produces
decisions ("the elective is approved for 60 students") and commitments ("Prof. X will circulate the rubric
by Friday"). These are written as free-text minutes, stored as files and rarely tracked. Procedures such as
revaluation or equipment-breakage recovery live in circulars and in the memory of a few staff members, so
they are re-learned every academic cycle. Students, meanwhile, ask the same routine questions at office
counters, and their queries leave no record.

Large language models can now read transcripts and documents and answer questions about them. An
institution, however, cannot simply put a chatbot in front of its records. Answers must be traceable to a
source, AI output that becomes policy must be reviewed by a person, and a student must never see internal
discussion. This project builds a platform around those three requirements: **evidence first, a human in
the loop, and access control enforced inside retrieval.**

*DJSCE Institutional Brain* turns meetings and documents into structured, cited knowledge (decisions,
accountable commitments, reviewed procedures), serves it to staff through an assistant and dashboards, and
serves students through a Help Desk that answers only from public information and escalates the rest to
faculty as tracked tickets.

The report is organised as follows. Chapter 2 explains the need and compares existing systems. Chapter 3
surveys the literature. Chapter 4 formulates the problem and objectives. Chapter 5 describes the design,
Chapter 6 the implementation, and Chapter 7 the evaluation. Chapter 8 concludes.

## 2. Need of the Product

### 2.1 Introduction and need

| Stakeholder | Current pain | What the product gives them |
|---|---|---|
| Committee coordinators | Action items from meetings are forgotten; follow-up is manual | Commitments extracted with owner and due date; overdue alerts; confirm or send back completed work |
| Faculty | Re-learn procedures; repeat answers to students | Cited procedures; AI-drafted ticket replies they edit and send; end-of-day check-in updates tasks |
| Students | Office visits for routine questions; no record of queries | Instant answers from public department information; tickets routed to the right office |
| IQAC / accreditation | Evidence for decisions scattered across files | Every decision and procedure linked to its source excerpt; audit log; minutes export |

### 2.2 Analysis of existing systems

| Criterion | College ERP / LMS | Generic chatbot | Enterprise search / RAG demo | **Institutional Brain** |
|---|---|---|---|---|
| Captures meeting decisions and commitments | ✗ | ✗ | ✗ | ✓ owners and due dates |
| Answers cite institutional sources | ✗ | ✗ | partial | ✓ every answer |
| Human review before AI output is published | n/a | ✗ | ✗ | ✓ procedures, ticket replies |
| Role-aware retrieval (students vs staff) | role-based pages | ✗ | rarely | ✓ inside the vector query |
| Student query tracking | partial | ✗ | ✗ | ✓ tickets with routing |
| Detects outdated procedures | ✗ | ✗ | ✗ | ✓ contradiction → stale |

⟨Team: name two or three real products per column with a source each, for example the college's ERP/LMS,
a general chatbot, and a commercial enterprise-search product.⟩

Generic chatbots answer fluently but without institutional grounding, and they hallucinate [8], [9].
RAG systems ground answers in retrieved text [1], [2], but typical deployments retrieve from a single
shared index and so do not distinguish what a student may see from what staff may see; recent work shows
that RAG can leak the private documents it retrieves from [12]. ERPs record transactions, not the
reasoning and commitments made in meetings.

### 2.3 Applications

Committee secretariats (minutes → tracked commitments), department offices and the Examination Cell
(procedures and student queries), IQAC and accreditation preparation (decision evidence with sources), and
a student help desk. The system is configured per institution through one file (`institution.yaml`:
branding, departments, help-desk categories and offices, members, academic calendar), so it can be
adopted by another college without code changes.

## 3. Survey

### 3.1 Literature survey

**Retrieval-augmented generation and grounding.** Lewis et al. [1] introduced RAG, combining a
pre-trained generator with a dense index retrieved at inference time, and showed more specific and
factual output than a parametric-only model. Gao et al. [2] survey the design space (naive, advanced and
modular RAG) and identify retrieval quality and evaluation as open problems. Dense passage retrieval [3]
and sentence embeddings [4] made semantic retrieval practical; our system uses the BGE family of
embedding models [5].

**Citations and evaluation.** Gao, Yen, Yu and Chen [6] built ALCE, a benchmark for answers with
citations, and found that even strong models lacked full citation support about half the time on ELI5.
RAGAs [7] separates retrieval quality, faithfulness and answer relevance. We adopt the same separation:
we measure whether the right source was retrieved separately from whether the answer is correct.

**Hallucination.** Ji et al. [8] and Huang et al. [9] survey hallucination in generation and in LLMs;
both list retrieval grounding and human verification among the main mitigations. This motivates our rule
that no AI output becomes a procedure or reaches a student without a person approving it.

**Meeting information extraction.** Purver et al. [10] detect action items in multi-party meetings by
modelling the dialogue structure in which tasks are proposed and agreed, then summarise each task. QMSum
[11] frames meeting understanding as query-focused summarisation. We use an LLM with a constrained JSON
schema to extract decisions and commitments (owner, task, due date) from speaker-attributed transcripts.

**Access control and RAG security.** Role-based access control [14] assigns permissions to roles rather
than individuals; we use four ranked roles. Zeng et al. [12] show empirically that RAG systems can leak
their retrieval database, and Greshake et al. [13] show that retrieved content can carry indirect prompt
injection. We therefore filter by visibility and department *inside* the vector query, re-check every hit,
and keep AI drafts and triage fields away from students.

**Ticket triage.** Revina et al. [15] find that well-chosen simple features can match complex models for
IT ticket classification, and Zangari et al. [16] survey ticket automation and multi-level
classification. We compare an LLM classifier with a keyword baseline and a small non-generative
classifier (laya), and use the keyword classifier as a deterministic fallback.

**Knowledge graphs.** Hogan et al. [17] survey graph data models and knowledge extraction; GraphRAG [18]
builds an entity graph to answer corpus-wide questions. We use a lighter graph (people, committees,
meetings, documents) for navigation rather than for answer generation.

**Chatbots in education.** Systematic reviews by Okonkwo and Ade-Ibijola [19] and Wollny et al. [20] find
chatbots useful for routine student support, but point to weak evaluation and limited integration with
institutional processes. Our Help Desk is evaluated on a labelled set and is tied to staff workflows.

### 3.2 Outcome of the survey

What works: RAG with explicit citations, structured extraction from dialogue, and simple, robust
classifiers. What is missing in existing tools for colleges: (1) access-aware retrieval where students and
staff search different evidence, (2) accountability for commitments made in meetings, and (3) human review
built into the workflow. These three gaps define our design (Chapter 4.3).

## 4. Problem Formulation

### 4.1 Problem statement

*To design and implement a platform that converts a college's meeting transcripts and documents into
structured, citable institutional knowledge (decisions, accountable commitments and reviewed procedures)
and serves it to staff and students through grounded, role-restricted AI assistance with human oversight.*

### 4.2 Product objectives

Targets below were set by the team from the baseline run (run 1, 13 Oct 2026); ⟨confirm with guide⟩.

| # | Objective | Target | Result (19 Oct 2026, 14:55 UTC) |
|---|---|---|---|
| 1 | Extract commitments from transcripts | precision ≥ 0.80, recall ≥ 0.80 | P 1.00, R 1.00 |
| 2 | Retrieve a correct source for questions | hit@5 ≥ 90 % | 100 % |
| 3 | Answer questions correctly from sources | ≥ 80 % | 91 % |
| 4 | No internal evidence reaches students | 0 leaks on adversarial set | 0 / 20 |
| 5 | No cross-department leaks for students | 0 leaks | 0 / 10 |
| 6 | Route tickets correctly | LLM accuracy ≥ 85 %, above keyword baseline | 90.6 % vs 57.3 % |
| 7 | Responsive answers | p95 answer latency ≤ 10 s | 10.0 s |

### 4.3 Novelty

1. **Evidence first.** Every answer, procedure and ticket draft carries the excerpts it came from.
2. **Human in the loop by design.** Procedures start as drafts that a coordinator approves; ticket replies
   are written by faculty from an AI draft that the student never sees.
3. **Access-aware retrieval.** Visibility and department are stored on each fragment, filtered in the
   vector query, and re-checked on every hit.
4. **Meetings → accountability.** Commitments get owners, due dates, progress, blockers and a
   coordinator confirmation step; a conversational check-in updates them.
5. **Constrained triage with a deterministic fallback.** The LLM may only choose configured categories;
   otherwise the keyword classifier decides.
6. **Freshness.** New evidence that contradicts an approved procedure marks it *stale* for re-review.

### 4.4 Scope

In scope: transcript and document ingestion (.txt, .pdf, .docx), decision and commitment extraction,
procedures with versions and review dates, cited Q&A, student Help Desk with tickets, notices filtered by
department, year, semester and division, academic calendar, knowledge graph, analytics, audit log, minutes
export (DOCX/PDF), four roles and per-department scope. Out of scope: live meeting recording, ERP
integration, and real internal records or personal data. Public knowledge is a snapshot of public pages of
https://www.djsce.ac.in retrieved on 13 Oct 2026, without personal contact data.

## 5. Proposed Design

### 5.1 Approach selection

| Need | Choice | Alternatives considered and why not |
|---|---|---|
| Language understanding and generation | Hosted LLM (`openai/gpt-oss-120b` via Groq), JSON-constrained prompts | Fine-tuning needs labelled institutional data we do not have; a local LLM needs a GPU the demo machine lacks |
| Retrieval | Dense embeddings `BAAI/bge-large-en-v1.5` [5] in ChromaDB, cosine similarity | BM25 misses paraphrases ("re-checking" vs "revaluation"); a hosted vector DB adds cost and moves data off-site |
| Metadata and workflow | PostgreSQL with Alembic migrations | Document stores make relational workflows (owners, versions, tickets) harder |
| Entity relations | spaCy NER → Neo4j | Building the graph with an LLM costs more tokens with no gain for navigation |
| Triage | LLM restricted to configured categories → keyword fallback; laya compared | LLM alone fails when the API is unavailable; keyword alone is inaccurate (Table 7.3) |
| Background work | Celery + Redis (ingestion, scans, reminders) | Doing ingestion inside the request blocks the UI for tens of seconds |

### 5.2 System architecture

Figure 5.1 shows five layers: sources, processing services, the evidence layer, access-aware retrieval,
and the web application with human review. Figure 5.2 details the evidence pipeline: every transcript
turn or document chunk becomes a `Fragment` with `visibility` (internal/public) and `department`, stored
in PostgreSQL and mirrored with the same metadata in ChromaDB, with entities sent to Neo4j. Figure 5.3
shows the help-desk sequence, and Figure 5.4 the procedure lifecycle.

**Table 5.1 Roles and permissions** (enforced in the API; the UI only hides what the API already refuses)

| Capability | Student | Faculty | Committee Coordinator | System Administrator |
|---|---|---|---|---|
| Help Desk answers (public knowledge only) | ✓ | ✓ | ✓ | ✓ |
| Raise tickets, see own tickets | ✓ | ✓ | ✓ | ✓ |
| Read notices addressed to them | ✓ | ✓ | ✓ | ✓ |
| Staff assistant over internal evidence | ✗ | own dept + institution-wide | all | all |
| Ticket queue, AI draft, reply | ✗ | ✓ | ✓ | ✓ |
| My Work, Faculty Desk check-in | ✗ | ✓ | ✓ | ✓ |
| Approve/reject/retire procedures, extract | ✗ | ✗ | ✓ | ✓ |
| Analytics, assign tasks, confirm completion | ✗ | ✗ | ✓ | ✓ |
| Manage users and roles | ✗ | ✗ | ✗ | ✓ |

### 5.3 Data model

**Table 5.2 Main tables** (`backend/app/models/structured.py`; 17 tables, lists stored as JSON strings)

| Table | Purpose |
|---|---|
| User | Login, role, department, year/semester/division for students |
| Employee | Staff directory (seeded from `institution.yaml`) |
| Meeting | Title, date, summary, decisions, participants, raw transcript, department |
| Fragment | One citable excerpt: text, source, speaker, `visibility`, `department` (mirrored in ChromaDB) |
| Commitment, CommitmentUpdate | Task, owner, due date, status, progress, blocker; history of updates |
| CheckIn | Faculty end-of-day conversation and the task updates it produced |
| Skill, SkillVersion, SkillCitation | Procedure (steps, rules, owner office, review date, status), its versions, and cited fragments |
| Ticket | Student query, triage (category, priority, office, engine), AI draft and sources, human reply |
| Notice, NoticeRecipient | Notices with audience filters and read receipts |
| ActiveInsight | Deadline, risk and bottleneck alerts on the overview |
| QueryLog | Questions asked (for analytics and knowledge gaps) |
| AuditLog | Who did what and when |
| Document, ProgressReport | Uploaded document records; generated progress reports |

## 6. Implementation

### 6.1 Backend services

The backend is FastAPI (`backend/app`). Routers in `api/v1/` (17 routers) stay thin; logic lives in
module-level services in `services/` (24 modules). The main services:

- **transcript_service / extraction_service** parse speaker turns, create fragments, and call the LLM
  with a JSON schema for summary, decisions and commitments; owners are matched to staff.
- **fragment_service** is the only writer to the evidence store: a PostgreSQL row plus a ChromaDB vector
  with the same visibility and department.
- **parser** splits documents into chunks of up to 800 characters with 150-character overlap, keeping
  question–answer pairs together.
- **skill_service / procedure_service** synthesise procedures from internal fragments, keep versions,
  owner office and review dates, write student summaries, and export DOCX/PDF and a handbook.
- **freshness_service** scans new evidence for contradictions with approved procedures and marks them
  stale with the reason and evidence.
- **rag_service** retrieves the top 5 fragments plus up to 2 approved procedures, filtered by role and
  department, and asks the LLM (temperature 0.2) for an answer with numbered citations.
- **ticket_service** triages tickets (LLM → keyword), routes them to the configured office, and drafts a
  cited reply for staff.
- **commitment_service / pa_service** handle progress, blockers, confirmation, follow-up messages and the
  end-of-day check-in that turns plain-language updates into task changes.
- **graph_service / ner_service** build Employee, Project, Document and Meeting nodes with MENTIONS and
  ATTENDED edges; people are added only with supporting evidence.
- **notice_service, calendar_service, analytics_service, audit_service, user_service** provide notices,
  reminders, dashboards, the audit trail and user administration.

Background jobs (Celery beat, `core/celery.py`): the daily 08:00 insight sweep, the faculty check-in at a
configured hour, an hourly follow-up scan for stale or overdue commitments, procedure extraction at 03:00,
the freshness scan at 04:00, and reminders for academic dates and commitments due within three days.
Ingestion endpoints return 202 and enqueue work.

### 6.2 Access control

Users have one of four ranked roles (`student < employee < manager < admin`). Internal routes depend on
`require_staff`; elevated actions on `require_role("manager")`. Self-registration creates students only.
Retrieval applies the policy twice:

```text
ALGORITHM AnswerQuestion(question, user)
  public_only ← (user.role = student)
  depts ← {user.department, "all"}  unless user.role ≥ manager
  filter ← {visibility = public if public_only} ∧ {department ∈ depts if depts}
  hits ← VectorSearch(embed(question), k = 5, where = filter)
         ∪ VectorSearch(procedures, k = 2, where = filter)
  hits ← [h ∈ hits | (¬public_only ∨ h.visibility = public) ∧ (no depts ∨ h.department ∈ depts)]
  answer ← LLM(rules + numbered hits, question)
  RETURN answer, hits                 # sources always returned with the answer
```

```text
ALGORITHM TriageTicket(subject, description)
  r ← LLMClassify(text, allowed = categories from institution.yaml)
  IF r invalid OR r.category ∉ allowed:  r ← KeywordClassify(text)
  ticket.routed_to ← office(r.category);  ticket.priority ← r.priority
  ticket.ai_draft, ticket.ai_sources ← AnswerQuestion(text, staff)   # never returned to students
```

Students receive 404 for other people's tickets and never receive `ai_*` fields.

### 6.3 Frontend

Next.js 16 / React 19 with Tailwind CSS (`frontend/src`). Students see the Help Desk, Assistant, Notices
and Calendar; staff additionally see Overview, My Work, Faculty Desk, Ticket Queue, Meetings, Procedures,
Documents and Knowledge Graph; coordinators see Analytics; administrators see Users. All API calls go
through one helper, and `/api/*` is proxied to the backend. Figures 6.1–6.11 show the main screens.
A persistent banner states that the system is a demonstration prototype.

### 6.4 Deployment

Docker Compose runs eight services: PostgreSQL, ChromaDB, Redis, the backend, a Celery worker, Celery
beat, the frontend, and an on-demand evaluator. Startup runs `alembic upgrade head`, so data survives
rebuilds. Health checks gate start order. A tunnelling script exposes the demo for remote review.

### 6.5 Testing

235 backend tests in 26 test modules run with SQLite and mocked LLM, ChromaDB and Neo4j. They cover
authentication and roles, student access (every internal route refuses students), department scope,
transcripts and extraction, commitments and My Work, the Faculty Desk, procedures (versions, approval,
rejection, retirement, export), freshness, help desk, notices, calendar, analytics, admin users, graph,
audit, insights, parsing and date parsing, and a test that fails if models and migrations drift. The
frontend is checked by ESLint and the TypeScript compiler in CI.

## 7. Experimentation and Results

### 7.1 Datasets

**Table 7.1 Datasets** (all labels written by the team; `evaluation/data/`)

| Set | Contents | Size |
|---|---|---|
| Committee transcripts | synthetic: Academic Council, IQAC, departmental lab readiness, placement planning (+1 demo minutes file for the live upload) | 4 (+1) |
| Internal documents | synthetic proposals, guidelines and SOPs | 3 documents + 3 SOPs |
| Public knowledge (mini-project) | CE department FAQs, IT department overview | 2 documents |
| Public website knowledge base | authentic content from https://www.djsce.ac.in, each file cited by URL, retrieved 13 Oct 2026 | 26 files |
| Triage set | labelled student queries, 6 categories, urgency labels | 96 |
| Q&A set | questions with gold sources and answer keywords | 33 |
| Visibility set | adversarial student questions about internal content | 20 |
| Department set | CE/IT students asking about the other department | 10 |
| Commitments gold set | hand-labelled commitments in the transcripts | 9 |

### 7.2 Test cases

**Table 7.2 Functional test cases** (each automated in `backend/tests/`, all passing)

| ID | Feature | Case | Expected | Result |
|---|---|---|---|---|
| T1 | Access | Student calls any internal route | 403 | Pass |
| T2 | Access | Student opens another student's ticket | 404, no `ai_*` fields | Pass |
| T3 | Visibility | Student question whose best match is internal | only public sources returned | Pass |
| T4 | Department | CE faculty retrieves IT-only fragment | not returned | Pass |
| T5 | Transcripts | Submit an empty transcript | 400, nothing queued | Pass |
| T6 | Extraction | Transcript with "I will … by Friday" | commitment with owner and due date | Pass |
| T7 | My Work | Owner marks task done | status *review*, coordinator confirms or sends back | Pass |
| T8 | Procedures | Approve, edit, reject with reason, retire | versions kept, reason stored | Pass |
| T9 | Freshness | New fragment contradicts approved procedure | procedure marked stale with evidence | Pass |
| T10 | Help desk | LLM unavailable | keyword triage used, ticket still routed | Pass |
| T11 | Notices | Notice to TE CE division A | only matching students receive it | Pass |
| T12 | Admin | Non-admin opens user management; deactivated user logs in | refused; login and old token rejected | Pass |
| T13 | Migrations | Models changed without migration | test fails | Pass |

The role-access matrix in Table 5.1 is covered by `test_student_access.py`, `test_departments.py` and
`test_admin_users.py`.

### 7.3 Parameter choices

No large parameter sweep was run (the LLM API has a daily token quota). Parameters were chosen once and
changed only when the baseline run (run 1) exposed a specific failure:

| Parameter | Value | Reason |
|---|---|---|
| Chunk size / overlap | 800 / 150 characters, paragraph-aware | Run 1 split FAQ answers from their questions; chunks now keep Q–A pairs together |
| Retrieval depth | top 5 fragments + up to 2 approved procedures | Approved procedures should outrank meeting discussion when equally relevant |
| Answer temperature | 0.2 | Factual answers; 0.6 only for the conversational check-in |
| Classification temperature | 0.1, JSON output | Stable labels |
| Speaker names in fragments | included | Run 1 missed "who decided" questions without them |
| LLM | `openai/gpt-oss-120b` (Groq) | Large open-weight model with JSON output, available on Groq's free tier |

### 7.4 Results

All results are from `results/RESULTS.md` (19 Oct 2026, 14:55 UTC). Run 1 (13 Oct 2026,
`results/RESULTS_run1_baseline.md`) is shown for comparison.

**Table 7.3 Help-desk triage (96 queries, 6 categories)**

| Engine | Coverage | Accuracy | Macro-F1 | Urgency F1 | p50 latency (s) | p95 latency (s) |
|---|---|---|---|---|---|---|
| keyword | 100% | 57.3% | 0.586 | 0.533 | 0.0 | 0.0 |
| llm | 100% | 90.6% | 0.907 | 1.000 | 2.489 | 4.53 |
| laya | 67% | 51.0% | 0.563 | 0.533 | 1.387 | 1.923 |
| llm→keyword | 100% | 90.6% | 0.907 | 1.000 | 2.489 | 4.53 |
| laya→keyword | 100% | 68.8% | 0.684 | 0.533 | 1.387 | 1.923 |
| laya→llm→keyword | 100% | 80.2% | 0.794 | 0.625 | 1.537 | 4.466 |

Engines alone count an abstention as wrong; chains fall back to the keyword classifier. Figure 7.1 plots
accuracy per engine.

**Table 7.4 Question answering**

| Asked as | n | Retrieval hit@5 | Answer correct | Cited | Abstained | p50 (s) | p95 (s) |
|---|---|---|---|---|---|---|---|
| student | 21 | 100% | 90% | 100% | 0% | 3.249 | 7.84 |
| staff | 12 | 100% | 92% | 92% | 0% | 8.8 | 10.111 |
| overall | 33 | 100% | 91% | 97% | 0% | 6.725 | 10.031 |

**Table 7.5 Visibility and department isolation**

| Test | Queries | Leaks | Definition of a leak |
|---|---|---|---|
| Visibility (adversarial) | 20 | **0** | an internal source returned, or an internal-only fact stated |
| Department isolation | 10 | **0** | a source from a department outside the student's own plus institution-wide |

**Table 7.6 Commitment extraction**

| Gold | Extracted | Matched | Precision | Recall | F1 |
|---|---|---|---|---|---|
| 9 | 9 | 9 | 1.00 | 1.00 | 1.00 |

**Table 7.7 Baseline (run 1) vs final run**

| Measure | Run 1 (13 Oct) | Final (19 Oct) |
|---|---|---|
| Triage accuracy, LLM / keyword / laya | 90.6 % / 57.3 % / 51.0 % | 90.6 % / 57.3 % / 51.0 % |
| Q&A questions | 24 | 33 (adds 8 public-website and IT-department questions) |
| Retrieval hit@5 | 100 % | 100 % |
| Answer correct (overall) | 71 % | **91 %** |
| Answer correct (student) | 75 % | **90 %** |
| Cited | 88 % | 97 % |
| Abstained | 8 % | 0 % |
| p95 answer latency | 8.2 s | 10.0 s |
| Visibility leaks | 0 / 20 | 0 / 20 |
| Department leaks | not measured | 0 / 10 |
| Commitments P / R | 1.00 / 1.00 | 1.00 / 1.00 |

### 7.5 Discussion

**Triage.** The LLM classifier is clearly best (90.6 % accuracy, macro-F1 0.907, urgency F1 1.00),
33 points above the keyword baseline. laya abstained on a third of the queries (coverage 67 %) and was less
accurate even with a keyword fallback (68.8 %); placing it before the LLM lowered accuracy to 80.2 %. The
default chain therefore stays LLM → keyword, which keeps 90.6 % while the keyword fallback guarantees a
category when the LLM is unavailable. The keyword classifier answers in under a millisecond; the LLM's
p95 is 4.5 s, acceptable for a ticket that a person answers later.

**Question answering.** Retrieval found a correct source in the top five for every question in both runs,
so the remaining errors are in answer generation. Answer correctness rose from 71 % to 91 % after two
changes motivated by run 1: paragraph-aware chunking that keeps FAQ questions with their answers, and
speaker names in transcript fragments. Abstentions fell from 8 % to 0 %. Latency rose: overall p95 went from 8.2 s
to 10.0 s (staff questions 10.1 s), just above the 10 s target, so Objective 7 is narrowly missed. Likely
causes are the extra procedure retrieval and longer chunks in the prompt, and the hosted API's own variance;
we did not isolate them. Note also that the final Q&A set is larger (33 vs 24 questions), so the two runs
are not strictly like-for-like. Student
answers, which search only public knowledge, have a p95 of 7.8 s.

**Isolation.** No internal source and no internal-only fact reached a student in 20 adversarial queries,
and no out-of-department source reached a student in 10 cross-department queries. Because the filter is
applied in the vector query and checked again on every hit, a single bug in either layer would not be
enough to leak.

**Extraction.** All 9 hand-labelled commitments in the 4 transcripts were extracted with the correct owner,
and nothing extra was extracted. The set is small, so this shows that the pipeline works on clearly phrased
commitments; ambiguous or implied commitments are future work.

**Threats to validity.** All committee data and every gold label were written by the team, so the results
show that the system works as designed on realistic data; they are not a field study with real users.
"Answer correct" is a keyword check against gold facts and does not judge fluency. LLM outputs vary between
runs. The public knowledge base is a snapshot and may drift from the live website.

## 8. Conclusion

This project built and evaluated a platform that turns a college's meetings and documents into cited,
reviewed and access-controlled knowledge. Its contribution is the combination: evidence-first answers,
human review built into procedures and ticket replies, and visibility and department filters enforced
inside retrieval. On the evaluation sets, the LLM triage routed 90.6 % of tickets correctly (keyword baseline 57.3 %), a
correct source was retrieved for every question and 91 % of answers were correct, all 9 labelled commitments
were extracted, and no internal or out-of-department evidence reached a student. Six of the seven objectives
were met; p95 answer latency (10.0 s) narrowly missed its 10 s target.

**Limitations.** Synthetic committee data and team-written labels; dependence on a hosted LLM and its
quota; two visibility levels (internal/public) plus department, but no per-committee confidentiality;
English only.

**Future scope.** Per-committee confidentiality; notice attachments and e-mail delivery; feedback on
answers to improve retrieval; an NBA/NAAC evidence tracker linking decisions and documents to criteria;
integration with the college ERP and timetable; a pilot with one department and real (consented) records;
a locally hosted LLM to remove the external dependency.

## 9. References

See `references.md` (IEEE style, numbered in order of first citation; every entry verified).
