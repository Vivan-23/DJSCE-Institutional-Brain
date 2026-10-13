# DJSCE Institutional Brain — IPD Report (working draft)

> Structure follows the department's IPD report format (see
> `../references/senior_samples/AgriScan_IPD3_Report_Sem5.pdf`). Fill `⟨…⟩` placeholders;
> replace every `TBD` with a measured, reproducible value before submission.

---

## Front matter

1. **Title page** — *DJSCE Institutional Brain: An Evidence-Grounded, Access-Aware
   Knowledge and Help-Desk Platform for Colleges*. "Submitted in partial fulfilment of the
   requirements of the course Innovative Product Development-⟨N⟩, Year ⟨Y⟩, Sem ⟨S⟩,
   Computer Engineering". Team names + SAP IDs, guide name and designation, University of
   Mumbai, ⟨academic year⟩.
2. **Certificate** — signed by internal guide, Head of Department, Principal.
3. **Project report approval** — two examiner lines, date, place.
4. **Declaration** — standard academic-integrity declaration, signed by each member.
5. **Abstract** — draft below.
6. **Contents**, **List of Figures**, **List of Tables**, **List of Abbreviations**.

### Abstract (draft, ~250 words)

Colleges make most of their operational decisions in committee meetings and record
their procedures in scattered circulars and documents. As a result, action items go
untracked, procedures are re-learned every cycle, and students depend on office visits
for routine information. General-purpose AI chatbots are a poor fit: they cannot cite
institutional sources, may invent policy, and do not respect who is allowed to see what.
This work presents *DJSCE Institutional Brain*, a web platform that ingests meeting
transcripts and documents, uses a large language model to extract decisions, owner-
assigned commitments and step-by-step procedures, and routes every AI output through
human review. All knowledge is stored as citable evidence fragments labelled *internal*
or *public*; retrieval for students is restricted to public evidence inside the vector
search itself. Students use a Help Desk that answers from public department information
and escalates unresolved queries as tickets, which are triaged by a constrained AI
classifier with a deterministic fallback and answered by faculty from an AI-drafted,
cited reply. The system is implemented with FastAPI, Next.js, PostgreSQL, ChromaDB, Neo4j
and Celery, deployed with Docker, and covered by ⟨120⟩ automated tests. Evaluation on synthetic
committee records combined with authentic public college-website information (cited by
URL and retrieval date) reports triage accuracy of TBD, grounded-answer rate of
TBD and zero/TBD visibility leaks across TBD adversarial queries. ⟨Finalize after §7.⟩

### List of abbreviations (start)

| Abbr. | Expansion |
|---|---|
| AI | Artificial Intelligence |
| API | Application Programming Interface |
| CO / PO / PSO | Course / Program / Program-Specific Outcome |
| IQAC | Internal Quality Assurance Cell |
| JWT | JSON Web Token |
| LLM | Large Language Model |
| NBA / NAAC | National Board of Accreditation / National Assessment and Accreditation Council |
| NER | Named-Entity Recognition |
| RAG | Retrieval-Augmented Generation |
| RBAC | Role-Based Access Control |

---

## 1. Introduction

- Context: decision-making in Indian engineering colleges is committee-driven
  (Academic Council, Board of Studies, IQAC, Exam Cell, department committees).
- The gap: decisions and commitments are recorded as free-text minutes; procedures sit in
  PDFs; there is no single, trustworthy place to ask "what was decided, who owns it, how
  do we do this?"
- Why now: LLMs can read transcripts and documents, but institutions need *grounded,
  reviewable, access-controlled* AI — not a chatbot.
- Our product in one line, and the report's structure.

## 2. Need of the Product

### 2.1 Introduction and need
Stakeholder pains (coordinators, faculty, students, accreditation) — see the brief §2.

### 2.2 Analysis of existing systems

| Criterion | College ERP / LMS | Generic chatbot (ChatGPT-style) | Enterprise search / RAG demo | **Institutional Brain** |
|---|---|---|---|---|
| Captures meeting decisions & commitments | ✗ | ✗ | ✗ | ✓ owners + due dates |
| Answers cite institutional sources | ✗ | ✗ | partial | ✓ every answer |
| Human review before publishing AI output | n/a | ✗ | ✗ | ✓ procedures, ticket replies |
| Role-aware retrieval (students vs staff) | role-based pages | ✗ | rarely | ✓ inside vector search |
| Student query tracking | partial | ✗ | ✗ | ✓ tickets with routing |
| Detects outdated procedures | ✗ | ✗ | ✗ | ✓ contradiction → stale |

⟨Name 2–3 real products per column with citations.⟩

### 2.3 Applications of the product
Committee secretariats, department offices, exam cell, IQAC/accreditation evidence,
student help desk; transferable to other colleges via `institution.yaml`.

## 3. Survey

### 3.1 Literature survey — topics to cover (≥ 15 references)
1. Retrieval-augmented generation and citation/grounding.
2. Hallucination in LLMs and mitigation through grounding and human review.
3. Information extraction from meeting transcripts (action-item detection).
4. Access control in RAG systems / document-level security.
5. AI-assisted ticket triage and help-desk automation.
6. Knowledge graphs for organisational knowledge.
7. Chatbots in higher education (student query systems).

