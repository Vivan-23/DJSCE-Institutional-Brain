"""
Knowledge-graph writes (Neo4j).

Node kinds (labels kept from the original schema so existing queries still work):
  :Employee  — a person (faculty, staff, named official), keyed by a derived email
  :Project   — a body or initiative (committee, department, lab, programme)
  :Document  — an uploaded document, keyed by filename
  :Meeting   — an ingested meeting, keyed by title

Edges (every node is reachable from its source, so the graph page has something to draw):
  (Document)-[:MENTIONS]->(Employee|Project)
  (Employee)-[:ATTENDED]->(Meeting)
  (Meeting)-[:MENTIONS]->(Project)
  (Employee)-[:WORKS_ON]->(Project)   — explicit assignments only (none are inferred)

Entity text from NER is noisy, so it is cleaned here before it reaches the graph.
"""
import re
from typing import Iterable, Optional

from app.core.neo4j_db import neo4j_conn

_HONORIFIC = r"(?:Dr|Prof|Mr|Mrs|Ms|Shri|Smt)\.?"
_LEADING_TITLES = re.compile(rf"^(?:{_HONORIFIC}\s*(?:\((?:Mrs|Ms|Mr)\.?\)\s*)?)+", re.I)


def clean_entity(text: str) -> Optional[str]:
    """Normalize an NER span; reject fragments that span lines, read like sentences or are cut off."""
    if not text or "\n" in text:
        return None
    t = " ".join(text.split())
    t = re.sub(r"^[^\w(]+", "", t)  # leading bullets / '?' artefacts
    t = re.sub(r"^(?:the|a|an)\s+", "", t, flags=re.I).strip(" -:,.;")
    if t.count("(") != t.count(")") or re.search(r"\b(?:and|of|&)$", t, re.I):
        return None  # truncated span, e.g. "Data Mining and"
    if len(t) < 3 or len(t) > 60 or len(t.split()) > 6:
        return None
    return t


# A "body" is an institutional unit: a committee, council, cell, board, department, lab,
# office or chapter, or a well-known acronym. Course titles, companies and tools are not.
_BODY_HEADS = re.compile(
    r"\b(?:committee|council|cell|board|department|dept|laborator(?:y|ies)|lab|office|chapter|club|"
    r"society|institute|college|university|commission|desk|centre|center)\b",
    re.I,
)
_BODY_ACRONYMS = {"IQAC", "NBA", "NAAC", "AICTE", "UGC", "CSI", "DJ-CSI", "INIT-AI", "IIT", "CDAC", "DJSCE"}
_BODY_ALIASES = {
    "djcsi": "DJ-CSI",
    "j. sanghvi college of engineering": "DJSCE",
    "d.j. sanghvi": "DJSCE",
    "dwarkadas j. sanghvi college of engineering": "DJSCE",
    "national board of accreditation": "NBA",
}


def body_name(text: str) -> Optional[str]:
    """An institutional body named by an NER span, normalized, or None."""
    t = clean_entity(text)
    if not t:
        return None
    t = _BODY_ALIASES.get(t.lower(), t)
    if t.upper() in _BODY_ACRONYMS:
        return t.upper()
    if re.fullmatch(r"(?:head of )?department", t, re.I) or re.search(r"\bcourses?\b", t, re.I):
        return None  # a role or a course title, not a body
    return t if _BODY_HEADS.search(t) else None


def person_name(name: str) -> str:
    """'Dr. (Mrs.) Meera Narvekar' → 'Meera Narvekar' (titles removed, whitespace collapsed)."""
    return _LEADING_TITLES.sub("", " ".join(name.split())).strip()


def is_credible_person(name: str, text: str, known: Iterable[str] = ()) -> bool:
    """Accept a PERSON span only with evidence: a roster/speaker match or an honorific before it.

    spaCy tags many course and tool names ("Machine Learning", "GB RAM") as people;
    requiring evidence keeps the graph to real (synthetic) personnel.
    """
    bare = person_name(name)
    tokens = bare.split()
    if len(tokens) < 2 or any(not tok[:1].isupper() or tok.isupper() for tok in tokens):
        return False
    if bare.lower() in {person_name(k).lower() for k in known}:
        return True
    return re.search(rf"{_HONORIFIC}\s*(?:\(\w+\.?\)\s*)?{re.escape(bare)}", text, re.I) is not None


def person_key(name: str, domain: str) -> str:
    return person_name(name).lower().replace(" ", ".") + "@" + domain


