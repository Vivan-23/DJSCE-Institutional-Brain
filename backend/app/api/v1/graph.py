import structlog
from fastapi import APIRouter, Depends

from app.api.v1.auth import get_current_user
from app.core.neo4j_db import neo4j_conn
from app.models.structured import User

log = structlog.get_logger()
router = APIRouter()


@router.get("/data")
def get_graph_data(current_user: User = Depends(get_current_user)):
    query = """
    MATCH (n)-[r]->(m)
    RETURN n, r, m
    LIMIT 200
    """
    try:
        results = neo4j_conn.execute_query(query)

        nodes_seen: dict[str, dict] = {}
        links: list[dict] = []

        for record in results:
            n = record["n"]
            m = record["m"]
            r = record["r"]

            for node in (n, m):
                nid = node.element_id
                if nid not in nodes_seen:
                    label = list(node.labels)[0] if node.labels else "Unknown"
                    nodes_seen[nid] = {
                        "id": nid,
                        "name": node.get("name") or node.get("email", "Unknown"),
                        "type": label,
                    }

            links.append(
                {
                    "source": n.element_id,
                    "target": m.element_id,
                    "type": r.type,
                }
            )

        return {"nodes": list(nodes_seen.values()), "links": links}

    except Exception as e:
        log.error("Graph query failed", error=str(e))
        return {"nodes": [], "links": [], "error": "Graph unavailable"}


@router.get("/stats")
def get_graph_stats(current_user: User = Depends(get_current_user)):
    try:
        employee_count = neo4j_conn.execute_query("MATCH (e:Employee) RETURN count(e) AS c")[0]["c"]
        project_count = neo4j_conn.execute_query("MATCH (p:Project) RETURN count(p) AS c")[0]["c"]
        rel_count = neo4j_conn.execute_query("MATCH ()-[r]->() RETURN count(r) AS c")[0]["c"]
        return {
            "employees": employee_count,
            "projects": project_count,
            "relationships": rel_count,
        }
    except Exception as e:
        log.error("Graph stats failed", error=str(e))
        return {"employees": 0, "projects": 0, "relationships": 0}
