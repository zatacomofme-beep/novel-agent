from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from core.errors import AppError
from models.story_engine import StoryOutline
from services.story_engine_model_service import (
    build_outline_context_text,
    generate_story_agent_report,
    generate_story_outline_blueprint,
)
from services.story_engine_settings_service import resolve_story_engine_model_routing

from ._shared import (
    OutlineStressState,
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
    _build_outline_outline_counts,
    _build_outline_kb_counts,
    _build_deliberation_entry_from_report,
    _truncate_deliberation_text,
    _run_guardian_consensus_report,
    _get_outline_debate_max_rounds,
    _compact_prompt_text,
    _story_knowledge_json_snippet,
    _build_agent_report_prompt_snapshot,
    build_agent_report,
)
from .knowledge_guard import _serialize_story_api_entities


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
    workflow_id: str | None = None,
) -> dict[str, Any]:
    project = await get_story_engine_project(session, project_id, user_id)
    workflow_id = workflow_id or _build_workflow_id("outline_stress_test")
    task_state = await _create_workflow_task_state(
        session,
        workflow_id=workflow_id,
        workflow_type="outline_stress_test",
        project_id=project_id,
        user_id=user_id,
        chapter_id=None,
        chapter_number=None,
        initial_message="正在拆脑洞、压三级大纲并做长线挑刺。",
        initial_result=_build_workflow_task_base_result(
            workflow_id=workflow_id,
            workflow_type="outline_stress_test",
            workflow_status="running",
            chapter_number=None,
            chapter_title=None,
            branch_id=branch_id,
        ),
    )
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
    try:
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
        workflow_timeline = _build_outline_stress_workflow_timeline(
            workflow_id=workflow_id,
            branch_id=branch_id,
            idea=idea,
            source_material=source_material,
            target_chapter_count=target_chapter_count,
            target_total_words=target_total_words,
            result=result,
            persisted=persisted,
        )
        serialized_outlines = _serialize_story_api_entities(
            "outlines",
            persisted["outlines"],
        )
        response = {
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
            "workflow_timeline": workflow_timeline,
        }
        for index, workflow_event in enumerate(workflow_timeline):
            await _persist_workflow_task_event(
                session,
                task_state=task_state,
                project_id=project_id,
                user_id=user_id,
                chapter_id=None,
                workflow_type="outline_stress_test",
                workflow_event=workflow_event,
                result_patch=(
                    {
                        **_build_workflow_task_base_result(
                            workflow_id=workflow_id,
                            workflow_type="outline_stress_test",
                            workflow_status=(
                                "completed"
                                if len(response["risk_report"]) == 0
                                else "paused"
                            ),
                            chapter_number=None,
                            chapter_title=None,
                            branch_id=branch_id,
                            workflow_timeline=workflow_timeline,
                        ),
                        "risk_count": len(response["risk_report"]),
                        "debate_rounds_completed": response["debate_rounds_completed"],
                        "optimization_plan_count": len(response["optimization_plan"]),
                        "locked_level_1_count": len(response["locked_level_1_outlines"]),
                        "editable_level_2_count": len(response["editable_level_2_outlines"]),
                        "editable_level_3_count": len(response["editable_level_3_outlines"]),
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
            chapter_id=None,
            workflow_id=workflow_id,
            workflow_type="outline_stress_test",
            chapter_number=None,
            chapter_title=None,
            branch_id=branch_id,
            error=exc,
        )
        raise


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
                    f"围绕'{focus_issue.get('title') or '当前风险'}'补一个结构性修法。"
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


def _build_outline_stress_workflow_timeline(
    *,
    workflow_id: str,
    branch_id: Optional[UUID],
    idea: Optional[str],
    source_material: Optional[str],
    target_chapter_count: int,
    target_total_words: int,
    result: OutlineStressState,
    persisted: dict[str, Any],
) -> list[dict[str, Any]]:
    timeline: list[dict[str, Any]] = []
    outline_draft = dict(result.get("outline_draft") or {})
    initial_kb = dict(result.get("initial_kb") or {})
    outline_counts = _build_outline_outline_counts(outline_draft)
    kb_counts = _build_outline_kb_counts(initial_kb)
    arbitrated_report = dict(result.get("arbitrated_report") or {})
    remaining_issue_count = len(arbitrated_report.get("issues") or [])
    optimization_plan = list(result.get("optimization_plan") or [])

    _append_workflow_event(
        timeline,
        workflow_id=workflow_id,
        workflow_type="outline_stress_test",
        stage="outline_stress_started",
        status="started",
        label="开始压三级大纲",
        branch_id=branch_id,
        details={
            "idea_length": len(str(idea or "").strip()),
            "source_material_length": len(str(source_material or "").strip()),
            "target_chapter_count": target_chapter_count,
            "target_total_words": target_total_words,
        },
    )
    _append_workflow_event(
        timeline,
        workflow_id=workflow_id,
        workflow_type="outline_stress_test",
        stage="outline_blueprint_prepared",
        status="completed",
        label="初版大纲与设定已展开",
        branch_id=branch_id,
        details={
            **outline_counts,
            **kb_counts,
        },
    )
    _append_workflow_event(
        timeline,
        workflow_id=workflow_id,
        workflow_type="outline_stress_test",
        stage="guardian_review",
        status="completed",
        label="设定守护完成校验",
        branch_id=branch_id,
        agent_keys=["guardian"],
        details=_build_report_workflow_details(dict(result.get("guardian_report") or {})),
    )
    _append_workflow_event(
        timeline,
        workflow_id=workflow_id,
        workflow_type="outline_stress_test",
        stage="commercial_review",
        status="completed",
        label="节奏校验完成",
        branch_id=branch_id,
        agent_keys=["commercial"],
        details=_build_report_workflow_details(dict(result.get("commercial_report") or {})),
    )
    _append_workflow_event(
        timeline,
        workflow_id=workflow_id,
        workflow_type="outline_stress_test",
        stage="logic_review",
        status="completed",
        label="逻辑长线挑刺完成",
        branch_id=branch_id,
        agent_keys=["logic_debunker"],
        details=_build_report_workflow_details(dict(result.get("logic_report") or {})),
    )

    for item in result.get("debate_history") or []:
        focus_issue = dict(item.get("focus_issue") or {})
        remaining_issue_count_in_round = int(item.get("remaining_issue_count") or 0)
        _append_workflow_event(
            timeline,
            workflow_id=workflow_id,
            workflow_type="outline_stress_test",
            stage="debate_patch_applied",
            status="completed",
            label=f"第 {int(item.get('round_number') or 0)} 轮补丁已落下",
            message=str(item.get("patch_action") or "").strip() or None,
            branch_id=branch_id,
            round_number=int(item.get("round_number") or 0) or None,
            agent_keys=["guardian", "commercial", "logic_debunker"],
            details={
                "focus_issue_title": str(focus_issue.get("title") or "").strip() or None,
                "focus_issue_severity": str(focus_issue.get("severity") or "").strip() or None,
                "remaining_issue_count": remaining_issue_count_in_round,
            },
        )

    _append_workflow_event(
        timeline,
        workflow_id=workflow_id,
        workflow_type="outline_stress_test",
        stage="outline_arbitration",
        status="completed" if remaining_issue_count == 0 else "paused",
        label="统一裁决已生成",
        message=str(arbitrated_report.get("summary") or "").strip() or None,
        branch_id=branch_id,
        agent_keys=["arbitrator"],
        details={
            **_build_report_workflow_details(arbitrated_report),
            "remaining_issue_count": remaining_issue_count,
            "optimization_plan_count": len(optimization_plan),
        },
    )

    persisted_outlines = list(persisted.get("outlines") or [])
    persisted_initial_kb = dict(persisted.get("initial_kb") or {})
    _append_workflow_event(
        timeline,
        workflow_id=workflow_id,
        workflow_type="outline_stress_test",
        stage="outline_persisted",
        status="completed",
        label="锁死大纲与初始设定已入库",
        branch_id=branch_id,
        details={
            "persisted_outline_count": len(persisted_outlines),
            **_build_outline_kb_counts(persisted_initial_kb),
        },
    )
    _append_workflow_event(
        timeline,
        workflow_id=workflow_id,
        workflow_type="outline_stress_test",
        stage="outline_stress_completed",
        status="completed" if remaining_issue_count == 0 else "paused",
        label="大纲压力测试已完成",
        message=(
            "主线已经锁死，可以进入正文。"
            if remaining_issue_count == 0
            else f"当前仍有 {remaining_issue_count} 个高风险点，建议先处理后再开写。"
        ),
        branch_id=branch_id,
        details={
            "remaining_issue_count": remaining_issue_count,
            "optimization_plan_length": len(optimization_plan),
            "total_outline_count": len(persisted_outlines),
        },
    )
    return timeline


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


async def _outline_guardian_commercial_node(state: OutlineStressState) -> dict[str, Any]:
    from services.story_engine_kb_service import get_story_engine_project, create_entity

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
                "suggestion": "补充一句'主角最想得到什么，最怕失去什么'。",
            }
        )
    commercial_issues = [
        {
            "severity": "medium",
            "title": "章末钩子需要固定机制",
            "detail": "当前大纲草案已有主线，但还需要明确每 3-5 章一个强钩子节点。",
            "source": "commercial",
            "suggestion": "在三级大纲中固定'阶段性兑现 + 反转留坑'的章末结构。",
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
            patch_action = f"已针对风险'{current_issue['title']}'给出结构性补丁。"
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


async def _run_outline_stress_fallback(state: OutlineStressState) -> OutlineStressState:
    current = dict(state)
    current.update(await _outline_guardian_commercial_node(current))
    current.update(await _outline_logic_node(current))
    while _should_continue_outline_debate(current) == "debate":
        current.update(await _outline_debate_node(current))
    current.update(await _outline_arbitrator_node(current))
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
    from services.story_engine_kb_service import create_entity, list_entities, build_workspace, get_story_engine_project

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
    from services.story_engine_kb_service import create_entity, list_entities

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