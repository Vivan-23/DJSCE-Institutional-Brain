"""Graph API shaping: department scope, de-duplication, degree, neighbourhood endpoint."""
from unittest.mock import patch

from tests.helpers import register


class FakeNode(dict):
    def __init__(self, eid, label, **props):
        super().__init__(props)
        self.element_id = eid
        self.labels = {label}


class FakeRel:
    def __init__(self, type_):
        self.type = type_


PERSON = FakeNode("p1", "Employee", name="Pooja Verma")
CE_MEET = FakeNode("m1", "Meeting", name="CE sync", department="CE")
ALL_MEET = FakeNode("m2", "Meeting", name="IQAC review", department="all")
IT_DOC = FakeNode("d1", "Document", name="it.txt", department="IT", visibility="internal")
BODY = FakeNode("b1", "Project", name="IQAC")

RECORDS = [
    {"n": PERSON, "r": FakeRel("ATTENDED"), "m": CE_MEET},
    {"n": PERSON, "r": FakeRel("ATTENDED"), "m": ALL_MEET},
    {"n": PERSON, "r": FakeRel("ATTENDED"), "m": ALL_MEET},  # duplicate
    {"n": ALL_MEET, "r": FakeRel("MENTIONS"), "m": BODY},
    {"n": IT_DOC, "r": FakeRel("MENTIONS"), "m": BODY},
]


class TestBuildGraph:
    def test_unscoped_keeps_all_and_dedupes(self):
        from app.api.v1.graph import build_graph

        g = build_graph(RECORDS, None)
        assert {n["id"] for n in g["nodes"]} == {"p1", "m1", "m2", "d1", "b1"}
        assert len(g["links"]) == 4
        assert next(n for n in g["nodes"] if n["id"] == "b1")["degree"] == 2

    def test_scope_removes_other_departments(self):
        from app.api.v1.graph import build_graph

        g = build_graph(RECORDS, ["IT", "all"])
        ids = {n["id"] for n in g["nodes"]}
        assert "m1" not in ids and {"m2", "d1", "p1", "b1"} <= ids
        assert all("m1" not in (link["source"], link["target"]) for link in g["links"])


class TestEndpoints:
    def test_faculty_graph_is_scoped(self, client):
        token = register(client, "graph-it@test.com", role="employee", department="IT")
        with patch("app.api.v1.graph.neo4j_conn") as conn:
            conn.execute_query.return_value = RECORDS
            body = client.get("/api/v1/graph/data", headers={"Authorization": f"Bearer {token}"}).json()
        assert "m1" not in {n["id"] for n in body["nodes"]} and body["truncated"] is False

    def test_truncation_flag(self, client):
        token = register(client, "graph-coord@test.com", role="manager")
        with patch("app.api.v1.graph.neo4j_conn") as conn:
            conn.execute_query.return_value = RECORDS
            body = client.get("/api/v1/graph/data?limit=2", headers={"Authorization": f"Bearer {token}"}).json()
        assert body["truncated"] is True and len(body["links"]) <= 2

    def test_neighbors_hidden_node_is_404(self, client):
        token = register(client, "graph-it2@test.com", role="employee", department="IT")
        with patch("app.api.v1.graph.neo4j_conn") as conn:
            conn.execute_query.return_value = [RECORDS[0]]  # only the CE meeting's edge
            res = client.get("/api/v1/graph/neighbors/m1", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 404

    def test_neighbors_ok(self, client):
        token = register(client, "graph-coord2@test.com", role="manager")
        with patch("app.api.v1.graph.neo4j_conn") as conn:
            conn.execute_query.return_value = RECORDS[:2]
            body = client.get("/api/v1/graph/neighbors/p1?depth=2", headers={"Authorization": f"Bearer {token}"}).json()
        assert {n["id"] for n in body["nodes"]} == {"p1", "m1", "m2"}

    def test_students_refused(self, client):
        token = register(client, "graph-stu@test.com", role="student")
        assert client.get("/api/v1/graph/data", headers={"Authorization": f"Bearer {token}"}).status_code == 403
