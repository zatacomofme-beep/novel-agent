from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any
from typing import Optional
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.errors import AppError
from models.chapter import Chapter
from models.chapter_version import ChapterVersion
from models.project import Project
from models.project_branch import ProjectBranch
from models.project_volume import ProjectVolume
from models.story_bible_version import StoryBiblePendingChange, StoryBiblePendingChangeStatus
from schemas.chapter import ChapterRead
from schemas.project import (
    ProjectBootstrapProfileRead,
    ProjectChapterBlueprint,
    ProjectChapterGenerationDispatchRead,
    ProjectNextChapterCandidateRead,
    ProjectNovelBlueprintRead,
)
from services.chapter_service import get_owned_chapter
from services.project_service import (
    PROJECT_PERMISSION_EDIT,
    _story_bible_identity_key,
    build_project_structure_payload,
)
from services.story_bible_version_service import auto_trigger_story_bible_change
from services.story_bible_version_service import TRIGGER_TYPE_TO_SECTION


NEXT_CHAPTER_MODE_EXISTING_DRAFT = "existing_draft"
NEXT_CHAPTER_MODE_BLUEPRINT_SEED = "blueprint_seed"
NEXT_CHAPTER_MODE_DYNAMIC_CONTINUATION = "dynamic_continuation"


@dataclass
class _ResolvedNextChapterCandidate:
    chapter: Chapter | None
    chapter_number: int
    title: str | None
    branch: ProjectBranch
    volume: ProjectVolume | None
    generation_mode: str
    based_on_blueprint: bool
    outline_seed: dict[str, Any] | None

    def to_read(
        self,
        *,
        chapter_override: Chapter | None = None,
    ) -> ProjectNextChapterCandidateRead:
        chapter = chapter_override or self.chapter
        content = getattr(chapter, "content", "") if chapter is not None else ""
        return ProjectNextChapterCandidateRead(
            chapter_id=getattr(chapter, "id", None),
            chapter_number=self.chapter_number,
            title=getattr(chapter, "title", None) or self.title,
            branch_id=self.branch.id,
            branch_title=self.branch.title,
            volume_id=self.volume.id if self.volume is not None else getattr(chapter, "volume_id", None),
            volume_title=self.volume.title if self.volume is not None else None,
            generation_mode=self.generation_mode,
            based_on_blueprint=self.based_on_blueprint,
            has_existing_content=bool(str(content or "").strip()),
        )


def preview_next_project_chapter_candidate(
    project: Project,
    *,
    branch_id: UUID | None = None,
) -> ProjectNextChapterCandidateRead | None:
    candidate = _resolve_next_project_chapter_candidate(project, branch_id=branch_id)
    if candidate is None:
        return None
    return candidate.to_read()


async def dispatch_next_project_chapter_generation(
    session: AsyncSession,
    project: Project,
    *,
    actor_user_id: UUID,
    branch_id: UUID | None = None,
) -> ProjectChapterGenerationDispatchRead:
    candidate = _resolve_next_project_chapter_candidate(project, branch_id=branch_id)
    if candidate is None:
        raise AppError(
            code="project.next_chapter_unavailable",
            message="Project next chapter is unavailable. Generate a novel blueprint first.",
            status_code=400,
        )

    chapter = await _materialize_candidate_chapter(session, project, candidate)
    chapter = await get_owned_chapter(
        session,
        chapter.id,
        actor_user_id,
        permission=PROJECT_PERMISSION_EDIT,
    )
    # 这里延迟导入，避免 generation_service 和 project_generation_service 在模块加载期互相引用。
    from services.generation_service import build_generation_payload
    from tasks.chapter_generation import dispatch_generation_task, enqueue_chapter_generation_task

    payload = await build_generation_payload(session, chapter.id, actor_user_id)
    task_state = await enqueue_chapter_generation_task(
        str(chapter.id),
        str(actor_user_id),
        str(project.id),
        payload,
    )
    task_state = await dispatch_generation_task(
        task_id=task_state.task_id,
        chapter_id=str(chapter.id),
        project_id=str(project.id),
        user_id=str(actor_user_id),
    )

    return ProjectChapterGenerationDispatchRead(
        chapter=ChapterRead.model_validate(chapter),
        next_chapter=candidate.to_read(chapter_override=chapter),
        task_id=task_state.task_id,
        task_status=task_state.status,
        task=task_state,
    )


