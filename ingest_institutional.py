"""
DJSCE Institutional Brain — DEMO Institutional Data Loader.

Ingests synthetic institutional records (committee transcripts, SOPs, curriculum docs)
through the application pipeline:
  1. Authenticates as the demo admin (from institution.yaml).
  2. Submits synthetic committee meeting transcripts to POST /api/v1/transcripts.
  3. Uploads reference documents and SOPs to POST /api/v1/ingest/file for
     the ChromaDB vector store and Neo4j institutional relationship graph.
  4. Waits for Celery background processing.
  5. Optionally triggers procedure extraction and approval.

Usage:
  python ingest_institutional.py              # Ingests all 4 scenarios & reference documents
  python ingest_institutional.py --approve    # Also auto-approves extracted procedures
  python ingest_institutional.py --no-demo-tickets   # Skip the sample help-desk tickets

Sample tickets are raised by the demo students through the real help-desk API (so AI triage and
drafts run as normal); staff then answer or close some, giving open / answered / closed examples.
"""
import os
import sys
import time
import requests

API = os.environ.get("API_URL", "http://localhost:8001")
EMAIL = os.environ.get("DEMO_EMAIL", "admin@example.com")
PASSWORD = os.environ.get("DEMO_PASSWORD", "demo123")
FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mock_institutional_data")
PUBLIC_FOLDER = os.path.join(FOLDER, "public")
# Authentic public website content (djsce.ac.in), each file citing its source URL + retrieval date.
WEBSITE_KB_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "djsce_public_data", "kb")

PROCESS_WAIT_SECONDS = 180

# Owning department (code from institution.yaml) per file; anything not listed is
# institution-wide ("all"). CE students/faculty see CE + "all"; IT see IT + "all".
DEPARTMENT_OF = {
    "scenario_1_academic_council_curriculum_review.txt": "CE",  # CE elective
    "scenario_4_departmental_lab_readiness_sync.txt": "CE",
    "doc_Departmental_Research_and_Lab_Upgrades.txt": "CE",
    "doc_Elective_Proposal_AIML_Autonomous_Curriculum.txt": "CE",
    "kb_computer_engineering_faq.txt": "CE",
    "kb_information_technology_overview.txt": "IT",
    "kb_dept_computer_engineering.txt": "CE",
    "kb_dept_information_technology.txt": "IT",
    "kb_dept_ai_and_data_science.txt": "AIDS",
    "kb_dept_ai_and_machine_learning.txt": "AIML",
    "kb_dept_cse_data_science.txt": "CSDS",
    "kb_dept_cse_iot_cyber_security.txt": "IOTCS",
    "kb_dept_electronics_telecom.txt": "EXTC",
    "kb_dept_mechanical_engineering.txt": "MECH",
    "kb_dept_basic_sciences_humanities.txt": "BSH",
}


def _title_from(filename: str) -> str:
    base = os.path.splitext(filename)[0].replace("_", " ").strip()
    # Format readable academic title
    words = [w.capitalize() for w in base.split()]
    return " ".join(words)


def login(email: str = EMAIL, password: str = PASSWORD) -> str:
    r = requests.post(f"{API}/api/v1/auth/login", json={"email": email, "password": password})
    if r.status_code != 200:
        sys.exit(f"Login failed ({r.status_code}): {r.text}\nIs backend running and is {EMAIL} seeded in institution.yaml?")
    print(f"[OK] Logged in as {EMAIL}")
    return r.json()["access_token"]


def post_transcripts(token: str) -> int:
    headers = {"Authorization": f"Bearer {token}"}
    posted = 0
    transcript_files = [
        f for f in sorted(os.listdir(FOLDER))
        if f.startswith("scenario_") and f.endswith(".txt")
    ]

    for filename in transcript_files:
        with open(os.path.join(FOLDER, filename), "r", encoding="utf-8") as fh:
            text = fh.read()
        r = requests.post(
            f"{API}/api/v1/transcripts",
            json={"title": _title_from(filename), "transcript": text, "source": "demo_institutional",
                  "department": DEPARTMENT_OF.get(filename, "all")},
            headers=headers,
        )
        if r.status_code == 202:
            posted += 1
            print(f"  [OK] Queued meeting transcript: {filename}")
        else:
            print(f"  [!] Transcript rejected: {filename} ({r.status_code}) {r.text[:120]}")
    print(f"[OK] Queued {posted} institutional transcript(s)")
    return posted


