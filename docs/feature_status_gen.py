"""Generates docs/FEATURE_STATUS.html from the feature list below (one source of truth for the counts).

Run: python docs/feature_status_gen.py
"""
import html
from collections import Counter
from pathlib import Path

AS_OF = "14 Oct 2026"

STATUS = {
    "V": ("Working · verified", "Checked end-to-end on the running system or measured by the evaluation."),
    "T": ("Working · tests pass", "Covered by automated tests; not re-checked by hand on the live system in this cycle."),
    "U": ("Built · UI not clicked through", "Backend verified; the page itself has not yet been tried in a browser."),
    "P": ("Partial", "Works in part; the gap is stated."),
    "N": ("Not started", "Planned; no code yet."),
}

# (group, name, status, roles, page, how it works, note)
FEATURES = [
    ("Access & identity", "Login with four roles", "V", "All", "/login",
     "JWT sign-in. Roles rank Student < Faculty < Committee Coordinator < System Administrator. One-click demo logins on the login page; anyone who self-registers becomes a Student.",
     "Checked live: admin and student logins work."),
    ("Access & identity", "Backend-enforced access", "V", "All", "every API",
     "Every internal API (meetings, commitments, procedures, graph, documents, insights, PA, sources) requires a staff role; students get 403. Hiding menu items is cosmetic, the API is the real control.",
     "Checked live: student gets 403 on meetings, commitments, graph."),
    ("Access & identity", "Role-aware navigation and landing page", "V", "All", "sidebar",
     "Sidebar shows only the pages a role may use and the user's role name. Students land on the Help Desk; staff on the governance overview.", ""),
    ("Access & identity", "Admin user management", "V", "Admin", "/admin/users",
     "Create accounts (a temporary password is generated and shown once), change role, department, year, semester and division, deactivate or reactivate, reset passwords, import a CSV roster. An admin can't remove their own access and the last admin can't be removed. Shows a read-only table of what each role can do. Every change is audited.",
     "Page checked in a browser; 15 automated tests."),
    ("Access & identity", "Institution profile", "V", "Admin", "institution.yaml",
     "One file sets branding, check-in time, departments, the academic calendar, help-desk categories (with owning office, keywords, quick questions) and the people roster. Seeded on every start; idempotent.", ""),
    ("Access & identity", "Per-department access", "V", "Student / Faculty", "every search, /meetings",
     "Every excerpt and meeting carries a department (or 'all'). Students and faculty retrieve only their own department plus institution-wide material; coordinators and admins see everything. Filtered inside the search and re-checked; another department's meeting returns 'not found'. Registration and upload forms ask for the department.",
     "Checked live: IT faculty see 2 of 4 meetings; a CE student never gets IT sources. Public website pages stay institution-wide."),

    ("Knowledge capture", "Meeting transcript intelligence", "V", "Faculty+", "/meetings",
     "Paste a committee transcript. The LLM extracts a summary, participants, decisions and commitments with owners and due dates ('by Friday' becomes a date). Each spoken line is stored as citable evidence with its speaker and meeting.",
     "Eval run 1: commitments 9 of 9 extracted, no false ones."),
    ("Knowledge capture", "Document upload with visibility", "V", "Faculty+", "/sources",
     "Upload .txt/.pdf/.docx and mark it Internal (staff only) or Public (students can get answers from it). It is split into paragraph-sized chunks that become citable evidence and feed the graph.", ""),
    ("Knowledge capture", "Authentic DJSCE website knowledge base", "V", "Students see it", "djsce_public_data/kb",
     "26 files crawled from djsce.ac.in (admissions, 9 departments, exam manual rules, placements, facilities, governance), each citing its source URL and retrieval date. Loaded as public knowledge; answers show an 'Official page' link to the exact djsce.ac.in page.",
     "Independent fact-check: 22 facts, no wrong values. Checked live: answers carry the official links."),
    ("Knowledge capture", "Demo dataset", "V", "Team", "ingest_institutional.py",
     "One command loads 4 synthetic committee meetings, 6 internal documents (3 of them SOPs), the public FAQs and website pages, extracts and approves procedures, and raises 7 sample tickets as the demo students (3 open, 2 answered, 2 closed).",
     "Checked live after a fresh rebuild: 4 meetings, 9 commitments, 10 procedures, 7 tickets."),
    ("Knowledge capture", "Single evidence pipeline", "V", "System", "backend",
     "Transcripts, documents, check-ins and follow-ups all become 'fragments' in one store (PostgreSQL + ChromaDB), each labelled internal or public, so citations, search and procedures work the same way for every source.",
     "Chunking and speaker fixes landed after eval run 1; run 3 will measure them."),

    ("Commitments & Faculty Desk", "Commitment tracking", "T", "Faculty+", "/commitments",
     "Every action item has an owner, due date and status (open, in progress, blocked, done, dropped). Filter by status or 'assigned to me'; change status inline.", ""),
    ("Commitments & Faculty Desk", "Faculty Desk assistant (PA)", "T", "Faculty+", "/assistant",
     "Gives natural-language follow-ups on overdue commitments and runs an end-of-day check-in: the faculty member describes their day, and the assistant updates commitment statuses and records new ones.", ""),

    ("Procedures", "Procedure synthesis with citations", "V", "Coordinator+", "/skills",
     "Related internal evidence is clustered and turned into a structured procedure: trigger, steps, decision rules, guardrails, escalation. Every procedure links to the excerpts it came from.",
     "Checked live: 10 procedures, one per meeting or SOP (it used to merge everything into 1)."),
    ("Procedures", "Review, approve, export", "T", "Coordinator+", "/skills",
     "A coordinator approves or rejects each draft (shown as 'Approved in Review', never 'ratified'). Approved procedures export as a SKILL.md file.", ""),
    ("Procedures", "Evidence panel", "U", "Faculty+", "/skills",
     "Shows the source excerpts behind a procedure, grouping duplicate excerpts while keeping every original reference inspectable, with search, filter and copy.", ""),
    ("Procedures", "Freshness scan", "T", "System", "nightly job",
     "Each night, new evidence is compared with approved procedures. If it contradicts one, the procedure is flagged stale and an alert is raised for review.", ""),

    ("Q&A assistant", "Cited answers", "V", "All", "/chat",
     "Answers come only from indexed knowledge and cite it inline [1]; each answer lists its source excerpts with document or meeting name and an Internal/Public badge. Says plainly when it can't answer.",
     "Eval run 1: right source in top 5 for 100% of questions; 71% fully correct before the retrieval fixes."),
    ("Q&A assistant", "Students never see internal records", "V", "Student", "/chat, /helpdesk",
     "For students the search itself is restricted to public knowledge, and every result is re-checked before use.",
     "Eval run 1: 0 leaks in 20 adversarial student questions."),

    ("Student Help Desk", "Quick questions and instant answers", "V", "Student", "/helpdesk",
     "Category cards (Courses, Exams, Attendance, Labs, Placements, General) with one-click questions answered from public knowledge, with sources and a 'Not answered? Raise a ticket' button.",
     "Page checked in a browser; answers verified via the API."),
    ("Student Help Desk", "Tickets with AI triage and routing", "V", "Student raises; staff see triage", "/helpdesk",
     "A ticket is classified into a configured category and priority and routed to the responsible office (e.g. Examination Cell). The AI may only pick categories from institution.yaml.",
     "Eval run 1: 90.6% correct category (keyword rules alone: 57.3%)."),
    ("Student Help Desk", "Staff queue with AI-drafted reply", "V", "Faculty+", "/tickets",
     "Staff see the triage and its reasoning plus an AI draft reply with sources (warning shown if it used internal sources). They edit and send; students never see the draft, only the human reply.",
     "Page checked in a browser: triage, draft panel, reply box. With the AI quota used up it falls back to keyword triage and says no draft was made."),
    ("Student Help Desk", "Fallback and optional laya engine", "V", "System", "TRIAGE_ENGINES",
     "If the LLM fails or invents a category, a keyword classifier (from the mini-project) decides. laya, a fast non-generative classifier, can be switched on as an extra engine.",
     "Eval run 1: laya scored 51.0%, below the LLM, so it stays off by default."),

    ("Knowledge graph & insights", "Knowledge graph", "V", "Faculty+", "/relationships",
     "People ATTEND meetings; meetings and documents MENTION committees, departments and labs. Interactive view: zoom and pan, node size by number of connections, filters by type (documents off by default), hide hubs like 'DJSCE', search, click a node to focus on it and its connections, load a node's full neighbourhood for large graphs. Department-scoped like everything else.",
     "Checked in a browser: 121 links, all 4 meetings; focus mode works. Also fixed: faculty could see other departments' meetings in the graph."),
    ("Commitments & Faculty Desk", "Notices to students", "V", "Faculty+ send · everyone reads", "/notices",
     "Staff write a notice (title, message, urgent flag, optional 'show until' date) and pick who receives it by role, department, year, semester and division, with a live 'reaches N people' count. Faculty can only address their own department. Students get an inbox (unread and urgent first) and an unread badge in the sidebar; senders see how many have read it.",
     "Pages checked in a browser (inbox, compose); 12 automated tests. In-app only, no email or attachments yet."),
    ("Commitments & Faculty Desk", "Academic calendar and deadline reminders", "V", "All", "/calendar",
     "Published academic dates (term, exams, holidays, deadlines) filtered by audience and department, merged for faculty with their own commitment due dates. Each item is marked overdue / today / soon / upcoming; a daily job posts reminders for staff deadlines to the Active Feed.",
     "Page checked in a browser. Dates are synthetic placeholders until the official calendar is added."),
    ("Commitments & Faculty Desk", "Meeting minutes export", "V", "Coordinator+", "/meetings",
     "Formal draft minutes (attendees, summary, decisions, action items with owner, due date, status) as DOCX or PDF, built from what was already extracted, marked as a draft to verify, and audited.",
     "Checked live: DOCX and PDF downloaded and read. Buttons on the page not yet clicked."),
    ("Knowledge graph & insights", "Analytics dashboard", "V", "Coordinator+", "/analytics",
     "Open and overdue commitments per committee meeting, tickets by status and category, median time to reply, tickets waiting over 48 h, most-asked questions, questions that found nothing (knowledge gaps), knowledge by department.",
     "Page checked in a browser; faculty get 403. Questions are logged without user ids."),
    ("Knowledge graph & insights", "Active Feed insights", "P", "Faculty+", "/ (overview)",
     "Overview shows open commitments, meetings, procedures and AI insights; insights can be dismissed.",
     "Gap: 'bottleneck' alerts never fire because nothing records who works on which project; only freshness alerts appear."),

    ("Platform", "Audit trail", "T", "Coordinator+", "API /audit",
     "Every AI action and every human decision (extraction, approval, check-ins, tickets, replies) is logged with actor and time.", "No UI page; API only."),
    ("Platform", "Scheduled background jobs", "T", "System", "Celery beat",
     "Six jobs: daily insights, daily check-in prep, hourly commitment follow-ups, nightly procedure extraction, nightly freshness scan, morning deadline reminders.", ""),
    ("Platform", "Database migrations (data survives updates)", "V", "Team", "backend/migrations",
     "Alembic migrations run on every start, so rebuilding or updating the code keeps all data; only an explicit wipe deletes it. A test fails if the models and migrations ever disagree. Backup and restore commands are documented.",
     "Checked live: users, tickets, notices and excerpts kept across a full rebuild."),
    ("Platform", "Docker deployment", "V", "Admin", "docker compose",
     "Eight services (frontend, backend, worker, scheduler, PostgreSQL, ChromaDB, Neo4j, Redis) start with one command; safe on a fresh database.", ""),
    ("Platform", "Source connectors", "P", "Coordinator+", "API /sources",
     "Framework for pulling knowledge from other systems; the manual connector accepts pushed items.", "Gap: Slack and database connectors are stubs (no live integration)."),
    ("Platform", "Remote demo over the internet", "P", "Admin", "start_public_share.ps1",
     "Script starts the stack and an ngrok tunnel to the frontend; the frontend proxies the API, so one public URL is enough.", "Gap: access from outside the machine not yet confirmed."),
    ("Platform", "Evaluation harness", "V", "Team", "evaluation/",
     "One command measures triage, answer quality (33 questions), visibility leaks, department isolation and commitment extraction, and writes results for the report. Retries provider errors and saves after each part.", "Run 1 done. Run 3 stopped on the Groq daily token limit; re-run when the quota resets."),
    ("Platform", "Automated tests", "V", "Team", "backend/tests",
     "204 backend tests (access and department rules, users, notices, help desk, visibility, calendar, minutes, analytics, graph, migrations, chunking, extraction, procedures); frontend type-check and lint clean.", ""),

    ("Planned", "Notice attachments, email delivery, ask-about-notices in chat", "N", "All", "", "Attach PDFs to notices, optionally email them, and let the assistant answer questions from notices addressed to the asker.", ""),
    ("Planned", "NBA/NAAC evidence tracker", "N", "Coordinator+", "", "Link decisions, documents and CO-PO mappings to accreditation criteria.", ""),
    ("Planned", "Answer feedback (thumbs up/down)", "N", "All", "", "Shows which questions the knowledge base can't answer yet.", ""),
    ("Planned", "Jira sync (stretch)", "N", "Admin", "", "Optional two-way ticket sync through the connector framework.", ""),
]

