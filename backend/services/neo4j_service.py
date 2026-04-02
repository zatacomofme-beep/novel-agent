from __future__ import annotations

import uuid
from typing import Any, Optional

from core.config import get_settings


class Neo4jService:
    def __init__(self) -> None:
        settings = get_settings()
        self._url = getattr(settings, "neo4j_url", "bolt://localhost:7687")
        self._auth = getattr(settings, "neo4j_auth", ("neo4j", "password"))
        self._client: Any | None = None
        self._available = False

    async def _get_client(self) -> Any | None:
        if self._client is not None:
            return self._client
        try:
            from neo4j import AsyncGraphDatabase
            driver = AsyncGraphDatabase.driver(
                self._url,
                auth=self._auth,
            )
            await driver.verify_connectivity()
            self._client = driver
            self._available = True
            return driver
        except Exception:
            self._available = False
            return None

    async def close(self) -> None:
        if self._client:
            await self._client.close()
            self._client = None
            self._available = False

    async def create_event_node(
        self,
        project_id: uuid.UUID,
        chapter: int,
        name: str,
        summary: str,
        event_type: str = "generic",
    ) -> dict[str, Any] | None:
        driver = await self._get_client()
        if not driver:
            return None
        node_id = str(uuid.uuid4())
        cypher = """
        MERGE (p:Project {id: $project_id})
        CREATE (e:Event {
            id: $node_id,
            name: $name,
            summary: $summary,
            chapter: $chapter,
            event_type: $event_type,
            project_id: $project_id,
            created_at: datetime()
        })
        CREATE (e)-[:HAPPENED_IN]->(p)
        RETURN e.id AS id, e.name AS name
        """
        try:
            async with driver.session() as session:
                result = await session.run(
                    cypher,
                    project_id=str(project_id),
                    node_id=node_id,
                    name=name,
                    summary=summary,
                    chapter=chapter,
                    event_type=event_type,
                )
                record = await result.single()
                return dict(record) if record else None
        except Exception:
            return None

    async def create_causal_link(
        self,
        from_event_id: str,
        to_event_id: str,
        cause_type: str = "direct",
        confidence: float = 1.0,
    ) -> bool:
        driver = await self._get_client()
        if not driver:
            return False
        cypher = """
        MATCH (a:Event {id: $from_id}), (b:Event {id: $to_id})
        MERGE (a)-[r:CAUSED {type: $cause_type}]->(b)
        SET r.confidence = $confidence
        RETURN r
        """
        try:
            async with driver.session() as session:
                await session.run(
                    cypher,
                    from_id=from_event_id,
                    to_id=to_event_id,
                    cause_type=cause_type,
                    confidence=confidence,
                )
                return True
        except Exception:
            return False

    async def create_involves_link(
        self,
        event_id: str,
        entity_id: str,
        entity_name: str,
        role: str = "participant",
    ) -> bool:
        driver = await self._get_client()
        if not driver:
            return False
        cypher = """
        MERGE (c:Character {id: $entity_id, name: $entity_name})
        WITH c
        MATCH (e:Event {id: $event_id})
        MERGE (e)-[r:INVOLVES {role: $role}]->(c)
        RETURN r
        """
        try:
            async with driver.session() as session:
                await session.run(
                    cypher,
                    event_id=event_id,
                    entity_id=entity_id,
                    entity_name=entity_name,
                    role=role,
                )
                return True
        except Exception:
            return False

    async def link_foreshadow_to_payoff(
        self,
        foreshadow_event_id: str,
        payoff_event_id: str,
    ) -> bool:
        driver = await self._get_client()
        if not driver:
            return False
        cypher = """
        MATCH (f:Event {id: $foreshadow_id}), (p:Event {id: $payoff_id})
        MERGE (f)-[r:LEADS_TO]->(p)
        RETURN r
        """
        try:
            async with driver.session() as session:
                await session.run(
                    cypher,
                    foreshadow_id=foreshadow_event_id,
                    payoff_id=payoff_event_id,
                )
                return True
        except Exception:
            return False

    async def query_causal_paths(
        self,
        project_id: uuid.UUID,
        from_chapter: int,
        to_chapter: int,
        max_hops: int = 10,
    ) -> list[dict[str, Any]]:
        driver = await self._get_client()
        if not driver:
            return []
        cypher = """
        MATCH path = (start:Event {
            project_id: $project_id,
            chapter: $from_chapter
        })-[:CAUSED*1..%d]->(end:Event {
            project_id: $project_id,
            chapter: $to_chapter
        })
        RETURN path, length(path) AS hops
        ORDER BY hops DESC
        LIMIT 5
        """ % max_hops
        try:
            async with driver.session() as session:
                result = await session.run(
                    cypher,
                    project_id=str(project_id),
                    from_chapter=from_chapter,
                    to_chapter=to_chapter,
                )
                paths = []
                async for record in result:
                    path_data = []
                    for node in record["path"].nodes:
                        path_data.append({
                            "id": node.get("id"),
                            "name": node.get("name"),
                            "chapter": node.get("chapter"),
                        })
                    paths.append({
                        "nodes": path_data,
                        "hops": record["hops"],
                    })
                return paths
        except Exception:
            return []

    async def compute_character_influence(
        self,
        project_id: uuid.UUID,
    ) -> list[dict[str, Any]]:
        driver = await self._get_client()
        if not driver:
            return []
        cypher = """
        MATCH (c:Character {project_id: $project_id})
        OPTIONAL MATCH (e:Event)-[:INVOLVES]->(c)
        OPTIONAL MATCH (prev:Event)-[:CAUSED]->(e)
        WITH c, count(DISTINCT prev) AS incoming, count(DISTINCT e) AS events
        RETURN c.id AS id, c.name AS name, incoming, events,
               (incoming * 1.0 + events * 0.5) AS influence_score
        ORDER BY influence_score DESC
        LIMIT 20
        """
        try:
            async with driver.session() as session:
                result = await session.run(
                    cypher,
                    project_id=str(project_id),
                )
                records = []
                async for record in result:
                    records.append(dict(record))
                return records
        except Exception:
            return []

    async def detect_story_structure(
        self,
        project_id: uuid.UUID,
    ) -> list[dict[str, Any]]:
        driver = await self._get_client()
        if not driver:
            return []
        cypher = """
        MATCH path = (a:Event)-[:CAUSED]->(b:Event)-[:CAUSED]->(c:Event)
        WHERE a.project_id = $project_id AND b.project_id = $project_id AND c.project_id = $project_id
        RETURN a.name AS act1, b.name AS act2, c.name AS act3,
               a.chapter AS ch1, b.chapter AS ch2, c.chapter AS ch3
        LIMIT 20
        """
        try:
            async with driver.session() as session:
                result = await session.run(
                    cypher,
                    project_id=str(project_id),
                )
                records = []
                async for record in result:
                    records.append(dict(record))
                return records
        except Exception:
            return []

    @property
    def is_available(self) -> bool:
        return self._available


neo4j_service = Neo4jService()
