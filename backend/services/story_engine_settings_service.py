from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.config import get_settings
from core.errors import AppError
from models.project import Project
from models.user import User
from services.project_service import PROJECT_PERMISSION_EDIT


# 统一维护“职责 -> 环境变量默认模型”的映射，保证旧配置和新策略页同时兼容。
ROLE_MODEL_ATTR_MAP = {
    "outline": "story_engine_outline_model",
    "guardian": "story_engine_guardian_model",
    "logic_debunker": "story_engine_logic_model",
    "commercial": "story_engine_commercial_model",
    "style_guardian": "story_engine_style_model",
    "anchor": "story_engine_anchor_model",
    "arbitrator": "story_engine_arbitrator_model",
    "stream_writer": "story_engine_stream_model",
}

DEFAULT_ROLE_REASONING_MAP = {
    "outline": "high",
    "guardian": "high",
    "logic_debunker": "high",
    "commercial": "medium",
    "style_guardian": "medium",
    "anchor": "medium",
    "arbitrator": "high",
    "stream_writer": "medium",
}

VALID_REASONING_EFFORTS = ("minimal", "low", "medium", "high")
DEFAULT_GUARDIAN_CONSENSUS_CONFIG = {
    "enabled": True,
    "shadow_model": "gemini-3.1-pro-preview",
    "shadow_reasoning_effort": "high",
    "outline_enabled": True,
    "realtime_enabled": True,
    "final_enabled": True,
}

STORY_ENGINE_ROLE_CATALOG = [
    {
        "role_key": "outline",
        "label": "大纲拆解",
        "description": "负责把脑洞拆成主线圣经、分卷推进和章级节点。",
    },
    {
        "role_key": "guardian",
        "label": "设定守护",
        "description": "负责盯住人物边界、世界规则和时间线硬冲突。",
    },
    {
        "role_key": "logic_debunker",
        "label": "逻辑挑刺",
        "description": "负责放大长线矛盾、战力崩坏和因果断裂风险。",
    },
    {
        "role_key": "commercial",
        "label": "爽点优化",
        "description": "负责节奏、钩子、兑现点和追更驱动力。",
    },
    {
        "role_key": "style_guardian",
        "label": "文风贴合",
        "description": "负责保持样文气口、句式节奏和叙述距离。",
    },
    {
        "role_key": "anchor",
        "label": "自动记设定",
        "description": "负责生成章节总结并给出设定更新建议。",
    },
    {
        "role_key": "arbitrator",
        "label": "终稿收束",
        "description": "负责收敛分歧，给出唯一执行方案和终稿修订。",
    },
    {
        "role_key": "stream_writer",
        "label": "正文起稿",
        "description": "负责按细纲连续起稿，保证每段都有推进感。",
    },
]

STORY_ENGINE_ROLE_MAP = {
    item["role_key"]: item for item in STORY_ENGINE_ROLE_CATALOG
}

PROFILE_CONFIG_PATH = (
    Path(__file__).resolve().parents[1] / "config" / "story_engine_model_profiles.json"
)
_PROFILE_CACHE: dict[str, Any] = {"mtime": None, "payload": None}


def _build_env_default_route(role_key: str) -> dict[str, str]:
    settings = get_settings()
    attr_name = ROLE_MODEL_ATTR_MAP.get(role_key)
    if attr_name is None:
        model = settings.default_model
    else:
        model = str(getattr(settings, attr_name, settings.default_model))
    return {
        "model": model,
        "reasoning_effort": DEFAULT_ROLE_REASONING_MAP.get(role_key, "medium"),
    }


def _build_fallback_profile_config() -> dict[str, Any]:
    default_routing = {
        role_key: _build_env_default_route(role_key)
        for role_key in STORY_ENGINE_ROLE_MAP
    }
    model_to_roles: dict[str, list[str]] = {}
    for role_key, route in default_routing.items():
        model_to_roles.setdefault(route["model"], []).append(role_key)
    return {
        "version": 1,
        "default_preset_key": "balanced",
        "guardian_consensus": deepcopy(DEFAULT_GUARDIAN_CONSENSUS_CONFIG),
        "available_models": sorted(
            [
                {
                    "id": model_id,
                    "label": model_id,
                    "provider": "openai-compatible",
                    "description": "来自环境变量的默认模型。",
                    "supports_reasoning_effort": True,
                    "recommended_roles": roles,
                }
                for model_id, roles in model_to_roles.items()
            ],
            key=lambda item: item["id"],
        ),
        "presets": [
            {
                "key": "balanced",
                "label": "环境默认组合",
                "description": "当配置文件不可用时，自动回退到环境变量默认组合。",
                "routing": default_routing,
            }
        ],
    }