ROLES = ["Student", "Faculty", "Committee Coordinator", "System Administrator"]
# what each role can do, page by page (✓ full · R read-only/limited · — no access)
ROLE_MATRIX = [
    ("Help Desk: ask, raise and track own tickets", "✓", "✓", "✓", "✓"),
    ("Assistant (Q&A)", "public, own dept + all", "own dept + all", "✓ every dept", "✓ every dept"),
    ("Calendar and deadline reminders", "✓", "✓ + own commitments", "✓ + own commitments", "✓"),
    ("Notices: read my inbox", "✓", "✓", "✓", "✓"),
    ("Notices: send", "—", "own dept", "any dept", "any dept"),
    ("Help Desk Queue: triage, AI draft, reply", "—", "✓", "✓", "✓"),
    ("Meetings: upload transcripts, view extraction", "—", "own dept + all", "✓", "✓"),
    ("Meeting minutes export (DOCX/PDF)", "—", "—", "✓", "✓"),
    ("Commitments and Faculty Desk PA", "—", "✓", "✓", "✓"),
    ("Procedures: view, evidence panel", "—", "✓", "✓", "✓"),
    ("Procedures: run extraction, approve, reject", "—", "—", "✓", "✓"),
    ("Knowledge graph", "—", "✓", "✓", "✓"),
    ("Document upload (internal/public)", "—", "✓", "✓", "✓"),
    ("Analytics dashboard", "—", "—", "✓", "✓"),
    ("Source connector sync, audit log", "—", "—", "✓", "✓"),
    ("Manage users (create, roles, deactivate, passwords)", "—", "—", "—", "✓"),
]


