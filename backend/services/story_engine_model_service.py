from __future__ import annotations

import json
import re
from typing import Any, Optional

from agents.model_gateway import GenerationRequest, GenerationResult, model_gateway
from agents.story_agents import STORY_AGENT_SPECS, build_agent_report
from core.config import get_settings
from services.story_engine_settings_service import (
    DEFAULT_ROLE_REASONING_MAP,
    ROLE_MODEL_ATTR_MAP,
)


def get_story_engine_role_model(
    role: str,
    model_routing: Optional[dict[str, dict[str, Any]]] = None,
) -> str:
    # 优先使用项目级策略页保存的路由，未配置时才回退到环境变量默认值。
    if isinstance(model_routing, dict):
        route = model_routing.get(role)
        if isinstance(route, dict):
            model = str(route.get("model") or "").strip()
            if model:
                return model
    settings = get_settings()
    attr_name = ROLE_MODEL_ATTR_MAP.get(role)
    if attr_name is None:
        return settings.default_model
    return str(getattr(settings, attr_name, settings.default_model))


def get_story_engine_role_reasoning(
    role: str,
    model_routing: Optional[dict[str, dict[str, Any]]] = None,
) -> str:
    if isinstance(model_routing, dict):
        route = model_routing.get(role)
        if isinstance(route, dict):
            reasoning_effort = str(route.get("reasoning_effort") or "").strip().lower()
            if reasoning_effort:
                return reasoning_effort
    return DEFAULT_ROLE_REASONING_MAP.get(role, "medium")


def is_story_engine_remote_ready() -> bool:
    return model_gateway.is_remote_available()


def _build_story_stream_model_candidates(
    model_routing: Optional[dict[str, dict[str, Any]]] = None,
) -> list[dict[str, str]]:
    """为流式正文生成构造一个有序的写作模型候选链。"""

    candidates: list[dict[str, str]] = []
    seen_models: set[str] = set()
    for role in ("stream_writer", "commercial", "style_guardian", "arbitrator"):
        model = get_story_engine_role_model(role, model_routing).strip()
        if not model or model in seen_models:
            continue
        seen_models.add(model)
        candidates.append(
            {
                "role": role,
                "model": model,
                "reasoning_effort": get_story_engine_role_reasoning(role, model_routing),
            }
        )
    return candidates


def _should_failover_story_stream_result(result: GenerationResult) -> bool:
    """仅在明显属于模型/配额/服务抖动时，才继续切换后备写作模型。"""

    if not result.used_fallback:
        return False

    metadata = dict(result.metadata or {})
    remote_error = metadata.get("remote_error")
    if not isinstance(remote_error, dict):
        return False

    error_type = str(remote_error.get("error_type") or "").strip().lower()
    message = str(remote_error.get("message") or "").strip().lower()
    status_code = remote_error.get("status_code")

    if error_type in {
        "timeout",
        "rate_limit",
        "provider_unavailable",
        "empty_response",
    }:
        return True

    if error_type != "auth":
        return False

    return status_code in (401, 403) or any(
        marker in message
        for marker in (
            "quota",
            "insufficient",
            "not enough",
            "forbidden",
            "permission",
            "unsupported",
            "access denied",
        )
    )


def _build_story_stream_failover_attempt(
    *,
    candidate: dict[str, str],
    result: GenerationResult,
) -> dict[str, Any]:
    metadata = dict(result.metadata or {})
    remote_error = metadata.get("remote_error")
    if not isinstance(remote_error, dict):
        return {
            "role": candidate["role"],
            "model": candidate["model"],
            "selected_provider": metadata.get("selected_provider"),
        }
    return {
        "role": candidate["role"],
        "model": candidate["model"],
        "selected_provider": metadata.get("selected_provider"),
        "error_type": remote_error.get("error_type"),
        "status_code": remote_error.get("status_code"),
        "message": str(remote_error.get("message") or "").strip()[:240],
    }


def _extract_story_stream_character_name(candidate: Any) -> str:
    if isinstance(candidate, dict):
        return str(candidate.get("name") or "").strip()
    return str(getattr(candidate, "name", "") or "").strip()


def _pick_story_stream_character_name(
    characters: list[Any],
    *,
    preferred_markers: tuple[str, ...],
    excluded_names: Optional[set[str]] = None,
) -> Optional[str]:
    excluded_names = excluded_names or set()
    normalized: list[str] = [
        name
        for name in (_extract_story_stream_character_name(item) for item in characters)
        if name and name not in excluded_names
    ]
    for marker in preferred_markers:
        for name in normalized:
            if marker in name:
                return name
    return normalized[0] if normalized else None


