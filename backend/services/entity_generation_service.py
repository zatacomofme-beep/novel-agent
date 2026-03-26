from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any, Optional
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from agents.model_gateway import GenerationRequest, model_gateway
from memory.story_bible import StoryBibleContext, load_story_bible_context
from schemas.project import (
    CharacterGenerationRequest,
    CharacterGenerationResponse,
    FactionGenerationRequest,
    FactionGenerationResponse,
    GeneratedCharacter,
    GeneratedFaction,
    GeneratedItem,
    GeneratedLocation,
    GeneratedPlotThread,
    ItemGenerationRequest,
    ItemGenerationResponse,
    LocationGenerationRequest,
    LocationGenerationResponse,
    PlotThreadGenerationRequest,
    PlotThreadGenerationResponse,
)
from services.story_engine_model_service import (
    get_story_engine_role_model,
    get_story_engine_role_reasoning,
)
from services.story_engine_settings_service import resolve_story_engine_model_routing


_LIST_SPLIT_PATTERN = re.compile(r"[\n,，、/；;|]+")
_JSON_FENCE_PATTERN = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)
_CONTEXT_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9]{3,}|[\u4e00-\u9fff]{2,6}")

_CHARACTER_SURNAMES = ["林", "沈", "顾", "谢", "闻", "苏", "周", "秦", "陆", "程", "江", "叶", "白", "韩"]
_CHARACTER_GIVEN_LIGHT = ["清", "宁", "遥", "岚", "舟", "昭", "禾", "衡", "青", "言", "桥", "溪", "月", "安"]
_CHARACTER_GIVEN_DARK = ["烬", "霜", "夜", "砚", "沉", "魇", "焰", "鸦", "凛", "刃", "朔", "岑", "暮", "影"]
_CHARACTER_TRAITS_LIGHT = ["冷静克制", "敏锐机警", "外柔内韧", "善于观察", "温和却有底线", "行动果断"]
_CHARACTER_TRAITS_DARK = ["寡言警觉", "压抑锋利", "偏执坚忍", "冷硬自持", "善于伪装", "心思深沉"]
_CHARACTER_MOTIVATIONS = ["守住仅剩的归属", "查清隐藏已久的真相", "摆脱旧秩序的束缚", "完成无法回避的承诺", "阻止更大的灾祸扩散"]
_CHARACTER_CONFLICTS = ["必须在亲情与立场之间做出选择", "越接近真相越会失去重要之人", "能力每次使用都伴随明确代价", "与自己过去的判断持续冲突"]

_ITEM_ADJECTIVES = ["残月", "玄铁", "雾纹", "星辉", "沉砂", "风切", "烬火", "霜息", "回声", "夜航"]
_ITEM_NOUNS = {
    "weapon": ["长刃", "短枪", "折刀", "长弓", "战镰", "手炮"],
    "armor": ["甲胄", "护心镜", "披风", "臂铠", "锁衣"],
    "accessory": ["戒", "坠", "印章", "耳坠", "手串"],
    "consumable": ["药剂", "符包", "燃香", "针剂", "灵液"],
    "artifact": ["古印", "权杖", "石板", "罗盘", "灵匣"],
    "material": ["矿晶", "羽片", "鳞砂", "树脂", "骨片"],
    "key_item": ["钥匙", "地图匣", "契约书", "信物", "残页"],
}
_ITEM_EFFECTS = {
    "weapon": ["能在近身缠斗中压制对手", "会在危急时刻反馈持有者情绪", "对特定敌人造成额外压制"],
    "armor": ["能短暂削减致命伤害", "可在极端环境下维持行动能力", "会把冲击分散到四肢"],
    "accessory": ["强化感知与记忆", "在接近目标时轻微发热", "能稳定持有者情绪波动"],
    "consumable": ["快速恢复体力", "压制异常状态", "短时间提升反应速度"],
    "artifact": ["与世界规则产生共鸣", "能开启被封存的信息", "会记录使用者的重要选择"],
    "material": ["适合作为核心锻造素材", "能放大仪式效果", "对稀有装置有稳定作用"],
    "key_item": ["牵引主线谜团推进", "能够指向隐藏地点", "关系到关键人物的过去"],
}

_LOCATION_PREFIXES_LIGHT = ["青", "云", "潮", "星", "明", "远", "晴", "白", "银", "映"]
_LOCATION_PREFIXES_DARK = ["雾", "寒", "黑", "烬", "沉", "裂", "幽", "夜", "断", "霜"]
_LOCATION_MIDDLES = ["港", "川", "岭", "庭", "门", "汀", "湾", "原", "塔", "渊"]
_LOCATION_SUFFIXES = {
    "city": ["城", "都", "镇", "港"],
    "village": ["村", "寨", "里", "镇"],
    "dungeon": ["窟", "穴", "狱", "遗迹"],
    "mountain": ["山", "岭", "峰", "崖"],
    "forest": ["林", "原", "泽", "野"],
    "ocean": ["海", "湾", "潮", "湖"],
    "building": ["宫", "塔", "院", "馆"],
    "realm": ["境", "界", "域", "天"],
}
_LOCATION_CLIMATES = ["终年潮湿", "寒雾常驻", "风暴频发", "四季分明", "昼夜温差极大", "空气稀薄而清冽"]
_LOCATION_POPULATIONS = ["人口稀少", "商旅混杂", "守军严密", "流民聚集", "学者常驻", "多族群共居"]
_LOCATION_FEATURES = ["有严格的出入管制", "地下暗道四通八达", "建筑遵循古老禁制", "夜间会出现异常潮汐", "市场以情报交易闻名", "周边存在危险禁区"]

_FACTION_PREFIXES = ["赤曜", "雾港", "玄钟", "北辰", "裂风", "沉潮", "烬羽", "白塔", "夜巡", "镜庭"]
_FACTION_SUFFIXES = {
    "guild": ["行会", "公会", "同盟"],
    "sect": ["宗", "门", "派"],
    "nation": ["王庭", "帝国", "联邦"],
    "clan": ["氏族", "家", "宗族"],
    "religious": ["教团", "圣堂", "秘仪会"],
    "criminal": ["帮", "会", "网"],
    "corporation": ["财团", "商会", "工业社"],
    "military": ["军团", "营", "卫队"],
}
_FACTION_SCALES = ["地方势力", "跨城组织", "区域霸主", "隐秘小团体", "公开合法机构", "半地下网络"]
_FACTION_GOALS = ["垄断关键资源流向", "重写既有权力秩序", "守住被掩埋的旧秘密", "寻找足以改变局势的核心物件", "把影响力渗透到主角所在线索链"]
_FACTION_RESOURCES = ["情报网", "资金链", "训练有素的执行者", "稀缺仪式素材", "政治保护", "地下运输线"]
_FACTION_IDEOLOGIES = ["秩序高于个体", "结果优先于手段", "血统决定资格", "秘密必须被控制", "混乱才会带来新生"]