def _load_profile_config() -> dict[str, Any]:
    try:
        mtime = PROFILE_CONFIG_PATH.stat().st_mtime
    except FileNotFoundError:
        return _build_fallback_profile_config()

    if _PROFILE_CACHE["payload"] is not None and _PROFILE_CACHE["mtime"] == mtime:
        return deepcopy(_PROFILE_CACHE["payload"])

    try:
        raw_payload = json.loads(PROFILE_CONFIG_PATH.read_text(encoding="utf-8"))
        payload = _normalize_profile_config(raw_payload)
    except Exception:
        payload = _build_fallback_profile_config()

    _PROFILE_CACHE["mtime"] = mtime
    _PROFILE_CACHE["payload"] = payload
    return deepcopy(payload)


def _normalize_profile_config(raw_payload: Any) -> dict[str, Any]:
    if not isinstance(raw_payload, dict):
        raise ValueError("story_engine_model_profiles.json 顶层必须是对象。")

    raw_models = raw_payload.get("available_models")
    if not isinstance(raw_models, list) or not raw_models:
        raise ValueError("available_models 不能为空。")

    available_models: list[dict[str, Any]] = []
    available_model_ids: set[str] = set()
    for item in raw_models:
        if not isinstance(item, dict):
            raise ValueError("available_models 项必须是对象。")
        model_id = str(item.get("id") or "").strip()
        if not model_id:
            raise ValueError("available_models.id 不能为空。")
        if model_id in available_model_ids:
            raise ValueError(f"模型 {model_id} 重复定义。")
        available_model_ids.add(model_id)
        available_models.append(
            {
                "id": model_id,
                "label": str(item.get("label") or model_id).strip(),
                "provider": str(item.get("provider") or "openai-compatible").strip(),
                "description": str(item.get("description") or "").strip() or None,
                "supports_reasoning_effort": bool(
                    item.get("supports_reasoning_effort", True)
                ),
                "recommended_roles": [
                    role_key
                    for role_key in item.get("recommended_roles", [])
                    if role_key in STORY_ENGINE_ROLE_MAP
                ],
            }
        )

    raw_presets = raw_payload.get("presets")
    if not isinstance(raw_presets, list) or not raw_presets:
        raise ValueError("presets 不能为空。")

    presets: list[dict[str, Any]] = []
    preset_map: dict[str, dict[str, Any]] = {}
    for item in raw_presets:
        if not isinstance(item, dict):
            raise ValueError("preset 项必须是对象。")
        preset_key = str(item.get("key") or "").strip()
        if not preset_key:
            raise ValueError("preset.key 不能为空。")
        routing = _normalize_routing_map(
            item.get("routing"),
            available_model_ids=available_model_ids,
            strict=True,
        )
        preset = {
            "key": preset_key,
            "label": str(item.get("label") or preset_key).strip(),
            "description": str(item.get("description") or "").strip() or None,
            "routing": routing,
        }
        presets.append(preset)
        preset_map[preset_key] = preset

    default_preset_key = str(raw_payload.get("default_preset_key") or "").strip()
    if default_preset_key not in preset_map:
        default_preset_key = presets[0]["key"]

    return {
        "version": int(raw_payload.get("version") or 1),
        "default_preset_key": default_preset_key,
        "guardian_consensus": _normalize_guardian_consensus_config(
            raw_payload.get("guardian_consensus"),
            available_model_ids=available_model_ids,
        ),
        "available_models": available_models,
        "available_model_ids": available_model_ids,
        "presets": presets,
        "preset_map": preset_map,
    }


def _normalize_guardian_consensus_config(
    raw_config: Any,
    *,
    available_model_ids: set[str],
) -> dict[str, Any]:
    payload = raw_config if isinstance(raw_config, dict) else {}
    preferred_shadow_model = str(
        payload.get("shadow_model")
        or DEFAULT_GUARDIAN_CONSENSUS_CONFIG["shadow_model"]
    ).strip()
    if available_model_ids and preferred_shadow_model not in available_model_ids:
        preferred_shadow_model = DEFAULT_GUARDIAN_CONSENSUS_CONFIG["shadow_model"]
    if available_model_ids and preferred_shadow_model not in available_model_ids:
        preferred_shadow_model = next(iter(sorted(available_model_ids)), "")

    return {
        "enabled": bool(payload.get("enabled", DEFAULT_GUARDIAN_CONSENSUS_CONFIG["enabled"])),
        "shadow_model": preferred_shadow_model,
        "shadow_reasoning_effort": _normalize_reasoning_effort(
            payload.get("shadow_reasoning_effort"),
            role_key="guardian",
            strict=False,
        ),
        "outline_enabled": bool(
            payload.get(
                "outline_enabled",
                DEFAULT_GUARDIAN_CONSENSUS_CONFIG["outline_enabled"],
            )
        ),
        "realtime_enabled": bool(
            payload.get(
                "realtime_enabled",
                DEFAULT_GUARDIAN_CONSENSUS_CONFIG["realtime_enabled"],
            )
        ),
        "final_enabled": bool(
            payload.get(
                "final_enabled",
                DEFAULT_GUARDIAN_CONSENSUS_CONFIG["final_enabled"],
            )
        ),
    }