def badge(code):
    label, _ = STATUS[code]
    return f'<span class="badge s-{code}">{html.escape(label)}</span>'


def build():
    counts = Counter(f[2] for f in FEATURES)
    built = sum(counts[c] for c in "VTU")
    total = len(FEATURES)
    cards = "".join(
        f'<div class="card s-{c}"><div class="num">{counts[c]}</div><div class="lbl">{html.escape(STATUS[c][0])}</div></div>'
        for c in "VTUPN"
    )
    legend = "".join(f"<li>{badge(c)} {html.escape(d)}</li>" for c, (_, d) in STATUS.items())

    groups, sections = [], []
    for f in FEATURES:
        if f[0] not in groups:
            groups.append(f[0])
    for g in groups:
        rows = []
        for i, (grp, name, st, roles, page, how, note) in enumerate(FEATURES, 1):
            if grp != g:
                continue
            note_html = f'<div class="note">{html.escape(note)}</div>' if note else ""
            page_html = f'<code>{html.escape(page)}</code>' if page else ""
            rows.append(
                f"<tr><td class='n'>{i}</td><td><strong>{html.escape(name)}</strong><div class='meta'>{page_html}"
                f"<span class='roles'>{html.escape(roles)}</span></div></td><td>{badge(st)}</td>"
                f"<td>{html.escape(how)}{note_html}</td></tr>"
            )
        sections.append(
            f"<h2>{html.escape(g)}</h2><div class='tablewrap'><table><thead><tr><th>#</th><th>Feature</th>"
            f"<th>Status</th><th>How it works</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>"
        )

    matrix_rows = "".join(
        "<tr><td>" + html.escape(r[0]) + "</td>" + "".join(f"<td class='c'>{html.escape(x)}</td>" for x in r[1:]) + "</tr>"
        for r in ROLE_MATRIX
    )
    role_head = "".join(f"<th class='c'>{html.escape(r)}</th>" for r in ROLES)

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>DJSCE Institutional Brain — Feature Status</title>
<style>
:root{{--ink:#1c2430;--quiet:#5b6675;--rule:#dfe3e8;--bg:#fff;--panel:#f6f8fa;
--V:#1a7f37;--T:#0969da;--U:#8250df;--P:#9a6700;--N:#6e7781;color-scheme:light}}
@media (prefers-color-scheme:dark){{:root{{--ink:#e6edf3;--quiet:#9aa5b1;--rule:#30363d;--bg:#0d1117;--panel:#161b22;
--V:#3fb950;--T:#58a6ff;--U:#bc8cff;--P:#d29922;--N:#8b949e;color-scheme:dark}}}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 "Segoe UI",system-ui,sans-serif}}
main{{max-width:1080px;margin:0 auto;padding:40px 20px 80px}} h1{{font-size:1.9rem;margin:0 0 4px}}
h2{{font-size:1.15rem;margin:36px 0 8px;padding-top:10px;border-top:1px solid var(--rule)}}
.by{{color:var(--quiet);margin:0 0 22px}} .lead{{font-size:1.05rem}}
.cards{{display:flex;flex-wrap:wrap;gap:12px;margin:18px 0}} .card{{flex:1 1 150px;background:var(--panel);border-radius:10px;padding:14px 16px;border-left:4px solid}}
.card .num{{font-size:1.8rem;font-weight:700}} .card .lbl{{color:var(--quiet);font-size:.9rem}}
.s-V{{border-color:var(--V)}} .s-T{{border-color:var(--T)}} .s-U{{border-color:var(--U)}} .s-P{{border-color:var(--P)}} .s-N{{border-color:var(--N)}}
.badge{{display:inline-block;white-space:nowrap;font-size:.78rem;font-weight:600;padding:2px 8px;border-radius:999px;border:1px solid}}
.badge.s-V{{color:var(--V)}} .badge.s-T{{color:var(--T)}} .badge.s-U{{color:var(--U)}} .badge.s-P{{color:var(--P)}} .badge.s-N{{color:var(--N)}}
.legend{{list-style:none;padding:0;margin:8px 0}} .legend li{{margin:4px 0;color:var(--quiet)}}
.tablewrap{{overflow-x:auto}} table{{width:100%;border-collapse:collapse;margin:8px 0}}
th,td{{text-align:left;padding:8px 10px;border-bottom:1px solid var(--rule);vertical-align:top}}
th{{color:var(--quiet);font-size:.8rem;text-transform:uppercase;letter-spacing:.03em}}
td.n{{color:var(--quiet);width:2.2em}} td.c,th.c{{text-align:center}}
.meta{{margin-top:3px;font-size:.8rem;color:var(--quiet)}} .meta code{{margin-right:8px}}
.roles{{white-space:nowrap}} .note{{margin-top:4px;font-size:.85rem;color:var(--quiet)}}
code{{background:var(--panel);padding:1px 5px;border-radius:4px;font-size:.88em}}
footer{{margin-top:44px;color:var(--quiet);font-size:.85rem;border-top:1px solid var(--rule);padding-top:12px}}
</style></head><body><main>
<h1>DJSCE Institutional Brain — Feature Status</h1>
<p class="by">As of {AS_OF} · generated from <code>docs/feature_status_gen.py</code></p>
<p class="lead"><strong>{built} of {total} features are built and working</strong>; {counts['P']} are partial and
{counts['N']} are planned but not started. "Working" splits into how strongly it has been checked.</p>
<div class="cards">{cards}</div>
<ul class="legend">{legend}</ul>

<h2>What each role can do</h2>
<div class="tablewrap"><table><thead><tr><th>Capability</th>{role_head}</tr></thead><tbody>{matrix_rows}</tbody></table></div>
<p class="note">Enforced by the backend: a student calling a staff API gets 403, whatever the browser shows.</p>

{''.join(sections)}

<h2>Open items besides features</h2>
<ul>
<li>Final evaluation run 3 on the corrected data, then numbers into the report, poster and brief (run 2 was interrupted and wrote no results).</li>
<li>Click through the new pages once in a browser to promote the "UI not clicked through" items to verified.</li>
<li>Confirm the remote (ngrok) demo from another device.</li>
</ul>
<footer>Data: synthetic committee records combined with authentic public college-website information, cited by URL and retrieval date. Nothing synthetic is an official DJSCE record.</footer>
</main></body></html>
"""


if __name__ == "__main__":
    out = Path(__file__).with_name("FEATURE_STATUS.html")
    out.write_text(build(), encoding="utf-8")
    c = Counter(f[2] for f in FEATURES)
    print(out, dict(c), "total", len(FEATURES))