async def propose_story_bible_updates_from_generation(
    session: AsyncSession,
    *,
    project: Project,
    chapter: Chapter,
    story_bible,
    chapter_outline_seed: dict[str, Any] | None,
    final_outline: dict[str, Any] | None,
    agent_name: str = "project_generation",
) -> list[dict[str, Any]]:
    if chapter.branch_id is None:
        return []

    seed = chapter_outline_seed if isinstance(chapter_outline_seed, dict) else {}
    final_plan = final_outline if isinstance(final_outline, dict) else {}
    chapter_number = int(getattr(chapter, "chapter_number", 0) or 0)
    if chapter_number <= 0:
        return []

    objective = str(final_plan.get("objective") or seed.get("objective") or "").strip()
    summary = str(seed.get("summary") or final_plan.get("middle") or "").strip()
    proposals: list[dict[str, Any]] = []

    focus_characters = _extract_named_list(seed.get("focus_characters"))
    for name in focus_characters[:3]:
        existing = _find_story_bible_row(getattr(story_bible, "characters", []), "name", name)
        if existing is None:
            continue
        new_value = deepcopy(existing)
        data = new_value.setdefault("data", {})
        if isinstance(data, dict):
            data["last_active_chapter"] = chapter_number
            if objective:
                data["latest_objective"] = objective
        changed = await _upsert_auto_story_bible_change(
            session,
            project=project,
            branch_id=chapter.branch_id,
            chapter_id=chapter.id,
            trigger_type="character_level_up",
            new_item=new_value,
            old_item=existing,
            reason=f"Character activity synced from chapter {chapter_number}.",
            agent_name=agent_name,
        )
        if changed is not None:
            proposals.append(changed)

    key_locations = _extract_named_list(seed.get("key_locations"))
    for location_name in key_locations[:3]:
        existing = _find_story_bible_row(getattr(story_bible, "locations", []), "name", location_name)
        if existing is None:
            continue
        new_value = deepcopy(existing)
        data = new_value.setdefault("data", {})
        if isinstance(data, dict):
            data["last_visited_chapter"] = chapter_number
            if objective:
                data["latest_objective"] = objective
        changed = await _upsert_auto_story_bible_change(
            session,
            project=project,
            branch_id=chapter.branch_id,
            chapter_id=chapter.id,
            trigger_type="location_status_changed",
            new_item=new_value,
            old_item=existing,
            reason=f"Location activity synced from chapter {chapter_number}.",
            agent_name=agent_name,
        )
        if changed is not None:
            proposals.append(changed)

    plot_threads = _extract_named_list(seed.get("plot_thread_titles"))
    for title in plot_threads[:3]:
        existing = _find_story_bible_row(getattr(story_bible, "plot_threads", []), "title", title)
        new_value = deepcopy(existing) if existing is not None else {
            "title": title,
            "status": "active",
            "importance": 1,
            "data": {},
        }
        new_value["status"] = "active"
        data = new_value.setdefault("data", {})
        if isinstance(data, dict):
            data["last_progress_chapter"] = chapter_number
            if objective:
                data["latest_objective"] = objective
            if summary:
                data["latest_summary"] = summary
        changed = await _upsert_auto_story_bible_change(
            session,
            project=project,
            branch_id=chapter.branch_id,
            chapter_id=chapter.id,
            trigger_type="plot_thread_progressed",
            new_item=new_value,
            old_item=existing,
            reason=f"Plot thread progressed in chapter {chapter_number}.",
            agent_name=agent_name,
        )
        if changed is not None:
            proposals.append(changed)

    foreshadowing_items = _extract_named_list(seed.get("foreshadowing_to_plant"))
    for content in foreshadowing_items[:3]:
        existing = _find_story_bible_row(
            getattr(story_bible, "foreshadowing", []),
            "content",
            content,
        )
        new_value = deepcopy(existing) if existing is not None else {
            "content": content,
            "status": "pending",
            "importance": 1,
        }
        if not new_value.get("planted_chapter"):
            new_value["planted_chapter"] = chapter_number
        new_value["status"] = new_value.get("status") or "pending"
        changed = await _upsert_auto_story_bible_change(
            session,
            project=project,
            branch_id=chapter.branch_id,
            chapter_id=chapter.id,
            trigger_type="foreshadowing_fulfilled",
            new_item=new_value,
            old_item=existing,
            reason=f"Foreshadowing planted in chapter {chapter_number}.",
            agent_name=agent_name,
        )
        if changed is not None:
            proposals.append(changed)

    timeline_title = str(seed.get("title") or final_plan.get("title") or "").strip()
    if timeline_title:
        existing = _find_timeline_event(
            getattr(story_bible, "timeline_events", []),
            chapter_number=chapter_number,
            title=timeline_title,
        )
        new_value = deepcopy(existing) if existing is not None else {
            "chapter_number": chapter_number,
            "title": timeline_title,
            "data": {},
        }
        new_value["chapter_number"] = chapter_number
        data = new_value.setdefault("data", {})
        if isinstance(data, dict):
            if summary:
                data["summary"] = summary
            if objective:
                data["objective"] = objective
        changed = await _upsert_auto_story_bible_change(
            session,
            project=project,
            branch_id=chapter.branch_id,
            chapter_id=chapter.id,
            trigger_type="timeline_event_occurred",
            new_item=new_value,
            old_item=existing,
            reason=f"Timeline event captured for chapter {chapter_number}.",
            agent_name=agent_name,
        )
        if changed is not None:
            proposals.append(changed)

    if proposals:
        await session.commit()
    return proposals