async def generate_story_outline_blueprint(
    *,
    idea: str,
    source_material: Optional[str],
    source_material_name: Optional[str],
    genre: Optional[str],
    tone: Optional[str],
    target_chapter_count: int,
    target_total_words: int,
    fallback_outline_draft: dict[str, list[dict[str, Any]]],
    fallback_initial_kb: dict[str, list[dict[str, Any]]],
    model_routing: Optional[dict[str, dict[str, Any]]] = None,
) -> dict[str, Any]:
    """生成三级大纲与初始知识库；失败时退回本地骨架。"""

    system_prompt = (
        "你是网文创作平台中的大纲总设计模型。"
        "你的任务是把写手的脑洞拆成可锁死的一级大纲、可编辑的二级大纲和单章三级细纲，"
        "同时生成可直接落库的初始知识库。"
        "请严格输出 JSON，不要解释，不要 Markdown。"
        "一级大纲必须 locked=true。"
    )
    prompt = (
        "请根据下面的脑洞生成 JSON，对象结构必须包含 outline_draft 和 initial_kb。\n\n"
        f"脑洞：{idea or '未提供'}\n"
        f"已有大纲素材：{source_material_name or '未提供'}\n"
        f"大纲原文：{source_material or '未提供'}\n"
        f"题材：{genre or '未指定'}\n"
        f"气质：{tone or '未指定'}\n"
        f"目标章节数：{target_chapter_count}\n"
        f"目标总字数：{target_total_words}\n\n"
        "JSON 结构要求：\n"
        "{\n"
        '  "outline_draft": {\n'
        '    "level_1": [{"level":"level_1","title":"","content":"","status":"todo","node_order":1,"locked":true,"immutable_reason":""}],\n'
        '    "level_2": [{"level":"level_2","title":"","content":"","status":"todo","node_order":1}],\n'
        '    "level_3": [{"level":"level_3","title":"","content":"","status":"todo","node_order":1}]\n'
        "  },\n"
        '  "initial_kb": {"characters":[],"foreshadows":[],"items":[],"world_rules":[],"timeline_events":[]}\n'
        "}\n"
        "要求：如果提供了已有大纲素材，优先忠实解读原文，再把它整理成三级大纲；不要凭空改写主线方向。"
        "主线必须清晰，规则必须能约束后期，人物至少 2-3 个，长期伏笔至少 2 条。"
    )
    result = await model_gateway.generate_text(
        GenerationRequest(
            task_name="story_engine.outline_blueprint",
            prompt=prompt,
            system_prompt=system_prompt,
            model=get_story_engine_role_model("outline", model_routing),
            reasoning_effort=get_story_engine_role_reasoning("outline", model_routing),
            temperature=0.8,
            max_tokens=2600,
            metadata={"agent_role": "outline"},
        ),
        fallback=lambda: json.dumps(
            {
                "outline_draft": fallback_outline_draft,
                "initial_kb": fallback_initial_kb,
            },
            ensure_ascii=False,
        ),
    )
    payload = _extract_json_payload(result.content)
    if not isinstance(payload, dict):
        return {
            "outline_draft": fallback_outline_draft,
            "initial_kb": fallback_initial_kb,
            "_model_meta": _generation_meta(result),
        }
    return {
        "outline_draft": _normalize_outline_draft(
            payload.get("outline_draft"),
            fallback_outline_draft=fallback_outline_draft,
        ),
        "initial_kb": _normalize_initial_kb(
            payload.get("initial_kb"),
            fallback_initial_kb=fallback_initial_kb,
        ),
        "_model_meta": _generation_meta(result),
    }


async def generate_story_agent_report(
    *,
    agent_key: str,
    task_name: str,
    task_goal: str,
    context: str,
    fallback_report: dict[str, Any],
    model_routing: Optional[dict[str, dict[str, Any]]] = None,
) -> dict[str, Any]:
    """让指定 Agent 输出结构化评审报告；解析失败时回退到本地报告。"""

    spec = STORY_AGENT_SPECS[agent_key]
    prompt = (
        f"任务目标：{task_goal}\n\n"
        f"上下文：\n{context}\n\n"
        "请严格输出 JSON 对象，结构如下：\n"
        "{\n"
        '  "summary": "一句话总结",\n'
        '  "issues": [\n'
        '    {"severity":"critical|high|medium|low","title":"","detail":"","source":"","suggestion":""}\n'
        "  ],\n"
        '  "proposed_actions": ["动作1","动作2"]\n'
        "}\n"
        "不要输出 JSON 以外的任何文字。"
    )
    result = await model_gateway.generate_text(
        GenerationRequest(
            task_name=task_name,
            prompt=prompt,
            system_prompt=spec.system_prompt_template,
            model=get_story_engine_role_model(agent_key, model_routing),
            reasoning_effort=get_story_engine_role_reasoning(agent_key, model_routing),
            temperature=0.35,
            max_tokens=1600,
            metadata={"agent_role": agent_key},
        ),
        fallback=lambda: _report_to_json_text(fallback_report),
    )
    payload = _extract_json_payload(result.content)
    if not isinstance(payload, dict):
        return {
            **fallback_report,
            "raw_output": {
                **dict(fallback_report.get("raw_output") or {}),
                **_generation_meta(result),
            },
        }

    normalized = build_agent_report(
        agent_key,
        summary=str(payload.get("summary") or fallback_report.get("summary") or "").strip(),
        issues=_normalize_issues(payload.get("issues"), source_default=agent_key),
        proposed_actions=_normalize_actions(payload.get("proposed_actions")),
        raw_output={
            **_generation_meta(result),
            "parsed": True,
        },
    )
    if not normalized["summary"]:
        normalized["summary"] = fallback_report.get("summary") or ""
    if not normalized["issues"]:
        normalized["issues"] = fallback_report.get("issues") or []
    if not normalized["proposed_actions"]:
        normalized["proposed_actions"] = fallback_report.get("proposed_actions") or []
    return normalized


