from __future__ import annotations

import json
import re
from typing import Any, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from core.errors import AppError
from services.story_engine_model_service import (
    generate_story_agent_report,
)
from services.story_engine_settings_service import resolve_story_engine_model_routing
from services.story_engine_kb_service import build_workspace, get_story_engine_project

from ._shared import (
    LANGGRAPH_AVAILABLE,
    StateGraph,
    START,
    END,
    _build_workflow_id,
    _run_guardian_consensus_report,
    _merge_reports,
    build_agent_report,
)


async def run_story_knowledge_guard(
    session: AsyncSession,
    *,
    project_id: UUID,
    user_id: UUID,
    branch_id: Optional[UUID] = None,
    section_key: str,
    operation: str,
    candidate_item: dict[str, Any],
    entity_id: Optional[str] = None,
) -> dict[str, Any]:
    project = await get_story_engine_project(session, project_id, user_id)
    workspace = await build_workspace(
        session,
        project_id=project_id,
        user_id=user_id,
        branch_id=branch_id,
    )
    current_item = _find_story_knowledge_item_in_workspace(
        workspace=workspace,
        section_key=section_key,
        entity_id=entity_id,
    )
    fallback_issues = _build_story_knowledge_guard_fallback_issues(
        workspace=workspace,
        section_key=section_key,
        operation=operation,
        candidate_item=candidate_item,
        current_item=current_item,
    )
    fallback_report = build_agent_report(
        "guardian",
        summary=(
            "已完成设定修改前校验。"
            if fallback_issues
            else "当前设定修改暂未发现需要阻断的硬冲突。"
        ),
        issues=fallback_issues,
        proposed_actions=[
            item["suggestion"]
            for item in fallback_issues
            if str(item.get("suggestion") or "").strip()
        ]
        or ["当前改动可以写入设定圣经。"],
    )
    guard_report = await _run_guardian_consensus_report(
        task_name=f"story_engine.knowledge_guard.{section_key}.{operation}",
        task_goal="检查这次设定圣经的人工修改是否会撞上人物边界、世界规则、主线锁定或长期连续性红线。",
        context=_build_story_knowledge_guard_context_text(
            workspace=workspace,
            section_key=section_key,
            operation=operation,
            candidate_item=candidate_item,
            current_item=current_item,
        ),
        fallback_report=fallback_report,
        model_routing=resolve_story_engine_model_routing(project),
        workflow_key="knowledge",
        workflow_label="设定修改",
    )
    merged_report = _merge_reports(guard_report, fallback_report)
    alerts = list(merged_report.get("issues") or [])
    blocking_alerts = [
        item
        for item in alerts
        if str(item.get("severity") or "").strip().lower() in {"critical", "high"}
    ]
    warning_count = len(alerts) - len(blocking_alerts)
    if blocking_alerts:
        message = (
            f"这条设定暂时不能直接{operation}，先修掉'{blocking_alerts[0]['title']}'再继续。"
        )
    elif warning_count > 0:
        message = f"这条设定可以{operation}，但守护里还有 {warning_count} 条提醒，最好顺手修一下。"
    else:
        message = f"这条设定已经通过守护校验，可以直接{operation}。"
    return {
        "passed": not blocking_alerts,
        "blocked": bool(blocking_alerts),
        "message": message,
        "alerts": alerts,
        "blocking_issue_count": len(blocking_alerts),
        "warning_count": warning_count,
    }


async def run_story_bulk_import_guard(
    session: AsyncSession,
    *,
    project_id: UUID,
    user_id: UUID,
    branch_id: Optional[UUID] = None,
    payload: dict[str, Any],
) -> dict[str, Any]:
    project = await get_story_engine_project(session, project_id, user_id)
    workspace = await build_workspace(
        session,
        project_id=project_id,
        user_id=user_id,
        branch_id=branch_id,
    )
    fallback_issues = _build_story_bulk_import_guard_fallback_issues(
        workspace=workspace,
        payload=payload,
    )
    fallback_report = build_agent_report(
        "guardian",
        summary=(
            "已完成批量导入前校验。"
            if fallback_issues
            else "这批初始化设定暂未发现需要阻断的硬冲突。"
        ),
        issues=fallback_issues,
        proposed_actions=[
            str(item.get("suggestion") or "").strip()
            for item in fallback_issues
            if str(item.get("suggestion") or "").strip()
        ]
        or ["可以开始批量导入这套初始化设定。"],
    )
    remote_report = await generate_story_agent_report(
        agent_key="guardian",
        task_name="story_engine.bulk_import_guard",
        task_goal=(
            "检查这批初始化设定在正式导入前是否会撞上人物边界、世界规则、主线锁定、"
            "引用关系或长期连续性红线。"
            "请只标记真实存在的矛盾、缺漏引用和规则冲突。"
            "不要仅因为信息浓缩或字段较少，就把'信息颗粒度不足'本身判成高风险阻断项。"
        ),
        context=_build_story_bulk_import_guard_context_text(
            workspace=workspace,
            payload=payload,
        ),
        fallback_report=fallback_report,
        model_routing=resolve_story_engine_model_routing(project),
    )
    merged_report = _merge_reports(remote_report, fallback_report)
    alerts = list(merged_report.get("issues") or [])
    blocking_alerts = [
        item
        for item in alerts
        if str(item.get("severity") or "").strip().lower() in {"critical", "high"}
    ]
    warning_count = len(alerts) - len(blocking_alerts)
    if blocking_alerts:
        message = (
            f"这批设定暂时不能导入，先修掉'{blocking_alerts[0]['title']}'再继续。"
        )
    elif warning_count > 0:
        message = f"这批设定可以导入，但还有 {warning_count} 条连续性提醒。"
    else:
        message = "这批设定已经通过导入前校验，可以直接入库。"
    return {
        "passed": not blocking_alerts,
        "blocked": bool(blocking_alerts),
        "message": message,
        "alerts": alerts,
        "blocking_issue_count": len(blocking_alerts),
        "warning_count": warning_count,
        "report": merged_report,
    }


