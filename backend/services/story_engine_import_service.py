from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.errors import AppError
from models.story_engine import (
    StoryChapterSummary,
    StoryCharacter,
    StoryForeshadow,
    StoryItem,
    StoryOutline,
    StoryTimelineMapEvent,
    StoryWorldRule,
)
from schemas.story_engine import StoryBulkImportPayload
from services.story_engine_kb_service import (
    get_story_engine_project,
    list_entities,
)
from services.project_service import PROJECT_PERMISSION_EDIT, get_owned_project
from services.story_engine_settings_service import (
    build_story_engine_settings_for_preset,
    get_story_engine_model_preset_label,
)
from services.story_engine_unified_knowledge_service import (
    delete_story_knowledge,
    save_story_knowledge,
)
from services.story_engine_workflow_service import (
    _append_workflow_event,
    _build_workflow_id,
    _build_workflow_task_base_result,
    _create_workflow_task_state,
    _persist_workflow_task_event,
    _persist_workflow_task_failure,
    run_story_bulk_import_guard,
)


IMPORTABLE_SECTIONS = (
    "characters",
    "foreshadows",
    "items",
    "world_rules",
    "timeline_events",
    "outlines",
    "chapter_summaries",
)

SECTION_MODEL_MAP = {
    "characters": StoryCharacter,
    "foreshadows": StoryForeshadow,
    "items": StoryItem,
    "world_rules": StoryWorldRule,
    "timeline_events": StoryTimelineMapEvent,
    "outlines": StoryOutline,
    "chapter_summaries": StoryChapterSummary,
}

SECTION_ID_FIELD_MAP = {
    "characters": "character_id",
    "foreshadows": "foreshadow_id",
    "items": "item_id",
    "world_rules": "rule_id",
    "timeline_events": "event_id",
    "outlines": "outline_id",
    "chapter_summaries": "summary_id",
}

SECTION_LABEL_MAP = {
    "characters": "人物",
    "foreshadows": "伏笔",
    "items": "物品",
    "world_rules": "规则",
    "timeline_events": "时间线",
    "outlines": "大纲",
    "chapter_summaries": "章节总结",
}