async def generate_story_anchor_payload(
    *,
    chapter_number: int,
    chapter_title: Optional[str],
    draft_text: str,
    context: str,
    fallback_payload: dict[str, Any],
    model_routing: Optional[dict[str, dict[str, Any]]] = None,
) -> dict[str, Any]:
    """生成章节总结和知识库更新建议。"""

    spec = STORY_AGENT_SPECS["anchor"]
    prompt = (
        f"章节：{chapter_title or f'第{chapter_number}章'}\n\n"
        f"正文：\n{draft_text[:5000]}\n\n"
        f"上下文：\n{context}\n\n"
        "请严格输出 JSON：\n"
        "{\n"
        '  "chapter_summary": {\n'
        '    "content": "",\n'
        '    "core_progress": ["", ""],\n'
        '    "character_changes": [{"chapter_number": 1, "change": ""}],\n'
        '    "foreshadow_updates": [{"chapter_number": 1, "change": ""}],\n'
        '    "kb_update_suggestions": [{"entity_type": "", "action": "", "note": ""}]\n'
        "  },\n"
        '  "kb_updates": [{"entity_type": "", "action": "", "chapter_number": 1, "core_event": ""}]\n'
        "}\n"
        "只输出 JSON，不要解释。"
    )
    result = await model_gateway.generate_text(
        GenerationRequest(
            task_name="story_engine.anchor",
            prompt=prompt,
            system_prompt=spec.system_prompt_template,
            model=get_story_engine_role_model("anchor", model_routing),
            reasoning_effort=get_story_engine_role_reasoning("anchor", model_routing),
            temperature=0.3,
            max_tokens=1400,
            metadata={"agent_role": "anchor", "chapter_number": chapter_number},
        ),
        fallback=lambda: json.dumps(fallback_payload, ensure_ascii=False),
    )
    payload = _extract_json_payload(result.content)
    if not isinstance(payload, dict):
        return {
            **fallback_payload,
            "_model_meta": _generation_meta(result),
        }

    chapter_summary = payload.get("chapter_summary") if isinstance(payload.get("chapter_summary"), dict) else {}
    normalized_summary = {
        "content": str(chapter_summary.get("content") or fallback_payload["chapter_summary"]["content"]).strip()[:300],
        "core_progress": _normalize_string_list(chapter_summary.get("core_progress"))
        or list(fallback_payload["chapter_summary"]["core_progress"]),
        "character_changes": _normalize_dict_list(chapter_summary.get("character_changes"))
        or list(fallback_payload["chapter_summary"]["character_changes"]),
        "foreshadow_updates": _normalize_dict_list(chapter_summary.get("foreshadow_updates"))
        or list(fallback_payload["chapter_summary"]["foreshadow_updates"]),
        "kb_update_suggestions": _normalize_dict_list(chapter_summary.get("kb_update_suggestions"))
        or list(fallback_payload["chapter_summary"]["kb_update_suggestions"]),
    }
    return {
        "chapter_summary": normalized_summary,
        "kb_updates": _normalize_dict_list(payload.get("kb_updates")) or list(fallback_payload["kb_updates"]),
        "_model_meta": _generation_meta(result),
    }