_STORY_KNOWLEDGE_SECTION_LABELS = {
    "characters": "人物设定",
    "foreshadows": "伏笔设定",
    "items": "物品设定",
    "world_rules": "世界规则",
    "timeline_events": "时间线事件",
    "outlines": "大纲节点",
    "chapter_summaries": "章节总结",
    "locations": "地点设定",
    "factions": "势力设定",
    "plot_threads": "剧情线设定",
}

_STORY_KNOWLEDGE_ID_FIELDS = {
    "characters": "character_id",
    "foreshadows": "foreshadow_id",
    "items": "item_id",
    "world_rules": "rule_id",
    "timeline_events": "event_id",
    "outlines": "outline_id",
    "chapter_summaries": "summary_id",
}

_STORY_KNOWLEDGE_PRIMARY_LABEL_FIELDS = {
    "characters": ("name",),
    "foreshadows": ("content",),
    "items": ("name",),
    "world_rules": ("rule_name",),
    "timeline_events": ("core_event", "location"),
    "outlines": ("title",),
    "chapter_summaries": ("chapter_number",),
    "locations": ("name",),
    "factions": ("name",),
    "plot_threads": ("title",),
}


def _read_story_knowledge_value(item: Any, field: str) -> Any:
    if item is None:
        return None
    if isinstance(item, dict):
        return item.get(field)
    return getattr(item, field, None)


def _read_story_knowledge_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        dumped = value.model_dump(mode="json")
        return dumped if isinstance(dumped, dict) else {}
    if hasattr(value, "__dict__"):
        return {
            key: item
            for key, item in vars(value).items()
            if not key.startswith("_")
        }
    return {}


def _serialize_story_knowledge_item(item: Any) -> dict[str, Any]:
    payload = _read_story_knowledge_dict(item)
    return {
        key: value
        for key, value in payload.items()
        if not key.startswith("_")
    }


def _story_knowledge_json_snippet(payload: Any, limit: int = 1200) -> str:
    try:
        text = json.dumps(payload, ensure_ascii=False, default=str)
    except TypeError:
        text = str(payload)
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _compact_prompt_text(text: str, limit: int = 5000) -> str:
    normalized = str(text or "").strip()
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 3] + "..."


def _build_agent_report_prompt_snapshot(
    report: dict[str, Any],
    *,
    max_issues: int = 5,
    max_actions: int = 5,
) -> dict[str, Any]:
    raw_output = dict(report.get("raw_output") or {})
    return {
        "agent_name": report.get("agent_name"),
        "role": report.get("role"),
        "summary": report.get("summary"),
        "issues": [
            {
                "severity": item.get("severity"),
                "title": item.get("title"),
                "detail": _compact_prompt_text(str(item.get("detail") or ""), 240),
                "source": item.get("source"),
                "suggestion": item.get("suggestion"),
            }
            for item in list(report.get("issues") or [])[:max_issues]
        ],
        "proposed_actions": list(report.get("proposed_actions") or [])[:max_actions],
        "provider": raw_output.get("provider"),
        "model": raw_output.get("model"),
        "used_fallback": raw_output.get("used_fallback"),
    }


def _truncate_deliberation_text(text: Any, limit: int = 96) -> str:
    normalized = re.sub(r"\s+", " ", str(text or "").strip())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 1] + "…"


def _format_deliberation_actor_label(report: dict[str, Any]) -> str:
    role = str(report.get("role") or report.get("agent_name") or "分析者").strip()
    return role.replace("_Agent", "").replace("Agent", "").strip()


