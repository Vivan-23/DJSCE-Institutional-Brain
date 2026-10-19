# Access-Aware, Evidence-Grounded Assistance for College Governance and Student Help Desks

*Draft for an IEEE conference template (two columns, about 6 pages). Authors ⟨names, affiliation:
Department of Computer Engineering, Dwarkadas J. Sanghvi College of Engineering, Mumbai, India⟩.
Results from `../01_ipd_report/results/RESULTS.md` (19 Oct 2026, 14:55 UTC); references as in
`../01_ipd_report/references.md` (renumber to order of citation here before submission).*

**Abstract.** Colleges record committee decisions as free-text minutes and procedures as scattered
circulars, while students depend on office visits for routine information. LLM chatbots could help, but
they hallucinate, rarely cite institutional sources, and ignore who may see what. We present an
evidence-grounded platform in which every transcript turn and document chunk is stored as a citable
fragment labelled with visibility (internal or public) and department. Retrieval enforces these labels
inside the vector query and re-checks each hit, so students search public knowledge only. An LLM extracts
decisions and owner-assigned commitments from meetings and synthesises procedures that a coordinator must
approve; a student help desk answers from public information and escalates tickets, which are triaged by
a category-constrained LLM with a keyword fallback and answered by faculty from an unsent, cited AI
draft. On synthetic committee records combined with authentic public website content, triage accuracy is
90.6 % (keyword baseline 57.3 %), a correct source is retrieved for 100 % of
questions, commitment extraction reaches precision 1.00 and recall 1.00, and adversarial
tests show 0 leaks in 20 student queries.

**Index Terms** — retrieval-augmented generation, access control, action-item extraction, help desk,
human-in-the-loop, higher education.

## I. Introduction

- Committee-driven governance in Indian engineering colleges; minutes, circulars, student counters.
- RAG grounds LLMs [1], [2] but a single shared index ignores audience; RAG can leak its database [12].
- Contributions: (1) a fragment model with visibility and department enforced in retrieval; (2) a
  human-in-the-loop workflow for procedures and ticket replies; (3) meeting commitments with owners,
  progress and confirmation; (4) an evaluation covering triage, Q&A, isolation and extraction.

## II. Related Work

RAG and dense retrieval [1]–[5]; answers with citations and RAG evaluation [6], [7]; hallucination
[8], [9]; action items and meeting summarisation [10], [11]; RAG privacy and prompt injection [12], [13];
RBAC [14]; ticket classification [15], [16]; knowledge graphs and GraphRAG [17], [18]; chatbots in
education [19], [20]. (Condense §3.1 of the report to about 0.6 column.)

## III. System Design

A. *Evidence model.* Fragment (text, source, speaker, visibility, department) written once to PostgreSQL
and ChromaDB with identical metadata; NER entities to Neo4j (Fig. 1: `fig5_2_evidence_pipeline.png`).

B. *Access-aware retrieval.* Algorithm 1 (report §6.2): filter in the query, re-check hits, return sources.

C. *Extraction and procedures.* JSON-constrained LLM extraction of summary, decisions and commitments;
procedure synthesis from internal fragments only; lifecycle draft → approved → stale → deprecated with a
contradiction scan (Fig. 2: `fig5_4_skill_lifecycle.png`).

D. *Help desk.* Category-constrained LLM triage with keyword fallback, office routing, staff-only cited
draft, human reply (Fig. 3: `fig5_3_helpdesk_sequence.png`).

E. *Implementation.* FastAPI, Celery/Redis, PostgreSQL, ChromaDB (`bge-large-en-v1.5`), Neo4j, Next.js;
Docker Compose; 235 automated tests.

## IV. Evaluation

A. *Data.* 4 synthetic committee transcripts, 3 internal documents and 3 SOPs; 2 public mini-project
documents; 26 authentic public pages from the college website, cited by URL. Labelled sets: 96 triage
queries (6 categories), 33 Q&A items with gold sources, 20 adversarial visibility queries,
10 cross-department queries, 9 gold commitments.

B. *Results.* Table I triage (copy report Table 7.3); Table II Q&A, isolation and extraction (Tables
7.4–7.6); baseline vs final (Table 7.7).

C. *Discussion.* LLM triage (90.6 %) beats the keyword baseline (57.3 %) and a small non-generative
classifier (51.0 %, 67 % coverage). Retrieval hit@5 is 100 %; answer correctness rose from 71 % to 91 % after
paragraph-aware chunking and speaker attribution, at the cost of p95 latency (8.2 s → 10.0 s). No visibility
or department leaks were observed.

## V. Limitations and Future Work

Synthetic committee data and team-written labels; hosted LLM dependence; two visibility levels plus
department. Future: per-committee confidentiality, answer feedback, NBA/NAAC evidence tracking, a pilot
with consented real records, and a locally hosted LLM.

## VI. Conclusion

Grounding, review and access control can be built into one evidence pipeline; on our evaluation the
combination gives accurate triage and retrieval with no observed leaks to students.

## Acknowledgment

⟨Guide⟩, Department of Computer Engineering, DJSCE. Public content from djsce.ac.in is used with
attribution ⟨and the written permission obtained on date⟩.

## References

Use entries [1]–[21] from `../01_ipd_report/references.md` in IEEE format.
