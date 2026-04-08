from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from services.story_engine_model_service import (
    build_realtime_guard_context_text,
    generate_story_agent_report,
    generate_story_realtime_arbitration,
)
from services.story_engine_settings_service import resolve_story_engine_model_routing
from services.story_engine_kb_service import build_workspace, get_story_engine_project

from ._shared import (
    RealtimeGuardState,
    LANGGRAPH_AVAILABLE,
    StateGraph,
    START,
    END,
    _build_workflow_id,
    _build_workflow_task_base_result,
    _create_workflow_task_state,
    _persist_workflow_task_event,
    _persist_workflow_task_failure,
    _append_workflow_event,
    _build_report_workflow_details,
    _run_guardian_consensus_report,
    _resolve_workflow_chapter_id,
    _resolve_stream_outline_text,
    _compact_prompt_text,
    _story_knowledge_json_snippet,
    _build_agent_report_prompt_snapshot,
    _merge_reports,
    _merge_action_lists,
    build_agent_report,
)
from .knowledge_guard import _serialize_story_api_entities


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
        },
    )
    return timeline


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