def _build_deliberation_entry_from_report(
    report: dict[str, Any],
    *,
    stance: str,
    actor_label: Optional[str] = None,
    summary: Optional[str] = None,
    evidence: Optional[list[str]] = None,
    actions: Optional[list[str]] = None,
    issues: Optional[list[dict[str, Any]]] = None,
) -> dict[str, Any]:
    report_issues = list(issues if issues is not None else report.get("issues") or [])
    report_actions = list(actions if actions is not None else report.get("proposed_actions") or [])
    computed_evidence = list(evidence or [])
    raw_output = dict(report.get("raw_output") or {})

    if raw_output.get("guardian_consensus_mode") == "dual":
        if raw_output.get("disagreement"):
            computed_evidence.append("这一步先做了双路交叉复核，再由第三方收口。")
        else:
            computed_evidence.append("这一步做了双路交叉复核，结论一致。")

    if not computed_evidence and report_issues:
        for item in report_issues[:2]:
            computed_evidence.append(
                f"{str(item.get('title') or '').strip()}：{_truncate_deliberation_text(item.get('detail'), 72)}"
            )
    if not computed_evidence and report_actions:
        computed_evidence.extend(
            [f"动作：{_truncate_deliberation_text(item, 72)}" for item in report_actions[:2]]
        )
    if not computed_evidence:
        computed_evidence.append("本轮没有保留新的硬问题。")

    return {
        "actor_key": str(report.get("agent_name") or report.get("role") or stance).strip().lower(),
        "actor_label": actor_label or _format_deliberation_actor_label(report),
        "role": str(report.get("role") or "").strip(),
        "stance": stance,
        "summary": summary or str(report.get("summary") or "").strip(),
        "evidence": computed_evidence[:3],
        "actions": report_actions[:3],
        "issues": report_issues[:3],
    }


def _serialize_story_api_entities(
    entity_type: str,
    entities: list[Any],
) -> list[dict[str, Any]]:
    schema = _STORY_ENGINE_READ_SCHEMAS.get(entity_type)
    if schema is None:
        raise AppError(
            code="story_engine.api_entity_serialize_unsupported",
            message=f"当前实体类型暂不支持 API 序列化：{entity_type}",
            status_code=500,
        )
    return [
        schema.model_validate(item).model_dump(mode="json")
        for item in entities
    ]


def _normalize_story_knowledge_text(value: Any) -> str:
    return str(value or "").strip().lower()


def _get_story_knowledge_workspace_items(
    *,
    workspace: dict[str, Any],
    section_key: str,
) -> list[Any]:
    if section_key in {
        "characters",
        "foreshadows",
        "items",
        "world_rules",
        "timeline_events",
        "outlines",
        "chapter_summaries",
    }:
        return list(workspace.get(section_key) or [])
    story_bible = workspace.get("story_bible") or {}
    if section_key in {"locations", "factions", "plot_threads"}:
        return list(story_bible.get(section_key) or [])
    return []


def _resolve_story_knowledge_workspace_identity(section_key: str, item: Any) -> str:
    id_field = _STORY_KNOWLEDGE_ID_FIELDS.get(section_key)
    if id_field:
        value = _read_story_knowledge_value(item, id_field)
        if value is not None and str(value).strip():
            return str(value).strip()
    for field in ("id", "key", "name", "title", "content"):
        value = _read_story_knowledge_value(item, field)
        if value is not None and str(value).strip():
            return f"{field}:{str(value).strip()}"
    return ""


def _resolve_story_knowledge_item_label(section_key: str, item: Any) -> str:
    for field in _STORY_KNOWLEDGE_PRIMARY_LABEL_FIELDS.get(section_key, ()):
        value = _read_story_knowledge_value(item, field)
        if value is None:
            continue
        text = str(value).strip()
        if not text:
            continue
        if field == "chapter_number":
            return f"第{text}章总结"
        return text
    return ""


def _find_story_knowledge_item_in_workspace(
    *,
    workspace: dict[str, Any],
    section_key: str,
    entity_id: Optional[str],
) -> Any:
    target_entity_id = str(entity_id or "").strip()
    if not target_entity_id:
        return None
    for item in _get_story_knowledge_workspace_items(workspace=workspace, section_key=section_key):
        if _resolve_story_knowledge_workspace_identity(section_key, item) == target_entity_id:
            return item
    return None


def _build_story_knowledge_issue(
    *,
    severity: str,
    title: str,
    detail: str,
    suggestion: str,
) -> dict[str, Any]:
    return {
        "severity": severity,
        "title": title,
        "detail": detail,
        "source": "guardian",
        "suggestion": suggestion,
    }