_PLOT_THREAD_PREFIXES = {
    "main": ["主线", "核心", "命脉"],
    "sub": ["支线", "侧翼", "回声"],
    "character": ["角色", "心结", "过往"],
    "mystery": ["谜局", "暗线", "真相"],
    "romance": ["情感", "牵引", "迟来"],
    "conflict": ["冲突", "裂痕", "对抗"],
}
_PLOT_THREAD_STAGES = [
    ["引入异常", "局势升级", "代价显现", "逼近结点"],
    ["埋下动机", "出现错判", "联盟松动", "迎来反转"],
    ["获得线索", "扩大追查", "失去筹码", "逼出决断"],
]


@dataclass(frozen=True)
class EntityGenerationPipelineConfig:
    generation_type: str
    task_name: str
    result_key: str
    route_roles: tuple[str, ...]
    label: str


@dataclass
class EntityGenerationPipelineResult:
    generation_type: str
    result_key: str
    response: Any
    trace: dict[str, Any]


ENTITY_GENERATION_PIPELINE_CONFIGS: dict[str, EntityGenerationPipelineConfig] = {
    "characters": EntityGenerationPipelineConfig(
        generation_type="characters",
        task_name="story_bible.characters",
        result_key="characters",
        route_roles=("guardian", "outline", "style_guardian"),
        label="人物候选",
    ),
    "supporting": EntityGenerationPipelineConfig(
        generation_type="supporting",
        task_name="story_bible.characters",
        result_key="characters",
        route_roles=("guardian", "outline", "style_guardian"),
        label="配角候选",
    ),
    "items": EntityGenerationPipelineConfig(
        generation_type="items",
        task_name="story_bible.items",
        result_key="items",
        route_roles=("outline", "anchor", "guardian"),
        label="物品候选",
    ),
    "locations": EntityGenerationPipelineConfig(
        generation_type="locations",
        task_name="story_bible.locations",
        result_key="locations",
        route_roles=("outline", "guardian", "anchor"),
        label="地点候选",
    ),
    "factions": EntityGenerationPipelineConfig(
        generation_type="factions",
        task_name="story_bible.factions",
        result_key="factions",
        route_roles=("commercial", "guardian", "outline"),
        label="势力候选",
    ),
    "plot_threads": EntityGenerationPipelineConfig(
        generation_type="plot_threads",
        task_name="story_bible.plot_threads",
        result_key="plot_threads",
        route_roles=("commercial", "outline", "guardian"),
        label="剧情线候选",
    ),
}


async def generate_characters(
    session: AsyncSession,
    project_id: UUID,
    user_id: UUID,
    payload: CharacterGenerationRequest,
) -> CharacterGenerationResponse:
    pipeline_result = await run_entity_generation_pipeline(
        session,
        project_id=project_id,
        user_id=user_id,
        generation_type=(
            "supporting"
            if str(payload.character_type or "").strip().lower() == "supporting"
            else "characters"
        ),
        payload=payload,
    )
    return pipeline_result.response


async def generate_items(
    session: AsyncSession,
    project_id: UUID,
    user_id: UUID,
    payload: ItemGenerationRequest,
) -> ItemGenerationResponse:
    pipeline_result = await run_entity_generation_pipeline(
        session,
        project_id=project_id,
        user_id=user_id,
        generation_type="items",
        payload=payload,
    )
    return pipeline_result.response


async def generate_locations(
    session: AsyncSession,
    project_id: UUID,
    user_id: UUID,
    payload: LocationGenerationRequest,
) -> LocationGenerationResponse:
    pipeline_result = await run_entity_generation_pipeline(
        session,
        project_id=project_id,
        user_id=user_id,
        generation_type="locations",
        payload=payload,
    )
    return pipeline_result.response


async def generate_factions(
    session: AsyncSession,
    project_id: UUID,
    user_id: UUID,
    payload: FactionGenerationRequest,
) -> FactionGenerationResponse:
    pipeline_result = await run_entity_generation_pipeline(
        session,
        project_id=project_id,
        user_id=user_id,
        generation_type="factions",
        payload=payload,
    )
    return pipeline_result.response


async def generate_plot_threads(
    session: AsyncSession,
    project_id: UUID,
    user_id: UUID,
    payload: PlotThreadGenerationRequest,
) -> PlotThreadGenerationResponse:
    pipeline_result = await run_entity_generation_pipeline(
        session,
        project_id=project_id,
        user_id=user_id,
        generation_type="plot_threads",
        payload=payload,
    )
    return pipeline_result.response


async def run_entity_generation_pipeline(
    session: AsyncSession,
    *,
    project_id: UUID,
    user_id: UUID,
    generation_type: str,
    payload: Any,
) -> EntityGenerationPipelineResult:
    config = _get_entity_generation_pipeline_config(generation_type)
    story_bible = await load_story_bible_context(session, project_id, user_id)
    model_routing = await _resolve_entity_generation_model_routing(
        session,
        project_id=project_id,
        user_id=user_id,
    )
    context_snapshot = _build_entity_generation_context_snapshot(
        story_bible,
        payload,
        generation_type=generation_type,
    )

    if generation_type in {"characters", "supporting"}:
        return await _run_character_generation_pipeline(
            config=config,
            story_bible=story_bible,
            payload=payload,
            model_routing=model_routing,
            context_snapshot=context_snapshot,
        )
    if generation_type == "items":
        return await _run_item_generation_pipeline(
            config=config,
            story_bible=story_bible,
            payload=payload,
            model_routing=model_routing,
            context_snapshot=context_snapshot,
        )
    if generation_type == "locations":
        return await _run_location_generation_pipeline(
            config=config,
            story_bible=story_bible,
            payload=payload,
            model_routing=model_routing,
            context_snapshot=context_snapshot,
        )
    if generation_type == "factions":
        return await _run_faction_generation_pipeline(
            config=config,
            story_bible=story_bible,
            payload=payload,
            model_routing=model_routing,
            context_snapshot=context_snapshot,
        )
    if generation_type == "plot_threads":
        return await _run_plot_thread_generation_pipeline(
            config=config,
            story_bible=story_bible,
            payload=payload,
            model_routing=model_routing,
            context_snapshot=context_snapshot,
        )
    raise KeyError(f"Unsupported entity generation type: {generation_type}")


async def _run_character_generation_pipeline(
    *,
    config: EntityGenerationPipelineConfig,
    story_bible: StoryBibleContext,
    payload: CharacterGenerationRequest,
    model_routing: Optional[dict[str, dict[str, Any]]],
    context_snapshot: dict[str, Any],
) -> EntityGenerationPipelineResult:
    fallback_response = _build_character_fallback(story_bible, payload)
    raw_result = await _run_structured_generation(
        config=config,
        system_prompt=_build_character_system_prompt(),
        prompt=_build_character_prompt(story_bible, payload),
        fallback_response=fallback_response,
        response_model=CharacterGenerationResponse,
        model_routing=model_routing,
        context_snapshot=context_snapshot,
    )
    parsed = raw_result["parsed"]
    normalized_items = _normalize_named_models(
        parsed.characters if parsed is not None else [],
        fallback_response.characters,
        field_name="name",
        count=payload.count,
        taken_keys=_collect_existing_character_names(story_bible, payload.existing_characters),
        transform=lambda candidate: _normalize_character_candidate(
            candidate,
            fallback_role=payload.character_type,
        ),
    )
    response = CharacterGenerationResponse(characters=normalized_items)
    return EntityGenerationPipelineResult(
        generation_type=config.generation_type,
        result_key=config.result_key,
        response=response,
        trace=_build_generation_trace_payload(
            config=config,
            raw_result=raw_result,
            response=response,
            requested_count=payload.count,
        ),
    )


