from __future__ import annotations

import json
import math
import re
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agents.model_gateway import GenerationRequest, model_gateway
from core.errors import AppError
from memory.story_bible import load_story_bible_context
from models.chapter import Chapter
from models.chapter_version import ChapterVersion
from models.project import Project
from models.project_branch import ProjectBranch
from models.project_volume import ProjectVolume
from schemas.project import (
    CharacterItem,
    ForeshadowingItem,
    PlotThreadItem,
    ProjectBootstrapProfileRead,
    ProjectBootstrapProfileUpdate,
    ProjectBootstrapRead,
    ProjectBootstrapStoryStateSummaryRead,
    ProjectNovelBlueprintRead,
    StoryBibleUpdate,
    TimelineEventItem,
    WorldSettingItem,
)
from services.project_service import (
    DEFAULT_VOLUME_TITLE,
    build_project_structure_payload,
    get_owned_project,
    replace_story_bible,
)
from services.project_generation_service import preview_next_project_chapter_candidate


_JSON_FENCE_PATTERN = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


async def get_project_bootstrap_state(
    session: AsyncSession,
    project: Project,
    *,
    actor_user_id: UUID,
    branch_id: UUID | None = None,
) -> ProjectBootstrapRead:
    structure = build_project_structure_payload(project)
    resolved_branch = _resolve_target_branch(project, structure, branch_id)
    profile = _normalize_bootstrap_profile(project)
    blueprint = _normalize_blueprint(project)

    story_state = ProjectBootstrapStoryStateSummaryRead(
        branch_id=resolved_branch.id if resolved_branch is not None else None,
        branch_title=resolved_branch.title if resolved_branch is not None else None,
        branch_key=resolved_branch.key if resolved_branch is not None else None,
        chapter_blueprint_count=len(blueprint.chapter_blueprints) if blueprint is not None else 0,
        created_chapter_count=sum(
            1
            for chapter in project.chapters
            if resolved_branch is None or chapter.branch_id == resolved_branch.id
        ),
    )

    if resolved_branch is not None:
        story_bible = await load_story_bible_context(
            session,
            project.id,
            actor_user_id,
            branch_id=resolved_branch.id,
        )
        story_state.character_count = len(story_bible.characters)
        story_state.plot_thread_count = len(story_bible.plot_threads)
        story_state.foreshadowing_count = len(story_bible.foreshadowing)
        story_state.timeline_count = len(story_bible.timeline_events)

    return ProjectBootstrapRead(
        project=structure.project,
        profile=profile,
        blueprint=blueprint,
        story_state=story_state,
        next_chapter=preview_next_project_chapter_candidate(
            project,
            branch_id=resolved_branch.id if resolved_branch is not None else None,
        ),
    )


async def update_project_bootstrap_profile(
    session: AsyncSession,
    project: Project,
    payload: ProjectBootstrapProfileUpdate,
) -> Project:
    profile = _normalize_bootstrap_profile(project).model_dump(mode="json")
    updates = payload.model_dump(exclude_unset=True, mode="json")
    if updates.get("supporting_cast") is None and "supporting_cast" in updates:
        updates["supporting_cast"] = []
    profile.update(updates)

    project.bootstrap_profile = profile
    if "genre" in updates:
        project.genre = updates.get("genre")
    if "theme" in updates:
        project.theme = updates.get("theme")
    if "tone" in updates:
        project.tone = updates.get("tone")

    await session.commit()
    await session.refresh(project)
    return project


