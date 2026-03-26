from __future__ import annotations

import asyncio
import json
import re
from collections import Counter
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Optional, TypedDict
from uuid import UUID, uuid4

from fastapi.encoders import jsonable_encoder
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from agents.story_agents import build_agent_report, export_agent_specs
from core.config import get_settings
from core.errors import AppError
from models.story_engine import StoryChapterSummary, StoryOutline
from schemas.story_engine import (
    StoryCharacterRead,
    StoryForeshadowRead,
    StoryItemRead,
    StoryOutlineRead,
    StoryTimelineMapEventRead,
    StoryWorldRuleRead,
)
from services.chapter_service import get_owned_chapter
from services.story_engine_kb_service import (
    build_workspace,
    create_entity,
    get_entity,
    get_story_engine_project,
    list_entities,
    search_knowledge,
    update_entity,
)
from services.story_engine_model_service import (
    build_outline_context_text,
    build_realtime_guard_context_text,
    build_workspace_context_text,
    generate_story_agent_report,
    generate_story_anchor_payload,
    generate_story_outline_blueprint,
    generate_story_realtime_arbitration,
    generate_story_stream_paragraph,
    get_story_engine_role_model,
    revise_story_final_draft,
)
from services.story_engine_settings_service import (
    get_story_engine_guardian_consensus_config,
    resolve_story_engine_model_routing,
)
from services.task_service import create_task_event, create_task_run, update_task_run
from tasks.schemas import TaskState
from tasks.state_store import task_state_store

try:
    from langgraph.graph import END, START, StateGraph

    LANGGRAPH_AVAILABLE = True
except ImportError:  # pragma: no cover - 开发环境缺依赖时走本地串行兜底
    END = "__end__"
    START = "__start__"
    StateGraph = None
    LANGGRAPH_AVAILABLE = False


_STORY_ENGINE_READ_SCHEMAS = {
    "characters": StoryCharacterRead,
    "foreshadows": StoryForeshadowRead,
    "items": StoryItemRead,
    "world_rules": StoryWorldRuleRead,
    "timeline_events": StoryTimelineMapEventRead,
    "outlines": StoryOutlineRead,
}


class OutlineStressState(TypedDict, total=False):
    session: AsyncSession
    project_id: UUID
    user_id: UUID
    branch_id: Optional[UUID]
    idea: str
    source_material: Optional[str]
    source_material_name: Optional[str]
    genre: Optional[str]
    tone: Optional[str]
    target_chapter_count: int
    target_total_words: int
    model_routing: dict[str, dict[str, Any]]
    outline_draft: dict[str, list[dict[str, Any]]]
    initial_kb: dict[str, list[dict[str, Any]]]
    guardian_report: dict[str, Any]
    commercial_report: dict[str, Any]
    logic_report: dict[str, Any]
    debate_round: int
    unresolved_issues: list[dict[str, Any]]
    optimization_plan: list[str]
    debate_history: list[dict[str, Any]]
    arbitrated_report: dict[str, Any]


class RealtimeGuardState(TypedDict, total=False):
    session: AsyncSession
    project_id: UUID
    user_id: UUID
    branch_id: Optional[UUID]
    chapter_number: int
    chapter_title: Optional[str]
    outline_id: Optional[UUID]
    current_outline: Optional[str]
    recent_chapters: list[str]
    draft_text: str
    latest_paragraph: Optional[str]
    model_routing: dict[str, dict[str, Any]]
    workspace: dict[str, Any]
    guardian_report: dict[str, Any]
    commercial_report: dict[str, Any]
    alerts: list[dict[str, Any]]
    repair_options: list[str]
    arbitration_note: Optional[str]
    should_pause: bool


class FinalVerifyState(TypedDict, total=False):
    session: AsyncSession
    project_id: UUID
    user_id: UUID
    branch_id: Optional[UUID]
    chapter_number: int
    chapter_title: Optional[str]
    draft_text: str
    style_sample: Optional[str]
    model_routing: dict[str, dict[str, Any]]
    guardian_report: dict[str, Any]
    logic_report: dict[str, Any]
    commercial_report: dict[str, Any]
    style_report: dict[str, Any]
    anchor_payload: dict[str, Any]
    final_package: dict[str, Any]
    finalize_output: bool
    output_finalized: bool


async def run_outline_stress_test(
    session: AsyncSession,
    *,
    project_id: UUID,
    user_id: UUID,
    branch_id: Optional[UUID],
    idea: Optional[str],
    source_material: Optional[str],
    source_material_name: Optional[str],
    genre: Optional[str],
    tone: Optional[str],
    target_chapter_count: int,
    target_total_words: int,
) -> dict[str, Any]:
    project = await get_story_engine_project(session, project_id, user_id)
    initial_state: OutlineStressState = {
        "session": session,
        "project_id": project_id,
        "user_id": user_id,
        "branch_id": branch_id,
        "idea": (idea or "").strip(),
        "source_material": (source_material or "").strip() or None,
        "source_material_name": (source_material_name or "").strip() or None,
        "genre": genre,
        "tone": tone,
        "target_chapter_count": target_chapter_count,
        "target_total_words": target_total_words,
        "model_routing": resolve_story_engine_model_routing(project),
        "debate_round": 0,
        "optimization_plan": [],
        "unresolved_issues": [],
        "debate_history": [],
    }
    if LANGGRAPH_AVAILABLE:
        graph = _build_outline_stress_graph()
        result = await graph.ainvoke(initial_state)
    else:
        result = await _run_outline_stress_fallback(initial_state)
    persisted = await _persist_outline_stress_result(
        session=session,
        project_id=project_id,
        user_id=user_id,
        branch_id=branch_id,
        outline_draft=result["outline_draft"],
        initial_kb=result["initial_kb"],
    )
    serialized_outlines = _serialize_story_api_entities(
        "outlines",
        persisted["outlines"],
    )
    return {
        "locked_level_1_outlines": [
            item for item in serialized_outlines if item.get("level") == "level_1"
        ],
        "editable_level_2_outlines": [
            item for item in serialized_outlines if item.get("level") == "level_2"
        ],
        "editable_level_3_outlines": [
            item for item in serialized_outlines if item.get("level") == "level_3"
        ],
        "initial_knowledge_base": {
            entity_type: _serialize_story_api_entities(
                entity_type,
                persisted["initial_kb"].get(entity_type) or [],
            )
            for entity_type in (
                "characters",
                "foreshadows",
                "items",
                "world_rules",
                "timeline_events",
            )
        },
        "risk_report": result["arbitrated_report"]["issues"],
        "optimization_plan": result["optimization_plan"],
        "debate_rounds_completed": result["debate_round"],
        "agent_reports": [
            result["guardian_report"],
            result["commercial_report"],
            result["logic_report"],
            result["arbitrated_report"],
        ],
        "deliberation_rounds": _build_outline_deliberation_rounds(result),
    }


async def run_realtime_guard(
    session: AsyncSession,
    *,
    project_id: UUID,
    user_id: UUID,
    branch_id: Optional[UUID] = None,
    chapter_id: Optional[UUID] = None,
    chapter_number: int,
    chapter_title: Optional[str],
    outline_id: Optional[UUID],
    current_outline: Optional[str],
    recent_chapters: list[str],
    draft_text: str,
    latest_paragraph: Optional[str],
    model_routing: Optional[dict[str, dict[str, Any]]] = None,
    persist_task: bool = True,
) -> dict[str, Any]:
    project = await get_story_engine_project(session, project_id, user_id)
    workflow_id = _build_workflow_id("realtime_guard")
    resolved_chapter_id = await _resolve_workflow_chapter_id(
        session,
        project_id=project_id,
        user_id=user_id,
        chapter_id=chapter_id,
    )
    resolved_outline = await _resolve_stream_outline_text(
        session=session,
        project_id=project_id,
        user_id=user_id,
        outline_id=outline_id,
        current_outline=current_outline,
    )
    task_state = await _create_workflow_task_state(
        session,
        workflow_id=workflow_id,
        workflow_type="realtime_guard",
        project_id=project_id,
        user_id=user_id,
        chapter_id=resolved_chapter_id,
        chapter_number=chapter_number,
        initial_message="正在检查当前正文里的人设、规则和连续性风险。",
        initial_result=(
            _build_workflow_task_base_result(
                workflow_id=workflow_id,
                workflow_type="realtime_guard",
                workflow_status="running",
                chapter_number=chapter_number,
                chapter_title=chapter_title,
                branch_id=branch_id,
            )
            if persist_task
            else None
        ),
    ) if persist_task else None
    initial_state: RealtimeGuardState = {
        "session": session,
        "project_id": project_id,
        "user_id": user_id,
        "branch_id": branch_id,
        "chapter_number": chapter_number,
        "chapter_title": chapter_title,
        "outline_id": outline_id,
        "current_outline": resolved_outline,
        "recent_chapters": recent_chapters,
        "draft_text": draft_text,
        "latest_paragraph": latest_paragraph,
        "model_routing": model_routing or resolve_story_engine_model_routing(project),
        "alerts": [],
        "repair_options": [],
        "should_pause": False,
    }
    try:
        if LANGGRAPH_AVAILABLE:
            graph = _build_realtime_guard_graph()
            result = await graph.ainvoke(initial_state)
        else:
            result = await _run_realtime_guard_fallback(initial_state)
        workflow_timeline = _build_realtime_guard_workflow_timeline(
            workflow_id=workflow_id,
            state=initial_state,
            result=result,
        )
        response = {
            "passed": not result["alerts"],
            "should_pause": result["should_pause"],
            "alerts": result["alerts"],
            "repair_options": result["repair_options"],
            "arbitration_note": result["arbitration_note"],
            "workflow_timeline": workflow_timeline,
        }
        if persist_task:
            for index, workflow_event in enumerate(workflow_timeline):
                await _persist_workflow_task_event(
                    session,
                    task_state=task_state,
                    project_id=project_id,
                    user_id=user_id,
                    chapter_id=resolved_chapter_id,
                    workflow_type="realtime_guard",
                    workflow_event=workflow_event,
                    result_patch=(
                        {
                            **_build_workflow_task_base_result(
                                workflow_id=workflow_id,
                                workflow_type="realtime_guard",
                                workflow_status="paused" if response["should_pause"] else "completed",
                                chapter_number=chapter_number,
                                chapter_title=chapter_title,
                                branch_id=branch_id,
                                workflow_timeline=workflow_timeline,
                            ),
                            "passed": response["passed"],
                            "should_pause": response["should_pause"],
                            "alert_count": len(response["alerts"]),
                            "repair_option_count": len(response["repair_options"]),
                        }
                        if index == len(workflow_timeline) - 1
                        else None
                    ),
                    finalize=index == len(workflow_timeline) - 1,
                )
        return response
    except Exception as exc:
        if persist_task:
            await _persist_workflow_task_failure(
                session,
                task_state=task_state,
                project_id=project_id,
                user_id=user_id,
                chapter_id=resolved_chapter_id,
                workflow_id=workflow_id,
                workflow_type="realtime_guard",
                chapter_number=chapter_number,
                chapter_title=chapter_title,
                branch_id=branch_id,
                error=exc,
            )
        raise


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
            f"这条设定暂时不能直接{operation}，先修掉“{blocking_alerts[0]['title']}”再继续。"
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
            "不要仅因为信息浓缩或字段较少，就把“信息颗粒度不足”本身判成高风险阻断项。"
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
            f"这批设定暂时不能导入，先修掉“{blocking_alerts[0]['title']}”再继续。"
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


def _build_outline_deliberation_rounds(result: OutlineStressState) -> list[dict[str, Any]]:
    rounds: list[dict[str, Any]] = [
        {
            "round_number": 1,
            "title": "初版生成",
            "summary": "先把故事核心压成三级大纲，再做第一轮红线和节奏检查。",
            "resolution": "已经落出第一版主线与章纲骨架。",
            "entries": [
                _build_deliberation_entry_from_report(
                    result["guardian_report"],
                    stance="review",
                ),
                _build_deliberation_entry_from_report(
                    result["commercial_report"],
                    stance="review",
                ),
            ],
        },
        {
            "round_number": 2,
            "title": "逻辑挑刺",
            "summary": "把这套大纲往长篇尺度推演，专挑后期会炸的问题。",
            "resolution": (
                f"先挂出 {len(result['logic_report'].get('issues') or [])} 个需要继续收口的点。"
                if result["logic_report"].get("issues")
                else "这一轮没有发现必须继续追打的硬问题。"
            ),
            "entries": [
                _build_deliberation_entry_from_report(
                    result["logic_report"],
                    stance="challenge",
                )
            ],
        },
    ]

    for item in result.get("debate_history") or []:
        focus_issue = dict(item.get("focus_issue") or {})
        patch_action = str(item.get("patch_action") or "").strip()
        rounds.append(
            {
                "round_number": len(rounds) + 1,
                "title": f"补丁轮 {item.get('round_number')}",
                "summary": (
                    f"围绕“{focus_issue.get('title') or '当前风险'}”补一个结构性修法。"
                ),
                "resolution": (
                    f"处理完这一处后，还剩 {int(item.get('remaining_issue_count') or 0)} 个点继续盯。"
                ),
                "entries": [
                    {
                        "actor_key": "patch",
                        "actor_label": "收敛补丁",
                        "role": "结构修补",
                        "stance": "revise",
                        "summary": patch_action or "这一轮先补一个结构性缺口。",
                        "evidence": [
                            _truncate_deliberation_text(focus_issue.get("detail"), 84)
                        ]
                        if focus_issue.get("detail")
                        else ["这一步只针对当前最危险的问题动刀。"] ,
                        "actions": [patch_action] if patch_action else [],
                        "issues": [focus_issue] if focus_issue else [],
                    }
                ],
            }
        )

    arbitrated_issues = list(result["arbitrated_report"].get("issues") or [])
    rounds.append(
        {
            "round_number": len(rounds) + 1,
            "title": "终局裁决",
            "summary": "把前面所有意见收成唯一执行版。",
            "resolution": (
                "主线已经锁死，可以进入正文。"
                if not arbitrated_issues
                else f"仍保留 {len(arbitrated_issues)} 个高风险点，写正文前先处理。"
            ),
            "entries": [
                _build_deliberation_entry_from_report(
                    result["arbitrated_report"],
                    stance="arbitrate",
                )
            ],
        }
    )
    return rounds


def _build_final_anchor_deliberation_entry(anchor_payload: dict[str, Any]) -> dict[str, Any]:
    chapter_summary = dict(anchor_payload.get("chapter_summary") or {})
    kb_updates = list(anchor_payload.get("kb_updates") or [])
    return {
        "actor_key": "anchor",
        "actor_label": "剧情锚定",
        "role": "剧情锚定Agent",
        "stance": "anchor",
        "summary": str(chapter_summary.get("content") or "本轮已经整理出章节总结和设定更新。").strip(),
        "evidence": [
            f"本轮整理出 {len(kb_updates)} 条待确认设定。"
        ],
        "actions": [
            _truncate_deliberation_text(str(item.get("title") or item.get("name") or item.get("content") or "回写设定"), 72)
            for item in kb_updates[:2]
        ],
        "issues": [],
    }


def _build_final_deliberation_round(
    *,
    round_number: int,
    result: FinalVerifyState,
    resolution: str,
) -> dict[str, Any]:
    entries = [
        _build_deliberation_entry_from_report(result["guardian_report"], stance="review"),
        _build_deliberation_entry_from_report(result["logic_report"], stance="challenge"),
        _build_deliberation_entry_from_report(result["commercial_report"], stance="review"),
        _build_deliberation_entry_from_report(result["style_report"], stance="review"),
        _build_final_anchor_deliberation_entry(dict(result.get("anchor_payload") or {})),
        _build_deliberation_entry_from_report(
            result["final_package"]["arbitrator_report"],
            stance="arbitrate",
        ),
    ]
    return {
        "round_number": round_number,
        "title": f"收口轮 {round_number}",
        "summary": "四路独立检查后统一裁决，再决定要不要继续改一轮。",
        "resolution": resolution,
        "entries": entries,
    }


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _build_workflow_id(workflow_type: str) -> str:
    return f"{workflow_type}:{uuid4().hex}"


_WORKFLOW_TASK_TYPE_MAP = {
    "realtime_guard": "story_engine.realtime_guard",
    "chapter_stream": "story_engine.chapter_stream",
    "final_optimize": "story_engine.final_optimize",
}


def _supports_workflow_task_persistence(session: Any) -> bool:
    """单元测试里经常会传入 SimpleNamespace，这里先兜底跳过真实落库。"""

    return all(hasattr(session, attr) for attr in ("add", "flush", "commit"))


def _to_jsonable_payload(value: Any) -> Any:
    return jsonable_encoder(value)


async def _resolve_workflow_chapter_id(
    session: AsyncSession,
    *,
    project_id: UUID,
    user_id: UUID,
    chapter_id: Optional[UUID],
) -> Optional[UUID]:
    """优先用显式 chapter_id 绑定任务，避免章号在多卷/分线里失真。"""

    if chapter_id is None:
        return None
    chapter = await get_owned_chapter(
        session,
        chapter_id,
        user_id,
    )
    if chapter.project_id != project_id:
        raise AppError(
            code="story_engine.chapter_project_mismatch",
            message="当前章节不属于这个项目，暂时不能挂到这次流程里。",
            status_code=400,
        )
    return chapter.id


def _resolve_workflow_task_type(workflow_type: str) -> str:
    return _WORKFLOW_TASK_TYPE_MAP.get(workflow_type, f"story_engine.{workflow_type}")


def _build_workflow_task_base_result(
    *,
    workflow_id: str,
    workflow_type: str,
    workflow_status: str,
    chapter_number: Optional[int],
    chapter_title: Optional[str],
    branch_id: Optional[UUID],
    workflow_timeline: Optional[list[dict[str, Any]]] = None,
) -> dict[str, Any]:
    return {
        "workflow_id": workflow_id,
        "workflow_type": workflow_type,
        "workflow_status": workflow_status,
        "chapter_number": chapter_number,
        "chapter_title": chapter_title,
        "branch_id": str(branch_id) if branch_id is not None else None,
        "workflow_timeline": _to_jsonable_payload(workflow_timeline or []),
    }


