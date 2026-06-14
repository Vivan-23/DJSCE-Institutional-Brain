from app.core.neo4j_db import neo4j_conn

class GraphService:
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

graph_service = GraphService()