def _build_story_knowledge_guard_fallback_issues(
    *,
    workspace: dict[str, Any],
    section_key: str,
    operation: str,
    candidate_item: dict[str, Any],
    current_item: Any,
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    section_items = _get_story_knowledge_workspace_items(
        workspace=workspace,
        section_key=section_key,
    )
    current_identity = _resolve_story_knowledge_workspace_identity(section_key, current_item)
    other_items = [
        item
        for item in section_items
        if _resolve_story_knowledge_workspace_identity(section_key, item) != current_identity
    ]
    current_label = _resolve_story_knowledge_item_label(section_key, current_item)
    next_label = (
        _resolve_story_knowledge_item_label(section_key, candidate_item)
        or current_label
    )

    if operation == "删除":
        issues.extend(
            _build_story_knowledge_delete_guard_issues(
                workspace=workspace,
                section_key=section_key,
                current_item=current_item,
                section_items=section_items,
                current_label=current_label,
            )
        )
        return issues

    if section_key == "characters":
        if not next_label:
            issues.append(
                _build_story_knowledge_issue(
                    severity="critical",
                    title="人物名不能为空",
                    detail="这次人物设定没有给出稳定称呼，后续检索和连续性都会失焦。",
                    suggestion="先补一个稳定的人物名，再保存这条设定。",
                )
            )
        elif any(
            _normalize_story_knowledge_text(_resolve_story_knowledge_item_label("characters", item))
            == _normalize_story_knowledge_text(next_label)
            for item in other_items
        ):
            issues.append(
                _build_story_knowledge_issue(
                    severity="high",
                    title="人物重名会冲掉设定锚点",
                    detail=f"当前已经存在同名人物'{next_label}'，继续保存会让后续引用和守护检索变得混乱。",
                    suggestion="先把人物名区分开，或合并为同一人物后再保存。",
                )
            )

    if section_key == "world_rules":
        rule_name = str(candidate_item.get("rule_name") or current_label or "").strip()
        if not rule_name:
            issues.append(
                _build_story_knowledge_issue(
                    severity="critical",
                    title="规则名不能为空",
                    detail="没有稳定的规则名，后续规则校验很难锁定这条边界。",
                    suggestion="先补一个明确规则名，再保存。",
                )
            )
        elif any(
            _normalize_story_knowledge_text(_resolve_story_knowledge_item_label("world_rules", item))
            == _normalize_story_knowledge_text(rule_name)
            for item in other_items
        ):
            issues.append(
                _build_story_knowledge_issue(
                    severity="high",
                    title="世界规则名称重复",
                    detail=f"当前已经有一条规则叫'{rule_name}'，继续保存容易让规则边界互相覆盖。",
                    suggestion="把重复规则合并，或改成更具体的规则名。",
                )
            )

    if section_key == "foreshadows":
        chapter_planted = candidate_item.get("chapter_planted")
        chapter_reveal = candidate_item.get("chapter_planned_reveal")
        if (
            isinstance(chapter_planted, int)
            and isinstance(chapter_reveal, int)
            and chapter_reveal < chapter_planted
        ):
            issues.append(
                _build_story_knowledge_issue(
                    severity="high",
                    title="伏笔回收早于埋下",
                    detail=f"当前设定计划在第 {chapter_reveal} 章回收，但伏笔要到第 {chapter_planted} 章才埋下，时间线会直接打架。",
                    suggestion="把回收章节调到埋下章节之后，或提前埋伏笔。",
                )
            )

    if section_key == "outlines":
        current_level = str(_read_story_knowledge_value(current_item, "level") or "").strip()
        next_level = str(candidate_item.get("level") or current_level).strip()
        current_locked = bool(_read_story_knowledge_value(current_item, "locked"))
        next_locked = bool(candidate_item.get("locked")) or current_locked
        if current_locked or (
            operation != "导入"
            and next_level == "level_1"
            and next_locked
        ):
            issues.append(
                _build_story_knowledge_issue(
                    severity="critical",
                    title="一级大纲已锁定",
                    detail="这条大纲属于主线圣经锁定区，人工改写会直接破坏整本书的统一基准。",
                    suggestion="保留一级大纲不动，把变化落到二级或三级大纲里。",
                )
            )

    if section_key in {"locations", "factions", "plot_threads"} and next_label:
        duplicate_exists = any(
            _normalize_story_knowledge_text(
                _resolve_story_knowledge_item_label(section_key, item)
            )
            == _normalize_story_knowledge_text(next_label)
            for item in other_items
        )
        if duplicate_exists:
            issues.append(
                _build_story_knowledge_issue(
                    severity="medium",
                    title="主设定里已经有同名条目",
                    detail=f"当前分支里已经存在'{next_label}'，继续保存会让后续引用更难区分。",
                    suggestion="确认是不是同一条设定；如果是，建议直接改已有条目而不是再建一条。",
                )
            )

    if current_item and current_label and next_label and current_label != next_label:
        references = _collect_story_knowledge_references(
            workspace=workspace,
            section_key=section_key,
            label=current_label,
            entity_identity=current_identity,
        )
        if references:
            issues.append(
                _build_story_knowledge_issue(
                    severity="high",
                    title="改名会打断已有引用",
                    detail=(
                        f"当前还有 {len(references)} 处设定在引用'{current_label}'，"
                        f"直接改名成'{next_label}'会让这些引用失效。"
                        f"例如：{references[0]}"
                    ),
                    suggestion="先把引用一并改掉，或保留旧名作为别称后再保存。",
                )
            )
    return issues


def _build_story_knowledge_delete_guard_issues(
    *,
    workspace: dict[str, Any],
    section_key: str,
    current_item: Any,
    section_items: list[Any],
    current_label: str,
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    if current_item is None:
        issues.append(
            _build_story_knowledge_issue(
                severity="medium",
                title="当前条目不在最新工作台里",
                detail="这条设定在最新工作台里已经找不到了，删除前最好先刷新一下，避免删错目标。",
                suggestion="先刷新工作台确认目标条目，再执行删除。",
            )
        )
        return issues

    if section_key == "characters" and len(section_items) <= 1:
        issues.append(
            _build_story_knowledge_issue(
                severity="critical",
                title="至少保留一个人物锚点",
                detail="当前只剩这一个人物设定，直接删除会让人物关系、伏笔归属和后续正文全部失去锚点。",
                suggestion="至少保留一个核心人物，或先补入替代人物后再删。",
            )
        )

    if section_key == "world_rules" and len(section_items) <= 1:
        issues.append(
            _build_story_knowledge_issue(
                severity="critical",
                title="至少保留一条世界规则",
                detail="当前只剩这一条规则边界，删除后世界观会失去基础约束，后续守护也无法稳定判定。",
                suggestion="先补一条新的基础规则，或确认项目已有其它规则后再删。",
            )
        )

    if section_key == "outlines":
        current_level = str(_read_story_knowledge_value(current_item, "level") or "").strip()
        if current_level == "level_1" or bool(_read_story_knowledge_value(current_item, "locked")):
            issues.append(
                _build_story_knowledge_issue(
                    severity="critical",
                    title="主线锁定大纲不能删除",
                    detail="这条大纲属于整本书的锁定主线，一旦删除会导致所有卷线和章节细纲失去基准。",
                    suggestion="保留一级大纲不动，把变更下沉到二级或三级大纲。",
                )
            )

    references = _collect_story_knowledge_references(
        workspace=workspace,
        section_key=section_key,
        label=current_label,
        entity_identity=_resolve_story_knowledge_workspace_identity(section_key, current_item),
    )
    if references:
        issues.append(
            _build_story_knowledge_issue(
                severity="high",
                title="这条设定仍被其他内容引用",
                detail=(
                    f"当前还有 {len(references)} 处设定在引用'{current_label or '当前条目'}'，"
                    f"直接删除会留下悬空引用。"
                    f"例如：{references[0]}"
                ),
                suggestion="先清理相关引用，或改成停用状态而不是直接删除。",
            )
        )
    return issues


def _collect_story_knowledge_references(
    *,
    workspace: dict[str, Any],
    section_key: str,
    label: str,
    entity_identity: str,
) -> list[str]:
    references: list[str] = []
    normalized_label = _normalize_story_knowledge_text(label)
    normalized_identity = _normalize_story_knowledge_text(entity_identity)
    if not normalized_label and not normalized_identity:
        return references

    def matches(value: Any) -> bool:
        text = _normalize_story_knowledge_text(value)
        if not text:
            return False
        return text == normalized_label or text == normalized_identity

    if section_key == "characters":
        for item in workspace.get("items") or []:
            if matches(_read_story_knowledge_value(item, "owner")):
                references.append(
                    f"物品'{_resolve_story_knowledge_item_label('items', item) or '未命名物品'}'仍把 ta 记成持有人。"
                )
        for item in workspace.get("characters") or []:
            if _resolve_story_knowledge_workspace_identity("characters", item) == entity_identity:
                continue
            for relation in _read_story_knowledge_value(item, "relationships") or []:
                relation_dict = _read_story_knowledge_dict(relation)
                if matches(relation_dict.get("target_name")) or matches(relation_dict.get("target_id")):
                    references.append(
                        f"人物'{_resolve_story_knowledge_item_label('characters', item) or '未命名人物'}'的关系链仍指向 ta。"
                    )
                    break
        for item in workspace.get("foreshadows") or []:
            related_characters = _read_story_knowledge_value(item, "related_characters") or []
            if any(matches(name) for name in related_characters):
                references.append(
                    f"伏笔'{_resolve_story_knowledge_item_label('foreshadows', item)[:24]}'仍挂在 ta 身上。"
                )
        story_bible = workspace.get("story_bible") or {}
        for item in story_bible.get("factions") or []:
            if matches(_read_story_knowledge_value(item, "leader")) or any(
                matches(member) for member in (_read_story_knowledge_value(item, "members") or [])
            ):
                references.append(
                    f"势力'{_resolve_story_knowledge_item_label('factions', item) or '未命名势力'}'仍在引用 ta。"
                )
        for item in story_bible.get("locations") or []:
            data = _read_story_knowledge_dict(_read_story_knowledge_value(item, "data"))
            if any(matches(name) for name in (data.get("notable_residents") or [])):
                references.append(
                    f"地点'{_resolve_story_knowledge_item_label('locations', item) or '未命名地点'}'仍把 ta 记成常驻人物。"
                )
        for item in story_bible.get("plot_threads") or []:
            data = _read_story_knowledge_dict(_read_story_knowledge_value(item, "data"))
            if any(matches(name) for name in (data.get("main_characters") or [])):
                references.append(
                    f"剧情线'{_resolve_story_knowledge_item_label('plot_threads', item) or '未命名剧情线'}'仍把 ta 记成核心人物。"
                )
        for item in workspace.get("timeline_events") or []:
            for state in _read_story_knowledge_value(item, "character_states") or []:
                state_dict = _read_story_knowledge_dict(state)
                if matches(state_dict.get("name")) or matches(state_dict.get("character_name")):
                    references.append(
                        f"时间线事件'{_resolve_story_knowledge_item_label('timeline_events', item)[:24]}'仍写着 ta 的状态。"
                    )
                    break

    if section_key == "locations":
        for item in workspace.get("items") or []:
            if matches(_read_story_knowledge_value(item, "location")):
                references.append(
                    f"物品'{_resolve_story_knowledge_item_label('items', item) or '未命名物品'}'仍放在这里。"
                )
        for item in workspace.get("timeline_events") or []:
            if matches(_read_story_knowledge_value(item, "location")):
                references.append(
                    f"时间线事件'{_resolve_story_knowledge_item_label('timeline_events', item)[:24]}'仍发生在这里。"
                )
        story_bible = workspace.get("story_bible") or {}
        for item in story_bible.get("factions") or []:
            if matches(_read_story_knowledge_value(item, "territory")):
                references.append(
                    f"势力'{_resolve_story_knowledge_item_label('factions', item) or '未命名势力'}'仍把这里当作地盘。"
                )
        for item in story_bible.get("plot_threads") or []:
            data = _read_story_knowledge_dict(_read_story_knowledge_value(item, "data"))
            if any(matches(name) for name in (data.get("locations") or [])):
                references.append(
                    f"剧情线'{_resolve_story_knowledge_item_label('plot_threads', item) or '未命名剧情线'}'仍绑定这个地点。"
                )

    if section_key == "items":
        for item in workspace.get("foreshadows") or []:
            related_items = _read_story_knowledge_value(item, "related_items") or []
            if any(matches(name) for name in related_items):
                references.append(
                    f"伏笔'{_resolve_story_knowledge_item_label('foreshadows', item)[:24]}'仍在引用这件物品。"
                )
    return references


def _build_story_knowledge_guard_context_text(
    *,
    workspace: dict[str, Any],
    section_key: str,
    operation: str,
    candidate_item: dict[str, Any],
    current_item: Any,
) -> str:
    project = workspace.get("project") or {}
    section_items = _get_story_knowledge_workspace_items(
        workspace=workspace,
        section_key=section_key,
    )
    section_preview = [
        {
            "id": _resolve_story_knowledge_workspace_identity(section_key, item),
            "label": _resolve_story_knowledge_item_label(section_key, item),
        }
        for item in section_items[:8]
    ]
    story_bible = workspace.get("story_bible") or {}
    context_payload = {
        "project": {
            "title": project.get("title"),
            "genre": project.get("genre"),
            "theme": project.get("theme"),
            "tone": project.get("tone"),
        },
        "operation": operation,
        "section": {
            "key": section_key,
            "label": _STORY_KNOWLEDGE_SECTION_LABELS.get(section_key, section_key),
        },
        "current_item": _serialize_story_knowledge_item(current_item),
        "candidate_item": candidate_item,
        "same_section_items": section_preview,
        "workspace_snapshot": {
            "characters": [
                {
                    "name": _resolve_story_knowledge_item_label("characters", item),
                    "status": _read_story_knowledge_value(item, "status"),
                    "arc_stage": _read_story_knowledge_value(item, "arc_stage"),
                }
                for item in (workspace.get("characters") or [])[:6]
            ],
            "world_rules": [
                _resolve_story_knowledge_item_label("world_rules", item)
                for item in (workspace.get("world_rules") or [])[:6]
            ],
            "outlines": [
                {
                    "level": _read_story_knowledge_value(item, "level"),
                    "title": _resolve_story_knowledge_item_label("outlines", item),
                    "locked": bool(_read_story_knowledge_value(item, "locked")),
                }
                for item in (workspace.get("outlines") or [])[:6]
            ],
            "locations": [
                _resolve_story_knowledge_item_label("locations", item)
                for item in (story_bible.get("locations") or [])[:6]
            ],
            "factions": [
                _resolve_story_knowledge_item_label("factions", item)
                for item in (story_bible.get("factions") or [])[:6]
            ],
            "plot_threads": [
                _resolve_story_knowledge_item_label("plot_threads", item)
                for item in (story_bible.get("plot_threads") or [])[:6]
            ],
            "timeline_events": [
                _resolve_story_knowledge_item_label("timeline_events", item)
                for item in (workspace.get("timeline_events") or [])[:4]
            ],
        },
    }
    return (
        f"任务：检查一次设定圣经的人工{operation}是否安全。\n"
        f"上下文：{_story_knowledge_json_snippet(context_payload, 5200)}"
    )


def _build_story_bulk_import_guard_fallback_issues(
    *,
    workspace: dict[str, Any],
    payload: dict[str, Any],
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    imported_characters = payload.get("characters") if isinstance(payload.get("characters"), list) else []
    imported_world_rules = payload.get("world_rules") if isinstance(payload.get("world_rules"), list) else []
    imported_foreshadows = payload.get("foreshadows") if isinstance(payload.get("foreshadows"), list) else []
    imported_items = payload.get("items") if isinstance(payload.get("items"), list) else []
    imported_outlines = payload.get("outlines") if isinstance(payload.get("outlines"), list) else []

    known_character_names = {
        _resolve_story_knowledge_item_label("characters", item)
        for item in (workspace.get("characters") or [])
    }
    known_character_names.update(
        str(item.get("name") or "").strip()
        for item in imported_characters
        if str(item.get("name") or "").strip()
    )
    known_item_names = {
        _resolve_story_knowledge_item_label("items", item)
        for item in (workspace.get("items") or [])
    }
    known_item_names.update(
        str(item.get("name") or "").strip()
        for item in imported_items
        if str(item.get("name") or "").strip()
    )

    if not imported_characters and not (workspace.get("characters") or []):
        issues.append(
            {
                "severity": "critical",
                "title": "缺少人物锚点",
                "detail": "当前项目里没有可用人物，这批导入也没有补人物，后续正文会失去稳定锚点。",
                "source": "guardian",
                "suggestion": "至少补一个主角或核心对手，再开始初始化。",
            }
        )

    if not imported_world_rules and not (workspace.get("world_rules") or []):
        issues.append(
            {
                "severity": "high",
                "title": "缺少世界规则约束",
                "detail": "当前项目里没有世界规则，这批导入也没有补规则，后续很容易写出无代价开挂。",
                "source": "guardian",
                "suggestion": "至少补一条能长期约束战力或代价的世界规则。",
            }
        )

    for item in imported_characters:
        source_name = str(item.get("name") or "").strip() or "未命名人物"
        for relation in item.get("relationships") or []:
            target_name = str(relation.get("target_name") or "").strip()
            if target_name and target_name not in known_character_names:
                issues.append(
                    {
                        "severity": "high",
                        "title": f"人物关系目标缺失：{source_name}",
                        "detail": f"人物'{source_name}'引用了不存在的关系对象'{target_name}'。",
                        "source": "guardian",
                        "suggestion": "先补齐目标人物，或把这条关系移到后续再补。",
                    }
                )

    for item in imported_foreshadows:
        planted = item.get("chapter_planted")
        reveal = item.get("chapter_planned_reveal")
        content = str(item.get("content") or "").strip()[:24] or "未命名伏笔"
        if planted is not None and reveal is not None and int(reveal) < int(planted):
            issues.append(
                {
                    "severity": "high",
                    "title": f"伏笔回收顺序错误：{content}",
                    "detail": "计划回收章节早于埋设章节，这条伏笔会直接破坏时间线。",
                    "source": "guardian",
                    "suggestion": "把回收章节调到埋设章节之后，或重设埋点位置。",
                }
            )
        missing_characters = sorted(
            {
                str(name).strip()
                for name in item.get("related_characters") or []
                if str(name).strip() and str(name).strip() not in known_character_names
            }
        )
        if missing_characters:
            issues.append(
                {
                    "severity": "medium",
                    "title": f"伏笔关联人物待补齐：{content}",
                    "detail": f"这条伏笔引用了未落地人物：{', '.join(missing_characters)}。",
                    "source": "guardian",
                    "suggestion": "补齐对应人物，或先删掉这些关联字段。",
                }
            )
        missing_items = sorted(
            {
                str(name).strip()
                for name in item.get("related_items") or []
                if str(name).strip() and str(name).strip() not in known_item_names
            }
        )
        if missing_items:
            issues.append(
                {
                    "severity": "medium",
                    "title": f"伏笔关联物品待补齐：{content}",
                    "detail": f"这条伏笔引用了未落地物品：{', '.join(missing_items)}。",
                    "source": "guardian",
                    "suggestion": "补齐对应物品，或先删掉这组关联。",
                }
            )

    outline_titles = {
        str(item.get("title") or "").strip()
        for item in imported_outlines
        if str(item.get("title") or "").strip()
    }
    outline_titles.update(
        _resolve_story_knowledge_item_label("outlines", item)
        for item in (workspace.get("outlines") or [])
    )
    for item in imported_outlines:
        parent_title = str(item.get("parent_title") or "").strip()
        title = str(item.get("title") or "").strip() or "未命名大纲"
        if parent_title and parent_title not in outline_titles:
            issues.append(
                {
                    "severity": "medium",
                    "title": f"大纲父节点缺失：{title}",
                    "detail": f"大纲'{title}'声明了父节点'{parent_title}'，但当前项目中找不到它。",
                    "source": "guardian",
                    "suggestion": "先补父节点，或改成挂到现有卷纲/主线下。",
                }
            )
    return issues


def _build_story_bulk_import_guard_context_text(
    *,
    workspace: dict[str, Any],
    payload: dict[str, Any],
) -> str:
    project = workspace.get("project") or {}
    story_bible = workspace.get("story_bible") or {}
    context_payload = {
        "project": {
            "title": project.get("title"),
            "genre": project.get("genre"),
            "theme": project.get("theme"),
            "tone": project.get("tone"),
        },
        "existing_workspace": {
            "character_count": len(workspace.get("characters") or []),
            "world_rule_count": len(workspace.get("world_rules") or []),
            "outline_count": len(workspace.get("outlines") or []),
            "foreshadow_count": len(workspace.get("foreshadows") or []),
            "item_count": len(workspace.get("items") or []),
            "story_bible_sections": {
                "locations": len(story_bible.get("locations") or []),
                "factions": len(story_bible.get("factions") or []),
                "plot_threads": len(story_bible.get("plot_threads") or []),
            },
        },
        "incoming_payload": _build_story_bulk_import_payload_snapshot(payload),
        "incoming_payload_excerpt": _story_knowledge_json_snippet(payload, 3200),
    }
    return (
        "任务：检查一批初始化设定在正式导入前是否安全。\n"
        f"上下文：{_story_knowledge_json_snippet(context_payload, 5600)}"
    )


def _build_story_bulk_import_payload_snapshot(payload: dict[str, Any]) -> dict[str, Any]:
    def _items(key: str) -> list[dict[str, Any]]:
        value = payload.get(key)
        return value if isinstance(value, list) else []

    characters = _items("characters")
    world_rules = _items("world_rules")
    foreshadows = _items("foreshadows")
    items = _items("items")
    outlines = _items("outlines")
    timeline_events = _items("timeline_events")
    chapter_summaries = _items("chapter_summaries")
    return {
        "counts": {
            "characters": len(characters),
            "world_rules": len(world_rules),
            "foreshadows": len(foreshadows),
            "items": len(items),
            "outlines": len(outlines),
            "timeline_events": len(timeline_events),
            "chapter_summaries": len(chapter_summaries),
        },
        "character_labels": [
            str(item.get("name") or "").strip()
            for item in characters[:6]
            if str(item.get("name") or "").strip()
        ],
        "world_rule_labels": [
            str(item.get("rule_name") or "").strip()
            for item in world_rules[:6]
            if str(item.get("rule_name") or "").strip()
        ],
        "foreshadow_labels": [
            str(item.get("content") or "").strip()[:36]
            for item in foreshadows[:4]
            if str(item.get("content") or "").strip()
        ],
        "item_labels": [
            str(item.get("name") or "").strip()
            for item in items[:4]
            if str(item.get("name") or "").strip()
        ],
        "character_cards": [
            {
                "name": str(item.get("name") or "").strip(),
                "personality": str(item.get("personality") or "").strip(),
                "status": str(item.get("status") or "").strip(),
                "arc_stage": str(item.get("arc_stage") or "").strip(),
                "relationships": item.get("relationships") or [],
                "arc_boundaries": item.get("arc_boundaries") or [],
            }
            for item in characters[:4]
            if str(item.get("name") or "").strip()
        ],
        "world_rule_cards": [
            {
                "rule_name": str(item.get("rule_name") or "").strip(),
                "rule_content": str(item.get("rule_content") or "").strip(),
                "negative_list": item.get("negative_list") or [],
                "scope": str(item.get("scope") or "").strip(),
            }
            for item in world_rules[:4]
            if str(item.get("rule_name") or "").strip()
        ],
        "foreshadow_cards": [
            {
                "content": str(item.get("content") or "").strip(),
                "chapter_planted": item.get("chapter_planted"),
                "chapter_planned_reveal": item.get("chapter_planned_reveal"),
                "related_characters": item.get("related_characters") or [],
                "related_items": item.get("related_items") or [],
            }
            for item in foreshadows[:4]
            if str(item.get("content") or "").strip()
        ],
        "item_cards": [
            {
                "name": str(item.get("name") or "").strip(),
                "owner": str(item.get("owner") or "").strip(),
                "location": str(item.get("location") or "").strip(),
                "special_rules": item.get("special_rules") or [],
            }
            for item in items[:4]
            if str(item.get("name") or "").strip()
        ],
        "outline_labels": [
            {
                "level": str(item.get("level") or "").strip(),
                "title": str(item.get("title") or "").strip(),
                "content": str(item.get("content") or "").strip()[:120],
                "parent_title": str(item.get("parent_title") or "").strip(),
            }
            for item in outlines[:8]
            if str(item.get("title") or "").strip()
        ],
    }