def _resolve_workflow_task_message(
    workflow_event: Optional[dict[str, Any]],
    *,
    fallback: Optional[str] = None,
) -> Optional[str]:
    if isinstance(workflow_event, dict):
        message = str(workflow_event.get("message") or "").strip()
        if message:
            return message
        label = str(workflow_event.get("label") or "").strip()
        if label:
            return label
    return str(fallback or "").strip() or None


def _resolve_workflow_task_progress(
    workflow_type: str,
    workflow_event: Optional[dict[str, Any]],
) -> int:
    if not isinstance(workflow_event, dict):
        return 0

    stage = str(workflow_event.get("stage") or "").strip()
    if workflow_type == "realtime_guard":
        progress_map = {
            "guard_initialized": 15,
            "guardian_review": 55,
            "commercial_repair": 78,
            "guard_arbitration": 100,
        }
        return progress_map.get(stage, 0)

    if workflow_type == "chapter_stream":
        if stage == "stream_started":
            return 5
        if stage == "plan_prepared":
            return 12
        if stage == "paragraph_generated":
            paragraph_index = workflow_event.get("paragraph_index")
            paragraph_total = workflow_event.get("paragraph_total")
            if (
                isinstance(paragraph_index, int)
                and isinstance(paragraph_total, int)
                and paragraph_total > 0
            ):
                return min(92, 12 + round((paragraph_index / paragraph_total) * 76))
            return 45
        if stage == "stream_guard_paused":
            paragraph_index = workflow_event.get("paragraph_index")
            paragraph_total = workflow_event.get("paragraph_total")
            if (
                isinstance(paragraph_index, int)
                and isinstance(paragraph_total, int)
                and paragraph_total > 0
            ):
                return min(96, 18 + round((paragraph_index / paragraph_total) * 78))
            return 88
        if stage == "stream_completed":
            return 100
        return 0

    if workflow_type == "final_optimize":
        progress_map = {
            "final_optimize_started": 5,
            "review_round_started": 10,
            "guardian_review": 24,
            "logic_review": 36,
            "commercial_review": 48,
            "style_review": 60,
            "anchor_summary_prepared": 70,
            "final_arbitration": 78,
            "round_resolution": 82,
            "final_output_finalized": 88,
            "final_verify_concluded": 92,
            "kb_updates_normalized": 95,
            "chapter_summary_persisted": 98,
            "final_optimize_completed": 100,
        }
        return progress_map.get(stage, 0)

    return 0


def _build_workflow_task_event_payload(workflow_event: dict[str, Any]) -> dict[str, Any]:
    return {
        "workflow_key": "story_engine",
        "workflow_id": workflow_event.get("workflow_id"),
        "workflow_type": workflow_event.get("workflow_type"),
        "workflow_stage": workflow_event.get("stage"),
        "workflow_status": workflow_event.get("status"),
        "workflow_label": workflow_event.get("label"),
        "workflow_message": workflow_event.get("message"),
        "workflow_event": _to_jsonable_payload(workflow_event),
        "chapter_number": workflow_event.get("chapter_number"),
        "chapter_title": workflow_event.get("chapter_title"),
    }


async def _create_workflow_task_state(
    session: AsyncSession,
    *,
    workflow_id: str,
    workflow_type: str,
    project_id: UUID,
    user_id: UUID,
    chapter_id: Optional[UUID],
    chapter_number: Optional[int],
    initial_message: str,
    initial_result: Optional[dict[str, Any]] = None,
) -> Optional[TaskState]:
    if not _supports_workflow_task_persistence(session):
        return None

    task_state = TaskState(
        task_id=workflow_id,
        task_type=_resolve_workflow_task_type(workflow_type),
        status="running",
        progress=0,
        message=initial_message,
        result=_to_jsonable_payload(initial_result or {}),
        project_id=project_id,
        chapter_id=chapter_id,
        chapter_number=chapter_number,
    )
    task_state_store.set(task_state)
    await create_task_run(
        session,
        task_state=task_state,
        chapter_id=chapter_id,
        project_id=project_id,
        user_id=user_id,
        commit=False,
    )
    await session.commit()
    return task_state


async def _persist_workflow_task_event(
    session: AsyncSession,
    *,
    task_state: Optional[TaskState],
    project_id: UUID,
    user_id: UUID,
    chapter_id: Optional[UUID],
    workflow_type: str,
    workflow_event: dict[str, Any],
    result_patch: Optional[dict[str, Any]] = None,
    finalize: bool = False,
    failed: bool = False,
    error: Optional[str] = None,
) -> None:
    if task_state is None or not _supports_workflow_task_persistence(session):
        return

    next_result = dict(task_state.result or {})
    if result_patch:
        next_result.update(_to_jsonable_payload(result_patch))
    next_result["workflow_status"] = str(workflow_event.get("status") or "").strip() or None
    task_state.result = next_result
    task_state.message = _resolve_workflow_task_message(
        workflow_event,
        fallback=task_state.message,
    )
    task_state.progress = max(
        int(task_state.progress or 0),
        _resolve_workflow_task_progress(workflow_type, workflow_event),
    )
    if failed:
        task_state.status = "failed"
        task_state.error = error
    elif finalize:
        task_state.status = "succeeded"
        task_state.progress = 100
        task_state.error = None
    else:
        task_state.status = "running"

    task_state_store.set(task_state)
    await update_task_run(
        session,
        task_state=task_state,
        commit=False,
    )
    await create_task_event(
        session,
        task_state=task_state,
        event_type=str(workflow_event.get("stage") or "workflow_event"),
        payload=_build_workflow_task_event_payload(workflow_event),
        chapter_id=chapter_id,
        project_id=project_id,
        user_id=user_id,
        commit=False,
    )
    await session.commit()


async def _persist_workflow_task_failure(
    session: AsyncSession,
    *,
    task_state: Optional[TaskState],
    project_id: UUID,
    user_id: UUID,
    chapter_id: Optional[UUID],
    workflow_id: str,
    workflow_type: str,
    chapter_number: Optional[int],
    chapter_title: Optional[str],
    branch_id: Optional[UUID],
    error: Exception,
    workflow_timeline: Optional[list[dict[str, Any]]] = None,
) -> None:
    if task_state is None or not _supports_workflow_task_persistence(session):
        return

    failure_event = {
        "workflow_id": workflow_id,
        "workflow_type": workflow_type,
        "sequence": len(workflow_timeline or []) + 1,
        "stage": "workflow_failed",
        "status": "failed",
        "label": "流程执行失败",
        "message": str(error),
        "chapter_number": chapter_number,
        "chapter_title": chapter_title,
        "branch_id": branch_id,
        "round_number": None,
        "paragraph_index": None,
        "paragraph_total": None,
        "agent_keys": [],
        "details": {
            "error_type": error.__class__.__name__,
        },
        "emitted_at": _utcnow(),
    }
    next_timeline = list(workflow_timeline or [])
    next_timeline.append(failure_event)
    await _persist_workflow_task_event(
        session,
        task_state=task_state,
        project_id=project_id,
        user_id=user_id,
        chapter_id=chapter_id,
        workflow_type=workflow_type,
        workflow_event=failure_event,
        result_patch={
            "workflow_status": "failed",
            "workflow_timeline": next_timeline,
        },
        finalize=False,
        failed=True,
        error=str(error),
    )


