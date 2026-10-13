import logging
import time

from neo4j import GraphDatabase
from neo4j.exceptions import TransientError

from app.core.config import settings

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

    def execute_schema(self, query, attempts: int = 5):
        """Run a schema command (e.g. CREATE CONSTRAINT), retrying transient errors: two
        workers creating constraints at once deadlock on the schema lock."""
        for i in range(attempts):
            try:
                with self.driver.session() as session:
                    return list(session.run(query))
            except TransientError:
                if i == attempts - 1:
                    raise
                time.sleep(0.5 * 2 ** i)

neo4j_conn = Neo4jConnection(settings.NEO4J_URI, settings.NEO4J_USER, settings.NEO4J_PASSWORD)