### 3.2 Outcome of survey
Summarise: what works (RAG + citations), what is missing (access-aware retrieval,
accountability for commitments, human-in-the-loop) → our design choices.

## 4. Problem Formulation

### 4.1 Problem statement
*To design and implement a platform that converts a college's meeting transcripts and
documents into structured, citable institutional knowledge — decisions, accountable
commitments and reviewed procedures — and serves it to staff and students through
grounded, role-restricted AI assistance with human oversight.*

### 4.2 Product objectives (SMART — set targets with the guide)
1. Extract commitments from transcripts with precision ≥ TBD and recall ≥ TBD.
2. Answer staff and student questions with ≥ TBD % of answers citing a correct source.
3. Zero visibility leaks of internal evidence to student accounts on an adversarial set.
4. Route help-desk tickets with accuracy ≥ TBD (LLM) and report the keyword baseline.
5. p95 answer latency ≤ TBD s on the demo deployment.

### 4.3 Novelty
See brief §6: evidence-first outputs, human-in-the-loop by design, access-aware
retrieval, meetings → accountability, constrained triage with deterministic fallback.

### 4.4 Scope
In scope: transcript and document ingestion (.txt/.pdf/.docx), extraction, procedures,
Q&A, help desk, graph, audit, four roles. Out of scope: live meeting recording, ERP
integration, real internal records or student/staff data (committee data is synthetic), per-department
access (planned). Public knowledge is a snapshot of the public website (https://www.djsce.ac.in,
retrieved 2026-10-13), public pages only, no personal contact data.

## 5. Proposed Design

### 5.1 Model / approach selection
- LLM via API (Groq, configurable) for extraction, synthesis, triage, answers — no
  training needed; JSON-constrained prompts with robust parsing.
- Sentence-transformer embeddings (`BAAI/bge-large-en-v1.5`) + ChromaDB for retrieval.
- spaCy NER for graph entities.
- Keyword classifier as a deterministic triage fallback.
- laya (non-generative classifier, `laya==0.3.21`) as an optional compared triage engine
  (`TRIAGE_ENGINES`); default remains LLM → keyword.
- ⟨Justify each against alternatives: fine-tuning, local LLM, BM25, etc.⟩

### 5.2 System architecture
Figure 5.1: architecture diagram (brief §5). Figure 5.2: evidence pipeline
(transcript/document → fragments with visibility → vectors → retrieval). Figure 5.3:
help-desk sequence (student → triage → draft → faculty review → reply). Table 5.1:
roles and permissions.

### 5.3 Data model
Table 5.2: main tables — User, Employee, Meeting, Fragment (with `visibility`),
Commitment, Skill (procedure), SkillCitation, Ticket, AuditLog.

## 6. Implementation

- 6.1 Backend services (one paragraph each): transcript, extraction, fragment, skill,
  freshness, RAG, ticket, PA, audit.
- 6.2 Access control: role ranking, `require_staff`, visibility-filtered retrieval with
  re-check (include the pseudocode below).
- 6.3 Frontend pages and screenshots (Figures 6.x).
- 6.4 Deployment: Docker Compose services, health checks, background jobs.
- 6.5 Testing: 120 automated tests; list what they cover.

```text
ALGORITHM AnswerQuestion(question, user)
  public_only ← (user.role = student)
  hits ← VectorSearch(embed(question), k=5,
                      filter = {visibility: public} if public_only)
  hits ← [h ∈ hits | not public_only or h.visibility = public]   # defence in depth
  answer ← LLM(prompt = rules + numbered hits, question)
  RETURN answer, hits                                            # sources always returned
```

```text
ALGORITHM TriageTicket(subject, description)
  r ← LLMClassify(text, allowed = configured categories)
  IF r is invalid OR r.category ∉ configured categories:
      r ← KeywordClassify(text)          # deterministic fallback
  ticket.routed_to ← office(r.category)
  ticket.draft, ticket.sources ← AnswerQuestion(text, staff)    # never shown to student
```

## 7. Experimentation and Results

### 7.1 Datasets
| Set | Contents | Size |
|---|---|---|
| Committee transcripts | synthetic Academic Council, IQAC, exam moderation, lab readiness | 4 |
| Internal documents | synthetic proposals and guidelines | 3 |
| Public knowledge (mini-project) | CE department FAQs + IT department overview | 2 documents |
| Public website knowledge base | authentic information from https://www.djsce.ac.in (admissions, departments, exam manual, placements, facilities, governance), each file and Q&A cited by URL, retrieved 2026-10-13 | 26 files, 6 sections |
| Triage evaluation set | labelled student queries | 96 queries |
| Q&A evaluation set | questions with known source passages | 25 (13 student + 12 staff) |
| Adversarial visibility set | student questions targeting internal content | 20 |
| Commitments gold set | expected commitments from transcripts | 9 across 4 transcripts |

### 7.2 Test cases — TBD (functional cases per feature + role-access matrix)
### 7.3 Parameter tuning — top-k, chunk size, temperature, model choice: TBD
### 7.4 Results — all TBD; report tables + charts, keyword vs LLM triage comparison.

## 8. Conclusion
⟨Write last.⟩ Summary of contribution, results, limitations (synthetic data, LLM
dependence, two-level visibility), future scope (brief §9).

## 9. References and Bibliography
IEEE style, numbered in order of citation. Keep a running list in `references.md`.
