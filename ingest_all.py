"""
Company Brain — DEMO data loader.

Loads the bundled sample meetings through the *real* product pipeline so a demo
lands on the things that sell it: auto-extracted commitments, a populated org +
graph, and synthesized, agent-consumable skill files.

What it does:
  1. Logs in as the demo admin (from company.yaml).
  2. Posts the curated scenario transcripts (refunds + incident response) and a
     sample of the generic meeting notes to POST /api/v1/transcripts.
  3. Posts a subset to POST /api/v1/ingest/file so the Neo4j Graph Map populates.
  4. Waits for the Celery worker to finish, then triggers skill extraction.
  5. Optionally auto-approves the synthesized skills so the SKILL.md export works
     immediately (otherwise approve them in the UI to show the review flow).

Prereqs: the stack is running (`docker compose up`) and GROQ_API_KEY is set so
the extraction LLM is available.

Usage:
  python ingest_all.py              # curated scenarios + ~25 sample notes
  python ingest_all.py --all        # every file in mock_company_data/
  python ingest_all.py --approve    # also auto-approve extracted skills
  python ingest_all.py --quick      # only the curated scenario transcripts
"""
import os
import sys
import time

import requests

API = os.environ.get("API_URL", "http://localhost:8001")
EMAIL = os.environ.get("DEMO_EMAIL", "demo@companybrain.ai")
PASSWORD = os.environ.get("DEMO_PASSWORD", "demo123")
FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mock_company_data")

GENERIC_SAMPLE_LIMIT = 25       # generic notes to load by default (keeps it fast)
GRAPH_INGEST_LIMIT = 30         # files also sent to /ingest for the graph
PROCESS_WAIT_SECONDS = 420      # max wait for the worker to drain the queue


def _title_from(filename: str) -> str:
    return os.path.splitext(filename)[0].replace("_", " ").replace("demo ", "").strip()


def login() -> str:
    r = requests.post(f"{API}/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD})
    if r.status_code != 200:
        sys.exit(f"Login failed ({r.status_code}): {r.text}\nIs the backend up and is {EMAIL} seeded?")
    print(f"✓ Logged in as {EMAIL}")
    return r.json()["access_token"]


def pick_files(mode: str) -> list[str]:
    if not os.path.isdir(FOLDER):
        sys.exit(f"Sample data folder not found: {FOLDER}")
    everything = sorted(f for f in os.listdir(FOLDER) if f.endswith(".txt"))
    curated = [f for f in everything if f.startswith("demo_")]
    generic = [f for f in everything if not f.startswith("demo_")]

    if mode == "quick":
        return curated
    if mode == "all":
        return curated + generic
    return curated + generic[:GENERIC_SAMPLE_LIMIT]


def post_transcripts(token: str, files: list[str]) -> int:
    headers = {"Authorization": f"Bearer {token}"}
    posted = 0
    for filename in files:
        with open(os.path.join(FOLDER, filename), "r", encoding="utf-8") as fh:
            text = fh.read()
        r = requests.post(
            f"{API}/api/v1/transcripts",
            json={"title": _title_from(filename), "transcript": text, "source": "demo"},
            headers=headers,
        )
        if r.status_code == 202:
            posted += 1
        else:
            print(f"  ! transcript rejected: {filename} ({r.status_code}) {r.text[:120]}")
    print(f"✓ Queued {posted}/{len(files)} transcripts")
    return posted


def post_graph_docs(token: str, files: list[str]) -> int:
    """Send a subset through the document pipeline so the Neo4j graph populates."""
    headers = {"Authorization": f"Bearer {token}"}
    sent = 0
    for filename in files[:GRAPH_INGEST_LIMIT]:
        with open(os.path.join(FOLDER, filename), "rb") as fh:
            r = requests.post(
                f"{API}/api/v1/ingest/file",
                files={"file": (filename, fh, "text/plain")},
                headers=headers,
            )
        if r.status_code in (200, 202):
            sent += 1
    print(f"✓ Queued {sent} documents for the graph")
    return sent


def wait_for_processing(token: str, expected_meetings: int) -> None:
    headers = {"Authorization": f"Bearer {token}"}
    print("… waiting for the worker to process transcripts", end="", flush=True)
    deadline = time.time() + PROCESS_WAIT_SECONDS
    stable = 0
    last = -1
    while time.time() < deadline:
        time.sleep(6)
        print(".", end="", flush=True)
        r = requests.get(f"{API}/api/v1/transcripts", headers=headers)
        if r.status_code != 200:
            continue
        count = len(r.json())
        if count >= expected_meetings:
            break
        stable = stable + 1 if count == last else 0
        last = count
        if stable >= 8:  # no progress for ~48s — worker likely idle/done
            break
    print(f"  done (meetings: {last if last >= 0 else '?'})")


def extract_skills(token: str, approve: bool) -> None:
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.post(f"{API}/api/v1/skills/extract", headers=headers)
    if r.status_code != 202:
        print(f"  ! skill extraction failed ({r.status_code}): {r.text[:160]}")
        return
    created = r.json().get("candidates_created", 0)
    print(f"✓ Synthesized {created} candidate skill(s)")

    if not approve:
        return
    skills = requests.get(f"{API}/api/v1/skills", headers=headers).json()
    approved = 0
    for s in skills:
        if s.get("status") == "draft":
            a = requests.post(f"{API}/api/v1/skills/{s['id']}/approve", headers=headers)
            if a.status_code == 200:
                approved += 1
    print(f"✓ Approved {approved} skill(s) — their SKILL.md files now export")


def summary(token: str) -> None:
    headers = {"Authorization": f"Bearer {token}"}
    def n(path):
        r = requests.get(f"{API}{path}", headers=headers)
        return len(r.json()) if r.status_code == 200 else "?"

    print("\n" + "=" * 56)
    print("  DEMO DATA LOADED")
    print("=" * 56)
    print(f"  Meetings:     {n('/api/v1/transcripts')}")
    print(f"  Commitments:  {n('/api/v1/commitments')}")
    print(f"  Skills:       {n('/api/v1/skills')}")
    print("\n  Open the app:   http://localhost:3000")
    print(f"  Sign in:        {EMAIL} / {PASSWORD}")
    print("  Try:  Meetings → Commitments → Skills (review & approve) →")
    print("        open an approved skill and view its exported SKILL.md file.")
    print("=" * 56)


def main() -> None:
    args = set(sys.argv[1:])
    mode = "quick" if "--quick" in args else "all" if "--all" in args else "default"
    approve = "--approve" in args

    token = login()
    files = pick_files(mode)
    print(f"Loading {len(files)} sample meeting file(s) [{mode}] …")

    posted = post_transcripts(token, files)
    post_graph_docs(token, files)
    wait_for_processing(token, expected_meetings=posted)
    extract_skills(token, approve=approve)
    summary(token)


if __name__ == "__main__":
    main()