def graph_entities(text: str, extracted: dict, known_people: Iterable[str] = ()) -> tuple[list[dict], list[str]]:
    """Turn raw NER output into clean graph rows: ([{name, email}], [body names])."""
    from app.core.institution_config import get_institution_config

    cfg = get_institution_config()
    roster = [m.name for m in cfg.members]  # speakers get no free pass: they need the same evidence
    people: dict[str, dict] = {}
    for raw in list(extracted.get("persons") or []) + list(known_people):
        name = clean_entity(raw)
        if name and is_credible_person(name, text, roster):
            bare = person_name(name)
            people.setdefault(bare.lower(), {"name": bare, "email": person_key(bare, cfg.email_domain)})
    names = {p["name"].lower() for p in people.values()}
    # Bodies: NER organisations that name an institutional unit, plus the help-desk offices
    # (institution.yaml routed_to) whenever the text names them.
    found = {b for b in (body_name(o) for o in extracted.get("orgs") or []) if b}
    offices = {part for c in cfg.helpdesk_categories for part in re.split(r"\s*/\s*", c.routed_to)}
    for phrase in (offices - {"", "Help Desk"}) | {"Academic Council", "Board of Studies"}:
        if re.search(r"\b" + re.escape(phrase) + r"\b", text, re.I):
            found.add(phrase)
    bodies = sorted(b for b in found if b.lower() not in names)
    return list(people.values()), bodies


class GraphService:
    _constraints_ready = False

    def _ensure_constraints(self) -> None:
        """Uniqueness constraints make concurrent MERGEs (two Celery workers) safe: no duplicate nodes."""
        if GraphService._constraints_ready:
            return
        for label, prop in (("Employee", "email"), ("Project", "name"), ("Document", "name"), ("Meeting", "name")):
            neo4j_conn.execute_schema(
                f"CREATE CONSTRAINT {label.lower()}_{prop}_unique IF NOT EXISTS "
                f"FOR (n:{label}) REQUIRE n.{prop} IS UNIQUE"
            )
        GraphService._constraints_ready = True

    def upsert_employee(self, name: str, email: str, role: str = "employee"):
        query = """
        MERGE (e:Employee {email: $email})
        ON CREATE SET e.name = $name, e.role = $role, e.id = randomUUID()
        ON MATCH SET e.name = $name
        RETURN e
        """
        return neo4j_conn.execute_query(query, {"email": email, "name": name, "role": role})

    def upsert_project(self, project_name: str, status: str):
        query = """
        MERGE (p:Project {name: $name})
        ON CREATE SET p.status = $status, p.id = randomUUID()
        ON MATCH SET p.status = $status
        RETURN p
        """
        return neo4j_conn.execute_query(query, {"name": project_name, "status": status})

    def assign_employee_to_project(self, email: str, project_name: str):
        query = """
        MATCH (e:Employee {email: $email})
        MATCH (p:Project {name: $project_name})
        MERGE (e)-[r:WORKS_ON]->(p)
        RETURN r
        """
        return neo4j_conn.execute_query(query, {"email": email, "project_name": project_name})

    def record_document(
        self, filename: str, visibility: str, people: list[dict], bodies: list[str], department: str = "all"
    ) -> None:
        """One document node + MENTIONS edges to every person and body found in it."""
        self._ensure_constraints()
        neo4j_conn.execute_write(
            """
            MERGE (d:Document {name: $filename})
            SET d.visibility = $visibility, d.department = $department
            FOREACH (person IN $people |
              MERGE (e:Employee {email: person.email})
              ON CREATE SET e.name = person.name, e.id = randomUUID()
              MERGE (d)-[:MENTIONS]->(e))
            FOREACH (body IN $bodies |
              MERGE (p:Project {name: body})
              ON CREATE SET p.status = 'active', p.id = randomUUID()
              MERGE (d)-[:MENTIONS]->(p))
            """,
            # Sorted so concurrent writers lock nodes in the same order (avoids deadlocks).
            {"filename": filename, "visibility": visibility, "department": department,
             "people": sorted(people, key=lambda p: p["email"]), "bodies": sorted(bodies or [])},
        )

    def record_meeting(self, title: str, people: list[dict], bodies: list[str], department: str = "all") -> None:
        """One meeting node; ATTENDED edges from participants, MENTIONS edges to bodies discussed."""
        self._ensure_constraints()
        neo4j_conn.execute_write(
            """
            MERGE (m:Meeting {name: $title})
            SET m.department = $department
            FOREACH (person IN $people |
              MERGE (e:Employee {email: person.email})
              ON CREATE SET e.name = person.name, e.id = randomUUID()
              MERGE (e)-[:ATTENDED]->(m))
            FOREACH (body IN $bodies |
              MERGE (p:Project {name: body})
              ON CREATE SET p.status = 'active', p.id = randomUUID()
              MERGE (m)-[:MENTIONS]->(p))
            """,
            {"title": title, "department": department,
             "people": sorted(people, key=lambda p: p["email"]), "bodies": sorted(bodies or [])},
        )


graph_service = GraphService()