def _resolve_next_project_chapter_candidate(
    project: Project,
    *,
    branch_id: UUID | None = None,
) -> _ResolvedNextChapterCandidate | None:
    structure = build_project_structure_payload(project)
    resolved_branch = _resolve_target_branch(project, structure.default_branch_id, branch_id)
    if resolved_branch is None:
        return None

    volumes = sorted(project.volumes, key=lambda item: item.volume_number)
    volumes_by_id = {volume.id: volume for volume in volumes}
    volumes_by_number = {volume.volume_number: volume for volume in volumes}
    default_volume = next(
        (volume for volume in volumes if volume.id == structure.default_volume_id),
        volumes[0] if volumes else None,
    )
    blueprint = _normalize_blueprint(project)
    blueprint_by_number = (
        {item.chapter_number: item for item in blueprint.chapter_blueprints}
        if blueprint is not None
        else {}
    )

    branch_chapters = [
        chapter
        for chapter in project.chapters
        if chapter.branch_id == resolved_branch.id
    ]
    branch_chapters.sort(
        key=lambda chapter: (
            chapter.chapter_number,
            volumes_by_id.get(chapter.volume_id).volume_number
            if chapter.volume_id in volumes_by_id
            else 9999,
        )
    )

    for chapter in branch_chapters:
        if not _chapter_is_blank(chapter):
            continue
        chapter_blueprint = blueprint_by_number.get(chapter.chapter_number)
        volume = volumes_by_id.get(chapter.volume_id)
        if volume is None and chapter_blueprint is not None:
            volume = volumes_by_number.get(chapter_blueprint.volume_number)
        outline_seed = (
            deepcopy(chapter.outline)
            if isinstance(chapter.outline, dict)
            else chapter_blueprint.model_dump(mode="json")
            if chapter_blueprint is not None
            else None
        )
        title = (
            chapter.title
            or (chapter_blueprint.title if chapter_blueprint is not None else None)
            or f"第{chapter.chapter_number}章"
        )
        return _ResolvedNextChapterCandidate(
            chapter=chapter,
            chapter_number=chapter.chapter_number,
            title=title,
            branch=resolved_branch,
            volume=volume or default_volume,
            generation_mode=NEXT_CHAPTER_MODE_EXISTING_DRAFT,
            based_on_blueprint=chapter_blueprint is not None,
            outline_seed=outline_seed,
        )

    if blueprint is None:
        return None

    existing_by_number = {chapter.chapter_number: chapter for chapter in branch_chapters}
    for chapter_blueprint in sorted(
        blueprint.chapter_blueprints,
        key=lambda item: item.chapter_number,
    ):
        if chapter_blueprint.chapter_number in existing_by_number:
            continue
        volume = volumes_by_number.get(chapter_blueprint.volume_number) or default_volume
        return _ResolvedNextChapterCandidate(
            chapter=None,
            chapter_number=chapter_blueprint.chapter_number,
            title=chapter_blueprint.title,
            branch=resolved_branch,
            volume=volume,
            generation_mode=NEXT_CHAPTER_MODE_BLUEPRINT_SEED,
            based_on_blueprint=True,
            outline_seed=chapter_blueprint.model_dump(mode="json"),
        )

    next_chapter_number = max(
        [
            *(chapter.chapter_number for chapter in branch_chapters),
            *(item.chapter_number for item in blueprint.chapter_blueprints),
            0,
        ]
    ) + 1
    dynamic_volume = _resolve_dynamic_volume(
        blueprint=blueprint,
        next_chapter_number=next_chapter_number,
        volumes_by_number=volumes_by_number,
        default_volume=default_volume,
    )
    dynamic_outline = _build_dynamic_outline_seed(
        project=project,
        blueprint=blueprint,
        next_chapter_number=next_chapter_number,
        volume=dynamic_volume,
    )
    return _ResolvedNextChapterCandidate(
        chapter=None,
        chapter_number=next_chapter_number,
        title=str(dynamic_outline.get("title") or f"第{next_chapter_number}章"),
        branch=resolved_branch,
        volume=dynamic_volume,
        generation_mode=NEXT_CHAPTER_MODE_DYNAMIC_CONTINUATION,
        based_on_blueprint=True,
        outline_seed=dynamic_outline,
    )