async def _run_item_generation_pipeline(
    *,
    config: EntityGenerationPipelineConfig,
    story_bible: StoryBibleContext,
    payload: ItemGenerationRequest,
    model_routing: Optional[dict[str, dict[str, Any]]],
    context_snapshot: dict[str, Any],
) -> EntityGenerationPipelineResult:
    fallback_response = _build_item_fallback(story_bible, payload)
    raw_result = await _run_structured_generation(
        config=config,
        system_prompt=_build_item_system_prompt(),
        prompt=_build_item_prompt(story_bible, payload),
        fallback_response=fallback_response,
        response_model=ItemGenerationResponse,
        model_routing=model_routing,
        context_snapshot=context_snapshot,
    )
    parsed = raw_result["parsed"]
    normalized_items = _normalize_named_models(
        parsed.items if parsed is not None else [],
        fallback_response.items,
        field_name="name",
        count=payload.count,
        taken_keys=_collect_existing_item_names(story_bible, payload.existing_items),
        transform=lambda candidate: _normalize_item_candidate(
            candidate,
            fallback_type=payload.item_type,
        ),
    )
    response = ItemGenerationResponse(items=normalized_items)
    return EntityGenerationPipelineResult(
        generation_type=config.generation_type,
        result_key=config.result_key,
        response=response,
        trace=_build_generation_trace_payload(
            config=config,
            raw_result=raw_result,
            response=response,
            requested_count=payload.count,
        ),
    )


async def _run_location_generation_pipeline(
    *,
    config: EntityGenerationPipelineConfig,
    story_bible: StoryBibleContext,
    payload: LocationGenerationRequest,
    model_routing: Optional[dict[str, dict[str, Any]]],
    context_snapshot: dict[str, Any],
) -> EntityGenerationPipelineResult:
    fallback_response = _build_location_fallback(story_bible, payload)
    raw_result = await _run_structured_generation(
        config=config,
        system_prompt=_build_location_system_prompt(),
        prompt=_build_location_prompt(story_bible, payload),
        fallback_response=fallback_response,
        response_model=LocationGenerationResponse,
        model_routing=model_routing,
        context_snapshot=context_snapshot,
    )
    parsed = raw_result["parsed"]
    normalized_items = _normalize_named_models(
        parsed.locations if parsed is not None else [],
        fallback_response.locations,
        field_name="name",
        count=payload.count,
        taken_keys=_collect_existing_location_names(story_bible, payload.existing_locations),
        transform=lambda candidate: _normalize_location_candidate(
            candidate,
            fallback_type=payload.location_type,
        ),
    )
    response = LocationGenerationResponse(locations=normalized_items)
    return EntityGenerationPipelineResult(
        generation_type=config.generation_type,
        result_key=config.result_key,
        response=response,
        trace=_build_generation_trace_payload(
            config=config,
            raw_result=raw_result,
            response=response,
            requested_count=payload.count,
        ),
    )


async def _run_faction_generation_pipeline(
    *,
    config: EntityGenerationPipelineConfig,
    story_bible: StoryBibleContext,
    payload: FactionGenerationRequest,
    model_routing: Optional[dict[str, dict[str, Any]]],
    context_snapshot: dict[str, Any],
) -> EntityGenerationPipelineResult:
    fallback_response = _build_faction_fallback(story_bible, payload)
    raw_result = await _run_structured_generation(
        config=config,
        system_prompt=_build_faction_system_prompt(),
        prompt=_build_faction_prompt(story_bible, payload),
        fallback_response=fallback_response,
        response_model=FactionGenerationResponse,
        model_routing=model_routing,
        context_snapshot=context_snapshot,
    )
    parsed = raw_result["parsed"]
    normalized_items = _normalize_named_models(
        parsed.factions if parsed is not None else [],
        fallback_response.factions,
        field_name="name",
        count=payload.count,
        taken_keys=_collect_existing_faction_names(story_bible, payload.existing_factions),
        transform=lambda candidate: _normalize_faction_candidate(
            candidate,
            fallback_type=payload.faction_type,
        ),
    )
    response = FactionGenerationResponse(factions=normalized_items)
    return EntityGenerationPipelineResult(
        generation_type=config.generation_type,
        result_key=config.result_key,
        response=response,
        trace=_build_generation_trace_payload(
            config=config,
            raw_result=raw_result,
            response=response,
            requested_count=payload.count,
        ),
    )


async def _run_plot_thread_generation_pipeline(
    *,
    config: EntityGenerationPipelineConfig,
    story_bible: StoryBibleContext,
    payload: PlotThreadGenerationRequest,
    model_routing: Optional[dict[str, dict[str, Any]]],
    context_snapshot: dict[str, Any],
) -> EntityGenerationPipelineResult:
    fallback_response = _build_plot_thread_fallback(story_bible, payload)
    raw_result = await _run_structured_generation(
        config=config,
        system_prompt=_build_plot_thread_system_prompt(),
        prompt=_build_plot_thread_prompt(story_bible, payload),
        fallback_response=fallback_response,
        response_model=PlotThreadGenerationResponse,
        model_routing=model_routing,
        context_snapshot=context_snapshot,
    )
    parsed = raw_result["parsed"]
    normalized_items = _normalize_named_models(
        parsed.plot_threads if parsed is not None else [],
        fallback_response.plot_threads,
        field_name="title",
        count=payload.count,
        taken_keys=_collect_existing_plot_thread_names(story_bible, payload.existing_plots),
        transform=lambda candidate: _normalize_plot_thread_candidate(
            candidate,
            fallback_type=payload.plot_type,
        ),
    )
    response = PlotThreadGenerationResponse(plot_threads=normalized_items)
    return EntityGenerationPipelineResult(
        generation_type=config.generation_type,
        result_key=config.result_key,
        response=response,
        trace=_build_generation_trace_payload(
            config=config,
            raw_result=raw_result,
            response=response,
            requested_count=payload.count,
        ),
    )