def list_import_templates() -> list[dict[str, Any]]:
    return [
        {
            "key": "blank_minimal",
            "label": "空白起盘模板",
            "description": "只给出最基础的 JSON 结构，适合你已经有自己设定时直接往里填。",
            "usage_notes": [
                "一级大纲建议只保留 1 条，它会在导入后自动锁死。",
                "人物关系可以先填 target_name，后续再细化为更复杂的关系网。",
                "replace_existing_sections 填要覆盖的区块，不填就走增量导入。",
            ],
            "recommended_model_preset_key": "balanced",
            "recommended_model_preset_label": get_story_engine_model_preset_label("balanced"),
            "payload": {
                "characters": [
                    {
                        "name": "主角",
                        "appearance": "",
                        "personality": "",
                        "micro_habits": [],
                        "abilities": {},
                        "relationships": [],
                        "status": "active",
                        "arc_stage": "initial",
                        "arc_boundaries": [],
                    }
                ],
                "foreshadows": [],
                "items": [],
                "world_rules": [],
                "timeline_events": [],
                "outlines": [
                    {
                        "level": "level_1",
                        "title": "全本主线圣经",
                        "content": "这里写整本书不允许动摇的主线目标、终局方向和核心代价。",
                        "status": "todo",
                        "node_order": 1,
                        "locked": True,
                        "immutable_reason": "一级大纲导入后自动锁定。",
                    }
                ],
                "chapter_summaries": [],
            },
        },
        {
            "key": "xuanhuan_upgrade",
            "label": "玄幻升级流模板",
            "description": "预置升级代价、宿敌线和卷级推进结构，适合玄幻/仙侠/高武类网文起盘。",
            "usage_notes": [
                "可以先导入，再把人物名和设定名替换成你自己的。",
                "世界规则里已经预埋了升级代价，后续不要轻易删掉。",
            ],
            "recommended_model_preset_key": "momentum_hook",
            "recommended_model_preset_label": get_story_engine_model_preset_label("momentum_hook"),
            "payload": {
                "characters": [
                    {
                        "name": "主角",
                        "appearance": "初看平平，却有让人过目不忘的伤痕或标记。",
                        "personality": "表面克制，内里极度执拗。",
                        "micro_habits": ["压怒时会摩挲指节"],
                        "abilities": {"core": "成长型功法", "ceiling": "后期可触及世界顶端"},
                        "relationships": [],
                        "status": "active",
                        "arc_stage": "initial",
                        "arc_boundaries": [
                            {
                                "stage": "initial",
                                "forbidden_behaviors": ["无代价越阶乱杀", "毫无铺垫地舍己救所有人"],
                                "allowed_behaviors": ["谨慎试探", "为了执念冒险"],
                            }
                        ],
                    },
                    {
                        "name": "宿敌",
                        "appearance": "出场自带压迫感。",
                        "personality": "冷硬、强控制欲、信奉弱肉强食。",
                        "micro_habits": ["说话前会停半拍"],
                        "abilities": {"core": "规则压制型战力"},
                        "relationships": [{"target_name": "主角", "relation": "宿敌", "intensity": "high"}],
                        "status": "active",
                        "arc_stage": "initial",
                        "arc_boundaries": [
                            {
                                "stage": "initial",
                                "forbidden_behaviors": ["机缘未成熟前亲手击杀主角", "无视更高层约束公开碾压主角"],
                                "allowed_behaviors": ["借外部势力持续施压", "把主角当成钓出更深层秘密的诱饵"],
                            }
                        ],
                    },
                ],
                "foreshadows": [
                    {
                        "content": "主角身世里藏着一条会在中后期爆开的核心真相。",
                        "chapter_planted": 1,
                        "chapter_planned_reveal": 80,
                        "status": "pending",
                        "related_characters": ["主角"],
                        "related_items": [],
                    }
                ],
                "items": [
                    {
                        "name": "起始机缘",
                        "features": "看似普通，却绑定主线秘密。",
                        "owner": "主角",
                        "location": "主角身边",
                        "special_rules": ["越级使用必须付出反噬"],
                    }
                ],
                "world_rules": [
                    {
                        "rule_name": "越级爆发必有代价",
                        "rule_content": "任何超出当前层级的爆发都要支付真实代价，不能白送。",
                        "negative_list": ["无代价开挂", "大战后秒恢复"],
                        "scope": "battle",
                    },
                    {
                        "rule_name": "规则压制存在触发门槛",
                        "rule_content": "规则压制型能力只有在境界、媒介和场域三者同时满足时才能生效，持续压制会反噬施术者，且可被更高阶规则、外部契约或未成熟的核心机缘干扰。",
                        "negative_list": ["没有前提就能无限压制", "压制失败却毫无反噬", "主角没有锚点就硬破规则"],
                        "scope": "battle",
                    }
                ],
                "timeline_events": [],
                "outlines": [
                    {
                        "level": "level_1",
                        "title": "主线圣经",
                        "content": "主角从被压制到站上顶峰，但每次升级都必须换来真实损失。",
                        "status": "todo",
                        "node_order": 1,
                        "locked": True,
                        "immutable_reason": "一级大纲导入后自动锁定。",
                    },
                    {
                        "level": "level_2",
                        "title": "卷一：被逼入局",
                        "content": "前期受压制，先立世界规则，再给第一波痛快反击。",
                        "status": "todo",
                        "node_order": 1,
                        "parent_title": "主线圣经",
                    },
                    {
                        "level": "level_3",
                        "title": "第一章：开局吃亏",
                        "content": "先吃亏，再埋下翻盘锚点。",
                        "status": "todo",
                        "node_order": 1,
                        "parent_title": "卷一：被逼入局",
                    },
                ],
                "chapter_summaries": [],
            },
        },
    ]


def get_import_template(template_key: str) -> dict[str, Any]:
    for item in list_import_templates():
        if item["key"] == template_key:
            return item
    raise AppError(
        code="story_engine.import_template_not_found",
        message=f"导入模板不存在：{template_key}",
        status_code=404,
    )


