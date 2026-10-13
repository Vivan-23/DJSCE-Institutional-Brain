"""
Knowledge graph API.

``/data`` returns the whole graph (bounded) and ``/neighbors/{id}`` a node's neighbourhood,
for large graphs where drawing everything is unreadable. Both apply the caller's
department scope: Document and Meeting nodes carry a ``department``, and nodes outside
the scope are removed together with their edges (people and bodies remain only where
an allowed meeting or document still links to them).
"""
from typing import Any, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.v1.auth import department_scope, require_staff
from app.core.neo4j_db import neo4j_conn
from app.models.structured import User

log = structlog.get_logger()
router = APIRouter()

_SCOPED_LABELS = {"Document", "Meeting"}


def _node(node) -> dict[str, Any]:
    label = list(node.labels)[0] if node.labels else "Unknown"
    return {
        "id": node.element_id,
        "name": node.get("name") or node.get("email", "Unknown"),
        "type": label,
        "department": node.get("department"),
        "visibility": node.get("visibility"),
    }


def build_graph(records, scope: Optional[list[str]]) -> dict[str, Any]:
    """Turn (n, r, m) records into {nodes, links}, dropping out-of-scope nodes and orphans."""
    nodes: dict[str, dict] = {}
    links: list[dict] = []
    seen_links: set[tuple] = set()

    def allowed(node: dict) -> bool:
        if scope is None or node["type"] not in _SCOPED_LABELS:
            return True
        return (node["department"] or "all") in scope

    for record in records:
        n, r, m = _node(record["n"]), record["r"], _node(record["m"])
        if not (allowed(n) and allowed(m)):
            continue
        key = (n["id"], m["id"], r.type)
        if key in seen_links:
            continue
        seen_links.add(key)
        nodes.setdefault(n["id"], n)
        nodes.setdefault(m["id"], m)
        links.append({"source": n["id"], "target": m["id"], "type": r.type})

    degree: dict[str, int] = {}
    for link in links:
        degree[link["source"]] = degree.get(link["source"], 0) + 1
        degree[link["target"]] = degree.get(link["target"], 0) + 1
    for nid, node in nodes.items():
        node["degree"] = degree.get(nid, 0)
    return {"nodes": list(nodes.values()), "links": links}


@router.get("/data")
def get_graph_data(
    limit: int = Query(2000, ge=1, le=10_000),
    current_user: User = Depends(require_staff),
):
    """Every relationship up to ``limit`` (scoped). ``truncated`` tells the UI to switch to neighbourhoods."""
    try:
        records = neo4j_conn.execute_query("MATCH (n)-[r]->(m) RETURN n, r, m LIMIT $limit", {"limit": limit + 1})
    except Exception as e:
        log.error("Graph query failed", error=str(e))
        return {"nodes": [], "links": [], "truncated": False, "error": "Graph unavailable"}
    graph = build_graph(records[:limit], department_scope(current_user))
    return {**graph, "truncated": len(records) > limit}


@router.get("/neighbors/{node_id}")
def get_neighbors(
    node_id: str,
    depth: int = Query(1, ge=1, le=2),
    current_user: User = Depends(require_staff),
):
    """The node and everything within ``depth`` hops (max 500 relationships), scoped."""
    try:
        records = neo4j_conn.execute_query(
            f"""
            MATCH (c) WHERE elementId(c) = $id
            MATCH p = (c)-[*1..{depth}]-()
            UNWIND relationships(p) AS r
            WITH DISTINCT r
            RETURN startNode(r) AS n, r, endNode(r) AS m
            LIMIT 500
            """,
            {"id": node_id},
        )
    except Exception as e:
        log.error("Graph neighbourhood query failed", error=str(e))
        raise HTTPException(status_code=503, detail="Graph unavailable")
    graph = build_graph(records, department_scope(current_user))
    if not any(n["id"] == node_id for n in graph["nodes"]):
        raise HTTPException(status_code=404, detail="Node not found")
    return graph


@router.get("/stats")
def get_graph_stats(current_user: User = Depends(require_staff)):
    try:
        employee_count = neo4j_conn.execute_query("MATCH (e:Employee) RETURN count(e) AS c")[0]["c"]
        project_count = neo4j_conn.execute_query("MATCH (p:Project) RETURN count(p) AS c")[0]["c"]
        meeting_count = neo4j_conn.execute_query("MATCH (m:Meeting) RETURN count(m) AS c")[0]["c"]
        document_count = neo4j_conn.execute_query("MATCH (d:Document) RETURN count(d) AS c")[0]["c"]
        rel_count = neo4j_conn.execute_query("MATCH ()-[r]->() RETURN count(r) AS c")[0]["c"]
        return {
            "employees": employee_count,
            "projects": project_count,
            "meetings": meeting_count,
            "documents": document_count,
            "relationships": rel_count,
        }
    except Exception as e:
        log.error("Graph stats failed", error=str(e))
        return {"employees": 0, "projects": 0, "meetings": 0, "documents": 0, "relationships": 0}