async def _run_structured_generation(
    *,
    config: EntityGenerationPipelineConfig,
    system_prompt: str,
    prompt: str,
    fallback_response: Any,
    response_model: Any,
    model_routing: Optional[dict[str, dict[str, Any]]],
    context_snapshot: dict[str, Any],
) -> dict[str, Any]:
    fallback_json = json.dumps(
        fallback_response.model_dump(mode="json"),
        ensure_ascii=False,
        indent=2,
    )
    candidates = _build_entity_generation_model_candidates(
        generation_type=config.generation_type,
        model_routing=model_routing,
    )
    failover_attempts: list[dict[str, Any]] = []
    selected_result: Any | None = None
    selected_candidate: dict[str, Any] | None = None
    parsed_payload: Any | None = None
    response_source = "fallback_response"

    for index, candidate in enumerate(candidates):
        result = await model_gateway.generate_text(
            GenerationRequest(
                task_name=config.task_name,
                prompt=prompt,
                system_prompt=system_prompt,
                model=candidate["model"],
                reasoning_effort=candidate["reasoning_effort"],
                temperature=0.85,
                max_tokens=2200,
                metadata={
                    "entity_generation_type": config.generation_type,
                    "entity_generation_label": config.label,
                    "entity_route_role": candidate["role"],
                    "entity_route_index": index,
                    "entity_route_total": len(candidates),
                },
            ),
            fallback=lambda: fallback_json,
        )
        parsed = _parse_structured_response(result.content, response_model)
        should_failover = _should_failover_entity_generation_result(
            result=result,
            parsed_payload=parsed,
        )
        if should_failover and index < len(candidates) - 1:
            failover_attempts.append(
                _build_entity_generation_failover_attempt(
                    candidate=candidate,
                    result=result,
                    parse_succeeded=parsed is not None,
                )
            )
            continue

        selected_result = result
        selected_candidate = candidate
        parsed_payload = parsed
        response_source = _resolve_entity_response_source(
            result=result,
            parsed_payload=parsed,
        )
        break

    if selected_result is None:
        selected_candidate = candidates[0] if candidates else None
        selected_result = await model_gateway.generate_text(
            GenerationRequest(
                task_name=config.task_name,
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=0.85,
                max_tokens=2200,
                metadata={
                    "entity_generation_type": config.generation_type,
                    "entity_generation_label": config.label,
                    "entity_route_role": selected_candidate["role"] if selected_candidate else "default",
                },
            ),
            fallback=lambda: fallback_json,
        )
        parsed_payload = _parse_structured_response(selected_result.content, response_model)
        response_source = _resolve_entity_response_source(
            result=selected_result,
            parsed_payload=parsed_payload,
        )

    return {
        "parsed": parsed_payload,
        "selected_result": selected_result,
        "selected_candidate": selected_candidate,
        "failover_attempts": failover_attempts,
        "response_source": response_source,
        "context_snapshot": context_snapshot,
        "fallback_response": fallback_response,
        "candidates": candidates,
    }


def _parse_structured_response(raw: str, response_model: Any) -> Any | None:
    payload = _extract_json_payload(raw)
    if payload is None:
        return None
    try:
        return response_model.model_validate(payload)
    except ValidationError:
        return None


def _get_entity_generation_pipeline_config(
    generation_type: str,
) -> EntityGenerationPipelineConfig:
    config = ENTITY_GENERATION_PIPELINE_CONFIGS.get(generation_type)
    if config is None:
        raise KeyError(f"Unsupported entity generation type: {generation_type}")
    return config


async def _resolve_entity_generation_model_routing(
    session: AsyncSession,
    *,
    project_id: UUID,
    user_id: UUID,
) -> Optional[dict[str, dict[str, Any]]]:
    try:
        from services.story_engine_kb_service import get_story_engine_project

        project = await get_story_engine_project(session, project_id, user_id)
        return resolve_story_engine_model_routing(project)
    except Exception:
        return None


def _build_entity_generation_model_candidates(
    *,
    generation_type: str,
    model_routing: Optional[dict[str, dict[str, Any]]],
) -> list[dict[str, str]]:
    config = _get_entity_generation_pipeline_config(generation_type)
    candidates: list[dict[str, str]] = []
    seen_models: set[str] = set()
    for role in config.route_roles:
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


def _should_failover_entity_generation_result(
    *,
    result: Any,
    parsed_payload: Any | None,
) -> bool:
    metadata = dict(getattr(result, "metadata", None) or {})
    remote_error = metadata.get("remote_error")
    if parsed_payload is None:
        return True
    if not getattr(result, "used_fallback", False):
        return False
    return isinstance(remote_error, dict) and bool(remote_error)


def _build_entity_generation_failover_attempt(
    *,
    candidate: dict[str, Any],
    result: Any,
    parse_succeeded: bool,
) -> dict[str, Any]:
    metadata = dict(getattr(result, "metadata", None) or {})
    remote_error = metadata.get("remote_error")
    payload: dict[str, Any] = {
        "role": candidate["role"],
        "model": candidate["model"],
        "reasoning_effort": candidate["reasoning_effort"],
        "selected_provider": metadata.get("selected_provider"),
        "used_fallback": bool(getattr(result, "used_fallback", False)),
        "parse_succeeded": parse_succeeded,
    }
    if isinstance(remote_error, dict):
        payload["remote_error"] = remote_error
    if not parse_succeeded:
        payload["failure_reason"] = "invalid_json"
    return payload


def _resolve_entity_response_source(
    *,
    result: Any,
    parsed_payload: Any | None,
) -> str:
    if parsed_payload is None:
        return "fallback_response"
    if getattr(result, "used_fallback", False):
        return "local_fallback"
    return "model_response"


def _build_generation_trace_payload(
    *,
    config: EntityGenerationPipelineConfig,
    raw_result: dict[str, Any],
    response: Any,
    requested_count: int,
) -> dict[str, Any]:
    parsed_payload = raw_result["parsed"]
    selected_result = raw_result["selected_result"]
    selected_candidate = raw_result["selected_candidate"] or {}
    fallback_response = raw_result["fallback_response"]
    result_key = config.result_key
    parsed_candidates = list(getattr(parsed_payload, result_key, []) or []) if parsed_payload is not None else []
    response_candidates = list(getattr(response, result_key, []) or [])
    fallback_candidates = list(getattr(fallback_response, result_key, []) or [])
    selected_metadata = dict(getattr(selected_result, "metadata", None) or {})
    remote_error = selected_metadata.get("remote_error")
    raw_candidate_count = len(parsed_candidates) if parsed_payload is not None else len(fallback_candidates)
    fallback_fill_count = max(0, len(response_candidates) - len(parsed_candidates))

    return {
        "generation_type": config.generation_type,
        "label": config.label,
        "result_key": result_key,
        "requested_count": requested_count,
        "returned_count": len(response_candidates),
        "raw_candidate_count": raw_candidate_count,
        "fallback_fill_count": fallback_fill_count,
        "response_source": raw_result["response_source"],
        "parse_succeeded": parsed_payload is not None,
        "selected_role": selected_candidate.get("role"),
        "selected_model": getattr(selected_result, "model", None),
        "selected_provider": getattr(selected_result, "provider", None),
        "selected_reasoning_effort": selected_candidate.get("reasoning_effort"),
        "used_fallback": bool(getattr(selected_result, "used_fallback", False)),
        "failover_triggered": len(raw_result["failover_attempts"]) > 0,
        "failover_attempts": raw_result["failover_attempts"],
        "candidate_route_roles": [item["role"] for item in raw_result["candidates"]],
        "candidate_route_models": [item["model"] for item in raw_result["candidates"]],
        "context_snapshot": raw_result["context_snapshot"],
        "entity_preview": [
            str(getattr(item, "name", None) or getattr(item, "title", None) or "").strip()
            for item in response_candidates[:5]
            if str(getattr(item, "name", None) or getattr(item, "title", None) or "").strip()
        ],
        "remote_error": remote_error if isinstance(remote_error, dict) else None,
    }