async def generate_story_realtime_arbitration(
    *,
    chapter_number: int,
    chapter_title: Optional[str],
    latest_paragraph: Optional[str],
    alerts: list[dict[str, Any]],
    repair_options: list[str],
    context: str,
    fallback_should_pause: bool,
    fallback_note: str,
    model_routing: Optional[dict[str, dict[str, Any]]] = None,
) -> dict[str, Any]:
    """对实时守护场景做秒级仲裁，决定是否必须暂停。"""

    spec = STORY_AGENT_SPECS["arbitrator"]
    prompt = (
        f"章节：{chapter_title or f'第{chapter_number}章'}\n"
        f"最新段落：{latest_paragraph or '（无单独段落）'}\n\n"
        f"Guardian 警报：{json.dumps(alerts, ensure_ascii=False)}\n"
        f"Commercial 修法：{json.dumps(repair_options, ensure_ascii=False)}\n\n"
        f"上下文：\n{context}\n\n"
        "请严格输出 JSON：\n"
        "{\n"
        '  "should_pause": true,\n'
        '  "arbitration_note": "",\n'
        '  "selected_repairs": [""]\n'
        "}\n"
        "只输出 JSON。"
    )
    result = await model_gateway.generate_text(
        GenerationRequest(
            task_name="story_engine.realtime_arbitrator",
            prompt=prompt,
            system_prompt=(
                f"{spec.system_prompt_template}"
                "你正在做秒级实时仲裁。"
                "如果问题会导致设定崩坏或后续扩写成本暴涨，就 should_pause=true。"
            ),
            model=get_story_engine_role_model("arbitrator", model_routing),
            reasoning_effort=get_story_engine_role_reasoning("arbitrator", model_routing),
            temperature=0.2,
            max_tokens=600,
            metadata={"agent_role": "arbitrator", "realtime": True},
        ),
        fallback=lambda: json.dumps(
            {
                "should_pause": fallback_should_pause,
                "arbitration_note": fallback_note,
                "selected_repairs": repair_options[:3],
            },
            ensure_ascii=False,
        ),
    )
    payload = _extract_json_payload(result.content)
    if not isinstance(payload, dict):
        return {
            "should_pause": fallback_should_pause,
            "arbitration_note": fallback_note,
            "selected_repairs": repair_options[:3],
            "_model_meta": _generation_meta(result),
        }
    return {
        "should_pause": bool(payload.get("should_pause", fallback_should_pause)),
        "arbitration_note": str(payload.get("arbitration_note") or fallback_note).strip(),
        "selected_repairs": _normalize_string_list(payload.get("selected_repairs")) or repair_options[:3],
        "_model_meta": _generation_meta(result),
    }