def post_documents(token: str) -> int:
    """Upload reference documents through /api/v1/ingest/file (vector index + graph).

    ``doc_*.txt`` are internal staff documents; everything in ``public/`` is
    student-visible knowledge (department FAQs, curriculum, outcomes), and
    ``djsce_public_data/kb/`` is authentic public website content, also public.
    Meeting transcripts are NOT re-uploaded here — they go through /transcripts.
    """
    headers = {"Authorization": f"Bearer {token}"}
    batches = [
        (FOLDER, [f for f in sorted(os.listdir(FOLDER)) if f.startswith("doc_") and f.endswith(".txt")], "internal"),
        (PUBLIC_FOLDER, sorted(f for f in os.listdir(PUBLIC_FOLDER) if f.endswith(".txt")) if os.path.isdir(PUBLIC_FOLDER) else [], "public"),
        (WEBSITE_KB_FOLDER, sorted(f for f in os.listdir(WEBSITE_KB_FOLDER) if f.endswith(".txt")) if os.path.isdir(WEBSITE_KB_FOLDER) else [], "public"),
    ]
    sent = 0
    for folder, files, visibility in batches:
        for filename in files:
            with open(os.path.join(folder, filename), "rb") as fh:
                r = requests.post(
                    f"{API}/api/v1/ingest/file",
                    files={"file": (filename, fh, "text/plain")},
                    data={"visibility": visibility, "department": DEPARTMENT_OF.get(filename, "all")},
                    headers=headers,
                )
            if r.status_code in (200, 202):
                sent += 1
                print(f"  [OK] Queued {visibility} document ({DEPARTMENT_OF.get(filename, 'all')}): {filename}")
            else:
                print(f"  [!] Document upload failed: {filename} ({r.status_code}) {r.text[:120]}")
    print(f"[OK] Queued {sent} document(s) for the knowledge index and graph")
    return sent


def wait_for_processing(token: str, expected_meetings: int) -> None:
    headers = {"Authorization": f"Bearer {token}"}
    print("... Waiting for worker to process transcripts", end="", flush=True)
    deadline = time.time() + PROCESS_WAIT_SECONDS
    last = -1
    stable = 0
    while time.time() < deadline:
        time.sleep(4)
        print(".", end="", flush=True)
        r = requests.get(f"{API}/api/v1/transcripts", headers=headers)
        if r.status_code != 200:
            continue
        count = len(r.json())
        if count >= expected_meetings:
            break
        stable = stable + 1 if count == last else 0
        last = count
        if stable >= 6:
            break
    print(f" done (total meetings: {last if last >= 0 else '?'})")


def extract_skills(token: str, approve: bool) -> None:
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.post(f"{API}/api/v1/skills/extract", headers=headers)
    if r.status_code != 202:
        print(f"  [!] Procedure extraction notice ({r.status_code}): {r.text[:140]}")
        return
    created = r.json().get("candidates_created", 0)
    print(f"[OK] Synthesized {created} candidate institutional procedure(s)")

    if not approve:
        return
    skills_resp = requests.get(f"{API}/api/v1/skills", headers=headers)
    if skills_resp.status_code != 200:
        return
    skills = skills_resp.json()
    approved = 0
    for s in skills:
        if s.get("status") == "draft":
            a = requests.post(f"{API}/api/v1/skills/{s['id']}/approve", headers=headers)
            if a.status_code == 200:
                approved += 1
    print(f"[OK] Approved {approved} procedure(s) for formal SKILL.md export")