def _build_entity_generation_context_snapshot(
    story_bible: StoryBibleContext,
    payload: Any,
    *,
    generation_type: str,
) -> dict[str, Any]:
    return {
        "generation_type": generation_type,
        "scope_kind": story_bible.scope_kind,
        "branch_title": story_bible.branch_title,
        "project_title": story_bible.title,
        "genre": payload.genre if hasattr(payload, "genre") else story_bible.genre,
        "tone": payload.tone if hasattr(payload, "tone") else story_bible.tone,
        "theme": getattr(payload, "theme", None) or story_bible.theme,
        "requested_count": getattr(payload, "count", None),
        "character_count": len(story_bible.characters),
        "item_count": len(story_bible.items),
        "location_count": len(story_bible.locations),
        "faction_count": len(story_bible.factions),
        "plot_thread_count": len(story_bible.plot_threads),
        "world_rule_count": len(story_bible.world_settings),
        "total_override_count": story_bible.total_override_count,
    }


def _extract_json_payload(raw: str) -> dict[str, Any] | None:
    candidate = raw.strip()
    if not candidate:
        return None

    for fenced in _JSON_FENCE_PATTERN.findall(candidate):
        parsed = _load_json_object(fenced)
        if parsed is not None:
            return parsed

    parsed = _load_json_object(candidate)
    if parsed is not None:
        return parsed

    first = candidate.find("{")
    last = candidate.rfind("}")
    if first == -1 or last == -1 or first >= last:
        return None
    return _load_json_object(candidate[first:last + 1])


def _load_json_object(raw: str) -> dict[str, Any] | None:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _normalize_named_models(
    parsed_items: list[Any],
    fallback_items: list[Any],
    *,
    field_name: str,
    count: int,
    taken_keys: set[str],
    transform,
) -> list[Any]:
    normalized: list[Any] = []
    seen = set(taken_keys)

    for candidate in [*parsed_items, *fallback_items]:
        normalized_candidate = transform(candidate)
        name = str(getattr(normalized_candidate, field_name, "") or "").strip()
        key = _normalize_key(name)
        if not key or key in seen:
            continue
        normalized.append(normalized_candidate)
        seen.add(key)
        if len(normalized) >= count:
            break

    return normalized


def _normalize_character_candidate(
    candidate: GeneratedCharacter,
    *,
    fallback_role: str,
) -> GeneratedCharacter:
    role = str(candidate.role or "").strip().lower() or str(fallback_role or "supporting").strip().lower()
    if role not in {"protagonist", "deuteragonist", "supporting", "minor"}:
        role = str(fallback_role or "supporting").strip().lower() or "supporting"
    relationships = _clean_string_list(candidate.relationships)
    return candidate.model_copy(
        update={
            "name": str(candidate.name).strip(),
            "role": role,
            "gender": _clean_optional_text(candidate.gender),
            "appearance": _clean_optional_text(candidate.appearance),
            "personality": _clean_optional_text(candidate.personality),
            "background": _clean_optional_text(candidate.background),
            "motivation": _clean_optional_text(candidate.motivation),
            "conflict": _clean_optional_text(candidate.conflict),
            "relationships": relationships,
        }
    )


def _normalize_item_candidate(
    candidate: GeneratedItem,
    *,
    fallback_type: str,
) -> GeneratedItem:
    return candidate.model_copy(
        update={
            "name": str(candidate.name).strip(),
            "type": str(candidate.type or fallback_type or "").strip(),
            "rarity": _clean_optional_text(candidate.rarity),
            "description": _clean_optional_text(candidate.description),
            "effects": _clean_string_list(candidate.effects),
            "owner": _clean_optional_text(candidate.owner),
        }
    )


def _normalize_location_candidate(
    candidate: GeneratedLocation,
    *,
    fallback_type: str,
) -> GeneratedLocation:
    return candidate.model_copy(
        update={
            "name": str(candidate.name).strip(),
            "type": str(candidate.type or fallback_type or "").strip(),
            "climate": _clean_optional_text(candidate.climate),
            "population": _clean_optional_text(candidate.population),
            "description": _clean_optional_text(candidate.description),
            "features": _clean_string_list(candidate.features),
            "notable_residents": _clean_string_list(candidate.notable_residents),
            "history": _clean_optional_text(candidate.history),
        }
    )


def _normalize_faction_candidate(
    candidate: GeneratedFaction,
    *,
    fallback_type: str,
) -> GeneratedFaction:
    return candidate.model_copy(
        update={
            "name": str(candidate.name).strip(),
            "type": str(candidate.type or fallback_type or "").strip(),
            "scale": _clean_optional_text(candidate.scale),
            "description": _clean_optional_text(candidate.description),
            "goals": _clean_optional_text(candidate.goals),
            "leader": _clean_optional_text(candidate.leader),
            "members": _clean_string_list(candidate.members),
            "territory": _clean_optional_text(candidate.territory),
            "resources": _clean_string_list(candidate.resources),
            "ideology": _clean_optional_text(candidate.ideology),
        }
    )


def _normalize_plot_thread_candidate(
    candidate: GeneratedPlotThread,
    *,
    fallback_type: str,
) -> GeneratedPlotThread:
    return candidate.model_copy(
        update={
            "title": str(candidate.title).strip(),
            "type": str(candidate.type or fallback_type or "").strip(),
            "description": _clean_optional_text(candidate.description),
            "main_characters": _clean_string_list(candidate.main_characters),
            "locations": _clean_string_list(candidate.locations),
            "stages": _clean_string_list(candidate.stages),
            "tension_arc": _clean_optional_text(candidate.tension_arc),
            "resolution": _clean_optional_text(candidate.resolution),
        }
    )


