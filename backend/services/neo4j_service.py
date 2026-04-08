from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from core.config import get_settings
from core.degraded_response import DegradedResponse
from core.exceptions import GraphDatabaseError
from core.logging import get_logger

if TYPE_CHECKING:
    from core.types_neo4j import Neo4jDriverProtocol


logger = get_logger(__name__)

_NEO4J_EXCEPTIONS: tuple[type[Exception], ...] = ()
try:
    from neo4j.exceptions import (  # type: ignore[attr-defined]
        ClientError,
        AuthError,
        ServiceUnavailableError,
        SessionExpiredError,
        TransactionError,
    )
    _NEO4J_EXCEPTIONS = (
        ClientError,
        AuthError,
        ServiceUnavailableError,
        SessionExpiredError,
        TransactionError,
        ConnectionError,
        OSError,
    )
except ImportError:
    _NEO4J_EXCEPTIONS = (Exception,)


class Neo4jService:
    def __init__(self) -> None:
        settings = get_settings()
        self._url = getattr(settings, "neo4j_url", "bolt://localhost:7687")
        self._auth = getattr(settings, "neo4j_auth", ("neo4j", "password"))
        self._client: Neo4jDriverProtocol | None = None
        self._available = False

    async def _get_client(self) -> Any | None:
        if self._client is not None:
            return self._client
        driver: Any | None = None
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
        except *_NEO4J_EXCEPTIONS as exc:
            logger.warning(
                "neo4j_connection_failed",
                extra={"error": str(exc), "url": self._url},
            )
            self._available = False
            driver = None

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
        result = None
        try:
            async with driver.session() as session:
                query_result = await session.run(
                    cypher,
                    project_id=str(project_id),
                    node_id=node_id,
                    name=name,
                    summary=summary,
                    chapter=chapter,
                    event_type=event_type,
                )
                record = await query_result.single()
                result = dict(record) if record else None
        except *_NEO4J_EXCEPTIONS as exc:
            logger.warning(
                "neo4j_create_event_node_failed",
                extra={
                    "error": str(exc),
                    "project_id": str(project_id),
                    "chapter": chapter,
                    "name": name,
                },
            )
        return result

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
        success = False
        try:
            async with driver.session() as session:
                await session.run(
                    cypher,
                    from_id=from_event_id,
                    to_id=to_event_id,
                    cause_type=cause_type,
                    confidence=confidence,
                )
                success = True
        except *_NEO4J_EXCEPTIONS as exc:
            logger.warning(
                "neo4j_create_causal_link_failed",
                extra={"error": str(exc), "from_id": from_event_id, "to_id": to_event_id},
            )
        return success

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
        success = False
        try:
            async with driver.session() as session:
                await session.run(
                    cypher,
                    event_id=event_id,
                    entity_id=entity_id,
                    entity_name=entity_name,
                    role=role,
                )
                success = True
        except *_NEO4J_EXCEPTIONS as exc:
            logger.warning(
                "neo4j_create_involves_link_failed",
                extra={"error": str(exc), "event_id": event_id, "entity_id": entity_id},
            )
        return success

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
        success = False
        try:
            async with driver.session() as session:
                await session.run(
                    cypher,
                    foreshadow_id=foreshadow_event_id,
                    payoff_id=payoff_event_id,
                )
                success = True
        except *_NEO4J_EXCEPTIONS as exc:
            logger.warning(
                "neo4j_link_foreshadow_to_payoff_failed",
                extra={"error": str(exc), "foreshadow_id": foreshadow_event_id},
            )
        return success

    async def query_causal_paths(
        self,
        project_id: uuid.UUID,
        from_chapter: int,
        to_chapter: int,
        max_hops: int = 10,
    ) -> DegradedResponse[list[dict[str, Any]]]:
        driver = await self._get_client()
        if not driver:
            return DegradedResponse.empty(source="neo4j", reason="driver_unavailable")
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
        paths = []
        try:
            async with driver.session() as session:
                result = await session.run(
                    cypher,
                    project_id=str(project_id),
                    from_chapter=from_chapter,
                    to_chapter=to_chapter,
                )
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
                return_value = DegradedResponse.ok(paths, source="neo4j")
        except *_NEO4J_EXCEPTIONS as exc:
            logger.warning(
                "neo4j_query_causal_paths_failed",
                extra={"error": str(exc), "project_id": str(project_id)},
            )
            return_value = DegradedResponse.fallback(
                [],
                source="neo4j",
                reason=f"query_error: {exc}",
            )
        return return_value

    async def compute_character_influence(
        self,
        project_id: uuid.UUID,
    ) -> DegradedResponse[list[dict[str, Any]]]:
        driver = await self._get_client()
        if not driver:
            return DegradedResponse.empty(source="neo4j", reason="driver_unavailable")
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
        records = []
        try:
            async with driver.session() as session:
                result = await session.run(
                    cypher,
                    project_id=str(project_id),
                )
                async for record in result:
                    records.append(dict(record))
                return_value = DegradedResponse.ok(records, source="neo4j")
        except *_NEO4J_EXCEPTIONS as exc:
            logger.warning(
                "neo4j_compute_character_influence_failed",
                extra={"error": str(exc), "project_id": str(project_id)},
            )
            return_value = DegradedResponse.fallback(
                [],
                source="neo4j",
                reason=f"query_error: {exc}",
            )
        return return_value

    async def detect_story_structure(
        self,
        project_id: uuid.UUID,
    ) -> DegradedResponse[list[dict[str, Any]]]:
        driver = await self._get_client()
        if not driver:
            return DegradedResponse.empty(source="neo4j", reason="driver_unavailable")
        cypher = """
        MATCH path = (a:Event)-[:CAUSED]->(b:Event)-[:CAUSED]->(c:Event)
        WHERE a.project_id = $project_id AND b.project_id = $project_id AND c.project_id = $project_id
        RETURN a.name AS act1, b.name AS act2, c.name AS act3,
               a.chapter AS ch1, b.chapter AS ch2, c.chapter AS ch3
        LIMIT 20
        """
        records = []
        try:
            async with driver.session() as session:
                result = await session.run(
                    cypher,
                    project_id=str(project_id),
                )
                async for record in result:
                    records.append(dict(record))
                return_value = DegradedResponse.ok(records, source="neo4j")
        except *_NEO4J_EXCEPTIONS as exc:
            logger.warning(
                "neo4j_detect_story_structure_failed",
                extra={"error": str(exc), "project_id": str(project_id)},
            )
            return_value = DegradedResponse.fallback(
                [],
                source="neo4j",
                reason=f"query_error: {exc}",
            )
        return return_value

    @property
    def is_available(self) -> bool:
        return self._available


neo4j_service = Neo4jService()