async def generate_story_stream_paragraph(
    *,
    chapter_number: int,
    chapter_title: Optional[str],
    beat: str,
    paragraph_index: int,
    paragraph_total: int,
    draft_text: str,
    outline_text: Optional[str],
    style_sample: Optional[str],
    workspace: dict[str, Any],
    recent_chapters: list[str],
    fallback: str,
    model_routing: Optional[dict[str, dict[str, Any]]] = None,
    repair_instruction: Optional[str] = None,
    social_topology: Optional[dict[str, Any]] = None,
    causal_context: Optional[dict[str, Any]] = None,
    open_threads: Optional[list[dict[str, Any]]] = None,
    constraints_text: Optional[str] = None,
) -> GenerationResult:
    """为单段正文生成构造真实模型请求；在写作模型失败时按候选链自动容灾。"""

    characters = workspace.get("characters", [])
    lead_name = _pick_story_stream_character_name(
        characters,
        preferred_markers=("主角", "男主", "女主", "主人公"),
    ) or "主角"
    foil_name = _pick_story_stream_character_name(
        characters,
        preferred_markers=("宿敌", "反派", "对手", "敌", "boss"),
        excluded_names={lead_name},
    ) or "对手"
    rule_snippets = [
        f"{item.rule_name}：{item.rule_content}"
        for item in workspace.get("world_rules", [])[:3]
    ]
    foreshadow_snippets = [item.content for item in workspace.get("foreshadows", [])[:2]]
    item_snippets = [item.name for item in workspace.get("items", [])[:3]]
    social_snippets = _build_story_stream_social_snippets(
        workspace=workspace,
        social_topology=social_topology if isinstance(social_topology, dict) else {},
    )
    causal_snippets = _build_story_stream_causal_snippets(
        causal_context=causal_context if isinstance(causal_context, dict) else {},
    )
    open_thread_snippets = _build_story_stream_open_thread_snippets(
        open_threads=open_threads if isinstance(open_threads, list) else [],
    )
    recent_summary = "\n".join(f"- {item[:160]}" for item in recent_chapters[-2:] if item.strip())
    style_hint = style_sample.strip()[:1200] if style_sample and style_sample.strip() else "无样文，保持自然、利落、适合网文连载。"
    outline_hint = outline_text.strip()[:1200] if outline_text and outline_text.strip() else "无明确细纲，请围绕当前冲突自然推进。"
    chapter_label = chapter_title or f"第{chapter_number}章"

    system_prompt = (
        "你是革命性网文创作平台中的正文生成模型。"
        "你的目标是写出可直接进入连载草稿的中文网文章节段落。"
        "必须遵守以下规则："
        "1. 只输出正文段落，不要解释，不要分析，不要标题。"
        "2. 段落必须承接已有文本，不允许重述前文摘要。"
        "3. 必须遵守人物设定、世界规则、伏笔和当前细纲。"
        "4. 文风贴近给定样文，但不要模仿出戏。"
        "5. 章末段要自然留钩子。"
    )

    if constraints_text and constraints_text.strip():
        system_prompt = system_prompt + "\n\n" + constraints_text.strip()

    prompt = (
        f"章节：{chapter_label}\n"
        f"当前要写第 {paragraph_index}/{paragraph_total} 段。\n"
        f"核心推进点：{beat}\n\n"
        f"本章细纲：\n{outline_hint}\n\n"
        f"当前已有正文：\n{draft_text[-2500:] if draft_text else '（暂无）'}\n\n"
        f"最近两章摘要：\n{recent_summary or '（暂无）'}\n\n"
        f"重点人物：{lead_name}\n"
        f"对立人物：{foil_name}\n"
        f"世界规则：{'; '.join(rule_snippets) or '暂无'}\n"
        f"关键伏笔：{'; '.join(foreshadow_snippets) or '暂无'}\n"
        f"可用物品：{'; '.join(item_snippets) or '暂无'}\n\n"
        f"修正要求：{repair_instruction or '无额外修正要求'}\n\n"
        f"样文参考：\n{style_hint}\n\n"
        "请直接写这一段正文，长度控制在 180-320 汉字左右，保证有画面、有推进、有因果。"
    )

    prompt = (
        f"{prompt}"
        f"Social topology: {'; '.join(social_snippets) or 'none'}\n"
        f"Causal context: {'; '.join(causal_snippets) or 'none'}\n"
        f"Open threads: {'; '.join(open_thread_snippets) or 'none'}\n"
    )

    candidates = _build_story_stream_model_candidates(model_routing)
    if not candidates:
        candidates = [
            {
                "role": "stream_writer",
                "model": get_story_engine_role_model("stream_writer", model_routing),
                "reasoning_effort": get_story_engine_role_reasoning("stream_writer", model_routing),
            }
        ]

    failover_attempts: list[dict[str, Any]] = []
    failover_triggered = False

    for index, candidate in enumerate(candidates, start=1):
        result = await model_gateway.generate_text(
            GenerationRequest(
                task_name="story_engine.stream_writer",
                prompt=prompt,
                system_prompt=system_prompt,
                model=candidate["model"],
                reasoning_effort=candidate["reasoning_effort"],
                temperature=0.85,
                max_tokens=420,
                metadata={
                    "chapter_number": chapter_number,
                    "paragraph_index": paragraph_index,
                    "agent_role": "stream_writer",
                    "stream_route_role": candidate["role"],
                    "stream_route_index": index,
                    "stream_route_total": len(candidates),
                },
            ),
            fallback=lambda: fallback,
        )

        should_failover = _should_failover_story_stream_result(result)
        if should_failover:
            failover_attempts.append(
                _build_story_stream_failover_attempt(
                    candidate=candidate,
                    result=result,
                )
            )

        if should_failover and index < len(candidates):
            failover_triggered = True
            continue

        result.metadata = {
            **dict(result.metadata or {}),
            "stream_selected_role": candidate["role"],
            "stream_candidate_roles": [item["role"] for item in candidates],
            "stream_candidate_models": [item["model"] for item in candidates],
            "stream_failover_triggered": failover_triggered,
            **(
                {"stream_failover_attempts": failover_attempts}
                if failover_attempts
                else {}
            ),
        }
        return result

    # 理论上循环内一定会 return；这里保底退回启发式正文。
    return GenerationResult(
        content=fallback,
        provider="local-fallback",
        model="heuristic-v1",
        used_fallback=True,
        metadata={
            "chapter_number": chapter_number,
            "paragraph_index": paragraph_index,
            "agent_role": "stream_writer",
            "stream_failover_triggered": failover_triggered,
            "stream_failover_attempts": failover_attempts,
        },
    )


def _build_story_stream_social_snippets(
    *,
    workspace: dict[str, Any],
    social_topology: dict[str, Any],
) -> list[str]:
    centrality_scores = social_topology.get("centrality_scores")
    if not isinstance(centrality_scores, dict) or not centrality_scores:
        return []

    id_to_name: dict[str, str] = {}
    for item in workspace.get("characters", []) or []:
        character_id = str(
            getattr(item, "character_id", None)
            or getattr(item, "id", None)
            or ""
        ).strip()
        name = str(getattr(item, "name", "") or "").strip()
        if character_id and name:
            id_to_name[character_id] = name

    ranked = sorted(
        (
            (str(char_id), float(score))
            for char_id, score in centrality_scores.items()
            if isinstance(score, (int, float))
        ),
        key=lambda item: item[1],
        reverse=True,
    )
    snippets: list[str] = []
    for char_id, score in ranked[:3]:
        name = id_to_name.get(char_id)
        if not name:
            continue
        snippets.append(f"{name}({score:.2f})")
    return snippets