def _build_character_fallback(
    story_bible: StoryBibleContext,
    payload: CharacterGenerationRequest,
) -> CharacterGenerationResponse:
    taken = _collect_existing_character_names(story_bible, payload.existing_characters)
    role = str(payload.character_type or "supporting").strip().lower() or "supporting"
    dark_tone = _is_dark_tone(story_bible.tone, payload.tone)
    given_pool = _CHARACTER_GIVEN_DARK if dark_tone else _CHARACTER_GIVEN_LIGHT
    traits = _CHARACTER_TRAITS_DARK if dark_tone else _CHARACTER_TRAITS_LIGHT
    relationships = _extract_labels(story_bible.characters, "name")
    locations = _extract_labels(story_bible.locations, "name")
    world_rules = _extract_labels(story_bible.world_settings, "title", "key")
    theme_anchor = _primary_context_anchor(story_bible, payload.theme, payload.genre)
    age_floor = 17 if role in {"protagonist", "deuteragonist"} else 20

    characters: list[GeneratedCharacter] = []
    offset = 0
    while len(characters) < payload.count and offset < payload.count + 16:
        name = _build_character_name(
            title=story_bible.title,
            role=role,
            dark_tone=dark_tone,
            offset=offset,
            given_pool=given_pool,
        )
        offset += 1
        key = _normalize_key(name)
        if key in taken:
            continue
        relationship_target = _pick_from_list(relationships, len(characters))
        location_anchor = _pick_from_list(locations, len(characters)) or "边境旧城"
        world_anchor = _pick_from_list(world_rules, len(characters)) or theme_anchor
        characters.append(
            GeneratedCharacter(
                name=name,
                role=role,
                age=age_floor + (len(characters) * 3) % 15,
                gender="女" if (len(characters) + len(name)) % 2 else "男",
                appearance=f"常以{location_anchor}风格的衣着示人，细节里带着{world_anchor}留下的痕迹。",
                personality=_pick_from_list(traits, len(characters)),
                background=f"出身与“{theme_anchor}”直接相关的旧线索圈层，后来在{location_anchor}站稳脚跟。",
                motivation=_pick_from_list(_CHARACTER_MOTIVATIONS, len(characters)),
                conflict=_pick_from_list(_CHARACTER_CONFLICTS, len(characters)),
                relationships=(
                    [f"与{relationship_target}之间有尚未摊开的旧账"]
                    if relationship_target and relationship_target != name
                    else []
                ),
            )
        )
        taken.add(key)

    return CharacterGenerationResponse(characters=characters)


def _build_item_fallback(
    story_bible: StoryBibleContext,
    payload: ItemGenerationRequest,
) -> ItemGenerationResponse:
    taken = _collect_existing_item_names(story_bible, payload.existing_items)
    item_type = str(payload.item_type or "artifact").strip() or "artifact"
    owners = _extract_labels(story_bible.characters, "name")
    world_rules = _extract_labels(story_bible.world_settings, "title", "key")
    descriptions = _collect_context_tokens(story_bible.title, story_bible.theme, payload.genre, payload.tone)

    items: list[GeneratedItem] = []
    offset = 0
    while len(items) < payload.count and offset < payload.count + 18:
        adjective = _ITEM_ADJECTIVES[offset % len(_ITEM_ADJECTIVES)]
        noun_pool = _ITEM_NOUNS.get(item_type, _ITEM_NOUNS["artifact"])
        noun = noun_pool[(offset + len(story_bible.title)) % len(noun_pool)]
        name = f"{adjective}{noun}"
        offset += 1
        key = _normalize_key(name)
        if key in taken:
            continue
        anchor = _pick_from_list(world_rules, len(items)) or _pick_from_list(descriptions, len(items)) or story_bible.title
        items.append(
            GeneratedItem(
                name=name,
                type=item_type,
                rarity=["常见", "稀有", "珍贵", "传承"][len(items) % 4],
                description=f"围绕“{anchor}”流传的关键物件，常被拿来撬动局势。",
                effects=[
                    _pick_from_list(_ITEM_EFFECTS.get(item_type, _ITEM_EFFECTS["artifact"]), len(items)),
                    "会在剧情关键节点暴露额外代价",
                ],
                owner=_pick_from_list(owners, len(items)),
            )
        )
        taken.add(key)

    return ItemGenerationResponse(items=items)


def _build_location_fallback(
    story_bible: StoryBibleContext,
    payload: LocationGenerationRequest,
) -> LocationGenerationResponse:
    taken = _collect_existing_location_names(story_bible, payload.existing_locations)
    location_type = str(payload.location_type or "city").strip() or "city"
    dark_tone = _is_dark_tone(story_bible.tone, payload.tone)
    prefixes = _LOCATION_PREFIXES_DARK if dark_tone else _LOCATION_PREFIXES_LIGHT
    residents = _extract_labels(story_bible.characters, "name")

    locations: list[GeneratedLocation] = []
    offset = 0
    while len(locations) < payload.count and offset < payload.count + 18:
        prefix = prefixes[offset % len(prefixes)]
        middle = _LOCATION_MIDDLES[(offset + len(story_bible.title)) % len(_LOCATION_MIDDLES)]
        suffix_pool = _LOCATION_SUFFIXES.get(location_type, _LOCATION_SUFFIXES["city"])
        suffix = suffix_pool[(offset + len(location_type)) % len(suffix_pool)]
        name = f"{prefix}{middle}{suffix}"
        offset += 1
        key = _normalize_key(name)
        if key in taken:
            continue
        locations.append(
            GeneratedLocation(
                name=name,
                type=location_type,
                climate=_pick_from_list(_LOCATION_CLIMATES, len(locations)),
                population=_pick_from_list(_LOCATION_POPULATIONS, len(locations)),
                description=f"{name}与项目主题“{story_bible.theme or story_bible.title}”紧密相关，是推动局势变化的关键空间。",
                features=[
                    _pick_from_list(_LOCATION_FEATURES, len(locations)),
                    "核心区域常被不同立场的人争夺",
                ],
                notable_residents=_pick_many(residents, start=len(locations), count=2),
                history=f"这里曾在旧事件中留下无法完全抹除的痕迹，因此成为后续冲突的高频舞台。",
            )
        )
        taken.add(key)

    return LocationGenerationResponse(locations=locations)


def _build_faction_fallback(
    story_bible: StoryBibleContext,
    payload: FactionGenerationRequest,
) -> FactionGenerationResponse:
    taken = _collect_existing_faction_names(story_bible, payload.existing_factions)
    faction_type = str(payload.faction_type or "guild").strip() or "guild"
    leaders = _extract_labels(story_bible.characters, "name")
    territories = _extract_labels(story_bible.locations, "name")
    members = _extract_labels(story_bible.characters, "name")

    factions: list[GeneratedFaction] = []
    offset = 0
    while len(factions) < payload.count and offset < payload.count + 18:
        prefix = _FACTION_PREFIXES[(offset + len(story_bible.title)) % len(_FACTION_PREFIXES)]
        suffix = _pick_from_list(_FACTION_SUFFIXES.get(faction_type, _FACTION_SUFFIXES["guild"]), offset)
        name = f"{prefix}{suffix}"
        offset += 1
        key = _normalize_key(name)
        if key in taken:
            continue
        factions.append(
            GeneratedFaction(
                name=name,
                type=faction_type,
                scale=_pick_from_list(_FACTION_SCALES, len(factions)),
                description=f"{name}长期在“{story_bible.title}”的核心矛盾外围布局，既能施压也能交易。",
                goals=_pick_from_list(_FACTION_GOALS, len(factions)),
                leader=_pick_from_list(leaders, len(factions)),
                members=_pick_many(members, start=len(factions), count=3),
                territory=_pick_from_list(territories, len(factions)),
                resources=_pick_many(_FACTION_RESOURCES, start=len(factions), count=2),
                ideology=_pick_from_list(_FACTION_IDEOLOGIES, len(factions)),
            )
        )
        taken.add(key)

    return FactionGenerationResponse(factions=factions)


