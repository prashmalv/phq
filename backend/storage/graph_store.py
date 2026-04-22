"""
Neo4j graph store client.
Node types: Person, Organization, Location, Event, Source
Relationship types: MENTIONED_IN, LOCATED_IN, INVOLVED_IN, POSTED_BY, RELATED_TO
"""
from datetime import datetime
from typing import Optional

from loguru import logger
from neo4j import GraphDatabase

from backend.config import settings


SCHEMA_CYPHER = """
CREATE CONSTRAINT person_name IF NOT EXISTS FOR (p:Person) REQUIRE p.name IS UNIQUE;
CREATE CONSTRAINT org_name IF NOT EXISTS FOR (o:Organization) REQUIRE o.name IS UNIQUE;
CREATE CONSTRAINT location_name IF NOT EXISTS FOR (l:Location) REQUIRE l.name IS UNIQUE;
CREATE CONSTRAINT event_id IF NOT EXISTS FOR (e:Event) REQUIRE e.event_id IS UNIQUE;
CREATE INDEX event_type_idx IF NOT EXISTS FOR (e:Event) ON (e.event_type);
CREATE INDEX event_date_idx IF NOT EXISTS FOR (e:Event) ON (e.occurred_at);
CREATE INDEX location_district IF NOT EXISTS FOR (l:Location) ON (l.district);
"""


class GraphStore:
    def __init__(self):
        self.driver = GraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
        )
        self._ensure_schema()

    def _ensure_schema(self):
        with self.driver.session() as session:
            for stmt in SCHEMA_CYPHER.strip().split(";"):
                stmt = stmt.strip()
                if stmt:
                    try:
                        session.run(stmt)
                    except Exception as e:
                        logger.warning(f"Schema setup warning: {e}")
        logger.info("Neo4j schema initialized")

    def close(self):
        self.driver.close()

    # ─── Ingest enriched event ───────────────────────────────────────────────

    def ingest_event(self, event: dict) -> None:
        """
        Creates Event node + Person/Org/Location nodes and relationships
        from an enriched event dict.
        event must contain: event_id, content, event_type, occurred_at,
                            district, entities {persons, orgs, locations}
        """
        with self.driver.session() as session:
            session.execute_write(self._create_event_subgraph, event)

    @staticmethod
    def _create_event_subgraph(tx, event: dict):
        # Create Event node
        tx.run(
            """
            MERGE (e:Event {event_id: $event_id})
            SET e.content    = $content,
                e.event_type = $event_type,
                e.source     = $source,
                e.sentiment  = $sentiment,
                e.occurred_at = datetime($occurred_at),
                e.district   = $district,
                e.city       = $city,
                e.credibility = $credibility
            """,
            event_id=str(event["event_id"]),
            content=event["content"][:500],  # keep node payload small
            event_type=event.get("event_type", "unknown"),
            source=event.get("source"),
            sentiment=event.get("sentiment", 0),
            occurred_at=str(event.get("occurred_at")),
            district=event.get("district"),
            city=event.get("city"),
            credibility=event.get("credibility", 0.5),
        )

        # Create Location node and link
        if event.get("district"):
            tx.run(
                """
                MERGE (l:Location {name: $district})
                SET l.district = $district, l.state = $state
                WITH l
                MATCH (e:Event {event_id: $event_id})
                MERGE (e)-[:LOCATED_IN]->(l)
                """,
                district=event["district"],
                state=event.get("state", "Uttar Pradesh"),
                event_id=str(event["event_id"]),
            )

        entities = event.get("entities", {})

        # Create Person nodes
        for person_name in entities.get("persons", []):
            if person_name.strip():
                tx.run(
                    """
                    MERGE (p:Person {name: $name})
                    WITH p
                    MATCH (e:Event {event_id: $event_id})
                    MERGE (p)-[:MENTIONED_IN]->(e)
                    """,
                    name=person_name.strip(),
                    event_id=str(event["event_id"]),
                )

        # Create Organization nodes
        for org_name in entities.get("orgs", []):
            if org_name.strip():
                tx.run(
                    """
                    MERGE (o:Organization {name: $name})
                    WITH o
                    MATCH (e:Event {event_id: $event_id})
                    MERGE (o)-[:MENTIONED_IN]->(e)
                    """,
                    name=org_name.strip(),
                    event_id=str(event["event_id"]),
                )

    # ─── Query helpers ───────────────────────────────────────────────────────

    def events_by_person(self, person_name: str, limit: int = 20) -> list[dict]:
        """All events a person was mentioned in."""
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (p:Person {name: $name})-[:MENTIONED_IN]->(e:Event)
                RETURN e.event_id AS event_id, e.content AS content,
                       e.event_type AS event_type, e.occurred_at AS occurred_at,
                       e.district AS district
                ORDER BY e.occurred_at DESC
                LIMIT $limit
                """,
                name=person_name,
                limit=limit,
            )
            return [dict(r) for r in result]

    def events_in_location(
        self,
        district: str,
        event_type: Optional[str] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        limit: int = 50,
    ) -> list[dict]:
        where_clauses = ["l.district = $district"]
        params: dict = {"district": district, "limit": limit}

        if event_type:
            where_clauses.append("e.event_type = $event_type")
            params["event_type"] = event_type
        if from_date:
            where_clauses.append("e.occurred_at >= datetime($from_date)")
            params["from_date"] = from_date.isoformat()
        if to_date:
            where_clauses.append("e.occurred_at <= datetime($to_date)")
            params["to_date"] = to_date.isoformat()

        where_str = " AND ".join(where_clauses)
        with self.driver.session() as session:
            result = session.run(
                f"""
                MATCH (e:Event)-[:LOCATED_IN]->(l:Location)
                WHERE {where_str}
                RETURN e.event_id AS event_id, e.content AS content,
                       e.event_type AS event_type, e.occurred_at AS occurred_at,
                       e.sentiment AS sentiment, e.credibility AS credibility
                ORDER BY e.occurred_at DESC
                LIMIT $limit
                """,
                **params,
            )
            return [dict(r) for r in result]

    def person_event_location_path(self, person_name: str) -> list[dict]:
        """Trace a person's appearance across events and locations."""
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (p:Person {name: $name})-[:MENTIONED_IN]->(e:Event)-[:LOCATED_IN]->(l:Location)
                RETURN p.name AS person, e.event_type AS event_type,
                       e.occurred_at AS occurred_at, l.district AS district
                ORDER BY e.occurred_at DESC
                LIMIT 30
                """,
                name=person_name,
            )
            return [dict(r) for r in result]

    def co_occurring_persons(self, person_name: str) -> list[dict]:
        """Find other persons mentioned in the same events."""
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (p1:Person {name: $name})-[:MENTIONED_IN]->(e:Event)
                      <-[:MENTIONED_IN]-(p2:Person)
                WHERE p2.name <> $name
                RETURN p2.name AS co_person, COUNT(e) AS shared_events
                ORDER BY shared_events DESC
                LIMIT 10
                """,
                name=person_name,
            )
            return [dict(r) for r in result]