async def generate_project_blueprint(
    session: AsyncSession,
    project: Project,
    *,
    actor_user_id: UUID,
    branch_id: UUID | None = None,
    create_missing_chapters: bool = True,
) -> ProjectBootstrapRead:
    profile = _normalize_bootstrap_profile(project)
    _validate_profile_for_generation(profile)

    structure = build_project_structure_payload(project)
    resolved_branch = _resolve_target_branch(project, structure, branch_id)
    if resolved_branch is None:
        raise AppError(
            code="project.branch_not_found",
            message="Project branch not found.",
            status_code=404,
        )

    story_bible = await load_story_bible_context(
        session,
        project.id,
        actor_user_id,
        branch_id=resolved_branch.id,
    )
    blueprint = await _generate_novel_blueprint(
        project=project,
        profile=profile,
        story_bible=story_bible,
    )
    blueprint.generated_at = datetime.now(timezone.utc)

    project.bootstrap_profile = profile.model_dump(mode="json")
    project.novel_blueprint = blueprint.model_dump(mode="json")
    project.genre = profile.genre or project.genre
    project.theme = profile.theme or project.theme
    project.tone = profile.tone or project.tone

    await _sync_project_volumes(session, project, blueprint)
    await session.flush()

    await _sync_story_bible_from_blueprint(
        session,
        project=project,
        actor_user_id=actor_user_id,
        branch_id=resolved_branch.id,
        story_bible=story_bible,
        profile=profile,
        blueprint=blueprint,
    )

    refreshed = await get_owned_project(
        session,
        project.id,
        actor_user_id,
        with_relations=True,
    )

    if create_missing_chapters:
        await _create_blueprint_chapters(
            session,
            project=refreshed,
            branch_id=resolved_branch.id,
            blueprint=blueprint,
        )
        refreshed = await get_owned_project(
            session,
            project.id,
            actor_user_id,
            with_relations=True,
        )

    return await get_project_bootstrap_state(
        session,
        refreshed,
        actor_user_id=actor_user_id,
        branch_id=resolved_branch.id,
    )


def _normalize_bootstrap_profile(project: Project) -> ProjectBootstrapProfileRead:
    raw = project.bootstrap_profile if isinstance(project.bootstrap_profile, dict) else {}
    payload = {
        "genre": raw.get("genre", project.genre),
        "theme": raw.get("theme", project.theme),
        "tone": raw.get("tone", project.tone),
        "protagonist_name": raw.get("protagonist_name"),
        "protagonist_summary": raw.get("protagonist_summary"),
        "supporting_cast": raw.get("supporting_cast") or [],
        "world_background": raw.get("world_background"),
        "core_story": raw.get("core_story"),
        "novel_style": raw.get("novel_style"),
        "prose_style": raw.get("prose_style"),
        "target_total_words": raw.get("target_total_words"),
        "target_chapter_words": raw.get("target_chapter_words"),
        "planned_chapter_count": raw.get("planned_chapter_count"),
        "special_requirements": raw.get("special_requirements"),
    }
    return ProjectBootstrapProfileRead.model_validate(payload)


def _normalize_blueprint(project: Project) -> ProjectNovelBlueprintRead | None:
    raw = project.novel_blueprint if isinstance(project.novel_blueprint, dict) else None
    if raw is None:
        return None
    try:
        return ProjectNovelBlueprintRead.model_validate(raw)
    except ValidationError:
        return None


def _validate_profile_for_generation(profile: ProjectBootstrapProfileRead) -> None:
    missing_fields: list[str] = []
    if not (profile.protagonist_name or "").strip():
        missing_fields.append("主角")
    if not (profile.world_background or "").strip():
        missing_fields.append("世界背景")
    if not (profile.core_story or "").strip():
        missing_fields.append("核心故事")
    if missing_fields:
        raise AppError(
            code="project.bootstrap_profile_incomplete",
            message=f"Project bootstrap profile is incomplete: {', '.join(missing_fields)}.",
            status_code=400,
        )


async def _generate_novel_blueprint(
    *,
    project: Project,
    profile: ProjectBootstrapProfileRead,
    story_bible,
) -> ProjectNovelBlueprintRead:
    fallback_blueprint = _build_fallback_blueprint(project, profile)
    fallback_json = json.dumps(
        fallback_blueprint.model_dump(mode="json"),
        ensure_ascii=False,
        indent=2,
    )
    result = await model_gateway.generate_text(
        GenerationRequest(
            task_name="project.bootstrap.blueprint",
            system_prompt=_build_blueprint_system_prompt(),
            prompt=_build_blueprint_prompt(project, profile, story_bible),
            temperature=0.7,
            max_tokens=2800,
            metadata={"agent": "bootstrap_planner"},
        ),
        fallback=lambda: fallback_json,
    )

    parsed = _parse_blueprint_payload(result.content)
    if parsed is None:
        return fallback_blueprint

    try:
        return ProjectNovelBlueprintRead.model_validate(parsed)
    except ValidationError:
        return fallback_blueprint