def _normalize_reasoning_effort(
    reasoning_effort: Any,
    *,
    role_key: str,
    strict: bool,
) -> str:
    if reasoning_effort is None or str(reasoning_effort).strip() == "":
        return DEFAULT_ROLE_REASONING_MAP.get(role_key, "medium")
    normalized = str(reasoning_effort).strip().lower()
    if normalized not in VALID_REASONING_EFFORTS:
        if strict:
            raise AppError(
                code="story_engine.reasoning_effort_invalid",
                message="推理强度不合法，请重新选择后再保存。",
                status_code=422,
                metadata={"role_key": role_key, "reasoning_effort": reasoning_effort},
            )
        return DEFAULT_ROLE_REASONING_MAP.get(role_key, "medium")
    return normalized


def _normalize_route(
    role_key: str,
    raw_route: Any,
    *,
    available_model_ids: set[str],
    strict: bool,
) -> dict[str, str]:
    if not isinstance(raw_route, dict):
        if strict:
            raise AppError(
                code="story_engine.route_invalid",
                message="模型策略格式不正确，请刷新后重试。",
                status_code=422,
                metadata={"role_key": role_key},
            )
        return _build_env_default_route(role_key)

    model = str(raw_route.get("model") or "").strip()
    if not model:
        if strict:
            raise AppError(
                code="story_engine.route_model_required",
                message="每个职责都必须绑定一个模型。",
                status_code=422,
                metadata={"role_key": role_key},
            )
        return _build_env_default_route(role_key)

    if available_model_ids and model not in available_model_ids:
        if strict:
            raise AppError(
                code="story_engine.route_model_unknown",
                message="你选择的模型不在当前可用列表里，请先刷新策略页。",
                status_code=422,
                metadata={"role_key": role_key, "model": model},
            )
        return _build_env_default_route(role_key)

    return {
        "model": model,
        "reasoning_effort": _normalize_reasoning_effort(
            raw_route.get("reasoning_effort"),
            role_key=role_key,
            strict=strict,
        ),
    }


def _normalize_routing_map(
    raw_routing: Any,
    *,
    available_model_ids: set[str],
    strict: bool,
) -> dict[str, dict[str, str]]:
    payload = raw_routing if isinstance(raw_routing, dict) else {}
    normalized: dict[str, dict[str, str]] = {}
    for role_key in STORY_ENGINE_ROLE_MAP:
        if role_key in payload:
            normalized[role_key] = _normalize_route(
                role_key,
                payload.get(role_key),
                available_model_ids=available_model_ids,
                strict=strict,
            )
        else:
            normalized[role_key] = _build_env_default_route(role_key)
    return normalized


def _normalize_project_settings(
    raw_settings: Any,
    *,
    config: dict[str, Any],
    strict: bool,
) -> dict[str, Any]:
    payload = raw_settings if isinstance(raw_settings, dict) else {}
    preset_map = config["preset_map"]
    default_preset_key = config["default_preset_key"]

    requested_preset_key = str(payload.get("active_preset_key") or "").strip()
    if requested_preset_key not in preset_map:
        if strict and requested_preset_key:
            raise AppError(
                code="story_engine.preset_not_found",
                message="所选组合不存在，请刷新策略页后重试。",
                status_code=422,
                metadata={"active_preset_key": requested_preset_key},
            )
        requested_preset_key = default_preset_key

    base_routing = preset_map[requested_preset_key]["routing"]
    raw_overrides = payload.get("manual_overrides")
    if raw_overrides is None:
        raw_overrides = {}
    if not isinstance(raw_overrides, dict):
        if strict:
            raise AppError(
                code="story_engine.manual_overrides_invalid",
                message="单项微调格式不正确，请刷新后重试。",
                status_code=422,
            )
        raw_overrides = {}

    normalized_overrides: dict[str, dict[str, str]] = {}
    for role_key, raw_route in raw_overrides.items():
        if role_key not in STORY_ENGINE_ROLE_MAP:
            if strict:
                raise AppError(
                    code="story_engine.role_key_invalid",
                    message="存在无法识别的职责项，请刷新策略页后重试。",
                    status_code=422,
                    metadata={"role_key": role_key},
                )
            continue
        normalized_route = _normalize_route(
            role_key,
            raw_route,
            available_model_ids=config["available_model_ids"],
            strict=strict,
        )
        if normalized_route != base_routing[role_key]:
            normalized_overrides[role_key] = normalized_route

    return {
        "active_preset_key": requested_preset_key,
        "manual_overrides": normalized_overrides,
    }