async def _materialize_candidate_chapter(
    session: AsyncSession,
    project: Project,
    candidate: _ResolvedNextChapterCandidate,
) -> Chapter:
    if candidate.volume is None:
        raise AppError(
            code="project.volume_not_found",
            message="Project volume not found for the next chapter candidate.",
            status_code=400,
        )

    if candidate.chapter is not None:
        changed = False
        if candidate.title and not candidate.chapter.title:
            candidate.chapter.title = candidate.title
            changed = True
        if isinstance(candidate.outline_seed, dict) and (
            not isinstance(candidate.chapter.outline, dict) or not candidate.chapter.outline
        ):
            candidate.chapter.outline = deepcopy(candidate.outline_seed)
            changed = True
        if changed:
            await session.commit()
            await session.refresh(candidate.chapter)
        return candidate.chapter

    chapter = Chapter(
        project_id=project.id,
        volume_id=candidate.volume.id,
        branch_id=candidate.branch.id,
        chapter_number=candidate.chapter_number,
        title=candidate.title,
        content="",
        outline=deepcopy(candidate.outline_seed) if isinstance(candidate.outline_seed, dict) else None,
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
            change_reason="Created from project-level next chapter generation",
        )
    )
    await session.commit()
    return chapter


def _resolve_target_branch(
    project: Project,
    default_branch_id: UUID | None,
    branch_id: UUID | None,
) -> ProjectBranch | None:
    resolved_branch_id = branch_id or default_branch_id
    if resolved_branch_id is None:
        return None
    return next((branch for branch in project.branches if branch.id == resolved_branch_id), None)


def _normalize_blueprint(project: Project) -> ProjectNovelBlueprintRead | None:
    raw = project.novel_blueprint if isinstance(project.novel_blueprint, dict) else None
    if raw is None:
        return None
    try:
        return ProjectNovelBlueprintRead.model_validate(raw)
    except ValidationError:
        return None