def _build_blueprint_system_prompt() -> str:
    return (
        "你是长篇网文项目启动规划师。"
        "请输出结构化 JSON，帮助系统生成可持续推进的小说蓝图。"
        "不要输出解释，不要输出 markdown，只输出 JSON 对象。"
    )


def _build_blueprint_prompt(
    project: Project,
    profile: ProjectBootstrapProfileRead,
    story_bible,
) -> str:
    supporting_cast_text = "\n".join(
        f"- {item.name} / {item.role}: {item.summary or '待补充'}"
        for item in profile.supporting_cast[:8]
    ) or "- 暂无"
    existing_character_text = "\n".join(
        f"- {item.get('name')}"
        for item in story_bible.characters[:8]
        if isinstance(item, dict) and item.get("name")
    ) or "- 暂无"
    existing_plot_text = "\n".join(
        f"- {item.get('title')}"
        for item in story_bible.plot_threads[:6]
        if isinstance(item, dict) and item.get("title")
    ) or "- 暂无"

    target_total_words = profile.target_total_words or 0
    target_chapter_words = profile.target_chapter_words or 0
    planned_chapter_count = profile.planned_chapter_count or _derive_chapter_goal(profile)
    concrete_chapter_count = min(planned_chapter_count, 12)

    return f"""
项目标题：{project.title}
题材：{profile.genre or project.genre or '未指定'}
主题：{profile.theme or project.theme or '未指定'}
基调：{profile.tone or project.tone or '未指定'}

主角：
- {profile.protagonist_name}
- 简介：{profile.protagonist_summary or '待补充'}

关键配角：
{supporting_cast_text}

世界背景：
{profile.world_background or '待补充'}

核心故事：
{profile.core_story or '待补充'}

小说风格：
{profile.novel_style or '未指定'}

行文风格：
{profile.prose_style or '未指定'}

字数目标：
- 总字数：{target_total_words or '未指定'}
- 单章字数：{target_chapter_words or '未指定'}
- 计划章节数：{planned_chapter_count}
- 当前先细化前 {concrete_chapter_count} 章

特殊要求：
{profile.special_requirements or '无'}

当前 Story Bible 角色：
{existing_character_text}

当前 Story Bible 剧情线：
{existing_plot_text}

请输出 JSON，字段如下：
{{
  "premise": "一句话概括故事命题",
  "story_engine": "故事持续推进的核心动力",
  "opening_hook": "开篇抓手",
  "writing_rules": ["规则1", "规则2", "规则3"],
  "cast": [
    {{
      "name": "角色名",
      "role": "protagonist/supporting/antagonist/mentor/deuteragonist",
      "summary": "角色定位",
      "motivation": "主要动机",
      "conflict": "核心冲突"
    }}
  ],
  "plot_threads": [
    {{
      "title": "剧情线标题",
      "summary": "剧情线概述",
      "scope": "main/sub/character/mystery",
      "focus_characters": ["角色A"],
      "planned_turns": ["转折1", "转折2", "转折3"]
    }}
  ],
  "foreshadowing": [
    {{
      "content": "伏笔内容",
      "planted_chapter": 1,
      "payoff_chapter": 6,
      "status": "pending"
    }}
  ],
  "timeline_beats": [
    {{
      "chapter_number": 1,
      "title": "时间线节点",
      "summary": "节点意义"
    }}
  ],
  "volume_plans": [
    {{
      "volume_number": 1,
      "title": "卷标题",
      "summary": "卷概述",
      "narrative_goal": "这一卷要完成什么",
      "planned_chapter_count": 6
    }}
  ],
  "chapter_blueprints": [
    {{
      "volume_number": 1,
      "chapter_number": 1,
      "title": "章节标题",
      "objective": "本章目标",
      "summary": "本章摘要",
      "expected_word_count": {target_chapter_words or 2500},
      "focus_characters": ["角色A"],
      "key_locations": ["地点A"],
      "plot_thread_titles": ["剧情线A"],
      "foreshadowing_to_plant": ["伏笔A"]
    }}
  ]
}}
""".strip()