def _build_effective_routing(
    *,
    config: dict[str, Any],
    project_settings: dict[str, Any],
) -> dict[str, dict[str, str]]:
    effective = deepcopy(
        config["preset_map"][project_settings["active_preset_key"]]["routing"]
    )
    for role_key, route in project_settings.get("manual_overrides", {}).items():
        effective[role_key] = deepcopy(route)
    return effective


def _serialize_route(
    role_key: str,
    route: dict[str, str],
    *,
    is_override: bool,
) -> dict[str, Any]:
    role_meta = STORY_ENGINE_ROLE_MAP[role_key]
    return {
        "role_key": role_key,
        "label": role_meta["label"],
        "description": role_meta["description"],
        "model": route["model"],
        "reasoning_effort": route.get("reasoning_effort"),
        "is_override": is_override,
    }


def list_story_engine_model_preset_catalog() -> dict[str, Any]:
    config = _load_profile_config()
    return {
        "default_preset_key": config["default_preset_key"],
        "presets": [
            {
                "key": preset["key"],
                "label": preset["label"],
                "description": preset.get("description"),
            }
            for preset in config["presets"]
        ],
    }


def build_story_engine_model_routing_project_summary(project: Project) -> dict[str, Any]:
    config = _load_profile_config()
    project_settings = _normalize_project_settings(
        getattr(project, "story_engine_settings", None),
        config=config,
        strict=False,
    )
    active_preset_key = project_settings["active_preset_key"]
    preset = config["preset_map"].get(active_preset_key, {})
    manual_overrides = project_settings.get("manual_overrides", {})
    owner_email = getattr(getattr(project, "user", None), "email", None)
    return {
        "project_id": project.id,
        "title": project.title,
        "owner_email": owner_email,
        "genre": project.genre,
        "tone": project.tone,
        "status": project.status,
        "updated_at": project.updated_at,
        "active_preset_key": active_preset_key,
        "active_preset_label": preset.get("label"),
        "manual_override_count": len(manual_overrides),
    }
 