def _append_workflow_event(
    timeline: list[dict[str, Any]],
    *,
    workflow_id: str,
    workflow_type: str,
    stage: str,
    status: str,
    label: str,
    message: Optional[str] = None,
    chapter_number: Optional[int] = None,
    chapter_title: Optional[str] = None,
    branch_id: Optional[UUID] = None,
    round_number: Optional[int] = None,
    paragraph_index: Optional[int] = None,
    paragraph_total: Optional[int] = None,
    agent_keys: Optional[list[str]] = None,
    details: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    event = {
        "workflow_id": workflow_id,
        "workflow_type": workflow_type,
        "sequence": len(timeline) + 1,
        "stage": stage,
        "status": status,
        "label": label,
        "message": message,
        "chapter_number": chapter_number,
        "chapter_title": chapter_title,
        "branch_id": branch_id,
        "round_number": round_number,
        "paragraph_index": paragraph_index,
        "paragraph_total": paragraph_total,
        "agent_keys": list(agent_keys or []),
        "details": dict(details or {}),
        "emitted_at": _utcnow(),
    }
    timeline.append(event)
    return event


def _clone_workflow_timeline(timeline: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [dict(item) for item in timeline]


def _build_report_workflow_details(report: dict[str, Any]) -> dict[str, Any]:
    raw_output = dict(report.get("raw_output") or {})
    issues = list(report.get("issues") or [])
    return {
        "summary": str(report.get("summary") or "").strip() or None,
        "issue_count": len(issues),
        "issue_titles": [
            str(item.get("title") or "").strip()
            for item in issues[:3]
            if str(item.get("title") or "").strip()
        ],
        "proposed_action_count": len(report.get("proposed_actions") or []),
        "provider": raw_output.get("provider"),
        "model": raw_output.get("model"),
        "used_fallback": raw_output.get("used_fallback"),
    }


def _build_anchor_workflow_details(anchor_payload: dict[str, Any]) -> dict[str, Any]:
    chapter_summary = dict(anchor_payload.get("chapter_summary") or {})
    kb_updates = list(anchor_payload.get("kb_updates") or [])
    return {
        "summary_excerpt": _truncate_deliberation_text(chapter_summary.get("content"), 120),
        "core_progress_count": len(chapter_summary.get("core_progress") or []),
        "kb_update_count": len(kb_updates),
        "kb_update_titles": [
            str(item.get("title") or item.get("name") or item.get("content") or "").strip()
            for item in kb_updates[:3]
            if str(item.get("title") or item.get("name") or item.get("content") or "").strip()
        ],
    }


def _count_blocking_alerts(alerts: list[dict[str, Any]]) -> int:
    return len(
        [
            item
            for item in alerts
            if str(item.get("severity") or "").strip().lower() in {"critical", "high"}
        ]
    )


def _build_realtime_guard_workflow_timeline(
    *,
    workflow_id: str,
    state: RealtimeGuardState,
    result: RealtimeGuardState,
) -> list[dict[str, Any]]:
    timeline: list[dict[str, Any]] = []
    alerts = list(result.get("alerts") or [])
    blocking_alert_count = _count_blocking_alerts(alerts)
    repair_options = list(result.get("repair_options") or [])

    _append_workflow_event(
        timeline,
        workflow_id=workflow_id,
        workflow_type="realtime_guard",
        stage="guard_initialized",
        status="started",
        label="开始实时校验",
        chapter_number=state.get("chapter_number"),
        chapter_title=state.get("chapter_title"),
        branch_id=state.get("branch_id"),
        details={
            "draft_length": len(str(state.get("draft_text") or "")),
            "latest_paragraph_length": len(str(state.get("latest_paragraph") or "")),
            "outline_available": bool(str(state.get("current_outline") or "").strip()),
            "recent_chapter_count": len(state.get("recent_chapters") or []),
        },
    )

    guardian_report = dict(result.get("guardian_report") or {})
    _append_workflow_event(
        timeline,
        workflow_id=workflow_id,
        workflow_type="realtime_guard",
        stage="guardian_review",
        status="completed",
        label="设定守护完成校验",
        chapter_number=state.get("chapter_number"),
        chapter_title=state.get("chapter_title"),
        branch_id=state.get("branch_id"),
        agent_keys=["guardian"],
        details={
            **_build_report_workflow_details(guardian_report),
            "alert_count": len(alerts),
            "blocking_alert_count": blocking_alert_count,
        },
    )

    if alerts:
        commercial_report = dict(result.get("commercial_report") or {})
        _append_workflow_event(
            timeline,
            workflow_id=workflow_id,
            workflow_type="realtime_guard",
            stage="commercial_repair",
            status="completed",
            label="修正方案已生成",
            chapter_number=state.get("chapter_number"),
            chapter_title=state.get("chapter_title"),
            branch_id=state.get("branch_id"),
            agent_keys=["commercial"],
            details={
                **_build_report_workflow_details(commercial_report),
                "repair_option_count": len(repair_options),
            },
        )
    else:
        _append_workflow_event(
            timeline,
            workflow_id=workflow_id,
            workflow_type="realtime_guard",
            stage="commercial_repair",
            status="skipped",
            label="当前无需补修",
            chapter_number=state.get("chapter_number"),
            chapter_title=state.get("chapter_title"),
            branch_id=state.get("branch_id"),
            agent_keys=["commercial"],
            details={
                "repair_option_count": 0,
                "reason": "no_alerts",
            },
        )

    _append_workflow_event(
        timeline,
        workflow_id=workflow_id,
        workflow_type="realtime_guard",
        stage="guard_arbitration",
        status="paused" if bool(result.get("should_pause")) else "completed",
        label="实时裁决完成",
        message=str(result.get("arbitration_note") or "").strip() or None,
        chapter_number=state.get("chapter_number"),
        chapter_title=state.get("chapter_title"),
        branch_id=state.get("branch_id"),
        agent_keys=["arbitrator"],
        details={
            "passed": not alerts,
            "should_pause": bool(result.get("should_pause")),
            "alert_count": len(alerts),
            "blocking_alert_count": blocking_alert_count,
            "repair_option_count": len(repair_options),
        },
    )
    return timeline


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
                    detail=f"当前已经存在同名人物“{next_label}”，继续保存会让后续引用和守护检索变得混乱。",
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
                    detail=f"当前已经有一条规则叫“{rule_name}”，继续保存容易让规则边界互相覆盖。",
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
                    detail=f"当前分支里已经存在“{next_label}”，继续保存会让后续引用更难区分。",
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
                        f"当前还有 {len(references)} 处设定在引用“{current_label}”，"
                        f"直接改名成“{next_label}”会让这些引用失效。"
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
                    f"当前还有 {len(references)} 处设定在引用“{current_label or '当前条目'}”，"
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
                    f"物品“{_resolve_story_knowledge_item_label('items', item) or '未命名物品'}”仍把 ta 记成持有人。"
                )
        for item in workspace.get("characters") or []:
            if _resolve_story_knowledge_workspace_identity("characters", item) == entity_identity:
                continue
            for relation in _read_story_knowledge_value(item, "relationships") or []:
                relation_dict = _read_story_knowledge_dict(relation)
                if matches(relation_dict.get("target_name")) or matches(relation_dict.get("target_id")):
                    references.append(
                        f"人物“{_resolve_story_knowledge_item_label('characters', item) or '未命名人物'}”的关系链仍指向 ta。"
                    )
                    break
        for item in workspace.get("foreshadows") or []:
            related_characters = _read_story_knowledge_value(item, "related_characters") or []
            if any(matches(name) for name in related_characters):
                references.append(
                    f"伏笔“{_resolve_story_knowledge_item_label('foreshadows', item)[:24]}”仍挂在 ta 身上。"
                )
        story_bible = workspace.get("story_bible") or {}
        for item in story_bible.get("factions") or []:
            if matches(_read_story_knowledge_value(item, "leader")) or any(
                matches(member) for member in (_read_story_knowledge_value(item, "members") or [])
            ):
                references.append(
                    f"势力“{_resolve_story_knowledge_item_label('factions', item) or '未命名势力'}”仍在引用 ta。"
                )
        for item in story_bible.get("locations") or []:
            data = _read_story_knowledge_dict(_read_story_knowledge_value(item, "data"))
            if any(matches(name) for name in (data.get("notable_residents") or [])):
                references.append(
                    f"地点“{_resolve_story_knowledge_item_label('locations', item) or '未命名地点'}”仍把 ta 记成常驻人物。"
                )
        for item in story_bible.get("plot_threads") or []:
            data = _read_story_knowledge_dict(_read_story_knowledge_value(item, "data"))
            if any(matches(name) for name in (data.get("main_characters") or [])):
                references.append(
                    f"剧情线“{_resolve_story_knowledge_item_label('plot_threads', item) or '未命名剧情线'}”仍把 ta 记成核心人物。"
                )
        for item in workspace.get("timeline_events") or []:
            for state in _read_story_knowledge_value(item, "character_states") or []:
                state_dict = _read_story_knowledge_dict(state)
                if matches(state_dict.get("name")) or matches(state_dict.get("character_name")):
                    references.append(
                        f"时间线事件“{_resolve_story_knowledge_item_label('timeline_events', item)[:24]}”仍写着 ta 的状态。"
                    )
                    break

    if section_key == "locations":
        for item in workspace.get("items") or []:
            if matches(_read_story_knowledge_value(item, "location")):
                references.append(
                    f"物品“{_resolve_story_knowledge_item_label('items', item) or '未命名物品'}”仍放在这里。"
                )
        for item in workspace.get("timeline_events") or []:
            if matches(_read_story_knowledge_value(item, "location")):
                references.append(
                    f"时间线事件“{_resolve_story_knowledge_item_label('timeline_events', item)[:24]}”仍发生在这里。"
                )
        story_bible = workspace.get("story_bible") or {}
        for item in story_bible.get("factions") or []:
            if matches(_read_story_knowledge_value(item, "territory")):
                references.append(
                    f"势力“{_resolve_story_knowledge_item_label('factions', item) or '未命名势力'}”仍把这里当作地盘。"
                )
        for item in story_bible.get("plot_threads") or []:
            data = _read_story_knowledge_dict(_read_story_knowledge_value(item, "data"))
            if any(matches(name) for name in (data.get("locations") or [])):
                references.append(
                    f"剧情线“{_resolve_story_knowledge_item_label('plot_threads', item) or '未命名剧情线'}”仍绑定这个地点。"
                )

    if section_key == "items":
        for item in workspace.get("foreshadows") or []:
            related_items = _read_story_knowledge_value(item, "related_items") or []
            if any(matches(name) for name in related_items):
                references.append(
                    f"伏笔“{_resolve_story_knowledge_item_label('foreshadows', item)[:24]}”仍在引用这件物品。"
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
                        "detail": f"人物“{source_name}”引用了不存在的关系对象“{target_name}”。",
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
                    "detail": f"大纲“{title}”声明了父节点“{parent_title}”，但当前项目中找不到它。",
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


async def run_chapter_stream_generate(
    session: AsyncSession,
    *,
    project_id: UUID,
    user_id: UUID,
    branch_id: Optional[UUID] = None,
    chapter_id: Optional[UUID] = None,
    chapter_number: int,
    chapter_title: Optional[str],
    outline_id: Optional[UUID],
    current_outline: Optional[str],
    recent_chapters: list[str],
    existing_text: str,
    style_sample: Optional[str],
    target_word_count: int,
    target_paragraph_count: int,
    resume_from_paragraph: Optional[int] = None,
    repair_instruction: Optional[str] = None,
    rewrite_latest_paragraph: bool = False,
) -> AsyncIterator[dict[str, Any]]:
    """按段流式生成章节，并在每段后触发一次实时守护校验。"""

    project = await get_story_engine_project(session, project_id, user_id)
    workspace = await build_workspace(
        session,
        project_id=project_id,
        user_id=user_id,
        branch_id=branch_id,
    )
    model_routing = resolve_story_engine_model_routing(project)
    outline_text = await _resolve_stream_outline_text(
        session=session,
        project_id=project_id,
        user_id=user_id,
        outline_id=outline_id,
        current_outline=current_outline,
    )
    beats = _build_stream_beats(outline_text, target_paragraph_count=target_paragraph_count)
    style_hint = _build_style_hint(style_sample)
    stream_context = _build_stream_context(
        workspace=workspace,
        recent_chapters=recent_chapters,
        chapter_number=chapter_number,
        chapter_title=chapter_title,
    )
    paragraph_total = len(beats)
    resume_mode = resume_from_paragraph is not None
    starting_paragraph = min(max(resume_from_paragraph or 1, 1), paragraph_total + 1)
    running_paragraphs = _split_stream_paragraphs(existing_text)
    running_text = _join_stream_paragraphs(running_paragraphs)
    normalized_repair_instruction = str(repair_instruction or "").strip() or None
    rewritten_paragraph_index: Optional[int] = None
    provider_model_pairs: list[str] = []
    provider_model_seen: set[str] = set()
    providers_used: set[str] = set()
    models_used: set[str] = set()
    fallback_paragraphs: list[int] = []
    failover_paragraphs: list[int] = []
    failover_details: list[dict[str, Any]] = []
    workflow_id = _build_workflow_id("chapter_stream")
    workflow_timeline: list[dict[str, Any]] = []
    resolved_chapter_id = await _resolve_workflow_chapter_id(
        session,
        project_id=project_id,
        user_id=user_id,
        chapter_id=chapter_id,
    )
    task_state: Optional[TaskState] = None

    def _build_stream_metadata(
        metadata: dict[str, Any],
        workflow_event: dict[str, Any],
        *,
        include_timeline: bool = False,
    ) -> dict[str, Any]:
        payload = {
            **metadata,
            "workflow_id": workflow_id,
            "workflow_type": "chapter_stream",
            "workflow_sequence": workflow_event["sequence"],
            "workflow_timeline_count": len(workflow_timeline),
        }
        if include_timeline:
            payload["workflow_timeline"] = _clone_workflow_timeline(workflow_timeline)
        return payload

    def _record_stream_generation_result(
        paragraph_index: int,
        result: Any,
    ) -> dict[str, Any]:
        metadata = dict(getattr(result, "metadata", {}) or {})
        provider = str(getattr(result, "provider", "") or "").strip()
        model = str(getattr(result, "model", "") or "").strip()
        pair = f"{provider}:{model}" if provider or model else ""

        if pair and pair not in provider_model_seen:
            provider_model_seen.add(pair)
            provider_model_pairs.append(pair)
        if provider:
            providers_used.add(provider)
        if model:
            models_used.add(model)

        if bool(getattr(result, "used_fallback", False)) and paragraph_index not in fallback_paragraphs:
            fallback_paragraphs.append(paragraph_index)

        if metadata.get("stream_failover_triggered") and paragraph_index not in failover_paragraphs:
            failover_paragraphs.append(paragraph_index)

        attempts = metadata.get("stream_failover_attempts")
        if isinstance(attempts, list) and attempts:
            failover_details.append(
                {
                    "paragraph_index": paragraph_index,
                    "attempts": [
                        {
                            "role": str(item.get("role") or "").strip(),
                            "model": str(item.get("model") or "").strip(),
                            "selected_provider": str(
                                item.get("selected_provider") or ""
                            ).strip()
                            or None,
                            "error_type": str(item.get("error_type") or "").strip() or None,
                            "status_code": item.get("status_code"),
                            "message": str(item.get("message") or "").strip()[:160] or None,
                        }
                        for item in attempts
                        if isinstance(item, dict)
                    ],
                }
            )
        return metadata

    def _build_stream_done_metadata() -> dict[str, Any]:
        return {
            "status": "completed",
            "generated_length": len(running_text),
            "resume_mode": resume_mode,
            "rewritten_paragraph_index": rewritten_paragraph_index,
            "any_fallback": bool(fallback_paragraphs),
            "fallback_paragraphs": fallback_paragraphs,
            "providers_used": sorted(providers_used),
            "models_used": sorted(models_used),
            "provider_model_pairs": provider_model_pairs,
            "failover_paragraphs": failover_paragraphs,
            "failover_details": failover_details,
        }

    async def _persist_stream_event(
        workflow_event: dict[str, Any],
        *,
        result_patch: Optional[dict[str, Any]] = None,
        finalize: bool = False,
    ) -> None:
        await _persist_workflow_task_event(
            session,
            task_state=task_state,
            project_id=project_id,
            user_id=user_id,
            chapter_id=resolved_chapter_id,
            workflow_type="chapter_stream",
            workflow_event=workflow_event,
            result_patch=result_patch,
            finalize=finalize,
        )

    def _build_stream_task_result(workflow_status: str, **extra: Any) -> dict[str, Any]:
        payload = {
            **_build_workflow_task_base_result(
                workflow_id=workflow_id,
                workflow_type="chapter_stream",
                workflow_status=workflow_status,
                chapter_number=chapter_number,
                chapter_title=chapter_title,
                branch_id=branch_id,
                workflow_timeline=workflow_timeline,
            ),
            "resume_mode": resume_mode,
            "generated_length": len(running_text),
            "paragraph_total": paragraph_total,
            "provider_model_pairs": provider_model_pairs,
            "rewritten_paragraph_index": rewritten_paragraph_index,
        }
        payload.update(extra)
        return payload

    if rewrite_latest_paragraph:
        if normalized_repair_instruction is None:
            raise AppError(
                code="story_engine.repair_instruction_required",
                message="要按修法续写时，请先给出明确的修正要求。",
                status_code=400,
            )
        if not running_paragraphs:
            raise AppError(
                code="story_engine.rewrite_paragraph_missing",
                message="当前正文里还没有可重写的段落，暂时不能按修法续写。",
                status_code=400,
            )

        rewritten_paragraph_index = min(max(1, starting_paragraph - 1), len(running_paragraphs))
        rewrite_prefix_text = _join_stream_paragraphs(
            running_paragraphs[: rewritten_paragraph_index - 1]
        )
        rewrite_beat = (
            beats[min(rewritten_paragraph_index - 1, paragraph_total - 1)]
            if paragraph_total > 0
            else "把当前冲突修平，再自然接回章节推进。"
        )
        rewrite_fallback = _compose_stream_paragraph(
            beat=rewrite_beat,
            paragraph_index=rewritten_paragraph_index,
            paragraph_total=max(paragraph_total, rewritten_paragraph_index),
            target_word_count=target_word_count,
            existing_text=rewrite_prefix_text,
            style_hint=style_hint,
            stream_context=stream_context,
            repair_instruction=normalized_repair_instruction,
        )
        rewritten_result = await generate_story_stream_paragraph(
            chapter_number=chapter_number,
            chapter_title=chapter_title,
            beat=rewrite_beat,
            paragraph_index=rewritten_paragraph_index,
            paragraph_total=max(paragraph_total, rewritten_paragraph_index),
            draft_text=rewrite_prefix_text,
            outline_text=outline_text,
            style_sample=style_sample,
            workspace=workspace,
            recent_chapters=recent_chapters,
            fallback=rewrite_fallback,
            model_routing=model_routing,
            repair_instruction=normalized_repair_instruction,
        )
        _record_stream_generation_result(rewritten_paragraph_index, rewritten_result)
        running_paragraphs[rewritten_paragraph_index - 1] = rewritten_result.content.strip()
        running_text = _join_stream_paragraphs(running_paragraphs)

    task_state = await _create_workflow_task_state(
        session,
        workflow_id=workflow_id,
        workflow_type="chapter_stream",
        project_id=project_id,
        user_id=user_id,
        chapter_id=resolved_chapter_id,
        chapter_number=chapter_number,
        initial_message="正在按当前细纲顺正文。",
        initial_result=_build_workflow_task_base_result(
            workflow_id=workflow_id,
            workflow_type="chapter_stream",
            workflow_status="running",
            chapter_number=chapter_number,
            chapter_title=chapter_title,
            branch_id=branch_id,
        ),
    )

    try:
        preflight_guard_result: Optional[dict[str, Any]] = None
        latest_paragraph = _extract_latest_stream_paragraph(running_text)
        if resume_mode and running_text:
            preflight_guard_result = await run_realtime_guard(
            session,
            project_id=project_id,
            user_id=user_id,
            branch_id=branch_id,
            chapter_number=chapter_number,
            chapter_title=chapter_title,
            outline_id=outline_id,
            current_outline=outline_text,
                recent_chapters=recent_chapters,
                draft_text=running_text,
                latest_paragraph=latest_paragraph,
                model_routing=model_routing,
                persist_task=False,
            )

        start_workflow_event = _append_workflow_event(
            workflow_timeline,
            workflow_id=workflow_id,
            workflow_type="chapter_stream",
            stage="stream_started",
            status="started",
            label="开始顺正文",
            chapter_number=chapter_number,
            chapter_title=chapter_title,
            branch_id=branch_id,
            paragraph_index=min(max(starting_paragraph - 1, 0), paragraph_total),
            paragraph_total=paragraph_total,
            details={
                "resume_mode": resume_mode,
                "resume_from_paragraph": starting_paragraph if resume_mode else None,
                "rewritten_paragraph_index": rewritten_paragraph_index,
                "target_paragraph_count": target_paragraph_count,
                "target_word_count": target_word_count,
                "existing_paragraph_count": len(running_paragraphs),
            },
        )
        await _persist_stream_event(
            start_workflow_event,
            result_patch=_build_stream_task_result(
                "running",
                current_paragraph_index=min(max(starting_paragraph - 1, 0), paragraph_total),
            ),
        )
        yield {
            "event": "start",
            "message": (
                "已经按你当前的修正方向重新校过一遍，接着往下顺正文。"
                if resume_mode and rewritten_paragraph_index is not None
                else "已经从停下的位置重新接上，继续往下顺正文。"
                if resume_mode
                else "正在按细纲顺正文，写到硬冲突会自动停下。"
            ),
            "text": running_text or None,
            "paragraph_index": min(max(starting_paragraph - 1, 0), paragraph_total),
            "metadata": _build_stream_metadata(
                {
                    "chapter_number": chapter_number,
                    "chapter_title": chapter_title,
                    "target_paragraph_count": target_paragraph_count,
                    "target_word_count": target_word_count,
                    "status": "resumed" if resume_mode else "started",
                    "resume_from_paragraph": starting_paragraph if resume_mode else None,
                    "rewritten_paragraph_index": rewritten_paragraph_index,
                    "repair_instruction": normalized_repair_instruction,
                },
                start_workflow_event,
            ),
            "workflow_event": start_workflow_event,
        }

        if preflight_guard_result and preflight_guard_result["should_pause"]:
            paused_at = rewritten_paragraph_index or min(max(starting_paragraph - 1, 1), paragraph_total)
            guard_workflow_event = _append_workflow_event(
                workflow_timeline,
                workflow_id=workflow_id,
                workflow_type="chapter_stream",
                stage="stream_guard_paused",
                status="paused",
                label="续写前守护拦截",
                message=str(preflight_guard_result.get("arbitration_note") or "").strip() or None,
                chapter_number=chapter_number,
                chapter_title=chapter_title,
                branch_id=branch_id,
                paragraph_index=paused_at,
                paragraph_total=paragraph_total,
                agent_keys=["guardian", "commercial", "arbitrator"],
                details={
                    "alert_count": len(preflight_guard_result.get("alerts") or []),
                    "repair_option_count": len(preflight_guard_result.get("repair_options") or []),
                    "guard_timeline_count": len(preflight_guard_result.get("workflow_timeline") or []),
                },
            )
            await _persist_stream_event(
                guard_workflow_event,
                result_patch=_build_stream_task_result(
                    "paused",
                    paused_at_paragraph=paused_at,
                    should_pause=True,
                    alert_count=len(preflight_guard_result.get("alerts") or []),
                    repair_option_count=len(preflight_guard_result.get("repair_options") or []),
                ),
                finalize=True,
            )
            yield {
                "event": "guard",
                "message": "当前修正还没完全避开硬冲突，我先继续停在这里。",
                "text": running_text,
                "paragraph_index": paused_at,
                "paragraph_total": paragraph_total,
                "guard_result": preflight_guard_result,
                "metadata": _build_stream_metadata(
                    _build_stream_pause_metadata(
                        beats=beats,
                        paused_at_paragraph=paused_at,
                        paragraph_total=paragraph_total,
                        current_beat=beats[paused_at - 1] if 1 <= paused_at <= paragraph_total else None,
                    ),
                    guard_workflow_event,
                    include_timeline=True,
                ),
                "workflow_event": guard_workflow_event,
            }
            return

        if starting_paragraph > paragraph_total:
            done_workflow_event = _append_workflow_event(
                workflow_timeline,
                workflow_id=workflow_id,
                workflow_type="chapter_stream",
                stage="stream_completed",
                status="completed",
                label="正文续写完成",
                chapter_number=chapter_number,
                chapter_title=chapter_title,
                branch_id=branch_id,
                paragraph_index=paragraph_total,
                paragraph_total=paragraph_total,
                details={
                    "generated_length": len(running_text),
                    "resume_mode": resume_mode,
                    "rewritten_paragraph_index": rewritten_paragraph_index,
                    "no_remaining_paragraphs": True,
                },
            )
            await _persist_stream_event(
                done_workflow_event,
                result_patch=_build_stream_task_result(
                    "completed",
                    no_remaining_paragraphs=True,
                ),
                finalize=True,
            )
            yield {
                "event": "done",
                "message": "当前冲突已经修平，这一章也顺到可收口状态了。",
                "text": running_text,
                "paragraph_index": paragraph_total,
                "paragraph_total": paragraph_total,
                "metadata": _build_stream_metadata(
                    _build_stream_done_metadata(),
                    done_workflow_event,
                    include_timeline=True,
                ),
                "workflow_event": done_workflow_event,
            }
            return

        plan_workflow_event = _append_workflow_event(
            workflow_timeline,
            workflow_id=workflow_id,
            workflow_type="chapter_stream",
            stage="plan_prepared",
            status="completed",
            label="本章推进计划已展开",
            chapter_number=chapter_number,
            chapter_title=chapter_title,
            branch_id=branch_id,
            paragraph_index=min(max(starting_paragraph - 1, 0), paragraph_total),
            paragraph_total=paragraph_total,
            details={
                "remaining_beat_count": len(beats[starting_paragraph - 1 :]),
                "resume_mode": resume_mode,
            },
        )
        await _persist_stream_event(
            plan_workflow_event,
            result_patch=_build_stream_task_result(
                "running",
                current_paragraph_index=min(max(starting_paragraph - 1, 0), paragraph_total),
                remaining_beat_count=len(beats[starting_paragraph - 1 :]),
            ),
        )
        yield {
            "event": "plan",
            "message": (
                f"接下来从第 {starting_paragraph}/{paragraph_total} 段继续推进。"
                if resume_mode
                else "本章将按当前细纲拆成分段推进。"
            ),
            "paragraph_index": min(max(starting_paragraph - 1, 0), paragraph_total),
            "paragraph_total": paragraph_total,
            "metadata": _build_stream_metadata(
                {
                    "beats": beats[starting_paragraph - 1 :],
                    "all_beats": beats,
                    "outline_excerpt": outline_text[:240] if outline_text else None,
                    "style_hint": style_hint,
                    "resume_mode": resume_mode,
                },
                plan_workflow_event,
            ),
            "workflow_event": plan_workflow_event,
        }

        for paragraph_index in range(starting_paragraph, paragraph_total + 1):
            beat = beats[paragraph_index - 1]
            fallback_paragraph = _compose_stream_paragraph(
                beat=beat,
                paragraph_index=paragraph_index,
                paragraph_total=paragraph_total,
                target_word_count=target_word_count,
                existing_text=running_text,
                style_hint=style_hint,
                stream_context=stream_context,
                repair_instruction=normalized_repair_instruction if paragraph_index == starting_paragraph else None,
            )
            paragraph_result = await generate_story_stream_paragraph(
                chapter_number=chapter_number,
                chapter_title=chapter_title,
                beat=beat,
                paragraph_index=paragraph_index,
                paragraph_total=paragraph_total,
                draft_text=running_text,
                outline_text=outline_text,
                style_sample=style_sample,
                workspace=workspace,
                recent_chapters=recent_chapters,
                fallback=fallback_paragraph,
                model_routing=model_routing,
                repair_instruction=normalized_repair_instruction if paragraph_index == starting_paragraph else None,
            )
            paragraph_metadata = _record_stream_generation_result(paragraph_index, paragraph_result)
            paragraph = paragraph_result.content.strip()
            running_paragraphs.append(paragraph)
            running_text = _join_stream_paragraphs(running_paragraphs)
            chunk_workflow_event = _append_workflow_event(
                workflow_timeline,
                workflow_id=workflow_id,
                workflow_type="chapter_stream",
                stage="paragraph_generated",
                status="completed",
                label=f"第 {paragraph_index} 段已生成",
                chapter_number=chapter_number,
                chapter_title=chapter_title,
                branch_id=branch_id,
                paragraph_index=paragraph_index,
                paragraph_total=paragraph_total,
                agent_keys=["stream_writer"],
                details={
                    "beat": beat,
                    "provider": paragraph_result.provider,
                    "model": paragraph_result.model,
                    "used_fallback": paragraph_result.used_fallback,
                    "selected_role": paragraph_metadata.get("stream_selected_role"),
                    "failover_triggered": bool(paragraph_metadata.get("stream_failover_triggered")),
                },
            )
            await _persist_stream_event(
                chunk_workflow_event,
                result_patch=_build_stream_task_result(
                    "running",
                    current_paragraph_index=paragraph_index,
                    latest_provider=paragraph_result.provider,
                    latest_model=paragraph_result.model,
                ),
            )
            yield {
                "event": "chunk",
                "message": f"正在写第 {paragraph_index}/{paragraph_total} 段。",
                "delta": f"{paragraph}\n\n",
                "text": running_text,
                "paragraph_index": paragraph_index,
                "paragraph_total": paragraph_total,
                "metadata": _build_stream_metadata(
                    {
                        "beat": beat,
                        "provider": paragraph_result.provider,
                        "model": paragraph_result.model,
                        "used_fallback": paragraph_result.used_fallback,
                        "failover_triggered": bool(paragraph_metadata.get("stream_failover_triggered")),
                        "failover_attempts": paragraph_metadata.get("stream_failover_attempts") or [],
                        "selected_role": paragraph_metadata.get("stream_selected_role"),
                        "resume_mode": resume_mode,
                    },
                    chunk_workflow_event,
                ),
                "workflow_event": chunk_workflow_event,
            }

            guard_result = await run_realtime_guard(
                session,
                project_id=project_id,
                user_id=user_id,
                branch_id=branch_id,
                chapter_number=chapter_number,
                chapter_title=chapter_title,
                outline_id=outline_id,
                current_outline=outline_text,
                recent_chapters=recent_chapters,
                draft_text=running_text,
                latest_paragraph=paragraph,
                model_routing=model_routing,
                persist_task=False,
            )
            if guard_result["should_pause"]:
                guard_workflow_event = _append_workflow_event(
                    workflow_timeline,
                    workflow_id=workflow_id,
                    workflow_type="chapter_stream",
                    stage="stream_guard_paused",
                    status="paused",
                    label=f"第 {paragraph_index} 段触发守护拦截",
                    message=str(guard_result.get("arbitration_note") or "").strip() or None,
                    chapter_number=chapter_number,
                    chapter_title=chapter_title,
                    branch_id=branch_id,
                    paragraph_index=paragraph_index,
                    paragraph_total=paragraph_total,
                    agent_keys=["guardian", "commercial", "arbitrator"],
                    details={
                        "alert_count": len(guard_result.get("alerts") or []),
                        "repair_option_count": len(guard_result.get("repair_options") or []),
                        "guard_timeline_count": len(guard_result.get("workflow_timeline") or []),
                    },
                )
                await _persist_stream_event(
                    guard_workflow_event,
                    result_patch=_build_stream_task_result(
                        "paused",
                        paused_at_paragraph=paragraph_index,
                        should_pause=True,
                        alert_count=len(guard_result.get("alerts") or []),
                        repair_option_count=len(guard_result.get("repair_options") or []),
                    ),
                    finalize=True,
                )
                yield {
                    "event": "guard",
                    "message": "发现设定冲突，已经先替你停住了。",
                    "text": running_text,
                    "paragraph_index": paragraph_index,
                    "paragraph_total": paragraph_total,
                    "guard_result": guard_result,
                    "metadata": _build_stream_metadata(
                        _build_stream_pause_metadata(
                            beats=beats,
                            paused_at_paragraph=paragraph_index,
                            paragraph_total=paragraph_total,
                            current_beat=beat,
                        ),
                        guard_workflow_event,
                        include_timeline=True,
                    ),
                    "workflow_event": guard_workflow_event,
                }
                return

        done_workflow_event = _append_workflow_event(
            workflow_timeline,
            workflow_id=workflow_id,
            workflow_type="chapter_stream",
            stage="stream_completed",
            status="completed",
            label="正文生成完成",
            chapter_number=chapter_number,
            chapter_title=chapter_title,
            branch_id=branch_id,
            paragraph_index=paragraph_total,
            paragraph_total=paragraph_total,
            details={
                "generated_length": len(running_text),
                "resume_mode": resume_mode,
                "provider_model_pairs": provider_model_pairs,
                "fallback_paragraphs": fallback_paragraphs,
                "failover_paragraphs": failover_paragraphs,
            },
        )
        await _persist_stream_event(
            done_workflow_event,
            result_patch={
                **_build_stream_task_result("completed"),
                **_build_stream_done_metadata(),
                "paused_at_paragraph": None,
            },
            finalize=True,
        )
        yield {
            "event": "done",
            "message": "本章顺到这里了，可以继续手写，也可以直接做终稿优化。",
            "text": running_text,
            "paragraph_index": paragraph_total,
            "paragraph_total": paragraph_total,
            "metadata": _build_stream_metadata(
                _build_stream_done_metadata(),
                done_workflow_event,
                include_timeline=True,
            ),
            "workflow_event": done_workflow_event,
        }
    except Exception as exc:
        await _persist_workflow_task_failure(
            session,
            task_state=task_state,
            project_id=project_id,
            user_id=user_id,
            chapter_id=resolved_chapter_id,
            workflow_id=workflow_id,
            workflow_type="chapter_stream",
            chapter_number=chapter_number,
            chapter_title=chapter_title,
            branch_id=branch_id,
            error=exc,
            workflow_timeline=workflow_timeline,
        )
        raise


async def run_final_optimize(
    session: AsyncSession,
    *,
    project_id: UUID,
    user_id: UUID,
    branch_id: Optional[UUID] = None,
    chapter_id: Optional[UUID] = None,
    chapter_number: int,
    chapter_title: Optional[str],
    draft_text: str,
    style_sample: Optional[str],
) -> dict[str, Any]:
    project = await get_story_engine_project(session, project_id, user_id)
    model_routing = resolve_story_engine_model_routing(project)
    resolved_chapter_id = await _resolve_workflow_chapter_id(
        session,
        project_id=project_id,
        user_id=user_id,
        chapter_id=chapter_id,
    )
    workflow_id = _build_workflow_id("final_optimize")
    task_state = await _create_workflow_task_state(
        session,
        workflow_id=workflow_id,
        workflow_type="final_optimize",
        project_id=project_id,
        user_id=user_id,
        chapter_id=resolved_chapter_id,
        chapter_number=chapter_number,
        initial_message="正在深度收口这一章的硬伤、节奏和文风。",
        initial_result=_build_workflow_task_base_result(
            workflow_id=workflow_id,
            workflow_type="final_optimize",
            workflow_status="running",
            chapter_number=chapter_number,
            chapter_title=chapter_title,
            branch_id=branch_id,
        ),
    )
    try:
        result, convergence_meta, workflow_timeline = await _run_final_verify_until_converged(
            session=session,
            project_id=project_id,
            user_id=user_id,
            branch_id=branch_id,
            chapter_number=chapter_number,
            chapter_title=chapter_title,
            draft_text=draft_text,
            style_sample=style_sample,
            model_routing=model_routing,
            workflow_id=workflow_id,
        )
        normalized_kb_updates = _normalize_kb_update_suggestions(
            result["anchor_payload"].get("kb_updates"),
            chapter_number=chapter_number,
        )
        result["anchor_payload"]["kb_updates"] = normalized_kb_updates
        result["anchor_payload"]["chapter_summary"]["kb_update_suggestions"] = normalized_kb_updates
        workflow_id = (
            str(workflow_timeline[0].get("workflow_id"))
            if workflow_timeline
            else workflow_id
        )
        _append_workflow_event(
            workflow_timeline,
            workflow_id=workflow_id,
            workflow_type="final_optimize",
            stage="kb_updates_normalized",
            status="completed",
            label="设定更新建议已标准化",
            chapter_number=chapter_number,
            chapter_title=chapter_title,
            branch_id=branch_id,
            details={
                "kb_update_count": len(normalized_kb_updates),
            },
        )
        summary = await _upsert_chapter_summary(
            session=session,
            project_id=project_id,
            user_id=user_id,
            branch_id=branch_id,
            chapter_number=chapter_number,
            payload=result["anchor_payload"]["chapter_summary"],
        )
        _append_workflow_event(
            workflow_timeline,
            workflow_id=workflow_id,
            workflow_type="final_optimize",
            stage="chapter_summary_persisted",
            status="completed",
            label="章节总结已入库",
            chapter_number=chapter_number,
            chapter_title=chapter_title,
            branch_id=branch_id,
            details={
                "summary_id": summary.get("summary_id"),
                "summary_version": summary.get("version"),
                "kb_update_count": len(normalized_kb_updates),
            },
        )
        _append_workflow_event(
            workflow_timeline,
            workflow_id=workflow_id,
            workflow_type="final_optimize",
            stage="final_optimize_completed",
            status="completed" if convergence_meta["ready_for_publish"] else "paused",
            label="终稿收口已完成",
            message=convergence_meta["quality_summary"],
            chapter_number=chapter_number,
            chapter_title=chapter_title,
            branch_id=branch_id,
            details={
                "consensus_rounds": convergence_meta["consensus_rounds"],
                "consensus_reached": convergence_meta["consensus_reached"],
                "remaining_issue_count": convergence_meta["remaining_issue_count"],
                "ready_for_publish": convergence_meta["ready_for_publish"],
            },
        )
        response = {
            "final_draft": result["final_package"]["final_draft"],
            "revision_notes": result["final_package"]["revision_notes"],
            "chapter_summary": summary,
            "kb_update_list": result["anchor_payload"]["kb_updates"],
            "agent_reports": [
                result["guardian_report"],
                result["logic_report"],
                result["commercial_report"],
                result["style_report"],
                result["final_package"]["arbitrator_report"],
            ],
            "deliberation_rounds": result["final_package"].get("deliberation_rounds") or [],
            "original_draft": draft_text,
            "consensus_rounds": convergence_meta["consensus_rounds"],
            "consensus_reached": convergence_meta["consensus_reached"],
            "remaining_issue_count": convergence_meta["remaining_issue_count"],
            "ready_for_publish": convergence_meta["ready_for_publish"],
            "quality_summary": convergence_meta["quality_summary"],
            "workflow_timeline": workflow_timeline,
        }
        for index, workflow_event in enumerate(workflow_timeline):
            await _persist_workflow_task_event(
                session,
                task_state=task_state,
                project_id=project_id,
                user_id=user_id,
                chapter_id=resolved_chapter_id,
                workflow_type="final_optimize",
                workflow_event=workflow_event,
                result_patch=(
                    {
                        **_build_workflow_task_base_result(
                            workflow_id=workflow_id,
                            workflow_type="final_optimize",
                            workflow_status="completed" if response["ready_for_publish"] else "paused",
                            chapter_number=chapter_number,
                            chapter_title=chapter_title,
                            branch_id=branch_id,
                            workflow_timeline=workflow_timeline,
                        ),
                        "ready_for_publish": response["ready_for_publish"],
                        "remaining_issue_count": response["remaining_issue_count"],
                        "consensus_rounds": response["consensus_rounds"],
                        "kb_update_count": len(response["kb_update_list"]),
                        "chapter_summary_id": response["chapter_summary"].get("summary_id"),
                    }
                    if index == len(workflow_timeline) - 1
                    else None
                ),
                finalize=index == len(workflow_timeline) - 1,
            )
        return response
    except Exception as exc:
        await _persist_workflow_task_failure(
            session,
            task_state=task_state,
            project_id=project_id,
            user_id=user_id,
            chapter_id=resolved_chapter_id,
            workflow_id=workflow_id,
            workflow_type="final_optimize",
            chapter_number=chapter_number,
            chapter_title=chapter_title,
            branch_id=branch_id,
            error=exc,
        )
        raise


def list_story_engine_agent_specs() -> list[dict[str, Any]]:
    return export_agent_specs()


async def load_story_engine_workspace(
    session: AsyncSession,
    *,
    project_id: UUID,
    user_id: UUID,
    branch_id: Optional[UUID] = None,
) -> dict[str, Any]:
    return await build_workspace(
        session,
        project_id=project_id,
        user_id=user_id,
        branch_id=branch_id,
    )


async def _run_final_verify_once(state: FinalVerifyState) -> FinalVerifyState:
    if LANGGRAPH_AVAILABLE:
        graph = _build_final_verify_graph()
        return await graph.ainvoke(state)
    return await _run_final_verify_fallback(state)


def _collect_final_verify_issues(result: FinalVerifyState) -> list[dict[str, Any]]:
    return _merge_issue_lists(
        list(result.get("guardian_report", {}).get("issues") or []),
        list(result.get("logic_report", {}).get("issues") or []),
        list(result.get("commercial_report", {}).get("issues") or []),
        list(result.get("style_report", {}).get("issues") or []),
    )


def _build_issue_signature_set(issues: list[dict[str, Any]]) -> tuple[str, ...]:
    signatures = []
    for item in issues:
        severity = str(item.get("severity") or "").strip().lower()
        source = str(item.get("source") or "").strip().lower()
        title = re.sub(r"\s+", " ", str(item.get("title") or "").strip().lower())
        detail = re.sub(r"\s+", " ", str(item.get("detail") or "").strip().lower())
        summary_key = title or detail[:80]
        if not summary_key:
            continue
        signatures.append(f"{source}::{severity}::{summary_key}")
    return tuple(sorted(set(signatures)))


def _build_final_quality_summary(
    *,
    consensus_rounds: int,
    consensus_reached: bool,
    remaining_issue_count: int,
) -> str:
    if consensus_reached:
        if consensus_rounds <= 1:
            return "这一章已经完成深度校验，当前没有留下需要拦截的硬问题。"
        return f"这一章已经收口 {consensus_rounds} 轮，硬问题已经压干净，可以进入后续交稿动作。"
    if remaining_issue_count <= 0:
        return f"这一章已经收口 {consensus_rounds} 轮，当前没有新增硬问题，但建议再顺一遍重点段落。"
    return f"这一章已经收口 {consensus_rounds} 轮，但还剩 {remaining_issue_count} 个问题没有完全压平，建议先再修一轮。"


def _append_final_verify_round_trace(
    timeline: list[dict[str, Any]],
    *,
    workflow_id: str,
    chapter_number: int,
    chapter_title: Optional[str],
    branch_id: Optional[UUID],
    round_number: int,
    result: FinalVerifyState,
    resolution: str,
) -> None:
    report_specs = [
        ("guardian_review", "设定守护完成校验", "guardian_report", "guardian"),
        ("logic_review", "逻辑校验完成", "logic_report", "logic_debunker"),
        ("commercial_review", "节奏校验完成", "commercial_report", "commercial"),
        ("style_review", "文风校验完成", "style_report", "style_guardian"),
    ]
    for stage, label, report_key, agent_key in report_specs:
        report = dict(result.get(report_key) or {})
        _append_workflow_event(
            timeline,
            workflow_id=workflow_id,
            workflow_type="final_optimize",
            stage=stage,
            status="completed",
            label=label,
            chapter_number=chapter_number,
            chapter_title=chapter_title,
            branch_id=branch_id,
            round_number=round_number,
            agent_keys=[agent_key],
            details=_build_report_workflow_details(report),
        )

    anchor_payload = dict(result.get("anchor_payload") or {})
    _append_workflow_event(
        timeline,
        workflow_id=workflow_id,
        workflow_type="final_optimize",
        stage="anchor_summary_prepared",
        status="completed",
        label="章节总结与设定更新已整理",
        chapter_number=chapter_number,
        chapter_title=chapter_title,
        branch_id=branch_id,
        round_number=round_number,
        agent_keys=["anchor"],
        details=_build_anchor_workflow_details(anchor_payload),
    )

    final_package = dict(result.get("final_package") or {})
    arbitrator_report = dict(final_package.get("arbitrator_report") or {})
    _append_workflow_event(
        timeline,
        workflow_id=workflow_id,
        workflow_type="final_optimize",
        stage="final_arbitration",
        status="completed",
        label="统一裁决已生成",
        chapter_number=chapter_number,
        chapter_title=chapter_title,
        branch_id=branch_id,
        round_number=round_number,
        agent_keys=["arbitrator"],
        details={
            **_build_report_workflow_details(arbitrator_report),
            "revision_note_count": len(final_package.get("revision_notes") or []),
            "final_draft_length": len(str(final_package.get("final_draft") or "").strip()),
        },
    )

    _append_workflow_event(
        timeline,
        workflow_id=workflow_id,
        workflow_type="final_optimize",
        stage="round_resolution",
        status="completed",
        label=f"第 {round_number} 轮结论已收口",
        message=resolution,
        chapter_number=chapter_number,
        chapter_title=chapter_title,
        branch_id=branch_id,
        round_number=round_number,
        details={
            "resolution": resolution,
            "remaining_issue_count": len(_collect_final_verify_issues(result)),
        },
    )


def _get_outline_debate_max_rounds() -> int:
    settings = get_settings()
    return max(1, settings.story_engine_outline_max_debate_rounds)


def _get_final_verify_max_rounds() -> int:
    settings = get_settings()
    return max(1, settings.story_engine_final_verify_max_rounds)


async def _run_final_verify_until_converged(
    *,
    session: AsyncSession,
    project_id: UUID,
    user_id: UUID,
    branch_id: Optional[UUID],
    chapter_number: int,
    chapter_title: Optional[str],
    draft_text: str,
    style_sample: Optional[str],
    model_routing: dict[str, dict[str, Any]],
    workflow_id: Optional[str] = None,
) -> tuple[FinalVerifyState, dict[str, Any], list[dict[str, Any]]]:
    current_draft = draft_text
    previous_issue_signature: Optional[tuple[str, ...]] = None
    latest_result: Optional[FinalVerifyState] = None
    completed_rounds = 0
    deliberation_rounds: list[dict[str, Any]] = []
    max_rounds = _get_final_verify_max_rounds()
    workflow_id = workflow_id or _build_workflow_id("final_optimize")
    workflow_timeline: list[dict[str, Any]] = []

    _append_workflow_event(
        workflow_timeline,
        workflow_id=workflow_id,
        workflow_type="final_optimize",
        stage="final_optimize_started",
        status="started",
        label="开始终稿深度收口",
        chapter_number=chapter_number,
        chapter_title=chapter_title,
        branch_id=branch_id,
        details={
            "draft_length": len(str(draft_text or "")),
            "style_sample_length": len(str(style_sample or "")),
            "max_rounds": max_rounds,
        },
    )

    for round_index in range(1, max_rounds + 1):
        _append_workflow_event(
            workflow_timeline,
            workflow_id=workflow_id,
            workflow_type="final_optimize",
            stage="review_round_started",
            status="started",
            label=f"开始第 {round_index} 轮收口",
            chapter_number=chapter_number,
            chapter_title=chapter_title,
            branch_id=branch_id,
            round_number=round_index,
            details={
                "draft_length": len(str(current_draft or "")),
            },
        )
        state: FinalVerifyState = {
            "session": session,
            "project_id": project_id,
            "user_id": user_id,
            "branch_id": branch_id,
            "chapter_number": chapter_number,
            "chapter_title": chapter_title,
            "draft_text": current_draft,
            "style_sample": style_sample,
            "model_routing": model_routing,
            "finalize_output": False,
        }
        latest_result = await _run_final_verify_once(state)
        completed_rounds = round_index

        issues = _collect_final_verify_issues(latest_result)
        current_signature = _build_issue_signature_set(issues)
        round_resolution = ""
        if not current_signature:
            round_resolution = "这一轮已经没有保留硬问题，停止继续收口。"
            deliberation_rounds.append(
                _build_final_deliberation_round(
                    round_number=round_index,
                    result=latest_result,
                    resolution=round_resolution,
                )
            )
            _append_final_verify_round_trace(
                workflow_timeline,
                workflow_id=workflow_id,
                chapter_number=chapter_number,
                chapter_title=chapter_title,
                branch_id=branch_id,
                round_number=round_index,
                result=latest_result,
                resolution=round_resolution,
            )
            break
        if previous_issue_signature == current_signature:
            round_resolution = "这一轮和上一轮保留的问题一致，继续修改也不会明显收敛，先停在当前裁决。"
            deliberation_rounds.append(
                _build_final_deliberation_round(
                    round_number=round_index,
                    result=latest_result,
                    resolution=round_resolution,
                )
            )
            _append_final_verify_round_trace(
                workflow_timeline,
                workflow_id=workflow_id,
                chapter_number=chapter_number,
                chapter_title=chapter_title,
                branch_id=branch_id,
                round_number=round_index,
                result=latest_result,
                resolution=round_resolution,
            )
            break

        previous_issue_signature = current_signature
        next_draft = str(
            latest_result.get("final_package", {}).get("final_draft") or current_draft
        ).strip()
        if not next_draft or next_draft == current_draft.strip():
            round_resolution = "这一轮已经给出统一修法，但改稿不会继续明显变化，先保留当前版本。"
            deliberation_rounds.append(
                _build_final_deliberation_round(
                    round_number=round_index,
                    result=latest_result,
                    resolution=round_resolution,
                )
            )
            _append_final_verify_round_trace(
                workflow_timeline,
                workflow_id=workflow_id,
                chapter_number=chapter_number,
                chapter_title=chapter_title,
                branch_id=branch_id,
                round_number=round_index,
                result=latest_result,
                resolution=round_resolution,
            )
            break
        round_resolution = "按这一轮仲裁方案改一版，再回来看还有没有残留问题。"
        deliberation_rounds.append(
            _build_final_deliberation_round(
                round_number=round_index,
                result=latest_result,
                resolution=round_resolution,
            )
        )
        _append_final_verify_round_trace(
            workflow_timeline,
            workflow_id=workflow_id,
            chapter_number=chapter_number,
            chapter_title=chapter_title,
            branch_id=branch_id,
            round_number=round_index,
            result=latest_result,
            resolution=round_resolution,
        )
        current_draft = next_draft

    if latest_result is None:
        raise RuntimeError("final verify result is missing")

    if not latest_result.get("output_finalized"):
        latest_result = await _finalize_final_verify_output(latest_result)
        _append_workflow_event(
            workflow_timeline,
            workflow_id=workflow_id,
            workflow_type="final_optimize",
            stage="final_output_finalized",
            status="completed",
            label="终稿输出已定稿",
            chapter_number=chapter_number,
            chapter_title=chapter_title,
            branch_id=branch_id,
            round_number=completed_rounds if completed_rounds > 0 else None,
            agent_keys=["anchor", "arbitrator"],
            details={
                "final_draft_length": len(
                    str(latest_result.get("final_package", {}).get("final_draft") or "").strip()
                ),
                "kb_update_count": len(
                    latest_result.get("anchor_payload", {}).get("kb_updates") or []
                ),
            },
        )
        if deliberation_rounds:
            latest_resolution = str(deliberation_rounds[-1].get("resolution") or "").strip()
            deliberation_rounds[-1] = _build_final_deliberation_round(
                round_number=completed_rounds,
                result=latest_result,
                resolution=latest_resolution,
            )

    remaining_issues = _collect_final_verify_issues(latest_result)
    consensus_reached = len(remaining_issues) == 0
    convergence_meta = {
        "consensus_rounds": completed_rounds,
        "consensus_reached": consensus_reached,
        "remaining_issue_count": len(remaining_issues),
        "ready_for_publish": consensus_reached,
        "deliberation_rounds": deliberation_rounds,
        "quality_summary": _build_final_quality_summary(
            consensus_rounds=completed_rounds,
            consensus_reached=consensus_reached,
            remaining_issue_count=len(remaining_issues),
        ),
    }
    _append_workflow_event(
        workflow_timeline,
        workflow_id=workflow_id,
        workflow_type="final_optimize",
        stage="final_verify_concluded",
        status="completed" if consensus_reached else "paused",
        label="终稿校验阶段已结束",
        message=convergence_meta["quality_summary"],
        chapter_number=chapter_number,
        chapter_title=chapter_title,
        branch_id=branch_id,
        details={
            "consensus_rounds": completed_rounds,
            "consensus_reached": consensus_reached,
            "remaining_issue_count": len(remaining_issues),
            "ready_for_publish": consensus_reached,
        },
    )
    latest_result["final_package"] = {
        **dict(latest_result.get("final_package") or {}),
        **convergence_meta,
    }
    latest_result["final_package"]["arbitrator_report"] = {
        **dict(latest_result["final_package"]["arbitrator_report"]),
        "raw_output": {
            **dict(latest_result["final_package"]["arbitrator_report"].get("raw_output") or {}),
            **convergence_meta,
        },
    }
    return latest_result, convergence_meta, workflow_timeline


async def _finalize_final_verify_output(result: FinalVerifyState) -> FinalVerifyState:
    current = dict(result)
    final_draft = str(
        current.get("final_package", {}).get("final_draft") or current.get("draft_text") or ""
    ).strip()
    if final_draft:
        current["draft_text"] = final_draft
    current["finalize_output"] = True
    current.update(await _final_anchor_node(current))
    current.update(await _final_arbitrator_node(current))
    current["output_finalized"] = True
    return current


def _build_outline_stress_graph():
    if StateGraph is None:
        raise RuntimeError("LangGraph is not installed.")
    graph = StateGraph(OutlineStressState)
    graph.add_node("guardian_commercial", _outline_guardian_commercial_node)
    graph.add_node("logic_debunker", _outline_logic_node)
    graph.add_node("debate", _outline_debate_node)
    graph.add_node("arbitrator", _outline_arbitrator_node)
    graph.add_edge(START, "guardian_commercial")
    graph.add_edge("guardian_commercial", "logic_debunker")
    graph.add_edge("logic_debunker", "debate")
    graph.add_conditional_edges(
        "debate",
        _should_continue_outline_debate,
        {
            "debate": "debate",
            "arbitrator": "arbitrator",
        },
    )
    graph.add_edge("arbitrator", END)
    return graph.compile()


def _build_realtime_guard_graph():
    if StateGraph is None:
        raise RuntimeError("LangGraph is not installed.")
    graph = StateGraph(RealtimeGuardState)
    graph.add_node("guardian", _realtime_guardian_node)
    graph.add_node("commercial", _realtime_commercial_node)
    graph.add_node("arbitrator", _realtime_arbitrator_node)
    graph.add_edge(START, "guardian")
    graph.add_conditional_edges(
        "guardian",
        lambda state: "commercial" if state.get("alerts") else "arbitrator",
        {"commercial": "commercial", "arbitrator": "arbitrator"},
    )
    graph.add_edge("commercial", "arbitrator")
    graph.add_edge("arbitrator", END)
    return graph.compile()


def _build_final_verify_graph():
    if StateGraph is None:
        raise RuntimeError("LangGraph is not installed.")
    graph = StateGraph(FinalVerifyState)
    graph.add_node("guardian_review", _final_guardian_node)
    graph.add_node("logic_review", _final_logic_node)
    graph.add_node("commercial_review", _final_commercial_node)
    graph.add_node("style_review", _final_style_node)
    graph.add_node("anchor", _final_anchor_node)
    graph.add_node("arbitrator", _final_arbitrator_node)
    graph.add_edge(START, "guardian_review")
    graph.add_edge(START, "logic_review")
    graph.add_edge(START, "commercial_review")
    graph.add_edge(START, "style_review")
    graph.add_edge("guardian_review", "anchor")
    graph.add_edge("logic_review", "anchor")
    graph.add_edge("commercial_review", "anchor")
    graph.add_edge("style_review", "anchor")
    graph.add_edge("anchor", "arbitrator")
    graph.add_edge("arbitrator", END)
    return graph.compile()


async def _outline_guardian_commercial_node(state: OutlineStressState) -> dict[str, Any]:
    idea = state["idea"].strip()
    source_material = str(state.get("source_material") or "").strip()
    source_material_name = str(state.get("source_material_name") or "").strip() or None
    working_premise = idea or source_material.splitlines()[0].strip()
    volumes = 3
    chapters_per_volume = max(20, state["target_chapter_count"] // volumes)
    premise_title = working_premise[:18] if len(working_premise) > 18 else working_premise
    outline_draft = {
        "level_1": [
            {
                "level": "level_1",
                "title": f"{premise_title}·全本主线圣经",
                "content": (
                    f"核心命题：{working_premise}\n"
                    f"目标体量：约 {state['target_total_words']} 字，预计 {state['target_chapter_count']} 章。\n"
                    "主线要求：每卷都必须推进主冲突、抬升代价、留下长期伏笔，并保证主角弧光逐层升级。"
                ),
                "status": "todo",
                "node_order": 1,
                "locked": True,
                "immutable_reason": "一级大纲为全本主线圣经，压力测试通过后锁定。",
            }
        ],
        "level_2": [
            {
                "level": "level_2",
                "title": "卷一：起盘立局",
                "content": f"第 1-{chapters_per_volume} 章，完成设定亮相、核心冲突起爆、第一次爽点兑现。",
                "status": "todo",
                "node_order": 1,
            },
            {
                "level": "level_2",
                "title": "卷二：放大代价",
                "content": f"第 {chapters_per_volume + 1}-{chapters_per_volume * 2} 章，放大世界规则代价，推动宿敌与伏笔并线。",
                "status": "todo",
                "node_order": 2,
            },
            {
                "level": "level_2",
                "title": "卷三：主线收束",
                "content": f"第 {chapters_per_volume * 2 + 1}-{state['target_chapter_count']} 章，主线真相揭晓，完成终极回收与情感闭环。",
                "status": "todo",
                "node_order": 3,
            },
        ],
        "level_3": [
            {
                "level": "level_3",
                "title": "第一章：钩子起手",
                "content": "用一个强冲突开局，同时埋下能支撑百章的总悬念。",
                "status": "todo",
                "node_order": 1,
            },
            {
                "level": "level_3",
                "title": "第二章：展示代价",
                "content": "让主角第一次直面世界规则的约束，明确爽点不是白送。",
                "status": "todo",
                "node_order": 2,
            },
            {
                "level": "level_3",
                "title": "第三章：人物绑定",
                "content": "让核心同伴或对立者完成登场，用行动绑定人物关系。",
                "status": "todo",
                "node_order": 3,
            },
            {
                "level": "level_3",
                "title": "第四章：小胜利与更大坑",
                "content": "主角先拿到小赢面，再在章末留下更大的长期坑。",
                "status": "todo",
                "node_order": 4,
            },
            {
                "level": "level_3",
                "title": "第五章：首个卷级推进",
                "content": "将起始阶段的人物动机、目标和世界规则正式并线。",
                "status": "todo",
                "node_order": 5,
            },
        ],
    }
    initial_kb = {
        "characters": [
            {
                "name": "主角",
                "appearance": "带着明显记忆点的外貌锚点，初登场就能被记住。",
                "personality": "外冷内燃，遇强则强，但在关键禁区上有明确心理阴影。",
                "micro_habits": ["紧张时会下意识敲指节", "思考时先看出口"],
                "abilities": {"core": "成长型核心能力", "ceiling": "后期可触及世界顶点"},
                "relationships": [],
                "status": "active",
                "arc_stage": "initial",
                "arc_boundaries": [
                    {
                        "stage": "initial",
                        "forbidden_behaviors": ["无代价的无敌表现", "毫无原因的圣母式牺牲"],
                        "allowed_behaviors": ["谨慎试探", "为了执念冒险"],
                    }
                ],
            },
            {
                "name": "宿敌",
                "appearance": "压迫感极强，气场先于身份出场。",
                "personality": "理性、残酷、擅长把规则当武器。",
                "micro_habits": ["说话前停顿半拍"],
                "abilities": {"core": "规则系压制能力", "ceiling": "中后期主要压迫源"},
                "relationships": [{"target_name": "主角", "relation": "宿敌", "intensity": "high"}],
                "status": "active",
                "arc_stage": "initial",
                "arc_boundaries": [],
            },
            {
                "name": "关键盟友",
                "appearance": "看似不显眼，却有明确个人标签。",
                "personality": "口硬心软，擅长补足主角短板。",
                "micro_habits": ["先嘲讽后帮忙"],
                "abilities": {"core": "辅助/情报/资源位"},
                "relationships": [{"target_name": "主角", "relation": "盟友", "intensity": "medium"}],
                "status": "active",
                "arc_stage": "initial",
                "arc_boundaries": [],
            },
        ],
        "world_rules": [
            {
                "rule_name": "力量必须付出代价",
                "rule_content": "所有爆发式成长都要付出身体、记忆、身份或关系层面的真实代价。",
                "negative_list": ["无代价开挂", "危机全靠巧合解决"],
                "scope": "global",
            },
            {
                "rule_name": "核心秘密不能过早说穿",
                "rule_content": "中前期只能层层揭开主线真相，不能一章讲透所有谜底。",
                "negative_list": ["首卷透底", "反派自曝全部动机"],
                "scope": "main_plot",
            },
        ],
        "items": [
            {
                "name": "起始锚点物",
                "features": "既能推动主线，也能承担身份或谜团线索。",
                "owner": "主角",
                "location": "主角身边",
                "special_rules": ["首次使用必须带来反噬或误导"],
            }
        ],
        "foreshadows": [
            {
                "content": "开篇出现一个看似无关的异常细节，实际对应终局真相。",
                "chapter_planted": 1,
                "chapter_planned_reveal": max(30, state["target_chapter_count"] // 2),
                "status": "pending",
                "related_characters": ["主角", "宿敌"],
                "related_items": ["起始锚点物"],
            }
        ],
        "timeline_events": [],
    }
    guardian_issues: list[dict[str, Any]] = []
    if not source_material and len(idea) < 40:
        guardian_issues.append(
            {
                "severity": "medium",
                "title": "脑洞信息量偏少",
                "detail": "当前输入还不足以天然锁死百万字级因果链，建议补一句主角核心欲望和终局代价。",
                "source": "guardian",
                "suggestion": "补充一句“主角最想得到什么，最怕失去什么”。",
            }
        )
    commercial_issues = [
        {
            "severity": "medium",
            "title": "章末钩子需要固定机制",
            "detail": "当前大纲草案已有主线，但还需要明确每 3-5 章一个强钩子节点。",
            "source": "commercial",
            "suggestion": "在三级大纲中固定“阶段性兑现 + 反转留坑”的章末结构。",
        }
    ]
    fallback_guardian_report = build_agent_report(
        "guardian",
        summary="已完成大纲骨架和初始知识库红线校验，一级大纲将被锁定。",
        issues=guardian_issues,
        proposed_actions=["一级大纲锁死", "主角弧光边界提前绑定", "世界规则先写负面清单"],
    )
    fallback_commercial_report = build_agent_report(
        "commercial",
        summary="已补齐卷级推进节奏与开篇 5 章商业钩子骨架。",
        issues=commercial_issues,
        proposed_actions=["每卷至少一个阶段性高潮", "每章结尾保留追读驱动"],
    )

    blueprint = await generate_story_outline_blueprint(
        idea=idea,
        source_material=source_material or None,
        source_material_name=source_material_name,
        genre=state.get("genre"),
        tone=state.get("tone"),
        target_chapter_count=state["target_chapter_count"],
        target_total_words=state["target_total_words"],
        fallback_outline_draft=outline_draft,
        fallback_initial_kb=initial_kb,
        model_routing=state.get("model_routing"),
    )
    outline_draft = blueprint["outline_draft"]
    initial_kb = blueprint["initial_kb"]
    outline_context = build_outline_context_text(
        idea=idea or working_premise,
        genre=state.get("genre"),
        tone=state.get("tone"),
        outline_draft=outline_draft,
        initial_kb=initial_kb,
    )
    guardian_report = await _run_guardian_consensus_report(
        task_name="story_engine.outline_guardian",
        task_goal="检查当前大纲和初始知识库里的人设红线、世界规则红线与长期稳定性问题。",
        context=outline_context,
        fallback_report=fallback_guardian_report,
        model_routing=state.get("model_routing"),
        workflow_key="outline",
        workflow_label="大纲压力测试",
    )
    commercial_report = await generate_story_agent_report(
        agent_key="commercial",
        task_name="story_engine.outline_commercial",
        task_goal="检查当前大纲的商业节奏、爽点密度、章末钩子和卷级推进表现。",
        context=outline_context,
        fallback_report=fallback_commercial_report,
        model_routing=state.get("model_routing"),
    )
    return {
        "outline_draft": outline_draft,
        "initial_kb": initial_kb,
        "guardian_report": guardian_report,
        "commercial_report": commercial_report,
    }


async def _run_outline_stress_fallback(state: OutlineStressState) -> OutlineStressState:
    current = dict(state)
    current.update(await _outline_guardian_commercial_node(current))
    current.update(await _outline_logic_node(current))
    while _should_continue_outline_debate(current) == "debate":
        current.update(await _outline_debate_node(current))
    current.update(await _outline_arbitrator_node(current))
    return current


async def _outline_logic_node(state: OutlineStressState) -> dict[str, Any]:
    initial_kb = state["initial_kb"]
    issues: list[dict[str, Any]] = []
    if len(initial_kb.get("foreshadows", [])) < 2:
        issues.append(
            {
                "severity": "high",
                "title": "长期伏笔密度偏低",
                "detail": "目前只有一个长期伏笔，百万字推进时容易中后期失去连续牵引。",
                "source": "logic_debunker",
                "suggestion": "至少增加一个人物真相类伏笔和一个世界规则类伏笔。",
            }
        )
    if len(initial_kb.get("world_rules", [])) < 2:
        issues.append(
            {
                "severity": "high",
                "title": "世界规则不足以约束后期升级",
                "detail": "规则太少时，战力和奇迹事件会很快失控。",
                "source": "logic_debunker",
                "suggestion": "增加资源、代价、信息差三个维度中的至少一个硬限制。",
            }
        )
    if len(state["outline_draft"]["level_2"]) < 3:
        issues.append(
            {
                "severity": "medium",
                "title": "卷级切分偏弱",
                "detail": "卷结构不足，后续很容易把不同阶段揉成一锅。",
                "source": "logic_debunker",
                "suggestion": "重新明确起盘、扩盘、收束三层推进。",
            }
        )
    fallback_logic_report = build_agent_report(
        "logic_debunker",
        summary="已完成长线压力测试，重点筛出伏笔密度和规则约束风险。",
        issues=issues,
        proposed_actions=[
            "为主角增加中期认知翻转",
            "为世界规则增加不可绕过的代价",
        ],
    )
    logic_report = await generate_story_agent_report(
        agent_key="logic_debunker",
        task_name="story_engine.outline_logic",
        task_goal="模拟长篇连载推进，挑出战力、时间线、伏笔密度和因果链的长期风险。",
        context=build_outline_context_text(
            idea=state["idea"],
            genre=state.get("genre"),
            tone=state.get("tone"),
            outline_draft=state["outline_draft"],
            initial_kb=state["initial_kb"],
        ),
        fallback_report=fallback_logic_report,
        model_routing=state.get("model_routing"),
    )
    return {
        "logic_report": logic_report,
        "unresolved_issues": logic_report["issues"],
    }


async def _outline_debate_node(state: OutlineStressState) -> dict[str, Any]:
    debate_round = int(state.get("debate_round", 0)) + 1
    unresolved = list(state.get("unresolved_issues", []))
    optimization_plan = list(state.get("optimization_plan", []))
    debate_history = list(state.get("debate_history", []))
    initial_kb = dict(state["initial_kb"])
    current_issue: Optional[dict[str, Any]] = None
    patch_action = "当前这一轮没有新增结构补丁。"

    if unresolved:
        current_issue = unresolved.pop(0)
        if "伏笔" in current_issue["title"]:
            initial_kb.setdefault("foreshadows", []).append(
                {
                    "content": "关键盟友第一次反常选择，实则对应其隐藏身份。",
                    "chapter_planted": 8,
                    "chapter_planned_reveal": max(45, state["target_chapter_count"] // 2 + 10),
                    "status": "pending",
                    "related_characters": ["关键盟友"],
                    "related_items": [],
                }
            )
            patch_action = "新增人物真相类长期伏笔，避免中段只剩单线推进。"
            optimization_plan.append(patch_action)
        elif "规则" in current_issue["title"]:
            initial_kb.setdefault("world_rules", []).append(
                {
                    "rule_name": "越级使用力量会留下永久裂痕",
                    "rule_content": "越级爆发可以救急，但会造成无法完全逆转的后果。",
                    "negative_list": ["关键大战后立刻满血复原"],
                    "scope": "battle",
                }
            )
            patch_action = "补写战力代价规则，锁住后期升级边界。"
            optimization_plan.append(patch_action)
        else:
            patch_action = f"已针对风险“{current_issue['title']}”给出结构性补丁。"
            optimization_plan.append(patch_action)

        debate_history.append(
            {
                "round_number": debate_round,
                "focus_issue": current_issue,
                "patch_action": patch_action,
                "remaining_issue_count": len(unresolved),
            }
        )

    return {
        "debate_round": debate_round,
        "unresolved_issues": unresolved,
        "optimization_plan": optimization_plan,
        "debate_history": debate_history,
        "initial_kb": initial_kb,
    }


def _should_continue_outline_debate(state: OutlineStressState) -> str:
    unresolved = state.get("unresolved_issues", [])
    debate_round = int(state.get("debate_round", 0))
    if unresolved and debate_round < _get_outline_debate_max_rounds():
        return "debate"
    return "arbitrator"


async def _outline_arbitrator_node(state: OutlineStressState) -> dict[str, Any]:
    remaining_issues = list(state.get("unresolved_issues", []))
    optimization_plan = list(state.get("optimization_plan", []))
    if not optimization_plan:
        optimization_plan = ["当前大纲骨架可直接进入细化阶段。"]
    fallback_report = build_agent_report(
        "arbitrator",
        summary="压力测试已收敛，输出锁死版主线圣经与可编辑卷纲/章纲。",
        issues=remaining_issues,
        proposed_actions=optimization_plan,
        raw_output={"consensus": len(remaining_issues) == 0},
    )
    arbitrated_report = await generate_story_agent_report(
        agent_key="arbitrator",
        task_name="story_engine.outline_arbitrator",
        task_goal="综合 Guardian、Commercial、Logic 的意见，给出唯一可执行的大纲优化结论。",
        context=(
            "大纲上下文：\n"
            + _compact_prompt_text(
                build_outline_context_text(
                    idea=state["idea"],
                    genre=state.get("genre"),
                    tone=state.get("tone"),
                    outline_draft=state["outline_draft"],
                    initial_kb=state["initial_kb"],
                ),
                4800,
            )
            + "\nGuardian报告摘要："
            + _story_knowledge_json_snippet(
                _build_agent_report_prompt_snapshot(state["guardian_report"]),
                1800,
            )
            + "\nCommercial报告摘要："
            + _story_knowledge_json_snippet(
                _build_agent_report_prompt_snapshot(state["commercial_report"]),
                1600,
            )
            + "\nLogic报告摘要："
            + _story_knowledge_json_snippet(
                _build_agent_report_prompt_snapshot(state["logic_report"]),
                2000,
            )
            + "\n当前待处理问题："
            + _story_knowledge_json_snippet(remaining_issues, 1200)
            + "\n已形成优化方案："
            + _story_knowledge_json_snippet(optimization_plan, 800)
        ),
        fallback_report=fallback_report,
        model_routing=state.get("model_routing"),
    )
    arbitrated_report["raw_output"] = {
        **dict(arbitrated_report.get("raw_output") or {}),
        "consensus": len(arbitrated_report.get("issues") or []) == 0,
    }
    return {
        "arbitrated_report": arbitrated_report,
    }


async def _realtime_guardian_node(state: RealtimeGuardState) -> dict[str, Any]:
    workspace = state.get("workspace")
    if workspace is None:
        workspace = await build_workspace(
            state["session"],
            project_id=state["project_id"],
            user_id=state["user_id"],
            branch_id=state.get("branch_id"),
        )
    text = state.get("latest_paragraph") or state["draft_text"]
    alerts: list[dict[str, Any]] = []

    for rule in workspace["world_rules"]:
        for banned in rule.negative_list:
            if banned and banned in text:
                alerts.append(
                    {
                        "severity": "critical",
                        "title": "触发世界规则禁令",
                        "detail": f"文本命中了规则《{rule.rule_name}》的禁令：{banned}",
                        "source": "guardian",
                        "suggestion": "改写该段，让代价、限制或信息差重新成立。",
                    }
                )

    for character in workspace["characters"]:
        for boundary in character.arc_boundaries or []:
            for forbidden in boundary.get("forbidden_behaviors", []):
                if forbidden and forbidden in text:
                    alerts.append(
                        {
                            "severity": "high",
                            "title": f"{character.name}疑似OOC",
                            "detail": f"当前段落触碰到角色在弧光阶段中的禁区：{forbidden}",
                            "source": "guardian",
                            "suggestion": "要么先铺垫角色变化，要么把行为降级到当前阶段可成立的强度。",
                        }
                    )

    if state.get("current_outline"):
        outline_keywords = [token for token in state["current_outline"].replace("，", " ").split() if len(token) >= 2]
        if outline_keywords and not any(keyword in state["draft_text"] for keyword in outline_keywords[:3]):
            alerts.append(
                {
                    "severity": "medium",
                    "title": "正文偏离当前细纲",
                    "detail": "当前草稿没有明显覆盖细纲里的核心节点，继续写可能越走越偏。",
                    "source": "guardian",
                    "suggestion": "回到本章 3-5 个核心节点，至少先补齐一个。",
                }
            )
    fallback_guardian_report = build_agent_report(
        "guardian",
        summary=(
            "已完成最新段落的设定快检。"
            if alerts
            else "当前段落暂未发现需要立刻停笔的人设或规则硬冲突。"
        ),
        issues=alerts,
        proposed_actions=[
            item["suggestion"]
            for item in alerts
            if str(item.get("suggestion") or "").strip()
        ]
        or ["当前段落可继续推进，但建议继续盯住下一段的人设与规则边界。"],
    )
    guardian_report = await _run_guardian_consensus_report(
        task_name="story_engine.realtime_guardian",
        task_goal="检查最新段落与当前章节上下文是否触发人设、世界规则、时间线或细纲偏移风险。",
        context=build_realtime_guard_context_text(
            workspace=workspace,
            chapter_number=state["chapter_number"],
            chapter_title=state.get("chapter_title"),
            current_outline=state.get("current_outline"),
            draft_text=state["draft_text"],
            latest_paragraph=state.get("latest_paragraph"),
            recent_chapters=state.get("recent_chapters") or [],
        ),
        fallback_report=fallback_guardian_report,
        model_routing=state.get("model_routing"),
        workflow_key="realtime",
        workflow_label="实时守护",
    )
    guardian_report = _merge_reports(guardian_report, fallback_guardian_report)
    return {
        "workspace": workspace,
        "guardian_report": guardian_report,
        "alerts": guardian_report["issues"],
    }


async def _realtime_commercial_node(state: RealtimeGuardState) -> dict[str, Any]:
    workspace = state.get("workspace")
    if workspace is None:
        workspace = await build_workspace(
            state["session"],
            project_id=state["project_id"],
            user_id=state["user_id"],
            branch_id=state.get("branch_id"),
        )
    fallback_repair_options = [
        "先保留本段冲突，但补一段代价说明，让爽点成立。",
        "把角色行为改成试探版，等后续铺垫足够再升级。",
        "把章末钩子挪到冲突修正之后，避免爽点建立在设定漏洞上。",
    ]
    fallback_commercial_report = build_agent_report(
        "commercial",
        summary=(
            "已基于当前警报给出最小修法，优先保住追读节奏。"
            if state.get("alerts")
            else "当前段落暂时不需要节奏层面的紧急修法。"
        ),
        issues=[],
        proposed_actions=fallback_repair_options,
    )
    commercial_context = (
        build_realtime_guard_context_text(
            workspace=workspace,
            chapter_number=state["chapter_number"],
            chapter_title=state.get("chapter_title"),
            current_outline=state.get("current_outline"),
            draft_text=state["draft_text"],
            latest_paragraph=state.get("latest_paragraph"),
            recent_chapters=state.get("recent_chapters") or [],
        )
        + f"\nGuardian警报：{state.get('alerts') or []}\n"
        + "请只给出不突破设定红线的最小修法。"
    )
    remote_report = await generate_story_agent_report(
        agent_key="commercial",
        task_name="story_engine.realtime_commercial",
        task_goal="在不破坏设定红线的前提下，为当前段落提供最小修法、保爽点方案和继续往下写的节奏建议。",
        context=commercial_context,
        fallback_report=fallback_commercial_report,
        model_routing=state.get("model_routing"),
    )
    commercial_report = _merge_reports(remote_report, fallback_commercial_report)
    repair_options = _merge_action_lists(
        list(commercial_report.get("proposed_actions") or []),
        fallback_repair_options,
    )
    return {
        "workspace": workspace,
        "commercial_report": commercial_report,
        "repair_options": repair_options,
    }


async def _realtime_arbitrator_node(state: RealtimeGuardState) -> dict[str, Any]:
    alerts = list(state.get("alerts", []))
    fallback_should_pause = any(item["severity"] in {"critical", "high"} for item in alerts)
    fallback_note = (
        "当前段落建议先修再写，否则后续越扩写，设定冲突会越难收。"
        if fallback_should_pause
        else "当前草稿没有硬冲突，可以继续推进。"
    )
    workspace = state.get("workspace")
    if workspace is None:
        workspace = await build_workspace(
            state["session"],
            project_id=state["project_id"],
            user_id=state["user_id"],
            branch_id=state.get("branch_id"),
        )
    arbitration = await generate_story_realtime_arbitration(
        chapter_number=state["chapter_number"],
        chapter_title=state.get("chapter_title"),
        latest_paragraph=state.get("latest_paragraph"),
        alerts=alerts,
        repair_options=list(state.get("repair_options") or []),
        context=(
            _compact_prompt_text(
                build_realtime_guard_context_text(
                    workspace=workspace,
                    chapter_number=state["chapter_number"],
                    chapter_title=state.get("chapter_title"),
                    current_outline=state.get("current_outline"),
                    draft_text=state["draft_text"],
                    latest_paragraph=state.get("latest_paragraph"),
                    recent_chapters=state.get("recent_chapters") or [],
                ),
                4200,
            )
            + "\nGuardian报告摘要："
            + _story_knowledge_json_snippet(
                _build_agent_report_prompt_snapshot(state.get("guardian_report") or {}),
                1600,
            )
            + "\nCommercial报告摘要："
            + _story_knowledge_json_snippet(
                _build_agent_report_prompt_snapshot(state.get("commercial_report") or {}),
                1400,
            )
        ),
        fallback_should_pause=fallback_should_pause,
        fallback_note=fallback_note,
        model_routing=state.get("model_routing"),
    )
    repair_options = _merge_action_lists(
        list(arbitration.get("selected_repairs") or []),
        list(state.get("repair_options") or []),
    )
    return {
        "should_pause": bool(arbitration.get("should_pause", fallback_should_pause)),
        "arbitration_note": str(arbitration.get("arbitration_note") or fallback_note).strip(),
        "repair_options": repair_options[:5],
    }


async def _run_realtime_guard_fallback(state: RealtimeGuardState) -> RealtimeGuardState:
    current = dict(state)
    current.update(await _realtime_guardian_node(current))
    if current.get("alerts"):
        current.update(await _realtime_commercial_node(current))
    current.update(await _realtime_arbitrator_node(current))
    return current


async def _final_guardian_node(state: FinalVerifyState) -> dict[str, Any]:
    workspace = await build_workspace(
        state["session"],
        project_id=state["project_id"],
        user_id=state["user_id"],
        branch_id=state.get("branch_id"),
    )
    issues: list[dict[str, Any]] = []
    draft = state["draft_text"]
    for rule in workspace["world_rules"]:
        banned_hits = [token for token in rule.negative_list if token and token in draft]
        for hit in banned_hits:
            issues.append(
                {
                    "severity": "high",
                    "title": f"世界规则《{rule.rule_name}》存在违规风险",
                    "detail": f"正文出现禁令关键词：{hit}",
                    "source": "guardian",
                    "suggestion": "补写代价、限制条件或改掉这处直写。",
                }
            )
    fallback_report = build_agent_report(
        "guardian",
        summary="已完成终稿设定校验。",
        issues=issues,
        proposed_actions=["优先修复高风险设定冲突。"] if issues else ["设定层面可过稿。"],
    )
    guardian_report = await _run_guardian_consensus_report(
        task_name="story_engine.final_guardian",
        task_goal="检查终稿中的人设、世界规则、时间线和细纲一致性问题。",
        context=build_workspace_context_text(
            workspace=workspace,
            draft_text=state["draft_text"],
            chapter_number=state["chapter_number"],
            chapter_title=state.get("chapter_title"),
            style_sample=state.get("style_sample"),
        ),
        fallback_report=fallback_report,
        model_routing=state.get("model_routing"),
        workflow_key="final",
        workflow_label="终稿校验",
    )
    return {"guardian_report": _merge_reports(guardian_report, fallback_report)}


async def _final_logic_node(state: FinalVerifyState) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    paragraph_count = len([segment for segment in state["draft_text"].splitlines() if segment.strip()])
    if paragraph_count < 4:
        issues.append(
            {
                "severity": "medium",
                "title": "章节层次偏薄",
                "detail": "当前文本段落层次过少，容易像剧情梗概而不是完整章节。",
                "source": "logic_debunker",
                "suggestion": "至少补齐转折、反应和结果三个层次。",
            }
        )
    if "因为" not in state["draft_text"] and "所以" not in state["draft_text"]:
        issues.append(
            {
                "severity": "low",
                "title": "因果链表达偏弱",
                "detail": "文本里显性因果提示不多，读者可能感到事件只是并列发生。",
                "source": "logic_debunker",
                "suggestion": "补一句角色判断或代价反馈，强化因果闭环。",
            }
        )
    workspace = await build_workspace(
        state["session"],
        project_id=state["project_id"],
        user_id=state["user_id"],
        branch_id=state.get("branch_id"),
    )
    fallback_report = build_agent_report(
        "logic_debunker",
        summary="已完成终稿逻辑检视。",
        issues=issues,
        proposed_actions=["补强因果和段落层次。"] if issues else ["逻辑链条整体稳定。"],
    )
    remote_report = await generate_story_agent_report(
        agent_key="logic_debunker",
        task_name="story_engine.final_logic",
        task_goal="检查本章终稿中的因果链、层次推进、战力边界和长线逻辑漏洞。",
        context=build_workspace_context_text(
            workspace=workspace,
            draft_text=state["draft_text"],
            chapter_number=state["chapter_number"],
            chapter_title=state.get("chapter_title"),
            style_sample=state.get("style_sample"),
        ),
        fallback_report=fallback_report,
        model_routing=state.get("model_routing"),
    )
    return {"logic_report": _merge_reports(remote_report, fallback_report)}


async def _final_commercial_node(state: FinalVerifyState) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    draft = state["draft_text"].strip()
    last_line = draft.splitlines()[-1] if draft.splitlines() else draft
    if len(draft) < 1200:
        issues.append(
            {
                "severity": "medium",
                "title": "章节爽点密度不足",
                "detail": "文本偏短，可能还没完成情绪起落就结束了。",
                "source": "commercial",
                "suggestion": "补一个兑现节点，再加一个章末悬念。",
            }
        )
    if all(token not in last_line for token in ["却", "然而", "直到", "才发现", "还没结束"]):
        issues.append(
            {
                "severity": "medium",
                "title": "章末钩子偏弱",
                "detail": "最后一行没有形成明显追读抓手。",
                "source": "commercial",
                "suggestion": "在结尾加一个信息反转或代价抬升。",
            }
        )
    workspace = await build_workspace(
        state["session"],
        project_id=state["project_id"],
        user_id=state["user_id"],
        branch_id=state.get("branch_id"),
    )
    fallback_report = build_agent_report(
        "commercial",
        summary="已完成爽点和追读力检视。",
        issues=issues,
        proposed_actions=["补强章末钩子和情绪起落。"] if issues else ["商业节奏可发布。"],
    )
    remote_report = await generate_story_agent_report(
        agent_key="commercial",
        task_name="story_engine.final_commercial",
        task_goal="检查本章的爽点兑现、情绪起伏、章末钩子和追读驱动力。",
        context=build_workspace_context_text(
            workspace=workspace,
            draft_text=state["draft_text"],
            chapter_number=state["chapter_number"],
            chapter_title=state.get("chapter_title"),
            style_sample=state.get("style_sample"),
        ),
        fallback_report=fallback_report,
        model_routing=state.get("model_routing"),
    )
    return {"commercial_report": _merge_reports(remote_report, fallback_report)}


async def _final_style_node(state: FinalVerifyState) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    if state.get("style_sample"):
        sample_sentences = max(1, state["style_sample"].count("。") + state["style_sample"].count("！") + state["style_sample"].count("？"))
        draft_sentences = max(1, state["draft_text"].count("。") + state["draft_text"].count("！") + state["draft_text"].count("？"))
        sample_avg = len(state["style_sample"]) / sample_sentences
        draft_avg = len(state["draft_text"]) / draft_sentences
        if abs(sample_avg - draft_avg) > 18:
            issues.append(
                {
                    "severity": "medium",
                    "title": "句式节奏与样文偏离",
                    "detail": "当前稿子的平均句长与样文差距较大，可能会让文风跑偏。",
                    "source": "style_guardian",
                    "suggestion": "沿着样文的句长和停顿节奏重新梳一遍重点段落。",
                }
            )
    workspace = await build_workspace(
        state["session"],
        project_id=state["project_id"],
        user_id=state["user_id"],
        branch_id=state.get("branch_id"),
    )
    fallback_report = build_agent_report(
        "style_guardian",
        summary="已完成文风一致性检查。",
        issues=issues,
        proposed_actions=["按样文节奏轻修重点段落。"] if issues else ["文风未见明显跑偏。"],
    )
    remote_report = await generate_story_agent_report(
        agent_key="style_guardian",
        task_name="story_engine.final_style",
        task_goal="检查本章是否贴近样文气口、句式节奏、叙述距离和情绪表达。",
        context=build_workspace_context_text(
            workspace=workspace,
            draft_text=state["draft_text"],
            chapter_number=state["chapter_number"],
            chapter_title=state.get("chapter_title"),
            style_sample=state.get("style_sample"),
        ),
        fallback_report=fallback_report,
        model_routing=state.get("model_routing"),
    )
    return {"style_report": _merge_reports(remote_report, fallback_report)}


async def _final_anchor_node(state: FinalVerifyState) -> dict[str, Any]:
    draft = state["draft_text"].strip()
    summary_text = _build_summary_text(draft)
    updates = _build_kb_update_suggestions(
        chapter_number=state["chapter_number"],
        chapter_title=state.get("chapter_title"),
        draft_text=draft,
    )
    workspace = await build_workspace(
        state["session"],
        project_id=state["project_id"],
        user_id=state["user_id"],
        branch_id=state.get("branch_id"),
    )
    fallback_payload = {
        "chapter_summary": {
            "content": summary_text,
            "core_progress": updates["core_progress"],
            "character_changes": updates["character_changes"],
            "foreshadow_updates": updates["foreshadow_updates"],
            "kb_update_suggestions": updates["kb_updates"],
        },
        "kb_updates": updates["kb_updates"],
    }
    if state.get("finalize_output"):
        anchor_payload = await generate_story_anchor_payload(
            chapter_number=state["chapter_number"],
            chapter_title=state.get("chapter_title"),
            draft_text=draft,
            context=build_workspace_context_text(
                workspace=workspace,
                draft_text=state["draft_text"],
                chapter_number=state["chapter_number"],
                chapter_title=state.get("chapter_title"),
                style_sample=state.get("style_sample"),
            ),
            fallback_payload=fallback_payload,
            model_routing=state.get("model_routing"),
        )
    else:
        anchor_payload = fallback_payload
    return {
        "anchor_payload": {
            "chapter_summary": anchor_payload["chapter_summary"],
            "kb_updates": anchor_payload["kb_updates"],
        }
    }


async def _final_arbitrator_node(state: FinalVerifyState) -> dict[str, Any]:
    all_issues = (
        state["guardian_report"]["issues"]
        + state["logic_report"]["issues"]
        + state["commercial_report"]["issues"]
        + state["style_report"]["issues"]
    )
    revision_notes = [issue["suggestion"] for issue in all_issues if issue.get("suggestion")]
    fallback_final_draft = _apply_revision_actions(
        draft_text=state["draft_text"],
        issues=all_issues,
    )
    existing_final_package = dict(state.get("final_package") or {})
    existing_final_draft = str(existing_final_package.get("final_draft") or "").strip()
    revision_meta = dict(
        existing_final_package.get("arbitrator_report", {}).get("raw_output") or {}
    )
    if state.get("finalize_output") and existing_final_draft:
        final_draft = existing_final_draft
    else:
        revision_result = await revise_story_final_draft(
            chapter_number=state["chapter_number"],
            chapter_title=state.get("chapter_title"),
            draft_text=state["draft_text"],
            revision_notes=revision_notes or ["未发现必须修复的问题，请轻微润色并稳住文风。"],
            style_sample=state.get("style_sample"),
            fallback=fallback_final_draft,
            model_routing=state.get("model_routing"),
        )
        final_draft = revision_result.content.strip() or fallback_final_draft
        revision_meta = {
            "provider": revision_result.provider,
            "model": revision_result.model,
            "used_fallback": revision_result.used_fallback,
        }
    fallback_arbitrator_report = build_agent_report(
        "arbitrator",
        summary="已完成终稿仲裁，输出统一修改包。",
        issues=all_issues,
        proposed_actions=revision_notes or ["当前章节可直接进入发布流程。"],
        raw_output={
            "consensus": True,
            **revision_meta,
        },
    )
    if state.get("finalize_output"):
        remote_arbitrator_report = await generate_story_agent_report(
            agent_key="arbitrator",
            task_name="story_engine.final_arbitrator",
            task_goal="整合四份评审报告，收敛为一份唯一执行方案。",
            context=(
                f"章节：{state.get('chapter_title') or ('第' + str(state['chapter_number']) + '章')}\n"
                + "Guardian报告摘要："
                + _story_knowledge_json_snippet(
                    _build_agent_report_prompt_snapshot(state["guardian_report"]),
                    1800,
                )
                + "\nLogic报告摘要："
                + _story_knowledge_json_snippet(
                    _build_agent_report_prompt_snapshot(state["logic_report"]),
                    1800,
                )
                + "\nCommercial报告摘要："
                + _story_knowledge_json_snippet(
                    _build_agent_report_prompt_snapshot(state["commercial_report"]),
                    1600,
                )
                + "\nStyle报告摘要："
                + _story_knowledge_json_snippet(
                    _build_agent_report_prompt_snapshot(state["style_report"]),
                    1400,
                )
                + "\nAnchor更新建议："
                + _story_knowledge_json_snippet(state["anchor_payload"], 1600)
            ),
            fallback_report=fallback_arbitrator_report,
            model_routing=state.get("model_routing"),
        )
        arbitrator_report = _merge_reports(remote_arbitrator_report, fallback_arbitrator_report)
    else:
        arbitrator_report = fallback_arbitrator_report
    arbitrator_report["raw_output"] = {
        **dict(arbitrator_report.get("raw_output") or {}),
        "consensus": len(arbitrator_report.get("issues") or []) == 0,
        **revision_meta,
    }
    return {
        "final_package": {
            "final_draft": final_draft,
            "revision_notes": revision_notes or ["未发现必须修复的问题。"],
            "arbitrator_report": arbitrator_report,
        },
        "output_finalized": bool(state.get("finalize_output")),
    }


async def _run_final_verify_fallback(state: FinalVerifyState) -> FinalVerifyState:
    current = dict(state)
    current.update(await _final_guardian_node(current))
    current.update(await _final_logic_node(current))
    current.update(await _final_commercial_node(current))
    current.update(await _final_style_node(current))
    current.update(await _final_anchor_node(current))
    current.update(await _final_arbitrator_node(current))
    return current


async def _persist_outline_stress_result(
    session: AsyncSession,
    *,
    project_id: UUID,
    user_id: UUID,
    branch_id: Optional[UUID],
    outline_draft: dict[str, list[dict[str, Any]]],
    initial_kb: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    if branch_id is None:
        raise AppError(
            code="story_engine.branch_scope_required",
            message="当前分线范围缺失，暂时不能写入这套大纲。",
            status_code=422,
        )

    await session.execute(
        delete(StoryOutline).where(
            StoryOutline.project_id == project_id,
            StoryOutline.branch_id == branch_id,
        )
    )
    await session.commit()

    created_level_1: list[Any] = []
    created_level_2: list[Any] = []
    created_level_3: list[Any] = []

    for item in outline_draft["level_1"]:
        created = await create_entity(
            session,
            project_id=project_id,
            user_id=user_id,
            entity_type="outlines",
            payload={**item, "branch_id": branch_id},
            source_workflow="outline_stress_test",
        )
        created_level_1.append(created)

    parent_id = created_level_1[0].outline_id if created_level_1 else None
    for item in outline_draft["level_2"]:
        payload = {**item, "parent_id": parent_id}
        created = await create_entity(
            session,
            project_id=project_id,
            user_id=user_id,
            entity_type="outlines",
            payload={**payload, "branch_id": branch_id},
            source_workflow="outline_stress_test",
        )
        created_level_2.append(created)

    level_2_parent = created_level_2[0].outline_id if created_level_2 else parent_id
    for item in outline_draft["level_3"]:
        payload = {**item, "parent_id": level_2_parent}
        created = await create_entity(
            session,
            project_id=project_id,
            user_id=user_id,
            entity_type="outlines",
            payload={**payload, "branch_id": branch_id},
            source_workflow="outline_stress_test",
        )
        created_level_3.append(created)

    await _seed_initial_knowledge_base_if_empty(
        session=session,
        project_id=project_id,
        user_id=user_id,
        initial_kb=initial_kb,
    )

    outlines = await list_entities(
        session,
        project_id=project_id,
        user_id=user_id,
        entity_type="outlines",
        branch_id=branch_id,
    )
    workspace = await build_workspace(
        session,
        project_id=project_id,
        user_id=user_id,
        branch_id=branch_id,
    )
    return {
        "outlines": outlines,
        "initial_kb": {
            "characters": workspace["characters"],
            "foreshadows": workspace["foreshadows"],
            "items": workspace["items"],
            "world_rules": workspace["world_rules"],
            "timeline_events": workspace["timeline_events"],
        },
    }


async def _seed_initial_knowledge_base_if_empty(
    session: AsyncSession,
    *,
    project_id: UUID,
    user_id: UUID,
    initial_kb: dict[str, list[dict[str, Any]]],
) -> None:
    for entity_type in ("characters", "foreshadows", "items", "world_rules", "timeline_events"):
        existing = await list_entities(
            session,
            project_id=project_id,
            user_id=user_id,
            entity_type=entity_type,
        )
        if existing:
            continue
        for item in initial_kb.get(entity_type, []):
            await create_entity(
                session,
                project_id=project_id,
                user_id=user_id,
                entity_type=entity_type,
                payload=item,
                source_workflow="outline_stress_test",
            )


async def _upsert_chapter_summary(
    session: AsyncSession,
    *,
    project_id: UUID,
    user_id: UUID,
    branch_id: Optional[UUID],
    chapter_number: int,
    payload: dict[str, Any],
) -> Any:
    if branch_id is None:
        raise AppError(
            code="story_engine.branch_scope_required",
            message="当前分线范围缺失，暂时不能保存章节总结。",
            status_code=422,
        )
    statement = select(StoryChapterSummary).where(
        StoryChapterSummary.project_id == project_id,
        StoryChapterSummary.branch_id == branch_id,
        StoryChapterSummary.chapter_number == chapter_number,
    )
    result = await session.execute(statement)
    existing = result.scalar_one_or_none()
    if existing is None:
        return await create_entity(
            session,
            project_id=project_id,
            user_id=user_id,
            entity_type="chapter_summaries",
            payload={"chapter_number": chapter_number, "branch_id": branch_id, **payload},
            source_workflow="final_verify",
        )
    return await update_entity(
        session,
        project_id=project_id,
        user_id=user_id,
        entity_type="chapter_summaries",
        entity_id=existing.summary_id,
        payload=payload,
        source_workflow="final_verify",
    )


def _build_summary_text(draft_text: str) -> str:
    normalized = " ".join(segment.strip() for segment in draft_text.splitlines() if segment.strip())
    summary = normalized[:220]
    if len(summary) < 100:
        summary = (summary + " 本章完成一次关键推进，同时留下新的不确定因素与后续悬念。").strip()
    return summary[:300]


def _build_kb_update_suggestions(
    *,
    chapter_number: int,
    chapter_title: Optional[str],
    draft_text: str,
) -> dict[str, Any]:
    lines = [line.strip() for line in draft_text.splitlines() if line.strip()]
    headline = chapter_title or f"第{chapter_number}章"
    core_progress = [
        f"{headline}完成了当章主要冲突推进。",
        "人物关系或认知出现了可持续影响后续剧情的变化。",
    ]
    character_changes = [
        {
            "chapter_number": chapter_number,
            "change": "建议记录主角在本章的心理或立场变化。",
        }
    ]
    foreshadow_updates = [
        {
            "chapter_number": chapter_number,
            "change": "如果本章出现新异常细节，建议登记为新伏笔。",
        }
    ]
    kb_updates = [
        {
            "entity_type": "timeline_events",
            "action": "upsert",
            "chapter_number": chapter_number,
            "core_event": lines[-1][:120] if lines else draft_text[:120],
        }
    ]
    return {
        "core_progress": core_progress,
        "character_changes": character_changes,
        "foreshadow_updates": foreshadow_updates,
        "kb_updates": kb_updates,
    }


def _normalize_kb_update_suggestions(
    raw_updates: Any,
    *,
    chapter_number: int,
) -> list[dict[str, Any]]:
    if not isinstance(raw_updates, list):
        raw_updates = []
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(raw_updates):
        if not isinstance(item, dict):
            continue
        suggestion_id = str(item.get("suggestion_id") or "").strip() or f"kb-{chapter_number}-{index + 1}-{uuid4().hex[:8]}"
        entity_type = str(item.get("entity_type") or "timeline_events").strip() or "timeline_events"
        action = str(item.get("action") or "upsert").strip() or "upsert"
        status = str(item.get("status") or "pending").strip().lower() or "pending"
        if status not in {"pending", "applied", "ignored"}:
            status = "pending"
        normalized_item = {
            key: value for key, value in item.items() if value is not None
        }
        normalized_item["suggestion_id"] = suggestion_id
        normalized_item["entity_type"] = entity_type
        normalized_item["action"] = action
        normalized_item["status"] = status
        normalized_item.setdefault("chapter_number", chapter_number)
        normalized.append(normalized_item)
    return normalized


def _apply_revision_actions(
    *,
    draft_text: str,
    issues: list[dict[str, Any]],
) -> str:
    revised = draft_text.strip()
    issue_titles = Counter(issue["title"] for issue in issues)
    if issue_titles.get("章末钩子偏弱"):
        revised = revised.rstrip("。！？\n") + "\n\n可他还没来得及松口气，就意识到真正的代价现在才开始。"
    if issue_titles.get("章节层次偏薄"):
        revised += "\n\n他短暂地停了一下，把刚才的胜负重新在脑子里过了一遍，终于明白自己到底赌上了什么。"
    return revised


def _merge_reports(primary: dict[str, Any], fallback: dict[str, Any]) -> dict[str, Any]:
    merged_issues = _merge_issue_lists(
        list(primary.get("issues") or []),
        list(fallback.get("issues") or []),
    )
    merged_actions = _merge_action_lists(
        list(primary.get("proposed_actions") or []),
        list(fallback.get("proposed_actions") or []),
    )
    summary = primary.get("summary") or fallback.get("summary") or ""
    return {
        **fallback,
        **primary,
        "summary": summary,
        "issues": merged_issues,
        "proposed_actions": merged_actions,
    }


def _merge_issue_lists(*issue_groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for group in issue_groups:
        for item in group:
            title = str(item.get("title") or "").strip()
            detail = str(item.get("detail") or "").strip()
            if not title or not detail:
                continue
            key = (title, detail)
            if key in seen:
                continue
            seen.add(key)
            merged.append(item)
    return merged


def _merge_action_lists(*action_groups: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for group in action_groups:
        for item in group:
            text = str(item or "").strip()
            if not text or text in seen:
                continue
            seen.add(text)
            merged.append(text)
    return merged


def _with_overridden_role_route(
    model_routing: Optional[dict[str, dict[str, Any]]],
    *,
    role_key: str,
    model: str,
    reasoning_effort: str,
) -> dict[str, dict[str, Any]]:
    routing = {
        key: dict(value)
        for key, value in (model_routing or {}).items()
        if isinstance(value, dict)
    }
    routing[role_key] = {
        "model": model,
        "reasoning_effort": reasoning_effort,
    }
    return routing


def _issue_title_signature(issue: dict[str, Any]) -> str:
    return str(issue.get("title") or "").strip().lower()


def _blocking_issue_count(issues: list[dict[str, Any]]) -> int:
    return sum(
        1
        for item in issues
        if str(item.get("severity") or "").strip().lower() in {"critical", "high"}
    )


def _guardian_reports_disagree(
    primary_report: dict[str, Any],
    shadow_report: dict[str, Any],
) -> bool:
    primary_issues = list(primary_report.get("issues") or [])
    shadow_issues = list(shadow_report.get("issues") or [])
    if bool(primary_issues) != bool(shadow_issues):
        return True

    primary_blocking = _blocking_issue_count(primary_issues)
    shadow_blocking = _blocking_issue_count(shadow_issues)
    if primary_blocking != shadow_blocking:
        return True

    primary_titles = {_issue_title_signature(item) for item in primary_issues if _issue_title_signature(item)}
    shadow_titles = {_issue_title_signature(item) for item in shadow_issues if _issue_title_signature(item)}
    if primary_titles and shadow_titles and primary_titles.isdisjoint(shadow_titles):
        return True
    return False


def _overlap_guardian_issues(
    primary_report: dict[str, Any],
    shadow_report: dict[str, Any],
) -> list[dict[str, Any]]:
    shadow_titles = {
        _issue_title_signature(item)
        for item in shadow_report.get("issues") or []
        if _issue_title_signature(item)
    }
    overlap = [
        item
        for item in primary_report.get("issues") or []
        if _issue_title_signature(item) in shadow_titles
    ]
    return _merge_issue_lists(overlap)


def _select_guardian_shadow_route(
    *,
    model_routing: Optional[dict[str, dict[str, Any]]],
) -> Optional[dict[str, str]]:
    consensus_config = get_story_engine_guardian_consensus_config()
    if not consensus_config.get("enabled", True):
        return None

    primary_model = get_story_engine_role_model("guardian", model_routing)
    preferred_shadow_model = str(consensus_config.get("shadow_model") or "").strip()
    candidate_models = [
        preferred_shadow_model,
        "gemini-3.1-pro-preview",
        "gpt-5.4",
        "claude-opus-4-6",
    ]
    shadow_model = next(
        (item for item in candidate_models if item and item != primary_model),
        "",
    )
    if not shadow_model:
        return None
    return {
        "model": shadow_model,
        "reasoning_effort": str(
            consensus_config.get("shadow_reasoning_effort") or "high"
        ).strip()
        or "high",
    }


async def _run_guardian_consensus_report(
    *,
    task_name: str,
    task_goal: str,
    context: str,
    fallback_report: dict[str, Any],
    model_routing: Optional[dict[str, dict[str, Any]]],
    workflow_key: str,
    workflow_label: str,
) -> dict[str, Any]:
    consensus_config = get_story_engine_guardian_consensus_config()
    workflow_enabled = bool(consensus_config.get(f"{workflow_key}_enabled", True))
    shadow_route = (
        _select_guardian_shadow_route(model_routing=model_routing)
        if workflow_enabled
        else None
    )
    primary_model = get_story_engine_role_model("guardian", model_routing)

    primary_task = generate_story_agent_report(
        agent_key="guardian",
        task_name=task_name,
        task_goal=task_goal,
        context=context,
        fallback_report=fallback_report,
        model_routing=model_routing,
    )
    if shadow_route is None:
        primary_report = await primary_task
        primary_report["raw_output"] = {
            **dict(primary_report.get("raw_output") or {}),
            "guardian_consensus_mode": "single",
            "guardian_primary_model": primary_model,
        }
        return primary_report

    shadow_task = generate_story_agent_report(
        agent_key="guardian",
        task_name=f"{task_name}.shadow",
        task_goal=task_goal,
        context=context,
        fallback_report=fallback_report,
        model_routing=_with_overridden_role_route(
            model_routing,
            role_key="guardian",
            model=shadow_route["model"],
            reasoning_effort=shadow_route["reasoning_effort"],
        ),
    )
    primary_report, shadow_report = await asyncio.gather(primary_task, shadow_task)
    disagreement = _guardian_reports_disagree(primary_report, shadow_report)

    if not disagreement:
        return build_agent_report(
            "guardian",
            summary=f"双模型设定守护已完成交叉校验，{workflow_label}阶段结论一致。",
            issues=_merge_issue_lists(
                list(primary_report.get("issues") or []),
                list(shadow_report.get("issues") or []),
            ),
            proposed_actions=_merge_action_lists(
                list(primary_report.get("proposed_actions") or []),
                list(shadow_report.get("proposed_actions") or []),
            ),
            raw_output={
                "guardian_consensus_mode": "dual",
                "disagreement": False,
                "guardian_primary_model": primary_model,
                "guardian_shadow_model": shadow_route["model"],
                "primary_report": primary_report,
                "shadow_report": shadow_report,
            },
        )

    tiebreak_report = await generate_story_agent_report(
        agent_key="logic_debunker",
        task_name=f"{task_name}.tiebreak",
        task_goal=(
            f"当两个设定守护模型在{workflow_label}阶段意见不一致时，"
            "请作为第三方裁判，只保留真正会导致后续崩坏的设定/逻辑硬风险。"
        ),
        context=(
            f"{context}\n\n"
            f"Guardian主校验报告：{primary_report}\n"
            f"Guardian副校验报告：{shadow_report}\n"
            "请给出最终应保留的问题清单。"
        ),
        fallback_report=build_agent_report(
            "logic_debunker",
            summary="双模型守护存在分歧，已执行第三方复核。",
            issues=[],
            proposed_actions=["只保留真正会导致后续崩坏的风险。"],
        ),
        model_routing=model_routing,
    )
    consensus_issues = _merge_issue_lists(
        _overlap_guardian_issues(primary_report, shadow_report),
        list(tiebreak_report.get("issues") or []),
    )
    consensus_actions = _merge_action_lists(
        [
            str(item.get("suggestion") or "").strip()
            for item in consensus_issues
            if str(item.get("suggestion") or "").strip()
        ],
        list(tiebreak_report.get("proposed_actions") or []),
        list(primary_report.get("proposed_actions") or []),
        list(shadow_report.get("proposed_actions") or []),
    )
    return build_agent_report(
        "guardian",
        summary=(
            f"双模型设定守护在{workflow_label}阶段出现分歧，已由逻辑挑刺复核并收敛结论。"
            if consensus_issues
            else f"双模型设定守护在{workflow_label}阶段出现分歧，但第三方复核后未保留硬冲突。"
        ),
        issues=consensus_issues,
        proposed_actions=consensus_actions,
        raw_output={
            "guardian_consensus_mode": "dual",
            "disagreement": True,
            "guardian_primary_model": primary_model,
            "guardian_shadow_model": shadow_route["model"],
            "primary_report": primary_report,
            "shadow_report": shadow_report,
            "tiebreak_report": tiebreak_report,
        },
    )


async def _resolve_stream_outline_text(
    *,
    session: AsyncSession,
    project_id: UUID,
    user_id: UUID,
    outline_id: Optional[UUID],
    current_outline: Optional[str],
) -> Optional[str]:
    if current_outline and current_outline.strip():
        return current_outline.strip()
    if outline_id is None:
        return None
    outline = await get_entity(
        session,
        project_id=project_id,
        user_id=user_id,
        entity_type="outlines",
        entity_id=outline_id,
    )
    return getattr(outline, "content", None)


def _build_stream_beats(
    outline_text: Optional[str],
    *,
    target_paragraph_count: int,
) -> list[str]:
    if outline_text:
        parts = [
            part.strip(" -\t")
            for part in re.split(r"[\n；;]+", outline_text)
            if part.strip()
        ]
    else:
        parts = []

    if len(parts) == 1:
        parts = [
            item.strip()
            for item in re.split(r"[。！？!?.]+", parts[0])
            if item.strip()
        ]

    fallback_beats = [
        "用当前局面的压迫感开场，把人物困境先立住。",
        "让主角在限制条件下做出第一个选择。",
        "把人物关系、代价或世界规则往前推进一步。",
        "兑现一个阶段性收获，再抬高新的风险。",
        "在结尾留一个会逼读者点下一章的钩子。",
    ]
    beats = parts[:target_paragraph_count]
    for beat in fallback_beats:
        if len(beats) >= target_paragraph_count:
            break
        beats.append(beat)
    return beats[:target_paragraph_count]


def _split_stream_paragraphs(text: str) -> list[str]:
    normalized = text.replace("\r\n", "\n").strip()
    if not normalized:
        return []
    return [part.strip() for part in re.split(r"\n\s*\n", normalized) if part.strip()]


def _join_stream_paragraphs(paragraphs: list[str]) -> str:
    return "\n\n".join(part.strip() for part in paragraphs if part.strip()).strip()


def _extract_latest_stream_paragraph(text: str) -> Optional[str]:
    paragraphs = _split_stream_paragraphs(text)
    return paragraphs[-1] if paragraphs else None


def _build_stream_pause_metadata(
    *,
    beats: list[str],
    paused_at_paragraph: int,
    paragraph_total: int,
    current_beat: Optional[str],
) -> dict[str, Any]:
    next_paragraph_index = min(paused_at_paragraph + 1, paragraph_total + 1)
    return {
        "status": "paused",
        "paused_at_paragraph": paused_at_paragraph,
        "next_paragraph_index": next_paragraph_index,
        "current_beat": current_beat,
        "remaining_beats": beats[paused_at_paragraph:],
        "rewritable_paragraph_index": paused_at_paragraph,
        "paragraph_total": paragraph_total,
    }


def _build_style_hint(style_sample: Optional[str]) -> dict[str, Any]:
    if not style_sample or not style_sample.strip():
        return {
            "sentence_rhythm": "medium",
            "tone": "稳中带压迫感",
            "dialogue_density": "medium",
        }

    normalized = style_sample.strip()
    sentence_count = max(
        1,
        normalized.count("。") + normalized.count("！") + normalized.count("？"),
    )
    avg_sentence_length = len(normalized) / sentence_count
    if avg_sentence_length < 18:
        rhythm = "fast"
    elif avg_sentence_length > 36:
        rhythm = "dense"
    else:
        rhythm = "medium"
    dialogue_density = "high" if "“" in normalized or "\"" in normalized else "low"
    return {
        "sentence_rhythm": rhythm,
        "tone": "贴近写手样文气口",
        "dialogue_density": dialogue_density,
    }


def _extract_stream_character_name(candidate: Any) -> str:
    if isinstance(candidate, dict):
        return str(candidate.get("name") or "").strip()
    return str(getattr(candidate, "name", "") or "").strip()


def _pick_stream_character_name(
    characters: list[Any],
    *,
    preferred_markers: tuple[str, ...],
    excluded_names: Optional[set[str]] = None,
) -> Optional[str]:
    excluded_names = excluded_names or set()
    normalized: list[str] = [
        name
        for name in (_extract_stream_character_name(item) for item in characters)
        if name and name not in excluded_names
    ]
    for marker in preferred_markers:
        for name in normalized:
            if marker in name:
                return name
    return normalized[0] if normalized else None


def _build_stream_beat_sentence(beat: str, *, stage: str) -> str:
    normalized = re.sub(r"\s+", " ", str(beat or "").strip())
    normalized = normalized.rstrip("。！？；，,. ")
    if not normalized:
        normalized = "把局面继续往前推一步"

    if stage == "opening":
        if normalized.startswith("先"):
            return f"眼下第一步得{normalized}。"
        if normalized.startswith("用"):
            return f"眼下只能先{normalized}。"
        return f"眼下最要紧的，就是{normalized}。"

    if stage == "ending":
        if normalized.startswith("把"):
            return f"可这一线喘息还没落稳，接下来还得{normalized}。"
        if normalized.startswith("让"):
            return f"可这一线喘息还没落稳，更大的麻烦已经逼着他们去{normalized[1:]}。"
        return f"可这一线喘息还没落稳，{normalized}的余波就已经把下一层麻烦顶了上来。"

    if normalized.startswith("让"):
        return f"眼下最难的，就是{normalized}。"
    if normalized.startswith("把"):
        return f"真正决定走向的，是能不能{normalized}。"
    if normalized.startswith("用"):
        return f"眼下只能先{normalized}。"
    return f"这一步最要紧的，就是{normalized}。"


def _build_stream_context(
    *,
    workspace: dict[str, Any],
    recent_chapters: list[str],
    chapter_number: int,
    chapter_title: Optional[str],
) -> dict[str, Any]:
    characters = workspace.get("characters", [])
    items = workspace.get("items", [])
    world_rules = workspace.get("world_rules", [])
    foreshadows = workspace.get("foreshadows", [])
    lead_name = _pick_stream_character_name(
        characters,
        preferred_markers=("主角", "男主", "女主", "主人公"),
    ) or "主角"
    foil_name = _pick_stream_character_name(
        characters,
        preferred_markers=("宿敌", "反派", "对手", "敌", "boss"),
        excluded_names={lead_name},
    ) or "对手"
    support_name = _pick_stream_character_name(
        characters,
        preferred_markers=("盟友", "伙伴", "同伴", "朋友", "师父"),
        excluded_names={lead_name, foil_name},
    ) or "盟友"

    return {
        "chapter_label": chapter_title or f"第{chapter_number}章",
        "lead_name": lead_name,
        "foil_name": foil_name,
        "support_name": support_name,
        "anchor_item": items[0].name if items else "关键线索",
        "world_rule": world_rules[0].rule_name if world_rules else "代价规则",
        "foreshadow_hint": foreshadows[0].content if foreshadows else "一个尚未解释清楚的异常细节",
        "recent_context": " ".join(item.strip() for item in recent_chapters[-2:] if item.strip())[:220],
    }


def _compose_stream_paragraph(
    *,
    beat: str,
    paragraph_index: int,
    paragraph_total: int,
    target_word_count: int,
    existing_text: str,
    style_hint: dict[str, Any],
    stream_context: dict[str, Any],
    repair_instruction: Optional[str] = None,
) -> str:
    lead_name = stream_context["lead_name"]
    foil_name = stream_context["foil_name"]
    support_name = stream_context["support_name"]
    anchor_item = stream_context["anchor_item"]
    world_rule = stream_context["world_rule"]
    foreshadow_hint = stream_context["foreshadow_hint"]
    recent_context = stream_context["recent_context"]
    chapter_label = stream_context["chapter_label"]
    target_length = max(160, min(260, target_word_count // max(1, paragraph_total)))
    max_length = max(240, min(360, target_length + 90))

    sentences: list[str] = []
    seen_sentences: set[str] = set()

    def append_sentence(text: str) -> None:
        normalized = str(text or "").strip()
        if not normalized or normalized in seen_sentences:
            return
        seen_sentences.add(normalized)
        sentences.append(normalized)

    if paragraph_index == 1 and not existing_text.strip():
        append_sentence(f"{chapter_label}刚起势，{lead_name}就被新的局面推到了必须开口、也必须站队的位置。")
        append_sentence(_build_stream_beat_sentence(beat, stage="opening"))
        append_sentence(f"{foil_name}把试探压得很轻，却又轻得刚好能逼出{lead_name}最不能退的那一步。")
        append_sentence(f"{anchor_item}偏偏在这个节骨眼上被重新牵出来，让这场冲突一下子带上了旧账翻卷的味道。")
    elif paragraph_index >= paragraph_total:
        append_sentence(f"{lead_name}硬是把最危险的一步撑了过去，连{support_name}都看出了局势被扳回了一线。")
        append_sentence(_build_stream_beat_sentence(beat, stage="ending"))
        append_sentence(f"{foreshadow_hint}在这一刻冒了头，像有人故意把更大的风暴先掀开了一角。")
    else:
        append_sentence(f"{lead_name}没有立刻出手，而是先把眼前能踩和不能踩的地方在心里过了一遍。")
        append_sentence(_build_stream_beat_sentence(beat, stage="middle"))
        append_sentence(f"{foil_name}故意把局面让出一线松动，看着像给机会，实际上是在逼{lead_name}自己挑代价。")

    append_sentence(f"{lead_name}比谁都清楚，只要碰穿《{world_rule}》这条线，眼前占到的便宜迟早都得连本带利吐回来。")

    if repair_instruction:
        append_sentence(f"更棘手的是，{repair_instruction}这道口子必须在这一段里补平，不然前后的设定都会发虚。")
    if recent_context:
        append_sentence(f"前面埋下的余波还没散，{recent_context[:48]}像倒刺一样扎在这次推进里，让人怎么都不可能轻松落脚。")

    if style_hint.get("dialogue_density") == "high":
        append_sentence(f"“你现在收手，还来得及。”{foil_name}语气平得近乎冷，可那份平静本身就像是在逼人低头。")

    rhythm = style_hint.get("sentence_rhythm")
    if rhythm == "fast":
        rhythm_pool = [
            f"{lead_name}没再给自己犹豫的空当，抬手、试探、确认、逼近，动作一环压着一环。",
            f"局势根本不给人回头看的一秒空闲，所有选择都得在心跳落下之前做完。",
        ]
    elif rhythm == "dense":
        rhythm_pool = [
            f"{lead_name}甚至把每一步可能带出的后果都提前想了一遍，确认这条路虽然险，却仍旧比僵在原地更值得赌。",
            f"他不是在碰运气，而是在拿自己能承受的代价，去换这一线必须抢下来的主动。",
        ]
    else:
        rhythm_pool = [
            f"{lead_name}把呼吸压稳，先让局势顺着自己的判断走，再决定哪里该硬、哪里该藏。",
            f"这一回他没打算靠侥幸过关，而是准备把每个动作都落在能解释得通的因果上。",
        ]

    general_pool = [
        f"{support_name}没有插手，只在一旁盯着{lead_name}的反应，因为谁都知道这一步一旦走错，后面整章都会变味。",
        f"{anchor_item}在视线里安静得过分，反倒显得像一枚还没被真正引爆的钉子，随时可能把局面重新钉死。",
        f"{lead_name}表面上仍旧稳着，指节却已经一点点收紧，显然这一步要付的代价并不比旁人看见的少。",
        f"真正麻烦的从来不是眼前这一刀，而是这一刀落下去以后，会不会把后面所有退路一起斩断。",
    ]

    for extra_sentence in rhythm_pool + general_pool:
        if len("".join(sentences)) >= target_length:
            break
        append_sentence(extra_sentence)

    paragraph = "".join(sentences)
    if len(paragraph) < target_length:
        append_sentence(
            f"所以{lead_name}最后还是把那口气咽了回去，宁可把动作放慢半拍，也要确保这一步既能推进，又不会把后面的逻辑写塌。"
        )
        paragraph = "".join(sentences)

    return paragraph[:max_length]