def _build_plot_thread_fallback(
    story_bible: StoryBibleContext,
    payload: PlotThreadGenerationRequest,
) -> PlotThreadGenerationResponse:
    taken = _collect_existing_plot_thread_names(story_bible, payload.existing_plots)
    plot_type = str(payload.plot_type or "main").strip() or "main"
    characters = _extract_labels(story_bible.characters, "name")
    locations = _extract_labels(story_bible.locations, "name")
    theme_anchor = _primary_context_anchor(story_bible, payload.genre, payload.tone)

    plot_threads: list[GeneratedPlotThread] = []
    offset = 0
    while len(plot_threads) < payload.count and offset < payload.count + 18:
        prefix = _pick_from_list(_PLOT_THREAD_PREFIXES.get(plot_type, _PLOT_THREAD_PREFIXES["main"]), offset)
        char_anchor = _pick_from_list(characters, offset) or "关键人物"
        location_anchor = _pick_from_list(locations, offset) or "核心场域"
        title = f"{prefix}：{char_anchor}与{location_anchor}的{theme_anchor}"
        offset += 1
        key = _normalize_key(title)
        if key in taken:
            continue
        stages = _PLOT_THREAD_STAGES[len(plot_threads) % len(_PLOT_THREAD_STAGES)]
        plot_threads.append(
            GeneratedPlotThread(
                title=title,
                type=plot_type,
                description=f"围绕“{theme_anchor}”展开的持续冲突线，会直接影响主线推进节奏。",
                main_characters=_pick_many(characters, start=len(plot_threads), count=2),
                locations=_pick_many(locations, start=len(plot_threads), count=2),
                stages=stages,
                tension_arc="前段埋压，中段失控，尾段逼迫人物付出真实代价。",
                resolution="通过暴露隐藏信息或重组人物关系来完成收束。",
            )
        )
        taken.add(key)

    return PlotThreadGenerationResponse(plot_threads=plot_threads)


def _build_character_system_prompt() -> str:
    return (
        "你是资深长篇小说世界观策划。"
        "只输出合法 JSON，不要输出解释、Markdown 或额外文本。"
        "顶层字段必须是 characters。"
    )


def _build_item_system_prompt() -> str:
    return (
        "你是资深长篇小说设定策划。"
        "只输出合法 JSON，不要输出解释、Markdown 或额外文本。"
        "顶层字段必须是 items。"
    )


def _build_location_system_prompt() -> str:
    return (
        "你是资深长篇小说地理设定策划。"
        "只输出合法 JSON，不要输出解释、Markdown 或额外文本。"
        "顶层字段必须是 locations。"
    )


def _build_faction_system_prompt() -> str:
    return (
        "你是资深长篇小说组织设定策划。"
        "只输出合法 JSON，不要输出解释、Markdown 或额外文本。"
        "顶层字段必须是 factions。"
    )


def _build_plot_thread_system_prompt() -> str:
    return (
        "你是资深长篇小说剧情策划。"
        "只输出合法 JSON，不要输出解释、Markdown 或额外文本。"
        "顶层字段必须是 plot_threads。"
    )


def _build_character_prompt(
    story_bible: StoryBibleContext,
    payload: CharacterGenerationRequest,
) -> str:
    role = str(payload.character_type or "supporting").strip().lower() or "supporting"
    return (
        f"请为小说项目生成 {payload.count} 个中文角色候选。\n"
        "输出 schema:\n"
        '{"characters":[{"name":"", "role":"protagonist|deuteragonist|supporting|minor", "age":20, '
        '"gender":"", "appearance":"", "personality":"", "background":"", "motivation":"", '
        '"conflict":"", "relationships":[""]}]}\n'
        f"角色定位：{role}\n"
        f"项目上下文：{json.dumps(_build_prompt_context(story_bible), ensure_ascii=False)}\n"
        f"用户补充：{json.dumps({'genre': payload.genre, 'tone': payload.tone, 'theme': payload.theme, 'existing_characters': payload.existing_characters}, ensure_ascii=False)}\n"
        "要求：名字避免与已有角色重复；描述必须可直接用于故事圣经；内容尽量与现有地点、主题、人物关系形成可延展联系。"
    )


def _build_item_prompt(
    story_bible: StoryBibleContext,
    payload: ItemGenerationRequest,
) -> str:
    return (
        f"请为小说项目生成 {payload.count} 个中文物品候选。\n"
        "输出 schema:\n"
        '{"items":[{"name":"", "type":"", "rarity":"", "description":"", "effects":[""], "owner":""}]}\n'
        f"物品类型：{payload.item_type}\n"
        f"项目上下文：{json.dumps(_build_prompt_context(story_bible), ensure_ascii=False)}\n"
        f"用户补充：{json.dumps({'genre': payload.genre, 'tone': payload.tone, 'existing_items': payload.existing_items}, ensure_ascii=False)}\n"
        "要求：名字避免与已有物品重复；至少给出可见效果或用途；如果适合，owner 可以引用已有角色。"
    )


def _build_location_prompt(
    story_bible: StoryBibleContext,
    payload: LocationGenerationRequest,
) -> str:
    return (
        f"请为小说项目生成 {payload.count} 个中文地点候选。\n"
        "输出 schema:\n"
        '{"locations":[{"name":"", "type":"", "climate":"", "population":"", "description":"", "features":[""], "notable_residents":[""], "history":""}]}\n'
        f"地点类型：{payload.location_type}\n"
        f"项目上下文：{json.dumps(_build_prompt_context(story_bible), ensure_ascii=False)}\n"
        f"用户补充：{json.dumps({'genre': payload.genre, 'tone': payload.tone, 'existing_locations': payload.existing_locations}, ensure_ascii=False)}\n"
        "要求：避免与已有地点重名；描述要能支撑后续情节与角色互动。"
    )


def _build_faction_prompt(
    story_bible: StoryBibleContext,
    payload: FactionGenerationRequest,
) -> str:
    return (
        f"请为小说项目生成 {payload.count} 个中文势力/组织候选。\n"
        "输出 schema:\n"
        '{"factions":[{"name":"", "type":"", "scale":"", "description":"", "goals":"", "leader":"", "members":[""], "territory":"", "resources":[""], "ideology":""}]}\n'
        f"势力类型：{payload.faction_type}\n"
        f"项目上下文：{json.dumps(_build_prompt_context(story_bible), ensure_ascii=False)}\n"
        f"用户补充：{json.dumps({'genre': payload.genre, 'tone': payload.tone, 'existing_factions': payload.existing_factions}, ensure_ascii=False)}\n"
        "要求：避免与已有势力重名；尽量与已有角色、地点、主线矛盾形成关联。"
    )


