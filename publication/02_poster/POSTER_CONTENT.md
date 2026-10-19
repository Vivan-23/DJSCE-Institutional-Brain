# AVINYA poster — final content

Layout follows the AVINYA 2026 posters in `../references/senior_samples/`: college header (SVKM / DJSCE
logos, "Department of Computer Engineering"), team names and guide top-right, three columns, GitHub/demo QR
code bottom-right. Each box has 4–6 short lines; the architecture diagram is the visual centre.
Images: `../01_ipd_report/figures/` (architecture `fig5_1_architecture.png`, screenshots `fig6_*.png`,
triage chart `fig7_1_triage.png`). Numbers: `../01_ipd_report/results/RESULTS.md` (19 Oct 2026, 14:55 UTC).

---

**Title:** DJSCE Institutional Brain
**Tagline:** Evidence-grounded AI for college decisions, procedures and student queries

**Team:** ⟨names⟩ **Guide:** ⟨guide⟩

### Introduction
- Committee decisions and action items live in free-text minutes and are easily lost
- Procedures are scattered across circulars and people's memory
- Students visit offices for routine questions; their queries go untracked
- Generic chatbots can't cite sources or respect who may see what

### Key features (icon grid)
Meeting → commitments · Task follow-ups · Cited procedures · Coordinator approval ·
Cited Q&A · Student Help Desk · AI ticket triage · Notices · Knowledge graph · Role-based access

### Contributions / novelty
- Every AI answer, procedure and draft cites its source excerpts
- Human in the loop: nothing becomes policy or reaches a student without review
- Access-aware retrieval: students search public knowledge only, enforced in the vector query
- Meetings → accountable commitments with owners, due dates and progress
- Constrained AI triage with an offline keyword fallback

### System architecture (centre)
`fig5_1_architecture.png`: Sources → Processing (extraction, procedures, triage) → Evidence layer
(PostgreSQL · ChromaDB · Neo4j, every item labelled internal/public + department) → Access-aware
retrieval → Students and staff, with human review.

### Workflow strip
Transcript → Extract → Commitments → Follow-up → Procedure → Review → Ask (cited)
Student question → Instant answer → Ticket → AI triage + draft → Faculty reply

### Results
- Ticket triage: **90.6 %** (LLM) vs 57.3 % (keyword baseline), 96 queries
- Correct source retrieved: **100 %** of questions (top 5); answers correct: 91 %
- Commitment extraction: precision 1.00, recall 1.00
- Leaks to students: **0** / 20 adversarial queries; cross-department: 0 / 10
- p95 answer latency: 10.0 s · 235 automated tests passing

### Conclusion & future scope
- Turns meetings and documents into trustworthy, reviewable institutional knowledge
- Gives students tracked, cited answers without exposing internal records
- Next: per-committee confidentiality, NBA/NAAC evidence tracker, ERP integration, pilot with one department

### Footer
"Synthetic committee records combined with authentic public information from djsce.ac.in, cited by URL and
retrieval date. Not an official DJSCE system." · QR → repository / demo link