def _parse_blueprint_payload(raw: str) -> dict[str, Any] | None:
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


def _build_fallback_blueprint(
    project: Project,
    profile: ProjectBootstrapProfileRead,
) -> ProjectNovelBlueprintRead:
    chapter_goal = _derive_chapter_goal(profile)
    chapter_word_count = profile.target_chapter_words or 2500
    concrete_chapters = min(chapter_goal, 12)
    volume_count = max(1, min(3, math.ceil(chapter_goal / 6)))
    per_volume = max(1, math.ceil(chapter_goal / volume_count))

    cast = [
        {
            "name": profile.protagonist_name or "主角",
            "role": "protagonist",
            "summary": profile.protagonist_summary or "被卷入更大风暴的核心角色。",
            "motivation": "守住仅剩的归属，同时查清真相。",
            "conflict": "越接近真相，越要付出无法轻易承受的代价。",
        }
    ]
    for item in profile.supporting_cast[:4]:
        cast.append(
            {
                "name": item.name,
                "role": item.role or "supporting",
                "summary": item.summary or "与主角紧密相关的关键配角。",
                "motivation": item.motivation or "围绕主角的目标行动。",
                "conflict": item.conflict or "与主角立场并不完全一致。",
            }
        )

    volume_plans = []
    chapter_blueprints = []
    for volume_number in range(1, volume_count + 1):
        chapter_count = min(per_volume, max(chapter_goal - ((volume_number - 1) * per_volume), 1))
        volume_plans.append(
            {
                "volume_number": volume_number,
                "title": f"第{volume_number}卷：{_volume_label(volume_number, profile)}",
                "summary": f"围绕「{profile.core_story or project.title}」推进第 {volume_number} 阶段冲突。",
                "narrative_goal": _volume_goal(volume_number, volume_count),
                "planned_chapter_count": chapter_count,
            }
        )

    focus_names = [cast[0]["name"], *(item["name"] for item in cast[1:3])]
    focus_names = [name for name in focus_names if name]
    for chapter_number in range(1, concrete_chapters + 1):
        volume_number = min(volume_count, math.ceil(chapter_number / max(per_volume, 1)))
        chapter_blueprints.append(
            {
                "volume_number": volume_number,
                "chapter_number": chapter_number,
                "title": f"第{chapter_number}章：{_chapter_label(chapter_number)}",
                "objective": _chapter_objective(chapter_number, concrete_chapters, profile),
                "summary": _chapter_summary(chapter_number, profile),
                "expected_word_count": chapter_word_count,
                "focus_characters": focus_names[:2] or [profile.protagonist_name or "主角"],
                "key_locations": ["主场景"],
                "plot_thread_titles": ["主线推进", "人物关系变化"][: 1 + (1 if chapter_number > 2 else 0)],
                "foreshadowing_to_plant": (
                    [f"第{chapter_number}章埋下的隐性代价"]
                    if chapter_number in {1, 3, 5}
                    else []
                ),
            }
        )

    return ProjectNovelBlueprintRead.model_validate(
        {
            "premise": f"{profile.protagonist_name or '主角'}被卷入「{profile.core_story or project.title}」引发的持续风暴。",
            "story_engine": "每一次推进主线都会同步改写人物关系、代价结构与世界真相。",
            "opening_hook": "以一次打破日常秩序的突发事件，把主角强行推入主线。",
            "writing_rules": [
                "每章都要推进事件，而不是只补说明。",
                "人物选择必须带来代价与后果。",
                "伏笔和回收要跟着章节推进持续更新。",
            ],
            "cast": cast,
            "plot_threads": [
                {
                    "title": "主线推进",
                    "summary": profile.core_story or "围绕核心故事持续升级。",
                    "scope": "main",
                    "focus_characters": [profile.protagonist_name or "主角"],
                    "planned_turns": ["引发事件", "代价升级", "逼近真相"],
                },
                {
                    "title": "人物关系变化",
                    "summary": "关键角色在共同目标与相互猜疑之间不断重排。",
                    "scope": "character",
                    "focus_characters": focus_names[:3],
                    "planned_turns": ["建立互信", "误判裂痕", "重新站队"],
                },
            ],
            "foreshadowing": [
                {
                    "content": "主角掌握的线索本身就是更大骗局的一部分。",
                    "planted_chapter": 1,
                    "payoff_chapter": min(concrete_chapters, 6),
                    "status": "pending",
                }
            ],
            "timeline_beats": [
                {
                    "chapter_number": 1,
                    "title": "起点被打破",
                    "summary": "主角原本可维持的秩序正式失效。",
                },
                {
                    "chapter_number": min(concrete_chapters, 4),
                    "title": "首次付出重大代价",
                    "summary": "主角意识到主线并非一次性事件，而是长期困局。",
                },
            ],
            "volume_plans": volume_plans,
            "chapter_blueprints": chapter_blueprints,
        }
    )


