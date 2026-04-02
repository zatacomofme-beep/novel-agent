from __future__ import annotations

from collections import defaultdict
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.character import Character
from models.social_topology import (
    CharacterRelationship,
    CharacterSocialTopology,
    InteractionLog,
    RelationshipType,
)


class SocialTopologyService:

    async def upsert_relationship(
        self,
        session: AsyncSession,
        project_id: UUID,
        from_char_id: UUID,
        to_char_id: UUID,
        relationship_type: str,
        strength: float = 0.5,
        description: str | None = None,
        source_chapter: int | None = None,
    ) -> CharacterRelationship:
        result = await session.execute(
            select(CharacterRelationship).where(
                CharacterRelationship.project_id == project_id,
                CharacterRelationship.from_character_id == from_char_id,
                CharacterRelationship.to_character_id == to_char_id,
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            existing.relationship_type = relationship_type
            existing.strength = strength
            existing.description = description
            existing.is_active = True
            return existing

        rel = CharacterRelationship(
            project_id=project_id,
            from_character_id=from_char_id,
            to_character_id=to_char_id,
            relationship_type=relationship_type,
            strength=strength,
            description=description,
            source_chapter=source_chapter,
            is_active=True,
        )
        session.add(rel)
        return rel

    async def log_interaction(
        self,
        session: AsyncSession,
        project_id: UUID,
        chapter_id: UUID,
        char_a_id: UUID,
        char_b_id: UUID,
        interaction_type: str,
        emotional_tone: str | None = None,
        chapter_number: int = 0,
    ) -> InteractionLog:
        log = InteractionLog(
            project_id=project_id,
            chapter_id=chapter_id,
            character_a_id=char_a_id,
            character_b_id=char_b_id,
            interaction_type=interaction_type,
            emotional_tone=emotional_tone,
            chapter_number=chapter_number,
        )
        session.add(log)
        return log

    async def compute_centrality_scores(
        self,
        session: AsyncSession,
        project_id: UUID,
    ) -> dict[str, float]:
        result = await session.execute(
            select(CharacterRelationship).where(
                CharacterRelationship.project_id == project_id,
                CharacterRelationship.is_active == True,
            )
        )
        rels = result.scalars().all()

        degree: dict[UUID, float] = defaultdict(float)
        for rel in rels:
            degree[rel.from_character_id] += abs(rel.strength)
            degree[rel.to_character_id] += abs(rel.strength)

        if not degree:
            return {}

        max_degree = max(degree.values()) if degree else 1
        return {
            str(char_id): round(score / max_degree, 3)
            for char_id, score in degree.items()
        }

    async def build_social_topology(
        self,
        session: AsyncSession,
        project_id: UUID,
    ) -> CharacterSocialTopology:
        char_result = await session.execute(
            select(Character).where(Character.project_id == project_id)
        )
        characters = list(char_result.scalars().all())

        centrality = await self.compute_centrality_scores(session, project_id)

        rel_result = await session.execute(
            select(CharacterRelationship).where(
                CharacterRelationship.project_id == project_id,
                CharacterRelationship.is_active == True,
            )
        )
        rels = list(rel_result.scalars().all())

        char_ids = {c.id for c in characters}
        influence_graph: dict[str, list[str]] = defaultdict(list)
        for rel in rels:
            if rel.from_character_id in char_ids and rel.to_character_id in char_ids:
                influence_graph[str(rel.from_character_id)].append(str(rel.to_character_id))

        log_result = await session.execute(
            select(InteractionLog).where(
                InteractionLog.project_id == project_id
            ).order_by(InteractionLog.chapter_number)
        )
        logs = list(log_result.scalars().all())

        interaction_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for log in logs:
            key = f"{log.character_a_id}_{log.character_b_id}"
            interaction_counts[key][log.interaction_type] = (
                interaction_counts[key][log.interaction_type] + 1
            )

        social_dynamics = {
            "total_relationships": len(rels),
            "total_characters": len(characters),
            "interaction_types": {
                k: dict(v) for k, v in interaction_counts.items()
            },
        }

        result = await session.execute(
            select(CharacterSocialTopology).where(
                CharacterSocialTopology.project_id == project_id
            )
        )
        topology = result.scalar_one_or_none()

        if topology:
            topology.centrality_scores = centrality
            topology.influence_graph = dict(influence_graph)
            topology.social_dynamics = social_dynamics
            return topology

        topology = CharacterSocialTopology(
            project_id=project_id,
            centrality_scores=centrality,
            influence_graph=dict(influence_graph),
            social_dynamics=social_dynamics,
            confidence=0.6,
        )
        session.add(topology)
        return topology

    async def detect_relationship_conflicts(
        self,
        session: AsyncSession,
        project_id: UUID,
        char_a_id: UUID,
        char_b_id: UUID,
        new_type: str,
    ) -> list[dict]:
        result = await session.execute(
            select(CharacterRelationship).where(
                CharacterRelationship.project_id == project_id,
                CharacterRelationship.from_character_id == char_a_id,
                CharacterRelationship.to_character_id == char_b_id,
                CharacterRelationship.is_active == True,
            )
        )
        existing = result.scalar_one_or_none()

        conflicts = []
        if existing:
            enemy_types = {RelationshipType.ENEMY.value, RelationshipType.RIVAL.value}
            friendly_types = {
                RelationshipType.FAMILY.value,
                RelationshipType.FRIEND.value,
                RelationshipType.ROMANTIC.value,
            }
            if existing.relationship_type in enemy_types and new_type in friendly_types:
                conflicts.append({
                    "type": "hostile_to_friendly",
                    "existing": existing.relationship_type,
                    "proposed": new_type,
                    "description": f"Relationship shift from {existing.relationship_type} to {new_type} may feel abrupt",
                })
            if existing.relationship_type in friendly_types and new_type in enemy_types:
                conflicts.append({
                    "type": "friendly_to_hostile",
                    "existing": existing.relationship_type,
                    "proposed": new_type,
                    "description": f"Relationship shift from {existing.relationship_type} to {new_type} may feel abrupt",
                })

        return conflicts


social_topology_service = SocialTopologyService()
