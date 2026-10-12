"""
DJSCE Institutional Brain — DEMO Institutional Data Loader.

Ingests synthetic institutional records (committee transcripts, SOPs, curriculum docs)
through the application pipeline:
  1. Authenticates as the demo admin (from company.yaml).
  2. Submits synthetic committee meeting transcripts to POST /api/v1/transcripts.
  3. Uploads reference documents and SOPs to POST /api/v1/ingest/file for
     the ChromaDB vector store and Neo4j institutional relationship graph.
  4. Waits for Celery background processing.
  5. Optionally triggers procedure extraction and approval.

Usage:
  python ingest_institutional.py              # Ingests all 4 scenarios & reference documents
  python ingest_institutional.py --approve    # Also auto-approves extracted procedures
"""
import os
import sys
import time
import requests

API = os.environ.get("API_URL", "http://localhost:8001")
EMAIL = os.environ.get("DEMO_EMAIL", "demo@example.com")
PASSWORD = os.environ.get("DEMO_PASSWORD", "demo123")
FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mock_institutional_data")

PROCESS_WAIT_SECONDS = 180


def _title_from(filename: str) -> str:
    base = os.path.splitext(filename)[0].replace("_", " ").strip()
    # Format readable academic title
    words = [w.capitalize() for w in base.split()]
    return " ".join(words)


def login() -> str:
    r = requests.post(f"{API}/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD})
    if r.status_code != 200:
        # Fallback to legacy demo email if database was already seeded with companybrain.ai
        alt_email = "demo@companybrain.ai"
        r2 = requests.post(f"{API}/api/v1/auth/login", json={"email": alt_email, "password": PASSWORD})
        if r2.status_code == 200:
            print(f"✓ Logged in as {alt_email}")
            return r2.json()["access_token"]
        sys.exit(f"Login failed ({r.status_code}): {r.text}\nIs backend running and is {EMAIL} seeded in company.yaml?")
    print(f"✓ Logged in as {EMAIL}")
    return r.json()["access_token"]


def post_transcripts(token: str) -> int:
    headers = {"Authorization": f"Bearer {token}"}
    posted = 0
    transcript_files = [
        f for f in sorted(os.listdir(FOLDER))
        if f.endswith(".txt") and ("scenario" in f or "review" in f or "sync" in f)
    ]

    for filename in transcript_files:
        with open(os.path.join(FOLDER, filename), "r", encoding="utf-8") as fh:
            text = fh.read()
        r = requests.post(
            f"{API}/api/v1/transcripts",
            json={"title": _title_from(filename), "transcript": text, "source": "demo_institutional"},
            headers=headers,
        )
        if r.status_code == 202:
            posted += 1
            print(f"  ✓ Queued meeting transcript: {filename}")
        else:
            print(f"  ! Transcript rejected: {filename} ({r.status_code}) {r.text[:120]}")
    print(f"✓ Queued {posted} institutional transcript(s)")
    return posted


def post_documents(token: str) -> int:
    """Send reference documents and SOPs through /api/v1/ingest/file for Vector + Neo4j Graph."""
    headers = {"Authorization": f"Bearer {token}"}
    sent = 0
    doc_files = [f for f in sorted(os.listdir(FOLDER)) if f.endswith(".txt")]

    for filename in doc_files:
        with open(os.path.join(FOLDER, filename), "rb") as fh:
            r = requests.post(
                f"{API}/api/v1/ingest/file",
                files={"file": (filename, fh, "text/plain")},
                headers=headers,
            )
        if r.status_code in (200, 202):
            sent += 1
            print(f"  ✓ Ingested document for graph: {filename}")
        else:
            print(f"  ! Document upload failed: {filename} ({r.status_code})")
    print(f"✓ Ingested {sent} document(s) for RAG and Knowledge Graph")
    return sent


def wait_for_processing(token: str, expected_meetings: int) -> None:
    headers = {"Authorization": f"Bearer {token}"}
    print("… Waiting for worker to process transcripts", end="", flush=True)
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
        print(f"  ! Procedure extraction notice ({r.status_code}): {r.text[:140]}")
        return
    created = r.json().get("candidates_created", 0)
    print(f"✓ Synthesized {created} candidate institutional procedure(s)")

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
    print(f"✓ Approved {approved} procedure(s) for formal SKILL.md export")


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
    print_summary(token)


if __name__ == "__main__":
    main()