async def _sync_project_volumes(
    session: AsyncSession,
    project: Project,
    blueprint: ProjectNovelBlueprintRead,
) -> None:
    if not blueprint.volume_plans:
        return

    existing_by_number = {volume.volume_number: volume for volume in project.volumes}
    for plan in blueprint.volume_plans:
        volume = existing_by_number.get(plan.volume_number)
        if volume is None:
            volume = ProjectVolume(
                id=uuid4(),
                project_id=project.id,
                volume_number=plan.volume_number,
                title=plan.title,
                summary=plan.summary,
                status="planning",
            )
            session.add(volume)
            project.volumes.append(volume)
            existing_by_number[plan.volume_number] = volume
            continue

        chapter_count = sum(1 for chapter in project.chapters if chapter.volume_id == volume.id)
        if chapter_count == 0 and (volume.title == DEFAULT_VOLUME_TITLE or volume.volume_number > 1):
            volume.title = plan.title
        if not volume.summary:
            volume.summary = plan.summary


async def _sync_story_bible_from_blueprint(
    session: AsyncSession,
    *,
    project: Project,
    actor_user_id: UUID,
    branch_id: UUID,
    story_bible,
    profile: ProjectBootstrapProfileRead,
    blueprint: ProjectNovelBlueprintRead,
) -> None:
    characters = [
        CharacterItem.model_validate(item)
        for item in story_bible.characters
        if isinstance(item, dict)
    ]
    world_settings = [
        WorldSettingItem.model_validate(item)
        for item in story_bible.world_settings
        if isinstance(item, dict)
    ]
    plot_threads = [
        PlotThreadItem.model_validate(item)
        for item in story_bible.plot_threads
        if isinstance(item, dict)
    ]
    foreshadowing = [
        ForeshadowingItem.model_validate(item)
        for item in story_bible.foreshadowing
        if isinstance(item, dict)
    ]
    timeline_events = [
        TimelineEventItem.model_validate(item)
        for item in story_bible.timeline_events
        if isinstance(item, dict)
    ]

    characters = _merge_story_bible_characters(characters, profile, blueprint)
    world_settings = _merge_world_settings(world_settings, profile, blueprint)
    plot_threads = _merge_plot_threads(plot_threads, blueprint)
    foreshadowing = _merge_foreshadowing(foreshadowing, blueprint)
    timeline_events = _merge_timeline_events(timeline_events, blueprint)

    await replace_story_bible(
        session,
        project,
        StoryBibleUpdate(
            characters=characters,
            world_settings=world_settings,
            items=[
                item
                for item in story_bible.items
                if isinstance(item, dict)
            ],
            factions=[
                item
                for item in story_bible.factions
                if isinstance(item, dict)
            ],
            locations=[
                item
                for item in story_bible.locations
                if isinstance(item, dict)
            ],
            plot_threads=plot_threads,
            foreshadowing=foreshadowing,
            timeline_events=timeline_events,
        ),
        actor_user_id=actor_user_id,
        branch_id=branch_id,
    )