def _normalize_profile(project: Project) -> ProjectBootstrapProfileRead:
    raw = project.bootstrap_profile if isinstance(project.bootstrap_profile, dict) else {}
    return ProjectBootstrapProfileRead.model_validate(
        {
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
    )


def _resolve_dynamic_volume(
    *,
    blueprint: ProjectNovelBlueprintRead,
    next_chapter_number: int,
    volumes_by_number: dict[int, ProjectVolume],
    default_volume: ProjectVolume | None,
) -> ProjectVolume | None:
    cumulative = 0
    for plan in sorted(blueprint.volume_plans, key=lambda item: item.volume_number):
        cumulative += max(1, int(plan.planned_chapter_count or 1))
        if next_chapter_number <= cumulative:
            return volumes_by_number.get(plan.volume_number) or default_volume

    if blueprint.chapter_blueprints:
        last_blueprint = max(blueprint.chapter_blueprints, key=lambda item: item.chapter_number)
        volume = volumes_by_number.get(last_blueprint.volume_number)
        if volume is not None:
            return volume

    return default_volume


def _build_dynamic_outline_seed(
    *,
    project: Project,
    blueprint: ProjectNovelBlueprintRead,
    next_chapter_number: int,
    volume: ProjectVolume | None,
) -> dict[str, Any]:
    profile = _normalize_profile(project)
    protagonist_name = (
        profile.protagonist_name
        or (blueprint.cast[0].name if blueprint.cast else None)
        or "主角"
    )
    plot_thread_titles = [item.title for item in blueprint.plot_threads[:2] if item.title]
    focus_characters = [item.name for item in blueprint.cast[:2] if item.name]
    chapter_word_count = profile.target_chapter_words or 2500
    chapter_title = f"第{next_chapter_number}章：继续逼近真相"
    if volume is not None:
        chapter_title = f"第{next_chapter_number}章：{volume.title}的新裂口"

    return {
        "source": "project_dynamic_continuation",
        "chapter_number": next_chapter_number,
        "volume_number": volume.volume_number if volume is not None else 1,
        "title": chapter_title,
        "objective": (
            f"围绕 {plot_thread_titles[0] if plot_thread_titles else blueprint.story_engine} 持续推进，"
            f"并让 {protagonist_name} 承担新的代价。"
        ),
        "summary": (
            f"承接上一阶段余震，推动 {protagonist_name} 在第 {next_chapter_number} 章面对更深一层的冲突。"
        ),
        "expected_word_count": chapter_word_count,
        "focus_characters": focus_characters or [protagonist_name],
        "key_locations": [volume.title] if volume is not None else [],
        "plot_thread_titles": plot_thread_titles[:2],
        "foreshadowing_to_plant": [],
    }


def _chapter_is_blank(chapter: Chapter) -> bool:
    content = getattr(chapter, "content", "") or ""
    return not str(content).strip()


def _extract_named_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    labels: list[str] = []
    for item in value:
        if isinstance(item, str):
            label = item.strip()
        elif isinstance(item, dict):
            label = str(
                item.get("name")
                or item.get("title")
                or item.get("content")
                or ""
            ).strip()
        else:
            label = ""
        if label and label not in labels:
            labels.append(label)
    return labels


def _find_story_bible_row(rows: list[dict[str, Any]], field: str, value: str) -> dict[str, Any] | None:
    normalized = value.strip().lower()
    for row in rows:
        if not isinstance(row, dict):
            continue
        current = str(row.get(field) or "").strip().lower()
        if current and current == normalized:
            return deepcopy(row)
    return None


def _find_timeline_event(
    rows: list[dict[str, Any]],
    *,
    chapter_number: int,
    title: str,
) -> dict[str, Any] | None:
    normalized_title = title.strip().lower()
    for row in rows:
        if not isinstance(row, dict):
            continue
        current_title = str(row.get("title") or "").strip().lower()
        current_chapter = row.get("chapter_number")
        if current_title == normalized_title or current_chapter == chapter_number:
            return deepcopy(row)
    return None


async def _upsert_auto_story_bible_change(
    session: AsyncSession,
    *,
    project: Project,
    branch_id: UUID,
    chapter_id: UUID,
    trigger_type: str,
    new_item: dict[str, Any],
    old_item: dict[str, Any] | None,
    reason: str,
    agent_name: str,
) -> dict[str, Any] | None:
    if old_item is not None and old_item == new_item:
        return None

    entity_key = _story_bible_identity_key(new_item) or (
        _story_bible_identity_key(old_item) if old_item is not None else None
    )
    if entity_key is None:
        return None

    existing_stmt = select(StoryBiblePendingChange).where(
        StoryBiblePendingChange.project_id == project.id,
        StoryBiblePendingChange.branch_id == branch_id,
        StoryBiblePendingChange.triggered_by_chapter_id == chapter_id,
        StoryBiblePendingChange.changed_entity_key == entity_key,
        StoryBiblePendingChange.status == StoryBiblePendingChangeStatus.PENDING.value,
    )
    changed_section = TRIGGER_TYPE_TO_SECTION.get(trigger_type)
    if changed_section is not None:
        existing_stmt = existing_stmt.where(
            StoryBiblePendingChange.changed_section == changed_section.value,
        )
    existing_result = await session.execute(existing_stmt)
    existing_pending = existing_result.scalar_one_or_none()
    if existing_pending is not None:
        existing_pending.old_value = {"item": old_item} if old_item is not None else None
        existing_pending.new_value = {"item": new_item}
        existing_pending.reason = reason
        existing_pending.proposed_by_agent = agent_name
        await session.flush()
        return {
            "change_id": str(existing_pending.id),
            "trigger_type": trigger_type,
            "changed_section": existing_pending.changed_section,
            "entity_key": entity_key,
            "reason": reason,
        }

    changed = await auto_trigger_story_bible_change(
        session,
        project.id,
        branch_id,
        trigger_type=trigger_type,
        entity_key=entity_key,
        old_value={"item": old_item} if old_item is not None else None,
        new_value={"item": new_item},
        reason=reason,
        chapter_id=chapter_id,
        agent_name=agent_name,
    )
    if changed is None:
        return None

    return {
        "change_id": str(changed.id),
        "trigger_type": trigger_type,
        "changed_section": changed.changed_section,
        "entity_key": entity_key,
        "reason": reason,
    }