def _build_story_stream_causal_snippets(
    *,
    causal_context: dict[str, Any],
) -> list[str]:
    snippets: list[str] = []
    paths = causal_context.get("causal_paths")
    if isinstance(paths, list):
        for path in paths[:2]:
            if not isinstance(path, dict):
                continue
            nodes = path.get("nodes")
            if not isinstance(nodes, list):
                continue
            labels = [
                str(node.get("name") or "").strip()
                for node in nodes
                if isinstance(node, dict) and str(node.get("name") or "").strip()
            ]
            if labels:
                snippets.append(" -> ".join(labels[:4]))

    influences = causal_context.get("character_influence")
    if isinstance(influences, list):
        names = [
            str(item.get("name") or "").strip()
            for item in influences[:3]
            if isinstance(item, dict) and str(item.get("name") or "").strip()
        ]
        if names:
            snippets.append(f"High influence: {', '.join(names)}")
    return snippets[:3]


def _build_story_stream_open_thread_snippets(
    *,
    open_threads: list[dict[str, Any]],
) -> list[str]:
    snippets: list[str] = []
    for item in open_threads[:3]:
        if not isinstance(item, dict):
            continue
        entity_ref = str(item.get("entity_ref") or "").strip()
        entity_type = str(item.get("entity_type") or "").strip()
        if not entity_ref:
            continue
        snippets.append(f"{entity_ref}({entity_type})" if entity_type else entity_ref)
    return snippets


async def revise_story_final_draft(
    *,
    chapter_number: int,
    chapter_title: Optional[str],
    draft_text: str,
    revision_notes: list[str],
    style_sample: Optional[str],
    fallback: str,
    model_routing: Optional[dict[str, dict[str, Any]]] = None,
) -> GenerationResult:
    """用终局仲裁模型对整章做一次统一修订，失败时回退到规则补丁版。"""

    system_prompt = (
        f"{STORY_AGENT_SPECS['arbitrator'].system_prompt_template}"
        "你现在要直接输出修订后的章节终稿。"
        "不要解释过程，不要附加说明，只输出终稿正文。"
        "你必须优先消除设定矛盾，再保住文风和追读力。"
    )
    prompt = (
        f"章节：{chapter_title or f'第{chapter_number}章'}\n\n"
        f"待修订正文：\n{draft_text}\n\n"
        f"必须落实的修改要求：\n"
        + "\n".join(f"- {note}" for note in revision_notes[:12])
        + "\n\n"
        + f"样文参考：\n{style_sample.strip()[:1000] if style_sample and style_sample.strip() else '无额外样文，保持当前文风稳定。'}\n\n"
        + "请给出已经修好后的完整章节终稿。"
    )

    return await model_gateway.generate_text(
        GenerationRequest(
            task_name="story_engine.final_revise",
            prompt=prompt,
            system_prompt=system_prompt,
            model=get_story_engine_role_model("arbitrator", model_routing),
            reasoning_effort=get_story_engine_role_reasoning("arbitrator", model_routing),
            temperature=0.55,
            max_tokens=max(2200, min(9000, len(draft_text) * 2)),
            metadata={
                "chapter_number": chapter_number,
                "agent_role": "arbitrator",
            },
        ),
        fallback=lambda: fallback,
    )


def build_outline_context_text(
    *,
    idea: str,
    genre: Optional[str],
    tone: Optional[str],
    outline_draft: dict[str, list[dict[str, Any]]],
    initial_kb: dict[str, list[dict[str, Any]]],
) -> str:
    return (
        f"脑洞：{idea}\n"
        f"题材：{genre or '未指定'}\n"
        f"气质：{tone or '未指定'}\n"
        f"一级大纲：{_json_snippet(outline_draft.get('level_1', []), 1200)}\n"
        f"二级大纲：{_json_snippet(outline_draft.get('level_2', []), 1600)}\n"
        f"三级大纲：{_json_snippet(outline_draft.get('level_3', []), 1800)}\n"
        f"初始知识库：{_json_snippet(initial_kb, 2200)}"
    )


def build_workspace_context_text(
    *,
    workspace: dict[str, Any],
    draft_text: str,
    chapter_number: int,
    chapter_title: Optional[str],
    style_sample: Optional[str] = None,
) -> str:
    characters = [
        {
            "name": item.name,
            "personality": item.personality,
            "status": item.status,
            "arc_stage": item.arc_stage,
            "arc_boundaries": item.arc_boundaries,
        }
        for item in workspace.get("characters", [])[:6]
    ]
    world_rules = [
        {
            "rule_name": item.rule_name,
            "rule_content": item.rule_content,
            "negative_list": item.negative_list,
        }
        for item in workspace.get("world_rules", [])[:6]
    ]
    foreshadows = [
        {
            "content": item.content,
            "chapter_planted": item.chapter_planted,
            "chapter_planned_reveal": item.chapter_planned_reveal,
            "status": item.status,
        }
        for item in workspace.get("foreshadows", [])[:6]
    ]
    outlines = [
        {
            "level": item.level,
            "title": item.title,
            "content": item.content,
            "node_order": item.node_order,
        }
        for item in workspace.get("outlines", [])[:8]
    ]
    summaries = [
        {
            "chapter_number": item.chapter_number,
            "content": item.content,
        }
        for item in workspace.get("chapter_summaries", [])[:3]
    ]
    style_hint = style_sample.strip()[:1000] if style_sample and style_sample.strip() else "无样文"
    return (
        f"章节：{chapter_title or f'第{chapter_number}章'}\n"
        f"正文：{draft_text[:6000]}\n"
        f"人物：{_json_snippet(characters, 1800)}\n"
        f"世界规则：{_json_snippet(world_rules, 1600)}\n"
        f"伏笔：{_json_snippet(foreshadows, 1200)}\n"
        f"大纲：{_json_snippet(outlines, 1800)}\n"
        f"最近章节总结：{_json_snippet(summaries, 900)}\n"
        f"样文：{style_hint}"
    )


