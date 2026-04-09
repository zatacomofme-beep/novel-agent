from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from core.logging import get_logger
from services.relation_reasoner import (
    format_inferred_relations_for_constraints,
    reason_from_direct_relations,
    reason_from_paths,
)
from services.story_engine_kb_service import (
    build_workspace,
    search_knowledge,
)
from services.story_engine_vector_store import vector_store

logger = get_logger(__name__)


@dataclass
class Constraint:
    text: str
    source: str
    priority: int = 0
    entity_type: str = ""
    entity_id: str = ""

    def __lt__(self, other: Constraint) -> bool:
        return self.priority > other.priority


@dataclass
class ConstraintBlock:
    constraints: list[Constraint] = field(default_factory=list)

    def format_for_prompt(self) -> str:
        if not self.constraints:
            return ""
        lines = ["【必须遵守的设定约束】"]
        for i, c in enumerate(self.constraints, 1):
            lines.append(f"{i}. {c.text}")
        lines.append("")
        lines.append("以上约束来自已有设定，生成内容时必须严格遵守，不得违背。")
        return "\n".join(lines)


async def extract_constraints(
    session: AsyncSession,
    *,
    project_id: UUID,
    user_id: UUID,
    chapter_context: str,
    chapter_number: int = 0,
    max_constraints: int = 15,
    workspace: dict[str, Any] | None = None,
) -> ConstraintBlock:
    constraints: list[Constraint] = []

    if workspace is None:
        try:
            workspace = await build_workspace(
                session,
                project_id=project_id,
                user_id=user_id,
            )
        except Exception as exc:
            logger.warning(
                "constraint_extractor_workspace_failed",
                extra={"error": str(exc), "project_id": str(project_id)},
            )
            return ConstraintBlock(constraints=constraints)

    constraints.extend(
        _extract_character_constraints(workspace, chapter_number)
    )
    constraints.extend(
        _extract_world_rule_constraints(workspace)
    )
    constraints.extend(
        _extract_foreshadow_constraints(workspace, chapter_number)
    )
    constraints.extend(
        _extract_item_constraints(workspace)
    )
    constraints.extend(
        _extract_timeline_constraints(workspace, chapter_number)
    )

    if chapter_context.strip():
        vector_constraints = await _extract_vector_constraints(
            project_id=project_id,
            chapter_context=chapter_context,
            max_count=max(3, max_constraints // 3),
        )
        constraints.extend(vector_constraints)

    graph_constraints = await _extract_graph_constraints(
        project_id=project_id,
        workspace=workspace,
    )
    constraints.extend(graph_constraints)

    constraints.sort()
    constraints = _deduplicate_constraints(constraints)
    constraints = constraints[:max_constraints]

    return ConstraintBlock(constraints=constraints)


def _extract_character_constraints(
    workspace: dict[str, Any],
    chapter_number: int,
) -> list[Constraint]:
    constraints: list[Constraint] = []
    characters = workspace.get("characters", [])
    for char in characters[:8]:
        name = getattr(char, "name", None) or ""
        if not name:
            continue
        status = getattr(char, "status", None) or ""
        arc_stage = getattr(char, "arc_stage", None) or ""
        personality = getattr(char, "personality", None) or ""
        parts: list[str] = []
        if status:
            parts.append(f"当前状态为「{status}」")
        if arc_stage:
            parts.append(f"角色弧阶段为「{arc_stage}」")
        if personality:
            snippet = personality[:80]
            parts.append(f"性格特征：{snippet}")
        if parts:
            constraints.append(Constraint(
                text=f"角色「{name}」{'，'.join(parts)}",
                source="character",
                priority=8,
                entity_type="characters",
                entity_id=str(getattr(char, "character_id", "")),
            ))
        relationships = getattr(char, "relationships", None) or []
        for rel in relationships[:3]:
            target = rel.get("target_name") or rel.get("target_id") or ""
            relation_type = rel.get("relation") or rel.get("type") or ""
            if target and relation_type:
                constraints.append(Constraint(
                    text=f"角色「{name}」与「{target}」的关系是「{relation_type}」",
                    source="character_relationship",
                    priority=9,
                    entity_type="characters",
                    entity_id=str(getattr(char, "character_id", "")),
                ))
    return constraints


def _extract_world_rule_constraints(
    workspace: dict[str, Any],
) -> list[Constraint]:
    constraints: list[Constraint] = []
    world_rules = workspace.get("world_rules", [])
    for rule in world_rules[:6]:
        rule_name = getattr(rule, "rule_name", None) or ""
        rule_content = getattr(rule, "rule_content", None) or ""
        negative_list = getattr(rule, "negative_list", None) or []
        if rule_name and rule_content:
            text = f"世界规则「{rule_name}」：{rule_content[:120]}"
            constraints.append(Constraint(
                text=text,
                source="world_rule",
                priority=7,
                entity_type="world_rules",
                entity_id=str(getattr(rule, "id", "")),
            ))
        for neg in negative_list[:2]:
            neg_str = str(neg)[:80]
            constraints.append(Constraint(
                text=f"禁止：{neg_str}（违反世界规则「{rule_name}」）",
                source="world_rule_negative",
                priority=10,
                entity_type="world_rules",
                entity_id=str(getattr(rule, "id", "")),
            ))
    return constraints


def _extract_foreshadow_constraints(
    workspace: dict[str, Any],
    chapter_number: int,
) -> list[Constraint]:
    constraints: list[Constraint] = []
    foreshadows = workspace.get("foreshadows", [])
    for fs in foreshadows[:6]:
        content = getattr(fs, "content", None) or ""
        status = getattr(fs, "status", None) or ""
        planted = getattr(fs, "chapter_planted", None)
        reveal = getattr(fs, "chapter_planned_reveal", None)
        if not content:
            continue
        if status == "planted" and chapter_number > 0:
            if planted and chapter_number >= planted:
                constraints.append(Constraint(
                    text=f"伏笔「{content[:60]}」已埋设于第{planted}章，尚未回收，不可遗忘",
                    source="foreshadow_active",
                    priority=9,
                    entity_type="foreshadows",
                    entity_id=str(getattr(fs, "id", "")),
                ))
        elif status == "resolved":
            if planted:
                constraints.append(Constraint(
                    text=f"伏笔「{content[:60]}」已于第{planted}章埋设并已回收",
                    source="foreshadow_resolved",
                    priority=5,
                    entity_type="foreshadows",
                    entity_id=str(getattr(fs, "id", "")),
                ))
    return constraints


def _extract_item_constraints(
    workspace: dict[str, Any],
) -> list[Constraint]:
    constraints: list[Constraint] = []
    items = workspace.get("items", [])
    for item in items[:4]:
        name = getattr(item, "name", None) or ""
        description = getattr(item, "description", None) or ""
        owner = getattr(item, "owner", None) or ""
        if not name:
            continue
        parts: list[str] = []
        if owner:
            parts.append(f"持有者为「{owner}」")
        if description:
            parts.append(description[:80])
        if parts:
            constraints.append(Constraint(
                text=f"物品「{name}」{'，'.join(parts)}",
                source="item",
                priority=6,
                entity_type="items",
                entity_id=str(getattr(item, "id", "")),
            ))
    return constraints


def _extract_timeline_constraints(
    workspace: dict[str, Any],
    chapter_number: int,
) -> list[Constraint]:
    constraints: list[Constraint] = []
    timeline_events = workspace.get("timeline_events", [])
    for event in timeline_events[:4]:
        event_name = getattr(event, "event_name", None) or ""
        chapter = getattr(event, "chapter_number", None)
        description = getattr(event, "description", None) or ""
        if not event_name:
            continue
        if chapter is not None and chapter_number > 0 and chapter <= chapter_number:
            text = f"时间线事件「{event_name}」已发生于第{chapter}章"
            if description:
                text += f"：{description[:80]}"
            constraints.append(Constraint(
                text=text,
                source="timeline_event",
                priority=7,
                entity_type="timeline_events",
                entity_id=str(getattr(event, "id", "")),
            ))
    return constraints


async def _extract_vector_constraints(
    *,
    project_id: UUID,
    chapter_context: str,
    max_count: int = 5,
) -> list[Constraint]:
    constraints: list[Constraint] = []
    try:
        hits = await vector_store.search(
            project_id=str(project_id),
            query=chapter_context[:500],
            limit=max_count,
        )
        for hit in hits:
            if hit.score < 0.6:
                continue
            content = hit.content[:120] if hit.content else ""
            if not content:
                continue
            constraints.append(Constraint(
                text=content,
                source=f"vector_{hit.entity_type}",
                priority=4,
                entity_type=hit.entity_type,
                entity_id=hit.entity_id,
            ))
    except Exception as exc:
        logger.warning(
            "constraint_extractor_vector_search_failed",
            extra={"error": str(exc), "project_id": str(project_id)},
        )
    return constraints


def _deduplicate_constraints(constraints: list[Constraint]) -> list[Constraint]:
    seen_texts: set[str] = set()
    unique: list[Constraint] = []
    for c in constraints:
        normalized = c.text.strip().lower()
        if normalized not in seen_texts:
            seen_texts.add(normalized)
            unique.append(c)
    return unique


async def _extract_graph_constraints(
    *,
    project_id: UUID,
    workspace: dict[str, Any],
) -> list[Constraint]:
    constraints: list[Constraint] = []
    try:
        from services.neo4j_service import neo4j_service

        characters = workspace.get("characters", [])
        character_names = [
            getattr(c, "name", "")
            for c in characters[:6]
            if getattr(c, "name", "")
        ]

        if not character_names:
            return constraints

        direct_result = await neo4j_service.query_multi_entity_relations(
            project_id=project_id,
            entity_names=character_names,
        )
        if direct_result:
            direct_relations = direct_result.data if hasattr(direct_result, "data") else direct_result
            if isinstance(direct_relations, list) and direct_relations:
                inferred_direct = reason_from_direct_relations(direct_relations)
                for inf in inferred_direct:
                    constraints.append(Constraint(
                        text=f"角色「{inf.from_entity}」与「{inf.to_entity}」存在{inf.inferred_relation}",
                        source="graph_direct",
                        priority=8,
                        entity_type="characters",
                    ))

        lead_name = character_names[0] if character_names else ""
        if lead_name:
            path_result = await neo4j_service.query_entity_relations(
                project_id=project_id,
                entity_name=lead_name,
                max_hops=3,
            )
            if path_result:
                paths = path_result.data if hasattr(path_result, "data") else path_result
                if isinstance(paths, list) and paths:
                    inferred_paths = reason_from_paths(paths)
                    path_lines = format_inferred_relations_for_constraints(
                        inferred_paths,
                        max_count=5,
                    )
                    for line in path_lines:
                        constraints.append(Constraint(
                            text=line,
                            source="graph_inferred",
                            priority=7,
                            entity_type="characters",
                        ))
    except Exception as exc:
        logger.warning(
            "constraint_extractor_graph_failed",
            extra={"error": str(exc), "project_id": str(project_id)},
        )
    return constraints
