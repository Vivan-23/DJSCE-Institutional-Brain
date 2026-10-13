# AVINYA poster — content draft

Layout follows the AVINYA 2026 posters in `../references/senior_samples/`:
college header (SVKM / DJSCE logos, "Department of Computer Engineering"), team names
and guide top-right, three columns, GitHub/demo QR code bottom-right. Keep each box to
4–6 short bullets; the architecture diagram is the visual centre.

---

**Title:** DJSCE Institutional Brain
**Tagline:** Evidence-grounded AI for college decisions, procedures and student queries

**Team:** ⟨names⟩ **Guide:** ⟨guide⟩

### Introduction
- Committee decisions and action items live in free-text minutes and are easily lost
- Procedures are scattered across circulars and people's memory
- Students need office visits for routine questions; queries go untracked
- Generic chatbots can't cite sources or respect who may see what

### Key features (icon grid)
Meeting → commitments · Commitment follow-ups · Cited procedures · Coordinator approval ·
Cited Q&A · Student Help Desk · AI ticket triage · Knowledge graph · Audit trail · Role-based access

### Contributions / novelty
- Every AI answer, procedure and draft cites its source excerpts
- Human-in-the-loop: nothing reaches a student or becomes policy without review
- Access-aware retrieval: students search public knowledge only (enforced in vector search)
- Meetings → accountable commitments with owners and due dates
- Constrained AI triage with an offline keyword fallback

### System architecture (centre)
Use the diagram from `../00_project_brief/PROJECT_BRIEF.md` §5, redrawn cleanly:
Sources (transcripts, documents, student tickets) → AI extraction / triage →
evidence fragments (internal/public) → PostgreSQL · ChromaDB · Neo4j →
cited Q&A and Help Desk → human review.

### Workflow strip
Transcript → Extract → Commitments → Follow-up → Procedure → Review → Ask (cited)
Student question → Instant answer → Ticket → AI triage + draft → Faculty reply

### Results (fill from report §7 — no placeholders on the printed poster)
- Triage accuracy: TBD (LLM) vs TBD (keyword baseline)
- Answers citing a correct source: TBD %
- Visibility leaks on adversarial student queries: TBD
- p95 answer latency: TBD s
- 120 automated tests passing

### Conclusion & future scope
- Turns meetings and documents into trustworthy, reviewable institutional knowledge
- Gives students tracked, cited answers without exposing internal records
- Next: per-department access, notices feed, NBA/NAAC evidence tracker

### Footer
"Synthetic committee records combined with authentic public college-website information (djsce.ac.in), cited by URL and retrieval date." · QR → repository / demo link