def build_realtime_guard_context_text(
    *,
    workspace: dict[str, Any],
    chapter_number: int,
    chapter_title: Optional[str],
    current_outline: Optional[str],
    draft_text: str,
    latest_paragraph: Optional[str],
    recent_chapters: list[str],
) -> str:
    characters = [
        {
            "name": item.name,
            "status": item.status,
            "arc_stage": item.arc_stage,
            "arc_boundaries": item.arc_boundaries,
        }
        for item in workspace.get("characters", [])[:6]
    ]
    world_rules = [
        {
            "rule_name": item.rule_name,
            "rule_content": item.rule_content,
            "negative_list": item.negative_list,
        }
        for item in workspace.get("world_rules", [])[:6]
    ]
    latest_summaries = [item[:220] for item in recent_chapters[-2:] if item.strip()]
    return (
        f"章节：{chapter_title or f'第{chapter_number}章'}\n"
        f"当前细纲：{(current_outline or '无明确细纲')[:1200]}\n"
        f"当前全文：{draft_text[-3500:]}\n"
        f"最新段落：{(latest_paragraph or draft_text[-800:])[:1200]}\n"
        f"最近章节：{_json_snippet(latest_summaries, 700)}\n"
        f"人物：{_json_snippet(characters, 1400)}\n"
        f"世界规则：{_json_snippet(world_rules, 1400)}\n"
    )


def _normalize_outline_draft(
    raw: Any,
    *,
    fallback_outline_draft: dict[str, list[dict[str, Any]]],
) -> dict[str, list[dict[str, Any]]]:
    if not isinstance(raw, dict):
        return fallback_outline_draft

    normalized: dict[str, list[dict[str, Any]]] = {}
    for level_key, fallback_items in fallback_outline_draft.items():
        candidate_items = raw.get(level_key)
        if not isinstance(candidate_items, list) or not candidate_items:
            normalized[level_key] = fallback_items
            continue
        level_name = level_key.replace("_draft", "")
        cleaned_items: list[dict[str, Any]] = []
        expected_level = level_key
        if level_key == "level_1":
            expected_level = "level_1"
        elif level_key == "level_2":
            expected_level = "level_2"
        elif level_key == "level_3":
            expected_level = "level_3"
        for index, item in enumerate(candidate_items[:12], start=1):
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "").strip()
            content = str(item.get("content") or "").strip()
            if not title or not content:
                continue
            cleaned_items.append(
                {
                    "level": expected_level,
                    "title": title[:255],
                    "content": content[:2000],
                    "status": str(item.get("status") or "todo"),
                    "node_order": int(item.get("node_order") or index),
                    "locked": bool(item.get("locked")) if expected_level == "level_1" else False,
                    "immutable_reason": (
                        str(item.get("immutable_reason") or "一级大纲导入后自动锁定。")
                        if expected_level == "level_1"
                        else None
                    ),
                }
            )
        normalized[level_key] = cleaned_items or fallback_items
    if normalized["level_1"]:
        normalized["level_1"][0]["locked"] = True
        normalized["level_1"][0]["immutable_reason"] = (
            normalized["level_1"][0].get("immutable_reason") or "一级大纲导入后自动锁定。"
        )
    return normalized


def _normalize_initial_kb(
    raw: Any,
    *,
    fallback_initial_kb: dict[str, list[dict[str, Any]]],
) -> dict[str, list[dict[str, Any]]]:
    if not isinstance(raw, dict):
        return fallback_initial_kb
    normalized: dict[str, list[dict[str, Any]]] = {}
    for key, fallback_items in fallback_initial_kb.items():
        candidate = raw.get(key)
        normalized[key] = _normalize_kb_section_items(
            key,
            candidate,
            fallback_items=fallback_items,
        )
    return normalized


