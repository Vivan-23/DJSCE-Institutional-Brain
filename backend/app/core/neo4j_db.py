from neo4j import GraphDatabase
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

class Neo4jConnection:
    def __init__(self, uri, user, pwd):
        self.driver = GraphDatabase.driver(uri, auth=(user, pwd))
    
    def close(self):
        self.driver.close()
        
    def execute_query(self, query, parameters=None):
        with self.driver.session() as session:
            try:
                result = session.run(query, parameters)
                return [record for record in result]
            except Exception as e:
                logger.error(f"Neo4j query error: {e}")
                raise e

    def execute_write(self, query, parameters=None):
        """Run a write in a managed transaction: the driver retries transient errors
        (e.g. deadlocks when two Celery workers MERGE overlapping nodes)."""
        with self.driver.session() as session:
            return session.execute_write(lambda tx: list(tx.run(query, parameters)))

neo4j_conn = Neo4jConnection(settings.NEO4J_URI, settings.NEO4J_USER, settings.NEO4J_PASSWORD)