# (student, subject, description, staff who acts, action, staff reply). Action: None = stays open.
DEMO_TICKETS = [
    ("aarav.desai@example.com", "Revaluation of my Data Structures paper",
     "I got 38 in the semester-end Data Structures exam and expected more. How do I apply for revaluation and what is the deadline?",
     "karan.shah@example.com", "answer",
     "Apply through the Examination Cell within 7 days of the result, after paying the revaluation fee on the fee portal. "
     "Your script will be checked by a different examiner; the revised result is usually out within about three weeks."),
    ("aarav.desai@example.com", "Scholarship form for second year",
     "Which documents do I need for the post-matric scholarship renewal, and where do I submit them?",
     "pooja.verma@example.com", "close",
     "Renewal needs last year's marksheet, the income certificate and the fee receipt. Submit online on the state portal and "
     "hand the printed acknowledgement to the scholarship desk in the administrative office. Closing this; reopen if anything is unclear."),
    ("aarav.desai@example.com", "Wi-Fi not working in the second-floor lab",
     "The lab computers on the second floor have had no internet since Monday, so we cannot finish the web programming practical.",
     None, None, None),
    ("isha.kulkarni@example.com", "Can I change my honours specialisation?",
     "I registered for the honours track in AI/ML but want to switch to Cyber Security. Is it allowed after the first semester of the track?",
     "aditi.rao@example.com", "answer",
     "A switch is considered only before the second semester of the track and needs the Head of Department's approval. "
     "Write to the department office with your reason; credits already earned will count as electives."),
    ("isha.kulkarni@example.com", "Hostel fee receipt not generated",
     "I paid the hostel fee online three days ago but the portal still shows the fee as pending and no receipt was generated.",
     None, None, None),
    ("isha.kulkarni@example.com", "Duplicate ID card",
     "I lost my college ID card. How can I get a duplicate one?",
     "pooja.verma@example.com", "close",
     "Fill the duplicate ID card form at the administrative office with a passport photo and the fee receipt; the card is ready in about a week."),
    ("aarav.desai@example.com", "Internship letter for the summer",
     "I have an internship offer for June and the company needs a bonafide / no-objection letter from the college. Whom should I contact?",
     None, None, None),
]


def seed_demo_tickets() -> None:
    """Raise sample tickets as students; staff answer or close some. Skips subjects already raised."""
    print("Seeding sample help-desk tickets…")
    tokens: dict[str, str] = {}

    def auth(email: str) -> dict:
        if email not in tokens:
            tokens[email] = login(email, PASSWORD)
        return {"Authorization": f"Bearer {tokens[email]}"}

    counts = {"open": 0, "answered": 0, "closed": 0}
    for student, subject, description, staff, action, reply in DEMO_TICKETS:
        mine = requests.get(f"{API}/api/v1/helpdesk/tickets/mine", headers=auth(student))
        if mine.status_code == 200 and any(t["subject"] == subject for t in mine.json()):
            continue
        r = requests.post(f"{API}/api/v1/helpdesk/tickets", json={"subject": subject, "description": description},
                          headers=auth(student))
        if r.status_code != 201:
            print(f"  [!] Ticket not created: {subject} ({r.status_code}) {r.text[:120]}")
            continue
        ticket_id = r.json()["id"]
        if action:
            requests.post(f"{API}/api/v1/helpdesk/tickets/{ticket_id}/reply",
                          json={"reply": reply, "close": action == "close"}, headers=auth(staff))
        counts["closed" if action == "close" else "answered" if action else "open"] += 1
    print(f"[OK] Sample tickets: {counts['open']} open, {counts['answered']} answered, {counts['closed']} closed")


def print_summary(token: str) -> None:
    headers = {"Authorization": f"Bearer {token}"}
    def count_res(path):
        try:
            res = requests.get(f"{API}{path}", headers=headers)
            return len(res.json()) if res.status_code == 200 else "?"
        except Exception:
            return "?"

    print("\n" + "=" * 64)
    print("  DJSCE INSTITUTIONAL BRAIN — DEMO DATASET READY")
    print("=" * 64)
    print(f"  Meetings & Minutes:       {count_res('/api/v1/transcripts')}")
    print(f"  Action Commitments:       {count_res('/api/v1/commitments')}")
    print(f"  Institutional Procedures: {count_res('/api/v1/skills')}")
    print(f"  Active Feed Insights:     {count_res('/api/v1/insights/')}")
    print("\n  Access the Platform:      http://localhost:3000")
    print(f"  Demo Account:             {EMAIL} / {PASSWORD}")
    print("=" * 64)


def main() -> None:
    approve = "--approve" in sys.argv
    token = login()
    print("Ingesting DJSCE Synthetic Institutional Dataset…")
    posted = post_transcripts(token)
    post_documents(token)
    wait_for_processing(token, expected_meetings=posted)
    extract_skills(token, approve=approve)
    if "--no-demo-tickets" not in sys.argv:
        seed_demo_tickets()
    print_summary(token)


if __name__ == "__main__":
    main()