def _normalize_issues(raw: Any, *, source_default: str) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    if not isinstance(raw, list):
        return issues
    for item in raw[:8]:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        detail = str(item.get("detail") or "").strip()
        if not title or not detail:
            continue
        severity = str(item.get("severity") or "medium").lower()
        if severity not in {"critical", "high", "medium", "low"}:
            severity = "medium"
        issues.append(
            {
                "severity": severity,
                "title": title[:120],
                "detail": detail[:600],
                "source": str(item.get("source") or source_default),
                "suggestion": str(item.get("suggestion") or "").strip() or None,
            }
        )
    return issues


def _normalize_actions(raw: Any) -> list[str]:
    return _normalize_string_list(raw)[:10]


def _normalize_string_list(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    items: list[str] = []
    for item in raw:
        text = str(item or "").strip()
        if text:
            items.append(text[:300])
    return items


def _normalize_dict_list(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    items: list[dict[str, Any]] = []
    for item in raw[:12]:
        if isinstance(item, dict):
            items.append(item)
    return items


def _extract_json_payload(text: str) -> Any:
    candidate = text.strip()
    if not candidate:
        return None
    fenced_match = re.search(r"```(?:json)?\s*(\{.*\}|\[.*\])\s*```", candidate, flags=re.S)
    if fenced_match:
        candidate = fenced_match.group(1).strip()
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass

    first_brace = candidate.find("{")
    last_brace = candidate.rfind("}")
    if first_brace >= 0 and last_brace > first_brace:
        try:
            return json.loads(candidate[first_brace : last_brace + 1])
        except json.JSONDecodeError:
            return None
    return None


def _report_to_json_text(report: dict[str, Any]) -> str:
    payload = {
        "summary": report.get("summary") or "",
        "issues": report.get("issues") or [],
        "proposed_actions": report.get("proposed_actions") or [],
    }
    return json.dumps(payload, ensure_ascii=False)


def _generation_meta(result: GenerationResult) -> dict[str, Any]:
    return {
        "provider": result.provider,
        "model": result.model,
        "used_fallback": result.used_fallback,
    }


def _json_snippet(value: Any, max_length: int) -> str:
    text = json.dumps(value, ensure_ascii=False, default=str)
    return text[:max_length]


def _normalize_kb_section_items(
    section_key: str,
    raw: Any,
    *,
    fallback_items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not isinstance(raw, list) or not raw:
        return fallback_items

    cleaned: list[dict[str, Any]] = []
    for item in raw[:12]:
        if not isinstance(item, dict):
            continue
        if section_key == "characters":
            name = str(item.get("name") or "").strip()
            if not name:
                continue
            cleaned.append(
                {
                    "name": name[:255],
                    "appearance": item.get("appearance"),
                    "personality": item.get("personality"),
                    "micro_habits": _normalize_string_list(item.get("micro_habits")),
                    "abilities": item.get("abilities") if isinstance(item.get("abilities"), dict) else {},
                    "relationships": _normalize_dict_list(item.get("relationships")),
                    "status": str(item.get("status") or "active"),
                    "arc_stage": str(item.get("arc_stage") or "initial"),
                    "arc_boundaries": _normalize_dict_list(item.get("arc_boundaries")),
                }
            )
        elif section_key == "foreshadows":
            content = str(item.get("content") or "").strip()
            if not content:
                continue
            cleaned.append(
                {
                    "content": content[:600],
                    "chapter_planted": item.get("chapter_planted"),
                    "chapter_planned_reveal": item.get("chapter_planned_reveal"),
                    "status": str(item.get("status") or "pending"),
                    "related_characters": _normalize_string_list(item.get("related_characters")),
                    "related_items": _normalize_string_list(item.get("related_items")),
                }
            )
        elif section_key == "items":
            name = str(item.get("name") or "").strip()
            if not name:
                continue
            cleaned.append(
                {
                    "name": name[:255],
                    "features": item.get("features"),
                    "owner": item.get("owner"),
                    "location": item.get("location"),
                    "special_rules": _normalize_string_list(item.get("special_rules")),
                }
            )
        elif section_key == "world_rules":
            rule_name = str(item.get("rule_name") or "").strip()
            rule_content = str(item.get("rule_content") or "").strip()
            if not rule_name or not rule_content:
                continue
            cleaned.append(
                {
                    "rule_name": rule_name[:255],
                    "rule_content": rule_content[:1200],
                    "negative_list": _normalize_string_list(item.get("negative_list")),
                    "scope": str(item.get("scope") or "global"),
                }
            )
        elif section_key == "timeline_events":
            core_event = str(item.get("core_event") or "").strip()
            if not core_event:
                continue
            cleaned.append(
                {
                    "chapter_number": item.get("chapter_number"),
                    "in_universe_time": item.get("in_universe_time"),
                    "location": item.get("location"),
                    "weather": item.get("weather"),
                    "core_event": core_event[:1200],
                    "character_states": _normalize_dict_list(item.get("character_states")),
                }
            )

    return cleaned or fallback_items