def _merge_story_bible_characters(
    existing: list[CharacterItem],
    profile: ProjectBootstrapProfileRead,
    blueprint: ProjectNovelBlueprintRead,
) -> list[CharacterItem]:
    merged = {item.name.strip().lower(): item for item in existing if item.name.strip()}

    protagonist_data = {
        "role": "protagonist",
        "summary": profile.protagonist_summary,
        "motivation": "推动主线并守住核心关系。",
        "conflict": "越接近真相越要承受更大代价。",
    }
    protagonist = CharacterItem(
        name=profile.protagonist_name or "主角",
        data={key: value for key, value in protagonist_data.items() if value},
        version=1,
        created_chapter=1,
    )
    merged.setdefault(protagonist.name.strip().lower(), protagonist)

    for item in profile.supporting_cast:
        candidate = CharacterItem(
            name=item.name,
            data={
                key: value
                for key, value in {
                    "role": item.role,
                    "summary": item.summary,
                    "motivation": item.motivation,
                    "conflict": item.conflict,
                }.items()
                if value
            },
            version=1,
            created_chapter=1,
        )
        merged.setdefault(candidate.name.strip().lower(), candidate)

    for item in blueprint.cast:
        candidate = CharacterItem(
            name=item.name,
            data={
                key: value
                for key, value in {
                    "role": item.role,
                    "summary": item.summary,
                    "motivation": item.motivation,
                    "conflict": item.conflict,
                }.items()
                if value
            },
            version=1,
            created_chapter=1,
        )
        merged.setdefault(candidate.name.strip().lower(), candidate)

    return list(merged.values())


def _merge_world_settings(
    existing: list[WorldSettingItem],
    profile: ProjectBootstrapProfileRead,
    blueprint: ProjectNovelBlueprintRead,
) -> list[WorldSettingItem]:
    merged = {item.key.strip().lower(): item for item in existing if item.key.strip()}

    overview = WorldSettingItem(
        key="bootstrap-world-overview",
        title="项目世界背景",
        data={
            "summary": profile.world_background,
            "core_story": profile.core_story,
            "genre": profile.genre,
            "theme": profile.theme,
            "tone": profile.tone,
        },
        version=1,
    )
    merged[overview.key] = overview

    engine = WorldSettingItem(
        key="bootstrap-story-engine",
        title="故事推进引擎",
        data={
            "premise": blueprint.premise,
            "story_engine": blueprint.story_engine,
            "opening_hook": blueprint.opening_hook,
            "writing_rules": blueprint.writing_rules,
            "novel_style": profile.novel_style,
            "prose_style": profile.prose_style,
            "target_total_words": profile.target_total_words,
            "target_chapter_words": profile.target_chapter_words,
            "special_requirements": profile.special_requirements,
        },
        version=1,
    )
    merged[engine.key] = engine
    return list(merged.values())


def _merge_plot_threads(
    existing: list[PlotThreadItem],
    blueprint: ProjectNovelBlueprintRead,
) -> list[PlotThreadItem]:
    merged = {item.title.strip().lower(): item for item in existing if item.title.strip()}
    for item in blueprint.plot_threads:
        candidate = PlotThreadItem(
            title=item.title,
            status="planned",
            importance=2 if item.scope == "main" else 1,
            data={
                "summary": item.summary,
                "scope": item.scope,
                "main_characters": item.focus_characters,
                "stages": item.planned_turns,
            },
        )
        merged.setdefault(candidate.title.strip().lower(), candidate)
    return list(merged.values())


def _merge_foreshadowing(
    existing: list[ForeshadowingItem],
    blueprint: ProjectNovelBlueprintRead,
) -> list[ForeshadowingItem]:
    merged = {item.content.strip().lower(): item for item in existing if item.content.strip()}
    for item in blueprint.foreshadowing:
        candidate = ForeshadowingItem(
            content=item.content,
            planted_chapter=item.planted_chapter,
            payoff_chapter=item.payoff_chapter,
            status=item.status,
            importance=1,
        )
        merged.setdefault(candidate.content.strip().lower(), candidate)
    return list(merged.values())


def _merge_timeline_events(
    existing: list[TimelineEventItem],
    blueprint: ProjectNovelBlueprintRead,
) -> list[TimelineEventItem]:
    merged = {item.title.strip().lower(): item for item in existing if item.title.strip()}
    for item in blueprint.timeline_beats:
        candidate = TimelineEventItem(
            chapter_number=item.chapter_number,
            title=item.title,
            data={"summary": item.summary},
        )
        merged.setdefault(candidate.title.strip().lower(), candidate)
    return list(merged.values())


