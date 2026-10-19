# Review / viva deck — outline and speaker notes

12 slides, about 10 minutes plus a 5-minute live demo. Images from `../01_ipd_report/figures/`;
numbers from `../01_ipd_report/results/RESULTS.md` (19 Oct 2026, 14:55 UTC). Export the final deck next to this file.

| # | Slide | On the slide | Speaker notes |
|---|---|---|---|
| 1 | Title | DJSCE Institutional Brain; team ⟨…⟩; guide ⟨…⟩; IPD-⟨N⟩ | One line: evidence-grounded AI for college decisions, procedures and student queries. |
| 2 | The problem | Minutes as free text · procedures in circulars · students at counters · chatbots can't cite or restrict | Give one concrete example: a commitment made in an IQAC meeting that nobody followed up. |
| 3 | Why not a chatbot | Hallucination [8], [9] · RAG leaks private documents [12] · no review step | We need grounding, review and access control together. |
| 4 | What we built | Feature grid: commitments, procedures, cited Q&A, Help Desk, triage, notices, graph | Four roles; students see only public knowledge. |
| 5 | Architecture | `fig5_1_architecture.png` | Every item is a Fragment with visibility and department; one evidence pipeline. |
| 6 | Access-aware retrieval | `fig5_2_evidence_pipeline.png` + pseudocode | Filter inside the vector query, then re-check every hit (defence in depth). |
| 7 | Help desk flow | `fig5_3_helpdesk_sequence.png`, `fig6_06_ticket_review.png` | The AI drafts; a person sends. Students never see the draft. |
| 8 | Meetings → accountability | `fig6_05_my_work.png`, `fig5_4_skill_lifecycle.png` | Owners, due dates, progress, confirm or send back; procedures go stale when contradicted. |
| 9 | Evaluation setup | Datasets table (96 triage, 33 Q&A, 20 adversarial, 10 department, 9 commitments) | Synthetic committee data + authentic public website content; labels by the team. |
| 10 | Results | Triage 90.6 % vs 57.3 %; hit@5 100 %; correct 91 %; leaks 0/20; commitments P 1.00 R 1.00; `fig7_1_triage.png` | Compare with run 1 baseline; explain what changed (chunking, speaker names). |
| 11 | Limitations and future scope | Synthetic data · hosted LLM quota · two visibility levels · next: per-committee confidentiality, NBA/NAAC tracker, pilot | Be direct about what the numbers do and don't show. |
| 12 | Demo and thanks | QR code, demo logins | Then run the demo below. |

## Live demo script (5 minutes)

1. **Student** (`aarav.desai@example.com`): Help Desk → ask "What is the minimum attendance requirement?" →
   cited answer from public information. Raise a ticket "Internship letter for the summer".
2. **Coordinator** (`aditi.rao@example.com`): Ticket Queue → open the ticket → AI triage and unsent draft
   with sources → edit and send.
3. Meetings → Record meeting → load the "IQAC Quality Audit" sample → extract → My Work shows the new
   commitments with owners and due dates.
4. Procedures → open "Process revaluation or photocopy request" → steps, owner office, review date, versions.
5. Assistant → "What decisions were made in the latest Academic Council meeting?" → cited answer.
6. Back as the student: the same internal question returns only public information.

All demo passwords are `demo123`. Start the stack with `docker compose up -d` before the session.