async def list_story_engine_model_routing_projects(
    session: AsyncSession,
    *,
    query: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    statement = (
        select(Project)
        .join(Project.user)
        .options(selectinload(Project.user))
        .order_by(Project.updated_at.desc())
        .limit(limit)
    )

    normalized_query = (query or "").strip()
    if normalized_query:
        like_query = f"%{normalized_query}%"
        statement = statement.where(
            or_(
                Project.title.ilike(like_query),
                Project.genre.ilike(like_query),
                Project.tone.ilike(like_query),
                User.email.ilike(like_query),
            )
        )

    result = await session.execute(statement)
    projects = result.scalars().all()
    return [
        build_story_engine_model_routing_project_summary(project)
        for project in projects
    ]


async def _get_story_engine_model_routing_project_for_admin(
    session: AsyncSession,
    *,
    project_id: UUID,
) -> Project:
    statement = (
        select(Project)
        .where(Project.id == project_id)
        .options(selectinload(Project.user))
    )
    result = await session.execute(statement)
    project = result.scalar_one_or_none()
    if project is None:
        raise AppError(
            code="project.not_found",
            message="项目不存在。",
            status_code=404,
        )
    return project


def get_story_engine_model_preset_label(preset_key: Optional[str]) -> Optional[str]:
    if not preset_key:
        return None
    config = _load_profile_config()
    preset = config["preset_map"].get(str(preset_key))
    if preset is None:
        return None
    return str(preset.get("label") or preset_key)


def build_story_engine_settings_for_preset(
    preset_key: Optional[str] = None,
) -> dict[str, Any]:
    config = _load_profile_config()
    resolved_preset_key = (
        str(preset_key).strip() if preset_key is not None and str(preset_key).strip() else ""
    )
    if resolved_preset_key and resolved_preset_key not in config["preset_map"]:
        raise AppError(
            code="story_engine.preset_not_found",
            message="所选开局组合不存在，请刷新后重试。",
            status_code=422,
            metadata={"preset_key": resolved_preset_key},
        )
    return {
        "active_preset_key": resolved_preset_key or config["default_preset_key"],
        "manual_overrides": {},
    }


def build_story_engine_model_routing_payload(project: Project) -> dict[str, Any]:
    config = _load_profile_config()
    project_settings = _normalize_project_settings(
        getattr(project, "story_engine_settings", None),
        config=config,
        strict=False,
    )
    effective_routing = _build_effective_routing(
        config=config,
        project_settings=project_settings,
    )

    return {
        "project": {
            "project_id": project.id,
            "title": project.title,
            "genre": project.genre,
            "theme": project.theme,
            "tone": project.tone,
        },
        "default_preset_key": config["default_preset_key"],
        "active_preset_key": project_settings["active_preset_key"],
        "available_models": config["available_models"],
        "available_reasoning_efforts": list(VALID_REASONING_EFFORTS),
        "role_catalog": STORY_ENGINE_ROLE_CATALOG,
        "presets": [
            {
                "key": preset["key"],
                "label": preset["label"],
                "description": preset.get("description"),
                "routing": {
                    role_key: _serialize_route(
                        role_key,
                        route,
                        is_override=False,
                    )
                    for role_key, route in preset["routing"].items()
                },
            }
            for preset in config["presets"]
        ],
        "manual_overrides": {
            role_key: _serialize_route(role_key, route, is_override=True)
            for role_key, route in project_settings.get("manual_overrides", {}).items()
        },
        "effective_routing": {
            role_key: _serialize_route(
                role_key,
                route,
                is_override=role_key in project_settings.get("manual_overrides", {}),
            )
            for role_key, route in effective_routing.items()
        },
    }


def resolve_story_engine_model_routing(
    project: Optional[Project] = None,
    *,
    raw_project_settings: Optional[dict[str, Any]] = None,
) -> dict[str, dict[str, str]]:
    config = _load_profile_config()
    project_settings = _normalize_project_settings(
        raw_project_settings
        if raw_project_settings is not None
        else getattr(project, "story_engine_settings", None),
        config=config,
        strict=False,
    )
    return _build_effective_routing(
        config=config,
        project_settings=project_settings,
    )


def get_story_engine_guardian_consensus_config() -> dict[str, Any]:
    config = _load_profile_config()
    return deepcopy(config.get("guardian_consensus") or DEFAULT_GUARDIAN_CONSENSUS_CONFIG)


async def get_story_engine_model_routing(
    session: AsyncSession,
    *,
    project_id: UUID,
    user_id: UUID,
) -> dict[str, Any]:
    from services.story_engine_kb_service import get_story_engine_project

    project = await get_story_engine_project(session, project_id, user_id)
    return build_story_engine_model_routing_payload(project)


async def get_story_engine_model_routing_for_admin(
    session: AsyncSession,
    *,
    project_id: UUID,
) -> dict[str, Any]:
    project = await _get_story_engine_model_routing_project_for_admin(
        session,
        project_id=project_id,
    )
    return build_story_engine_model_routing_payload(project)


async def update_story_engine_model_routing(
    session: AsyncSession,
    *,
    project_id: UUID,
    user_id: UUID,
    active_preset_key: str,
    manual_overrides: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    from services.story_engine_kb_service import get_story_engine_project

    project = await get_story_engine_project(
        session,
        project_id,
        user_id,
        permission=PROJECT_PERMISSION_EDIT,
    )
    config = _load_profile_config()
    normalized_settings = _normalize_project_settings(
        {
            "active_preset_key": active_preset_key,
            "manual_overrides": manual_overrides,
        },
        config=config,
        strict=True,
    )
    project.story_engine_settings = normalized_settings
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return build_story_engine_model_routing_payload(project)


async def update_story_engine_model_routing_for_admin(
    session: AsyncSession,
    *,
    project_id: UUID,
    active_preset_key: str,
    manual_overrides: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    project = await _get_story_engine_model_routing_project_for_admin(
        session,
        project_id=project_id,
    )
    config = _load_profile_config()
    normalized_settings = _normalize_project_settings(
        {
            "active_preset_key": active_preset_key,
            "manual_overrides": manual_overrides,
        },
        config=config,
        strict=True,
    )
    project.story_engine_settings = normalized_settings
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return build_story_engine_model_routing_payload(project)
