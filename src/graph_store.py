"""
Temporal graph memory layer.
Facts are stored as (:Subject)-[:HAS_MEMORY]->(:Memory) nodes with valid-time
fields. Corrections close the prior fact's valid_to and link supersedes.
"""
from typing import List, Optional
from neo4j import GraphDatabase
from src.config import settings
from src.models import MemoryFact, now_iso


class GraphStore:
    def __init__(self):
        self.driver = GraphDatabase.driver(
            settings.NEO4J_URI, auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
        )
        self._ensure_constraints()

    def close(self):
        self.driver.close()

    def _ensure_constraints(self):
        with self.driver.session() as s:
            s.run(
                "CREATE CONSTRAINT memory_id_unique IF NOT EXISTS "
                "FOR (m:Memory) REQUIRE m.memory_id IS UNIQUE"
            )
            s.run(
                "CREATE CONSTRAINT subject_id_unique IF NOT EXISTS "
                "FOR (s:Subject) REQUIRE s.subject_id IS UNIQUE"
            )

    def upsert_memory(self, fact: MemoryFact) -> None:
        """Idempotent write of a memory fact, linked to its subject and entities."""
        with self.driver.session() as s:
            s.run(
                """
                MERGE (subj:Subject {subject_id: $subject_id})
                MERGE (m:Memory {memory_id: $memory_id})
                SET m.subject_id = $subject_id,
                    m.memory_type = $memory_type,
                    m.fact_text = $fact_text,
                    m.confidence = $confidence,
                    m.policy_class = $policy_class,
                    m.source_event_id = $source_event_id,
                    m.valid_from = $valid_from,
                    m.valid_to = $valid_to,
                    m.status = $status,
                    m.superseded_by = $superseded_by
                MERGE (subj)-[:HAS_MEMORY]->(m)
                WITH m
                UNWIND $entities AS ent
                MERGE (e:Entity {name: ent})
                MERGE (m)-[:ABOUT]->(e)
                """,
                subject_id=fact.subject_id,
                memory_id=fact.memory_id,
                memory_type=fact.memory_type.value,
                fact_text=fact.fact_text,
                confidence=fact.confidence,
                policy_class=fact.policy_class.value,
                source_event_id=fact.source_event_id,
                valid_from=fact.valid_from,
                valid_to=fact.valid_to,
                status=fact.status,
                superseded_by=fact.superseded_by,
                entities=fact.entities,
            )

    def supersede_memory(self, old_memory_id: str, new_memory_id: str) -> None:
        """Close out an old fact's valid-time window when a correction arrives."""
        with self.driver.session() as s:
            s.run(
                """
                MATCH (m:Memory {memory_id: $old_id})
                SET m.status = 'superseded',
                    m.valid_to = $now,
                    m.superseded_by = $new_id
                """,
                old_id=old_memory_id,
                new_id=new_memory_id,
                now=now_iso(),
            )

    def delete_memory(self, memory_id: str) -> None:
        with self.driver.session() as s:
            s.run(
                "MATCH (m:Memory {memory_id: $id}) SET m.status = 'deleted'",
                id=memory_id,
            )

    def hard_delete_memory(self, memory_id: str) -> None:
        with self.driver.session() as s:
            s.run("MATCH (m:Memory {memory_id: $id}) DETACH DELETE m", id=memory_id)

    def get_active_memories(self, subject_id: str, limit: int = 50) -> List[dict]:
        """Relational candidate generation: active, non-expired facts for a subject."""
        with self.driver.session() as s:
            result = s.run(
                """
                MATCH (:Subject {subject_id: $subject_id})-[:HAS_MEMORY]->(m:Memory)
                WHERE m.status = 'active' AND m.policy_class <> 'blocked'
                RETURN m
                ORDER BY m.confidence DESC
                LIMIT $limit
                """,
                subject_id=subject_id,
                limit=limit,
            )
            return [dict(r["m"]) for r in result]

    def find_similar_fact_by_entities(
        self, subject_id: str, entities: List[str]
    ) -> Optional[dict]:
        """Used for contradiction/correction detection before writing a new fact."""
        if not entities:
            return None
        with self.driver.session() as s:
            result = s.run(
                """
                MATCH (:Subject {subject_id: $subject_id})-[:HAS_MEMORY]->(m:Memory)-[:ABOUT]->(e:Entity)
                WHERE m.status = 'active' AND e.name IN $entities
                RETURN m LIMIT 1
                """,
                subject_id=subject_id,
                entities=entities,
            )
            record = result.single()
            return dict(record["m"]) if record else None