async def _create_blueprint_chapters(
    session: AsyncSession,
    *,
    project: Project,
    branch_id: UUID,
    blueprint: ProjectNovelBlueprintRead,
) -> None:
    if not blueprint.chapter_blueprints:
        return

    volumes_by_number = {volume.volume_number: volume for volume in project.volumes}
    existing_result = await session.execute(
        select(Chapter.volume_id, Chapter.chapter_number).where(
            Chapter.project_id == project.id,
            Chapter.branch_id == branch_id,
        )
    )
    existing_keys = {(volume_id, chapter_number) for volume_id, chapter_number in existing_result.all()}

    changed = False
    for chapter_blueprint in blueprint.chapter_blueprints:
        volume = volumes_by_number.get(chapter_blueprint.volume_number)
        if volume is None:
            continue

        chapter_key = (volume.id, chapter_blueprint.chapter_number)
        if chapter_key in existing_keys:
            continue

        chapter = Chapter(
            project_id=project.id,
            volume_id=volume.id,
            branch_id=branch_id,
            chapter_number=chapter_blueprint.chapter_number,
            title=chapter_blueprint.title,
            content="",
            outline=chapter_blueprint.model_dump(mode="json"),
            status="draft",
            word_count=0,
            current_version_number=1,
        )
        session.add(chapter)
        await session.flush()
        session.add(
            ChapterVersion(
                chapter_id=chapter.id,
                version_number=1,
                content="",
                change_reason="Created from project blueprint",
            )
        )
        existing_keys.add(chapter_key)
        changed = True

    if changed:
        await session.commit()


def _resolve_target_branch(
    project: Project,
    structure,
    branch_id: UUID | None,
) -> ProjectBranch | None:
    resolved_branch_id = branch_id or structure.default_branch_id
    if resolved_branch_id is None:
        return None
    return next((branch for branch in project.branches if branch.id == resolved_branch_id), None)


def _derive_chapter_goal(profile: ProjectBootstrapProfileRead) -> int:
    if profile.planned_chapter_count:
        return profile.planned_chapter_count
    if profile.target_total_words and profile.target_chapter_words:
        return max(1, math.ceil(profile.target_total_words / profile.target_chapter_words))
    return 8


def _volume_label(volume_number: int, profile: ProjectBootstrapProfileRead) -> str:
    if volume_number == 1:
        return "风暴初启"
    if volume_number == 2:
        return "真相逼近"
    if volume_number == 3:
        return "代价回收"
    return f"{profile.core_story or '主线'}阶段{volume_number}"


def _volume_goal(volume_number: int, volume_count: int) -> str:
    if volume_number == 1:
        return "建立主线牵引并打破角色原本秩序。"
    if volume_number == volume_count:
        return "集中回收关键伏笔，推动主线进入大转折。"
    return "放大冲突与代价，让人物关系和局势同步升级。"


def _chapter_label(chapter_number: int) -> str:
    labels = {
        1: "失衡",
        2: "逼近",
        3: "错判",
        4: "裂痕",
        5: "追索",
        6: "回响",
        7: "暗涌",
        8: "转折",
        9: "失控",
        10: "逼城",
        11: "反咬",
        12: "揭幕",
    }
    return labels.get(chapter_number, f"推进{chapter_number}")


def _chapter_objective(
    chapter_number: int,
    concrete_chapters: int,
    profile: ProjectBootstrapProfileRead,
) -> str:
    if chapter_number == 1:
        return "用一次突发事件打破主角日常，并把核心冲突正式推到台前。"
    if chapter_number == concrete_chapters:
        return "让阶段性真相露出轮廓，同时把更大后果压到下一阶段。"
    return f"继续推进「{profile.core_story or '主线'}」，并让人物代价升级。"


def _chapter_summary(chapter_number: int, profile: ProjectBootstrapProfileRead) -> str:
    protagonist = profile.protagonist_name or "主角"
    if chapter_number == 1:
        return f"{protagonist}在原有秩序被打破后，被迫与主线发生正面接触。"
    if chapter_number == 2:
        return f"{protagonist}试图理解局势，却因此卷入更深层的误判和冲突。"
    return f"{protagonist}在持续追索中付出更高代价，局势也不断失稳。"