async def bulk_import_story_payload(
    session: AsyncSession,
    *,
    project_id: UUID,
    user_id: UUID,
    payload: StoryBulkImportPayload,
    replace_existing_sections: list[str],
    branch_id: UUID | None = None,
    model_preset_key: str | None = None,
    workflow_id: str | None = None,
) -> dict[str, Any]:
    await get_story_engine_project(session, project_id, user_id)
    resolved_branch_id = await _resolve_import_branch_id(
        session,
        project_id=project_id,
        user_id=user_id,
        branch_id=branch_id,
    )
    workflow_id = workflow_id or _build_workflow_id("bulk_import")
    payload_snapshot = payload.model_dump(mode="json")
    input_counts = _build_import_section_counts(payload_snapshot)
    task_state = await _create_workflow_task_state(
        session,
        workflow_id=workflow_id,
        workflow_type="bulk_import",
        project_id=project_id,
        user_id=user_id,
        chapter_id=None,
        chapter_number=None,
        initial_message="正在导入起盘设定、三级大纲和基础圣经。",
        initial_result={
            **_build_workflow_task_base_result(
                workflow_id=workflow_id,
                workflow_type="bulk_import",
                workflow_status="running",
                chapter_number=None,
                chapter_title=None,
                branch_id=resolved_branch_id,
            ),
            "incoming_counts": input_counts,
        },
    )
    workflow_timeline: list[dict[str, Any]] = []
    normalized_replace_sections = [item for item in replace_existing_sections if item in IMPORTABLE_SECTIONS]
    existing_entities_by_section: dict[str, list[Any]] = {}
    warnings: list[str] = []

    async def record_event(
        *,
        stage: str,
        status: str,
        label: str,
        message: str | None = None,
        details: dict[str, Any] | None = None,
        finalize: bool = False,
        result_patch: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        workflow_event = _append_workflow_event(
            workflow_timeline,
            workflow_id=workflow_id,
            workflow_type="bulk_import",
            stage=stage,
            status=status,
            label=label,
            message=message,
            branch_id=resolved_branch_id,
            details=details,
        )
        next_result_patch = dict(result_patch or {})
        if "workflow_timeline" in next_result_patch:
            next_result_patch["workflow_timeline"] = workflow_timeline
        await _persist_workflow_task_event(
            session,
            task_state=task_state,
            project_id=project_id,
            user_id=user_id,
            chapter_id=None,
            workflow_type="bulk_import",
            workflow_event=workflow_event,
            result_patch=next_result_patch or None,
            finalize=finalize,
        )
        return workflow_event

    try:
        await record_event(
            stage="bulk_import_started",
            status="started",
            label="开始导入起盘设定",
            message="正在检查这批起盘设定，并准备写入项目圣经。",
            details={
                "incoming_counts": input_counts,
                "replace_section_count": len(replace_existing_sections),
            },
        )

        preflight_result = await run_story_bulk_import_guard(
            session,
            project_id=project_id,
            user_id=user_id,
            branch_id=resolved_branch_id,
            payload=payload_snapshot,
        )
        _raise_when_bulk_import_guard_blocks(preflight_result)
        _extend_import_preflight_warnings(warnings, preflight_result)
        if len(normalized_replace_sections) != len(replace_existing_sections):
            _append_import_warning(warnings, "部分 replace_existing_sections 无效，已自动忽略。")

        await record_event(
            stage="bulk_import_preflight_checked",
            status="completed",
            label="导入前检查已完成",
            message=str(preflight_result.get("message") or "").strip() or "这批设定可以开始导入。",
            details={
                "blocking_issue_count": int(preflight_result.get("blocking_issue_count") or 0),
                "warning_count": int(preflight_result.get("warning_count") or 0),
                "incoming_counts": input_counts,
            },
        )

        for section in normalized_replace_sections:
            existing_entities_by_section[section] = await list_entities(
                session,
                project_id=project_id,
                user_id=user_id,
                entity_type=section,
                branch_id=resolved_branch_id if section in {"outlines", "chapter_summaries"} else None,
            )
            if section == "outlines" and any(
                getattr(entity, "locked", False) for entity in existing_entities_by_section[section]
            ):
                _append_import_warning(
                    warnings,
                    "一级大纲已锁定；覆盖导入时只会替换可编辑卷纲和章纲，主线圣经保持不动。",
                )

        if normalized_replace_sections:
            await record_event(
                stage="bulk_import_replace_scope_prepared",
                status="completed",
                label="覆盖区块已确认",
                message=f"这次会按区块替换：{'、'.join(SECTION_LABEL_MAP[item] for item in normalized_replace_sections)}。",
                details={
                    "replaced_sections": normalized_replace_sections,
                    "replace_section_count": len(normalized_replace_sections),
                },
            )

        imported_counts = {section: 0 for section in IMPORTABLE_SECTIONS}
        imported_signatures = {section: set() for section in IMPORTABLE_SECTIONS}

        # 先导入世界规则，再导入人物，避免人物能力依赖的底层规则在守护校验时不可见。
        for item in payload.world_rules:
            item_payload = item.model_dump()
            imported_signatures["world_rules"].add(
                _build_import_payload_signature("world_rules", item_payload)
            )
            existing = await _find_by_field(
                session,
                project_id=project_id,
                entity_type="world_rules",
                field_name="rule_name",
                field_value=item.rule_name,
            )
            mutation_result = await save_story_knowledge(
                session,
                project_id=project_id,
                user_id=user_id,
                section_key="world_rules",
                item=item_payload,
                entity_id=str(existing.rule_id) if existing is not None else None,
                source_workflow="bulk_import",
                guard_operation="导入",
                skip_guard=True,
            )
            _extend_import_guard_warnings(
                warnings,
                section_key="world_rules",
                item_label=item.rule_name,
                mutation_result=mutation_result,
            )
            imported_counts["world_rules"] += 1

        if _should_emit_bulk_import_section_event(
            section_key="world_rules",
            input_counts=input_counts,
            replace_existing_sections=normalized_replace_sections,
        ):
            await record_event(
                stage="bulk_import_world_rules",
                status="completed",
                label="规则设定已导入",
                message=_build_bulk_import_section_message(
                    "world_rules",
                    imported_counts["world_rules"],
                    replace_mode="world_rules" in normalized_replace_sections,
                ),
                details={
                    "section_key": "world_rules",
                    "imported_count": imported_counts["world_rules"],
                    "replace_mode": "world_rules" in normalized_replace_sections,
                },
            )

        for item in payload.characters:
            item_payload = item.model_dump()
            imported_signatures["characters"].add(
                _build_import_payload_signature("characters", item_payload)
            )
            existing = await _find_by_field(
                session,
                project_id=project_id,
                entity_type="characters",
                field_name="name",
                field_value=item.name,
            )
            mutation_result = await save_story_knowledge(
                session,
                project_id=project_id,
                user_id=user_id,
                section_key="characters",
                item=item_payload,
                entity_id=str(existing.character_id) if existing is not None else None,
                source_workflow="bulk_import",
                guard_operation="导入",
                skip_guard=True,
            )
            _extend_import_guard_warnings(
                warnings,
                section_key="characters",
                item_label=item.name,
                mutation_result=mutation_result,
            )
            imported_counts["characters"] += 1

        if _should_emit_bulk_import_section_event(
            section_key="characters",
            input_counts=input_counts,
            replace_existing_sections=normalized_replace_sections,
        ):
            await record_event(
                stage="bulk_import_characters",
                status="completed",
                label="人物设定已导入",
                message=_build_bulk_import_section_message(
                    "characters",
                    imported_counts["characters"],
                    replace_mode="characters" in normalized_replace_sections,
                ),
                details={
                    "section_key": "characters",
                    "imported_count": imported_counts["characters"],
                    "replace_mode": "characters" in normalized_replace_sections,
                },
            )

        for item in payload.foreshadows:
            item_payload = item.model_dump()
            imported_signatures["foreshadows"].add(
                _build_import_payload_signature("foreshadows", item_payload)
            )
            existing = await _find_by_field(
                session,
                project_id=project_id,
                entity_type="foreshadows",
                field_name="content",
                field_value=item.content,
            )
            mutation_result = await save_story_knowledge(
                session,
                project_id=project_id,
                user_id=user_id,
                section_key="foreshadows",
                item=item_payload,
                entity_id=str(existing.foreshadow_id) if existing is not None else None,
                source_workflow="bulk_import",
                guard_operation="导入",
                skip_guard=True,
            )
            _extend_import_guard_warnings(
                warnings,
                section_key="foreshadows",
                item_label=_build_import_item_label("foreshadows", item_payload),
                mutation_result=mutation_result,
            )
            imported_counts["foreshadows"] += 1

        if _should_emit_bulk_import_section_event(
            section_key="foreshadows",
            input_counts=input_counts,
            replace_existing_sections=normalized_replace_sections,
        ):
            await record_event(
                stage="bulk_import_foreshadows",
                status="completed",
                label="伏笔设定已导入",
                message=_build_bulk_import_section_message(
                    "foreshadows",
                    imported_counts["foreshadows"],
                    replace_mode="foreshadows" in normalized_replace_sections,
                ),
                details={
                    "section_key": "foreshadows",
                    "imported_count": imported_counts["foreshadows"],
                    "replace_mode": "foreshadows" in normalized_replace_sections,
                },
            )

        for item in payload.items:
            item_payload = item.model_dump()
            imported_signatures["items"].add(
                _build_import_payload_signature("items", item_payload)
            )
            existing = await _find_by_field(
                session,
                project_id=project_id,
                entity_type="items",
                field_name="name",
                field_value=item.name,
            )
            mutation_result = await save_story_knowledge(
                session,
                project_id=project_id,
                user_id=user_id,
                section_key="items",
                item=item_payload,
                entity_id=str(existing.item_id) if existing is not None else None,
                source_workflow="bulk_import",
                guard_operation="导入",
                skip_guard=True,
            )
            _extend_import_guard_warnings(
                warnings,
                section_key="items",
                item_label=item.name,
                mutation_result=mutation_result,
            )
            imported_counts["items"] += 1

        if _should_emit_bulk_import_section_event(
            section_key="items",
            input_counts=input_counts,
            replace_existing_sections=normalized_replace_sections,
        ):
            await record_event(
                stage="bulk_import_items",
                status="completed",
                label="物品设定已导入",
                message=_build_bulk_import_section_message(
                    "items",
                    imported_counts["items"],
                    replace_mode="items" in normalized_replace_sections,
                ),
                details={
                    "section_key": "items",
                    "imported_count": imported_counts["items"],
                    "replace_mode": "items" in normalized_replace_sections,
                },
            )

        for item in payload.timeline_events:
            item_payload = item.model_dump()
            imported_signatures["timeline_events"].add(
                _build_import_payload_signature("timeline_events", item_payload)
            )
            existing = await _find_timeline_event(
                session,
                project_id=project_id,
                chapter_number=item.chapter_number,
                core_event=item.core_event,
            )
            mutation_result = await save_story_knowledge(
                session,
                project_id=project_id,
                user_id=user_id,
                section_key="timeline_events",
                item=item_payload,
                entity_id=str(existing.event_id) if existing is not None else None,
                source_workflow="bulk_import",
                guard_operation="导入",
                skip_guard=True,
            )
            _extend_import_guard_warnings(
                warnings,
                section_key="timeline_events",
                item_label=_build_import_item_label("timeline_events", item_payload),
                mutation_result=mutation_result,
            )
            imported_counts["timeline_events"] += 1

        if _should_emit_bulk_import_section_event(
            section_key="timeline_events",
            input_counts=input_counts,
            replace_existing_sections=normalized_replace_sections,
        ):
            await record_event(
                stage="bulk_import_timeline_events",
                status="completed",
                label="时间线设定已导入",
                message=_build_bulk_import_section_message(
                    "timeline_events",
                    imported_counts["timeline_events"],
                    replace_mode="timeline_events" in normalized_replace_sections,
                ),
                details={
                    "section_key": "timeline_events",
                    "imported_count": imported_counts["timeline_events"],
                    "replace_mode": "timeline_events" in normalized_replace_sections,
                },
            )

        outline_parent_map: dict[str, UUID] = {}
        for level in ("level_1", "level_2", "level_3"):
            for item in [outline for outline in payload.outlines if outline.level == level]:
                parent_id = outline_parent_map.get(item.parent_title or "")
                if parent_id is None and item.parent_title:
                    parent_outline = await _find_outline_by_title(
                        session,
                        project_id=project_id,
                        branch_id=resolved_branch_id,
                        title=item.parent_title,
                    )
                    if parent_outline is not None:
                        parent_id = parent_outline.outline_id
                outline_payload = item.model_dump(exclude={"parent_title"})
                if parent_id is not None:
                    outline_payload["parent_id"] = parent_id
                imported_signatures["outlines"].add(
                    _build_import_payload_signature("outlines", outline_payload)
                )
                existing = await _find_outline(
                    session,
                    project_id=project_id,
                    branch_id=resolved_branch_id,
                    title=item.title,
                    level=item.level,
                )
                target_outline = existing
                if item.level == "level_1" and target_outline is None:
                    target_outline = await _find_any_level_1_outline(
                        session,
                        project_id=project_id,
                        branch_id=resolved_branch_id,
                    )
                if target_outline is None:
                    mutation_result = await save_story_knowledge(
                        session,
                        project_id=project_id,
                        user_id=user_id,
                        section_key="outlines",
                        item=outline_payload,
                        branch_id=resolved_branch_id,
                        source_workflow="bulk_import",
                        guard_operation="导入",
                        skip_guard=True,
                    )
                    _extend_import_guard_warnings(
                        warnings,
                        section_key="outlines",
                        item_label=item.title,
                        mutation_result=mutation_result,
                    )
                    created = await _find_outline(
                        session,
                        project_id=project_id,
                        branch_id=resolved_branch_id,
                        title=item.title,
                        level=item.level,
                    )
                    if created is None:
                        raise AppError(
                            code="story_engine.import_outline_not_found",
                            message=f"大纲《{item.title}》导入后未能成功落库，请重试。",
                            status_code=500,
                        )
                else:
                    if item.level == "level_1" and getattr(target_outline, "locked", False):
                        _append_import_warning(
                            warnings,
                            f"一级大纲《{target_outline.title}》已锁定，这次导入保留原主线不覆盖。",
                        )
                        created = target_outline
                    else:
                        mutation_result = await save_story_knowledge(
                            session,
                            project_id=project_id,
                            user_id=user_id,
                            section_key="outlines",
                            item=outline_payload,
                            entity_id=str(target_outline.outline_id),
                            branch_id=resolved_branch_id,
                            source_workflow="bulk_import",
                            guard_operation="导入",
                            skip_guard=True,
                        )
                        _extend_import_guard_warnings(
                            warnings,
                            section_key="outlines",
                            item_label=item.title,
                            mutation_result=mutation_result,
                        )
                        created = await _find_outline(
                            session,
                            project_id=project_id,
                            branch_id=resolved_branch_id,
                            title=item.title,
                            level=item.level,
                        ) or target_outline
                outline_parent_map[item.title] = created.outline_id
                imported_counts["outlines"] += 1

        if _should_emit_bulk_import_section_event(
            section_key="outlines",
            input_counts=input_counts,
            replace_existing_sections=normalized_replace_sections,
        ):
            await record_event(
                stage="bulk_import_outlines",
                status="completed",
                label="三级大纲已导入",
                message=_build_bulk_import_section_message(
                    "outlines",
                    imported_counts["outlines"],
                    replace_mode="outlines" in normalized_replace_sections,
                ),
                details={
                    "section_key": "outlines",
                    "imported_count": imported_counts["outlines"],
                    "replace_mode": "outlines" in normalized_replace_sections,
                },
            )

        for item in payload.chapter_summaries:
            item_payload = item.model_dump()
            imported_signatures["chapter_summaries"].add(
                _build_import_payload_signature("chapter_summaries", item_payload)
            )
            existing = await _find_chapter_summary(
                session,
                project_id=project_id,
                branch_id=resolved_branch_id,
                chapter_number=item.chapter_number,
            )
            mutation_result = await save_story_knowledge(
                session,
                project_id=project_id,
                user_id=user_id,
                section_key="chapter_summaries",
                item=item_payload,
                entity_id=str(existing.summary_id) if existing is not None else None,
                branch_id=resolved_branch_id,
                source_workflow="bulk_import",
                guard_operation="导入",
                skip_guard=True,
            )
            _extend_import_guard_warnings(
                warnings,
                section_key="chapter_summaries",
                item_label=_build_import_item_label("chapter_summaries", item_payload),
                mutation_result=mutation_result,
            )
            imported_counts["chapter_summaries"] += 1

        if _should_emit_bulk_import_section_event(
            section_key="chapter_summaries",
            input_counts=input_counts,
            replace_existing_sections=normalized_replace_sections,
        ):
            await record_event(
                stage="bulk_import_chapter_summaries",
                status="completed",
                label="章节总结已导入",
                message=_build_bulk_import_section_message(
                    "chapter_summaries",
                    imported_counts["chapter_summaries"],
                    replace_mode="chapter_summaries" in normalized_replace_sections,
                ),
                details={
                    "section_key": "chapter_summaries",
                    "imported_count": imported_counts["chapter_summaries"],
                    "replace_mode": "chapter_summaries" in normalized_replace_sections,
                },
            )

        for section in normalized_replace_sections:
            for entity in existing_entities_by_section.get(section, []):
                if section == "outlines" and getattr(entity, "locked", False):
                    continue
                identity_signature = _build_import_entity_signature(section, entity)
                if identity_signature in imported_signatures[section]:
                    continue
                await delete_story_knowledge(
                    session,
                    project_id=project_id,
                    user_id=user_id,
                    section_key=section,
                    entity_id=str(getattr(entity, SECTION_ID_FIELD_MAP[section])),
                    branch_id=resolved_branch_id if section in {"outlines", "chapter_summaries"} else None,
                    source_workflow="bulk_import",
                )

        applied_model_preset_label: str | None = None
        if model_preset_key:
            project = await get_story_engine_project(
                session,
                project_id,
                user_id,
                permission=PROJECT_PERMISSION_EDIT,
            )
            project.story_engine_settings = build_story_engine_settings_for_preset(model_preset_key)
            session.add(project)
            await session.commit()
            await session.refresh(project)
            applied_model_preset_label = get_story_engine_model_preset_label(model_preset_key)
            await record_event(
                stage="bulk_import_model_preset_applied",
                status="completed",
                label="后台策略已套用",
                message=f"已套用后台策略：{applied_model_preset_label}。",
                details={
                    "applied_model_preset_key": model_preset_key,
                    "applied_model_preset_label": applied_model_preset_label,
                },
            )

        response = {
            "imported_counts": imported_counts,
            "replaced_sections": normalized_replace_sections,
            "applied_model_preset_key": model_preset_key,
            "applied_model_preset_label": applied_model_preset_label,
            "warnings": warnings,
            "workflow_timeline": workflow_timeline,
        }
        await record_event(
            stage="bulk_import_completed",
            status="completed",
            label="起盘设定已经导入",
            message=_build_bulk_import_completed_message(response),
            details={
                "imported_total": sum(imported_counts.values()),
                "warning_count": len(warnings),
                "replace_section_count": len(normalized_replace_sections),
            },
            finalize=True,
            result_patch={
                **_build_workflow_task_base_result(
                    workflow_id=workflow_id,
                    workflow_type="bulk_import",
                    workflow_status="completed",
                    chapter_number=None,
                    chapter_title=None,
                    branch_id=resolved_branch_id,
                    workflow_timeline=workflow_timeline,
                ),
                "incoming_counts": input_counts,
                "imported_counts": imported_counts,
                "replaced_sections": normalized_replace_sections,
                "warning_count": len(warnings),
                "applied_model_preset_key": model_preset_key,
                "applied_model_preset_label": applied_model_preset_label,
            },
        )
        return response
    except Exception as exc:
        await _persist_workflow_task_failure(
            session,
            task_state=task_state,
            project_id=project_id,
            user_id=user_id,
            chapter_id=None,
            workflow_id=workflow_id,
            workflow_type="bulk_import",
            chapter_number=None,
            chapter_title=None,
            branch_id=resolved_branch_id,
            error=exc,
            workflow_timeline=workflow_timeline,
        )
        raise


def _raise_when_bulk_import_guard_blocks(guard_result: dict[str, Any]) -> None:
    if not guard_result.get("blocked"):
        return
    raise AppError(
        code="story_engine.import_guard_blocked",
        message=str(guard_result.get("message") or "这批设定暂时不能导入。"),
        status_code=409,
        metadata={
            "alerts": guard_result.get("alerts") or [],
            "blocking_issue_count": int(guard_result.get("blocking_issue_count") or 0),
            "warning_count": int(guard_result.get("warning_count") or 0),
        },
    )


def _extend_import_preflight_warnings(
    warnings: list[str],
    guard_result: dict[str, Any],
) -> None:
    if int(guard_result.get("warning_count") or 0) <= 0:
        return
    issue_titles = [
        str(item.get("title") or "").strip()
        for item in guard_result.get("alerts") or []
        if str(item.get("severity") or "").strip().lower() in {"medium", "low"}
        and str(item.get("title") or "").strip()
    ]
    if issue_titles:
        summary = "；".join(issue_titles[:3])
    else:
        summary = str(guard_result.get("message") or "").strip() or "导入前总体验证有提醒"
    _append_import_warning(warnings, f"导入前校验提醒：{summary}。")


def _append_import_warning(warnings: list[str], message: str) -> None:
    normalized = str(message or "").strip()
    if not normalized or normalized in warnings:
        return
    if len(warnings) >= 20:
        return
    warnings.append(normalized)


def _extend_import_guard_warnings(
    warnings: list[str],
    *,
    section_key: str,
    item_label: str,
    mutation_result: dict[str, Any],
) -> None:
    if int(mutation_result.get("warning_count") or 0) <= 0:
        return
    alert_titles = [
        str(item.get("title") or "").strip()
        for item in mutation_result.get("alerts") or []
        if str(item.get("severity") or "").strip().lower() in {"medium", "low"}
        and str(item.get("title") or "").strip()
    ]
    if alert_titles:
        summary = "；".join(alert_titles[:2])
    else:
        summary = str(mutation_result.get("message") or "").strip() or "有连续性提醒"
    section_label = SECTION_LABEL_MAP.get(section_key, section_key)
    label = item_label.strip() or section_label
    _append_import_warning(
        warnings,
        f"{section_label}《{label}》已导入，但守护提醒：{summary}。",
    )


def _build_import_payload_signature(section_key: str, item: dict[str, Any]) -> str:
    if section_key == "characters":
        return f"name:{str(item.get('name') or '').strip()}"
    if section_key == "foreshadows":
        return f"content:{str(item.get('content') or '').strip()}"
    if section_key == "items":
        return f"name:{str(item.get('name') or '').strip()}"
    if section_key == "world_rules":
        return f"rule_name:{str(item.get('rule_name') or '').strip()}"
    if section_key == "timeline_events":
        return (
            f"chapter:{item.get('chapter_number')}|core_event:{str(item.get('core_event') or '').strip()}"
        )
    if section_key == "outlines":
        return f"level:{str(item.get('level') or '').strip()}|title:{str(item.get('title') or '').strip()}"
    if section_key == "chapter_summaries":
        return f"chapter_number:{item.get('chapter_number')}"
    return ""


def _build_import_entity_signature(section_key: str, entity: Any) -> str:
    if section_key == "characters":
        return f"name:{str(getattr(entity, 'name', '')).strip()}"
    if section_key == "foreshadows":
        return f"content:{str(getattr(entity, 'content', '')).strip()}"
    if section_key == "items":
        return f"name:{str(getattr(entity, 'name', '')).strip()}"
    if section_key == "world_rules":
        return f"rule_name:{str(getattr(entity, 'rule_name', '')).strip()}"
    if section_key == "timeline_events":
        return f"chapter:{getattr(entity, 'chapter_number', None)}|core_event:{str(getattr(entity, 'core_event', '')).strip()}"
    if section_key == "outlines":
        return f"level:{str(getattr(entity, 'level', '')).strip()}|title:{str(getattr(entity, 'title', '')).strip()}"
    if section_key == "chapter_summaries":
        return f"chapter_number:{getattr(entity, 'chapter_number', None)}"
    return ""


def _build_import_item_label(section_key: str, item: dict[str, Any]) -> str:
    if section_key == "foreshadows":
        return str(item.get("content") or "").strip()[:24] or "新伏笔"
    if section_key == "timeline_events":
        chapter_number = item.get("chapter_number")
        core_event = str(item.get("core_event") or "").strip()[:24]
        if chapter_number:
            return f"第{chapter_number}章 {core_event}".strip()
        return core_event or "时间线事件"
    if section_key == "chapter_summaries":
        chapter_number = item.get("chapter_number")
        return f"第{chapter_number}章总结" if chapter_number else "章节总结"
    for field in ("name", "rule_name", "title"):
        value = str(item.get(field) or "").strip()
        if value:
            return value
    return SECTION_LABEL_MAP.get(section_key, section_key)


def _build_import_section_counts(payload: dict[str, Any]) -> dict[str, int]:
    return {
        section: len(payload.get(section) or [])
        for section in IMPORTABLE_SECTIONS
    }


def _should_emit_bulk_import_section_event(
    *,
    section_key: str,
    input_counts: dict[str, int],
    replace_existing_sections: list[str],
) -> bool:
    return int(input_counts.get(section_key) or 0) > 0 or section_key in replace_existing_sections


def _build_bulk_import_section_message(
    section_key: str,
    imported_count: int,
    *,
    replace_mode: bool,
) -> str:
    section_label = SECTION_LABEL_MAP.get(section_key, section_key)
    if replace_mode:
        return f"{section_label}已导入 {imported_count} 条，并按区块清理了旧条目。"
    return f"{section_label}已导入 {imported_count} 条。"


def _build_bulk_import_completed_message(result: dict[str, Any]) -> str:
    imported_counts = dict(result.get("imported_counts") or {})
    pieces = [
        f"{SECTION_LABEL_MAP.get(section, section)}{count}条"
        for section, count in imported_counts.items()
        if int(count or 0) > 0
    ]
    summary = "，".join(pieces) if pieces else "设定包已经导入"
    warning_count = len(result.get("warnings") or [])
    if warning_count > 0:
        return f"起盘设定已导入：{summary}。另有 {warning_count} 条提醒可稍后处理。"
    return f"起盘设定已导入：{summary}。"


async def _find_by_field(
    session: AsyncSession,
    *,
    project_id: UUID,
    entity_type: str,
    field_name: str,
    field_value: Any,
) -> Any | None:
    model = SECTION_MODEL_MAP[entity_type]
    statement = select(model).where(
        model.project_id == project_id,
        getattr(model, field_name) == field_value,
    )
    result = await session.execute(statement)
    return result.scalar_one_or_none()


async def _find_timeline_event(
    session: AsyncSession,
    *,
    project_id: UUID,
    chapter_number: int | None,
    core_event: str,
) -> StoryTimelineMapEvent | None:
    statement = select(StoryTimelineMapEvent).where(
        StoryTimelineMapEvent.project_id == project_id,
        StoryTimelineMapEvent.chapter_number == chapter_number,
        StoryTimelineMapEvent.core_event == core_event,
    )
    result = await session.execute(statement)
    return result.scalar_one_or_none()


async def _find_outline(
    session: AsyncSession,
    *,
    project_id: UUID,
    branch_id: UUID,
    title: str,
    level: str,
) -> StoryOutline | None:
    statement = select(StoryOutline).where(
        StoryOutline.project_id == project_id,
        StoryOutline.branch_id == branch_id,
        StoryOutline.title == title,
        StoryOutline.level == level,
    )
    result = await session.execute(statement)
    return result.scalar_one_or_none()


async def _find_any_level_1_outline(
    session: AsyncSession,
    *,
    project_id: UUID,
    branch_id: UUID,
) -> StoryOutline | None:
    statement = select(StoryOutline).where(
        StoryOutline.project_id == project_id,
        StoryOutline.branch_id == branch_id,
        StoryOutline.level == "level_1",
    )
    result = await session.execute(statement)
    return result.scalars().first()


async def _find_outline_by_title(
    session: AsyncSession,
    *,
    project_id: UUID,
    branch_id: UUID,
    title: str,
) -> StoryOutline | None:
    statement = select(StoryOutline).where(
        StoryOutline.project_id == project_id,
        StoryOutline.branch_id == branch_id,
        StoryOutline.title == title,
    )
    result = await session.execute(statement)
    return result.scalars().first()


async def _find_chapter_summary(
    session: AsyncSession,
    *,
    project_id: UUID,
    branch_id: UUID,
    chapter_number: int,
) -> StoryChapterSummary | None:
    statement = select(StoryChapterSummary).where(
        StoryChapterSummary.project_id == project_id,
        StoryChapterSummary.branch_id == branch_id,
        StoryChapterSummary.chapter_number == chapter_number,
    )
    result = await session.execute(statement)
    return result.scalar_one_or_none()


async def _resolve_import_branch_id(
    session: AsyncSession,
    *,
    project_id: UUID,
    user_id: UUID,
    branch_id: UUID | None,
) -> UUID:
    project = await get_owned_project(
        session,
        project_id,
        user_id,
        with_relations=True,
        permission=PROJECT_PERMISSION_EDIT,
    )
    branches = sorted(
        list(project.branches),
        key=lambda item: (0 if item.is_default else 1, item.created_at),
    )
    if not branches:
        raise AppError(
            code="story_engine.branch_scope_missing",
            message="当前项目还没有可用分线，暂时不能导入这套设定。",
            status_code=409,
        )
    if branch_id is not None:
        matched_branch = next((item for item in branches if item.id == branch_id), None)
        if matched_branch is None:
            raise AppError(
                code="story_engine.branch_scope_not_found",
                message="当前分线不存在或已经被删除，请刷新后重试。",
                status_code=404,
            )
        return matched_branch.id
    default_branch = next((item for item in branches if item.is_default), None)
    return (default_branch or branches[0]).id