def _build_plot_thread_prompt(
    story_bible: StoryBibleContext,
    payload: PlotThreadGenerationRequest,
) -> str:
    return (
        f"请为小说项目生成 {payload.count} 条中文剧情线候选。\n"
        "输出 schema:\n"
        '{"plot_threads":[{"title":"", "type":"", "description":"", "main_characters":[""], "locations":[""], "stages":[""], "tension_arc":"", "resolution":""}]}\n'
        f"剧情类型：{payload.plot_type}\n"
        f"项目上下文：{json.dumps(_build_prompt_context(story_bible), ensure_ascii=False)}\n"
        f"用户补充：{json.dumps({'genre': payload.genre, 'tone': payload.tone, 'existing_plots': payload.existing_plots}, ensure_ascii=False)}\n"
        "要求：避免与已有剧情线重复；stage 需要是可推进的阶段链。"
    )


def _build_prompt_context(story_bible: StoryBibleContext) -> dict[str, Any]:
    return {
        "project_title": story_bible.title,
        "genre": story_bible.genre,
        "theme": story_bible.theme,
        "tone": story_bible.tone,
        "scope_kind": story_bible.scope_kind,
        "branch_title": story_bible.branch_title,
        "characters": _extract_labels(story_bible.characters, "name")[:8],
        "items": _extract_labels(story_bible.items, "name", "key")[:6],
        "factions": _extract_labels(story_bible.factions, "name", "key")[:6],
        "locations": _extract_labels(story_bible.locations, "name")[:8],
        "plot_threads": _extract_labels(story_bible.plot_threads, "title")[:6],
        "world_settings": _extract_labels(story_bible.world_settings, "title", "key")[:6],
    }


def _collect_existing_character_names(
    story_bible: StoryBibleContext,
    raw_existing: str | None,
) -> set[str]:
    return _collect_existing_names(
        _extract_labels(story_bible.characters, "name"),
        _split_existing_values(raw_existing),
    )


def _collect_existing_location_names(
    story_bible: StoryBibleContext,
    raw_existing: str | None,
) -> set[str]:
    return _collect_existing_names(
        _extract_labels(story_bible.locations, "name"),
        _split_existing_values(raw_existing),
    )


def _collect_existing_plot_thread_names(
    story_bible: StoryBibleContext,
    raw_existing: str | None,
) -> set[str]:
    return _collect_existing_names(
        _extract_labels(story_bible.plot_threads, "title"),
        _split_existing_values(raw_existing),
    )


def _collect_existing_item_names(
    story_bible: StoryBibleContext,
    raw_existing: str | None,
) -> set[str]:
    names = _extract_labels(story_bible.items, "name", "title", "key")
    for container in [*story_bible.characters, *story_bible.locations, *story_bible.world_settings]:
        data = container.get("data")
        if not isinstance(data, dict):
            continue
        for raw_item in data.get("items", []) if isinstance(data.get("items"), list) else []:
            if isinstance(raw_item, dict):
                label = str(raw_item.get("name") or raw_item.get("title") or "").strip()
                if label:
                    names.append(label)
    return _collect_existing_names(names, _split_existing_values(raw_existing))


def _collect_existing_faction_names(
    story_bible: StoryBibleContext,
    raw_existing: str | None,
) -> set[str]:
    names = _extract_labels(story_bible.factions, "name", "title", "key")
    for world_setting in story_bible.world_settings:
        data = world_setting.get("data")
        if not isinstance(data, dict):
            continue
        if str(data.get("entity_type") or "").strip() == "faction":
            label = str(world_setting.get("title") or world_setting.get("key") or "").strip()
            if label:
                names.append(label)
    return _collect_existing_names(names, _split_existing_values(raw_existing))


def _collect_existing_names(*sources: list[str]) -> set[str]:
    taken: set[str] = set()
    for source in sources:
        for value in source:
            key = _normalize_key(value)
            if key:
                taken.add(key)
    return taken


def _split_existing_values(raw: str | None) -> list[str]:
    if not raw:
        return []
    tokens = [
        item.strip()
        for item in _LIST_SPLIT_PATTERN.split(raw)
        if item and item.strip()
    ]
    return [token for token in tokens if len(token) <= 40]


def _extract_labels(rows: list[dict[str, Any]], *fields: str) -> list[str]:
    labels: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        for field in fields:
            value = row.get(field)
            if isinstance(value, str) and value.strip():
                labels.append(value.strip())
                break
    return labels


def _normalize_key(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value).strip().lower()


def _clean_string_list(values: list[str] | None) -> list[str]:
    if not values:
        return []
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values:
        candidate = _clean_optional_text(value)
        if not candidate:
            continue
        key = _normalize_key(candidate)
        if key in seen:
            continue
        cleaned.append(candidate)
        seen.add(key)
    return cleaned


def _clean_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    candidate = str(value).strip()
    return candidate or None


def _is_dark_tone(*values: str | None) -> bool:
    joined = " ".join(value or "" for value in values).lower()
    markers = ("黑", "暗", "冷", "悬", "压", "危", "诡", "肃", "dark", "grim", "mystery")
    return any(marker in joined for marker in markers)


def _build_character_name(
    *,
    title: str,
    role: str,
    dark_tone: bool,
    offset: int,
    given_pool: list[str],
) -> str:
    surname = _CHARACTER_SURNAMES[(len(title) + offset) % len(_CHARACTER_SURNAMES)]
    first = given_pool[(offset * 2 + len(role)) % len(given_pool)]
    second_pool = _CHARACTER_GIVEN_DARK if dark_tone else _CHARACTER_GIVEN_LIGHT
    second = second_pool[(offset * 3 + len(title)) % len(second_pool)]
    if offset % 3 == 0:
        return f"{surname}{first}{second}"
    return f"{surname}{first}"


def _primary_context_anchor(
    story_bible: StoryBibleContext,
    *values: str | None,
) -> str:
    tokens = _collect_context_tokens(story_bible.theme, story_bible.genre, story_bible.tone, *values)
    return tokens[0] if tokens else story_bible.title


def _collect_context_tokens(*values: str | None) -> list[str]:
    seen: set[str] = set()
    tokens: list[str] = []
    for value in values:
        if not value:
            continue
        for token in _CONTEXT_TOKEN_PATTERN.findall(value):
            candidate = token.strip()
            if len(candidate) <= 1:
                continue
            key = _normalize_key(candidate)
            if key in seen:
                continue
            seen.add(key)
            tokens.append(candidate)
    return tokens


def _pick_from_list(values: list[str], index: int) -> str | None:
    if not values:
        return None
    return values[index % len(values)]


def _pick_many(values: list[str], *, start: int, count: int) -> list[str]:
    if not values:
        return []
    selected: list[str] = []
    seen: set[str] = set()
    offset = 0
    while len(selected) < count and offset < len(values) + count:
        candidate = values[(start + offset) % len(values)]
        offset += 1
        key = _normalize_key(candidate)
        if not key or key in seen:
            continue
        selected.append(candidate)
        seen.add(key)
    return selected
