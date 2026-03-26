from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.errors import AppError
from models import (
    Project,
    ProjectBranch,
    ProjectBranchStoryBible,
    StoryBiblePendingChange,
    StoryBiblePendingChangeStatus,
    StoryBibleVersion,
)
from models.story_bible_version import (
    StoryBibleChangeSource,
    StoryBibleChangeType,
    StoryBibleSection,
)
from schemas.story_bible_version import (
    ConflictCheckRequest,
    ConflictCheckResult,
    StoryBiblePendingChangeCreate,
    StoryBiblePendingChangeRead,
    StoryBiblePendingChangeList,
    StoryBibleRollbackRequest,
    StoryBibleVersionList,
    StoryBibleVersionRead,
)
from schemas.project import StoryBibleBranchItemDelete, StoryBibleBranchItemUpsert
from services.project_service import (
    _branch_and_descendant_ids,
    _invalidate_story_bible_related_chapter_evaluations,
    PROJECT_PERMISSION_EDIT,
    STORY_BIBLE_PUBLIC_SECTION_KEYS,
    build_public_story_bible_sections,
    canonicalize_story_bible_branch_payload,
    delete_story_bible_branch_item,
    get_owned_project,
    get_project_branch_story_bible,
    resolve_story_bible_resolution,
    upsert_story_bible_branch_item,
)


async def get_story_bible_versions(
    session: AsyncSession,
    project_id: UUID,
    branch_id: UUID,
    *,
    page: int = 1,
    page_size: int = 20,
) -> StoryBibleVersionList:
    await _ensure_project_branch(session, project_id, branch_id)

    offset = (page - 1) * page_size
    stmt = (
        select(StoryBibleVersion)
        .where(
            StoryBibleVersion.project_id == project_id,
            StoryBibleVersion.branch_id == branch_id,
        )
        .order_by(StoryBibleVersion.version_number.desc())
        .offset(offset)
        .limit(page_size)
    )
    result = await session.execute(stmt)
    versions = result.scalars().all()

    count_stmt = select(func.count()).select_from(StoryBibleVersion).where(
        StoryBibleVersion.project_id == project_id,
        StoryBibleVersion.branch_id == branch_id,
    )
    count_result = await session.execute(count_stmt)
    total = int(count_result.scalar_one() or 0)

    return StoryBibleVersionList(
        items=[StoryBibleVersionRead.model_validate(v) for v in versions],
        total=total,
        page=page,
        page_size=page_size,
    )


async def create_story_bible_version(
    session: AsyncSession,
    project_id: UUID,
    branch_id: UUID,
    *,
    change_type: StoryBibleChangeType,
    change_source: StoryBibleChangeSource,
    changed_section: StoryBibleSection,
    old_value: dict[str, Any] | None = None,
    new_value: dict[str, Any] | None = None,
    snapshot: dict[str, Any],
    note: str | None = None,
    changed_entity_id: UUID | None = None,
    changed_entity_key: str | None = None,
    created_by: UUID | None = None,
) -> StoryBibleVersion:
    max_version_stmt = (
        select(StoryBibleVersion.version_number)
        .where(
            StoryBibleVersion.project_id == project_id,
            StoryBibleVersion.branch_id == branch_id,
        )
        .order_by(StoryBibleVersion.version_number.desc())
        .limit(1)
    )
    max_version_result = await session.execute(max_version_stmt)
    max_version = max_version_result.scalar_one_or_none()
    next_version = (max_version or 0) + 1

    version = StoryBibleVersion(
        project_id=project_id,
        branch_id=branch_id,
        version_number=next_version,
        change_type=change_type.value,
        change_source=change_source.value,
        changed_section=changed_section.value,
        changed_entity_id=changed_entity_id,
        changed_entity_key=changed_entity_key,
        old_value=old_value,
        new_value=new_value,
        snapshot=snapshot,
        note=note,
        created_by=created_by,
    )
    session.add(version)
    await session.flush()
    return version


async def rollback_story_bible(
    session: AsyncSession,
    project: Project,
    branch_id: UUID,
    request: StoryBibleRollbackRequest,
    user_id: UUID,
) -> StoryBibleVersion:
    branch = next((item for item in project.branches if item.id == branch_id), None)
    if branch is None:
        raise AppError(
            code="project.branch_not_found",
            message="Project branch not found.",
            status_code=404,
        )

    target_stmt = select(StoryBibleVersion).where(
        StoryBibleVersion.id == request.target_version_id,
        StoryBibleVersion.project_id == project.id,
        StoryBibleVersion.branch_id == branch_id,
    )
    target_result = await session.execute(target_stmt)
    target_version = target_result.scalar_one_or_none()

    if not target_version:
        raise AppError(
            code="story_bible.version_not_found",
            message="Target Story Bible version not found.",
            status_code=404,
        )

    branch_story_bible = await get_project_branch_story_bible(
        session,
        project.id,
        branch_id,
    )
    resolution = await resolve_story_bible_resolution(
        session,
        project,
        branch_id=branch_id,
    )
    current_snapshot = (
        canonicalize_story_bible_branch_payload(
            resolution.base_sections,
            deepcopy(branch_story_bible.payload),
        )
        if branch_story_bible is not None and isinstance(branch_story_bible.payload, dict)
        else {}
    )
    target_snapshot = (
        canonicalize_story_bible_branch_payload(
            resolution.base_sections,
            deepcopy(target_version.snapshot),
        )
        if isinstance(target_version.snapshot, dict)
        else {}
    )

    await _restore_branch_story_bible_snapshot(
        session,
        project_id=project.id,
        branch_id=branch_id,
        branch_story_bible=branch_story_bible,
        snapshot=target_snapshot,
    )
    await _invalidate_story_bible_related_chapter_evaluations(
        session,
        project,
        reason=(
            f'The Story Bible snapshot for branch "{branch.title}" was rolled back after the latest evaluation.'
        ),
        branch_ids=_branch_and_descendant_ids(project.branches, branch.id),
    )

    return await create_story_bible_version(
        session=session,
        project_id=project.id,
        branch_id=branch_id,
        change_type=_resolve_rollback_change_type(
            current_snapshot=current_snapshot,
            target_snapshot=target_snapshot,
        ),
        change_source=StoryBibleChangeSource.USER,
        changed_section=StoryBibleSection(target_version.changed_section),
        old_value=current_snapshot,
        new_value=target_snapshot,
        snapshot=target_snapshot,
        note=f"Rollback to version {target_version.version_number}: {request.reason or 'No reason provided'}",
        created_by=user_id,
    )


async def get_pending_changes(
    session: AsyncSession,
    project_id: UUID,
    branch_id: UUID | None = None,
) -> StoryBiblePendingChangeList:
    if branch_id is not None:
        await _ensure_project_branch(session, project_id, branch_id)

    filters = [
        StoryBiblePendingChange.project_id == project_id,
        StoryBiblePendingChange.status == StoryBiblePendingChangeStatus.PENDING.value,
    ]
    if branch_id:
        filters.append(StoryBiblePendingChange.branch_id == branch_id)

    stmt = select(StoryBiblePendingChange).where(*filters)
    stmt = stmt.order_by(StoryBiblePendingChange.created_at.desc())
    result = await session.execute(stmt)
    pending = result.scalars().all()

    total_stmt = select(func.count()).select_from(StoryBiblePendingChange).where(*filters)
    total_result = await session.execute(total_stmt)
    total = int(total_result.scalar_one() or 0)

    return StoryBiblePendingChangeList(
        items=[StoryBiblePendingChangeRead.model_validate(p) for p in pending],
        total=total,
        pending_count=total,
    )


async def create_pending_change(
    session: AsyncSession,
    project_id: UUID,
    branch_id: UUID,
    request: StoryBiblePendingChangeCreate,
) -> StoryBiblePendingChange:
    if request.project_id != project_id:
        raise AppError(
            code="story_bible.project_mismatch",
            message="Request project_id does not match URL project_id.",
            status_code=400,
        )

    await _ensure_project_branch(session, project_id, branch_id)

    expires_at = datetime.now(timezone.utc) + timedelta(days=7)

    pending = StoryBiblePendingChange(
        project_id=project_id,
        branch_id=branch_id,
        change_type=request.change_type.value,
        change_source=request.change_source.value,
        changed_section=request.changed_section.value,
        changed_entity_id=request.changed_entity_id,
        changed_entity_key=request.changed_entity_key,
        old_value=request.old_value,
        new_value=request.new_value,
        reason=request.reason,
        triggered_by_chapter_id=request.triggered_by_chapter_id,
        proposed_by_agent=request.proposed_by_agent,
        expires_at=expires_at,
    )
    session.add(pending)
    await session.flush()
    return pending


async def approve_pending_change(
    session: AsyncSession,
    change_id: UUID,
    user_id: UUID,
    comment: str | None = None,
    *,
    expected_project_id: UUID | None = None,
) -> StoryBiblePendingChange:
    stmt = select(StoryBiblePendingChange).where(
        StoryBiblePendingChange.id == change_id,
        StoryBiblePendingChange.status == StoryBiblePendingChangeStatus.PENDING.value,
    )
    if expected_project_id is not None:
        stmt = stmt.where(StoryBiblePendingChange.project_id == expected_project_id)
    result = await session.execute(stmt)
    pending = result.scalar_one_or_none()

    if not pending:
        raise AppError(
            code="story_bible.pending_change_not_found",
            message="Pending change not found or already processed.",
            status_code=404,
        )

    project = await get_owned_project(
        session,
        pending.project_id,
        user_id,
        with_relations=True,
        permission=PROJECT_PERMISSION_EDIT,
    )

    pending.status = StoryBiblePendingChangeStatus.APPROVED.value
    pending.approved_by = user_id
    pending.approved_at = datetime.now(timezone.utc)
    if comment:
        pending.reason = (
            f"{pending.reason}\n\nApproval note: {comment}"
            if pending.reason
            else f"Approval note: {comment}"
        )

    await _apply_pending_change(session, project, pending, actor_user_id=user_id)
    await session.refresh(pending)
    return pending


async def reject_pending_change(
    session: AsyncSession,
    change_id: UUID,
    user_id: UUID,
    reason: str,
    *,
    expected_project_id: UUID | None = None,
) -> StoryBiblePendingChange:
    stmt = select(StoryBiblePendingChange).where(
        StoryBiblePendingChange.id == change_id,
        StoryBiblePendingChange.status == StoryBiblePendingChangeStatus.PENDING.value,
    )
    if expected_project_id is not None:
        stmt = stmt.where(StoryBiblePendingChange.project_id == expected_project_id)
    result = await session.execute(stmt)
    pending = result.scalar_one_or_none()

    if not pending:
        raise AppError(
            code="story_bible.pending_change_not_found",
            message="Pending change not found or already processed.",
            status_code=404,
        )

    pending.status = StoryBiblePendingChangeStatus.REJECTED.value
    pending.rejected_by = user_id
    pending.rejected_at = datetime.now(timezone.utc)
    pending.rejection_reason = reason

    await session.flush()
    return pending


async def check_conflict(
    session: AsyncSession,
    project: Project,
    request: ConflictCheckRequest,
    *,
    branch_id: UUID | None = None,
) -> ConflictCheckResult:
    if request.section.value not in STORY_BIBLE_PUBLIC_SECTION_KEYS:
        return ConflictCheckResult(
            has_conflict=False,
            conflicting_items=[],
            suggestion=None,
        )

    resolution = await resolve_story_bible_resolution(
        session,
        project,
        branch_id=branch_id,
    )
    section_items = build_public_story_bible_sections(resolution.sections).get(
        request.section.value,
        [],
    )
    conflicting = []

    for item in section_items:
        if not isinstance(item, dict):
            continue
        item_identity = _story_bible_identity_key(item)
        item_key = item.get("key")
        if request.entity_key not in {item_identity, item_key}:
            continue
        for key, value in request.proposed_value.items():
            existing_value = _story_bible_lookup_value(item, key)
            if existing_value is None or existing_value == value:
                continue
            conflicting.append({
                "entity_id": str(item.get("id") or ""),
                "entity_key": item_key or item_identity or request.entity_key,
                "field": key,
                "existing_value": existing_value,
                "proposed_value": value,
            })

    has_conflict = len(conflicting) > 0
    suggestion = None
    if has_conflict:
        suggestion = (
            f"检测到与现有设定冲突。"
            f"建议：保留现有值 '{conflicting[0]['existing_value']}' "
            f"或使用冲突解决工具进行合并。"
        )

    return ConflictCheckResult(
        has_conflict=has_conflict,
        conflicting_items=conflicting,
        suggestion=suggestion,
    )


TRIGGER_TYPE_TO_SECTION = {
    "character_acquired_item": StoryBibleSection.CHARACTERS,
    "character_lost_item": StoryBibleSection.CHARACTERS,
    "character_relationship_changed": StoryBibleSection.CHARACTERS,
    "character_level_up": StoryBibleSection.CHARACTERS,
    "location_status_changed": StoryBibleSection.LOCATIONS,
    "plot_thread_progressed": StoryBibleSection.PLOT_THREADS,
    "foreshadowing_fulfilled": StoryBibleSection.FORESHADOWING,
    "timeline_event_occurred": StoryBibleSection.TIMELINE_EVENTS,
    "world_setting_changed": StoryBibleSection.WORLD_SETTINGS,
}


async def auto_trigger_story_bible_change(
    session: AsyncSession,
    project_id: UUID,
    branch_id: UUID,
    *,
    trigger_type: str,
    entity_id: UUID | None = None,
    entity_key: str | None = None,
    old_value: dict[str, Any] | None = None,
    new_value: dict[str, Any] | None = None,
    reason: str | None = None,
    chapter_id: UUID | None = None,
    agent_name: str | None = None,
) -> StoryBiblePendingChange | None:
    changed_section = TRIGGER_TYPE_TO_SECTION.get(trigger_type)
    if not changed_section:
        return None

    change_source = StoryBibleChangeSource.AUTO_TRIGGER
    if trigger_type in ("user_edit", "manual_update"):
        change_source = StoryBibleChangeSource.USER

    expires_at = datetime.now(timezone.utc) + timedelta(days=7)

    pending = StoryBiblePendingChange(
        project_id=project_id,
        branch_id=branch_id,
        status=StoryBiblePendingChangeStatus.PENDING.value,
        change_type=StoryBibleChangeType.UPDATED.value,
        change_source=change_source.value,
        changed_section=changed_section.value,
        changed_entity_id=entity_id,
        changed_entity_key=entity_key,
        old_value=old_value,
        new_value=new_value,
        reason=reason or f"Auto-triggered by {trigger_type}",
        triggered_by_chapter_id=chapter_id,
        proposed_by_agent=agent_name,
        expires_at=expires_at,
    )
    session.add(pending)
    await session.flush()
    return pending


def parse_story_bible_followups(
    followups: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    parsed = []
    for followup in followups:
        if not isinstance(followup, dict):
            continue

        dimension = followup.get("dimension", "")
        message = followup.get("message", "")
        entity_key = followup.get("entity_key") or followup.get("key")
        entity_id = followup.get("entity_id")

        trigger_type = None
        if "item" in dimension.lower():
            trigger_type = "character_acquired_item"
        elif "relationship" in dimension.lower():
            trigger_type = "character_relationship_changed"
        elif "location" in dimension.lower():
            trigger_type = "location_status_changed"
        elif "plot" in dimension.lower():
            trigger_type = "plot_thread_progressed"
        elif "foreshadow" in dimension.lower():
            trigger_type = "foreshadowing_fulfilled"
        elif "timeline" in dimension.lower() or "event" in dimension.lower():
            trigger_type = "timeline_event_occurred"
        elif "world" in dimension.lower() or "setting" in dimension.lower():
            trigger_type = "world_setting_changed"
        elif "character" in dimension.lower():
            trigger_type = "character_level_up"

        if trigger_type:
            parsed.append({
                "trigger_type": trigger_type,
                "entity_key": entity_key,
                "entity_id": entity_id,
                "message": message,
                "dimension": dimension,
                "proposed_change": followup.get("proposed_change") or followup.get("change"),
            })

    return parsed


async def _apply_pending_change(
    session: AsyncSession,
    project: Project,
    pending: StoryBiblePendingChange,
    *,
    actor_user_id: UUID,
) -> None:
    section_key = pending.changed_section
    if pending.change_type == StoryBibleChangeType.REMOVED.value:
        entity_key = _extract_pending_entity_key(pending)
        await delete_story_bible_branch_item(
            session,
            project,
            StoryBibleBranchItemDelete(
                section_key=section_key,
                entity_key=entity_key,
            ),
            actor_user_id=actor_user_id,
            branch_id=pending.branch_id,
        )
        return

    item_payload = _extract_pending_item_payload(pending)
    await upsert_story_bible_branch_item(
        session,
        project,
        StoryBibleBranchItemUpsert(
            section_key=section_key,
            item=item_payload,
        ),
        actor_user_id=actor_user_id,
        branch_id=pending.branch_id,
    )


def _extract_pending_item_payload(
    pending: StoryBiblePendingChange,
) -> dict[str, Any]:
    entity_key = pending.changed_entity_key
    item = _extract_pending_item_from_value(
        value=pending.new_value,
        section_key=pending.changed_section,
        entity_key=entity_key,
    )
    if item is not None:
        return item

    raise AppError(
        code="story_bible.pending_change_payload_invalid",
        message="Pending change does not contain a valid Story Bible item payload.",
        status_code=400,
    )


def _extract_pending_entity_key(
    pending: StoryBiblePendingChange,
) -> str:
    if pending.changed_entity_key:
        return pending.changed_entity_key

    for value in (pending.old_value, pending.new_value):
        item = _extract_pending_item_from_value(
            value=value,
            section_key=pending.changed_section,
            entity_key=None,
        )
        if item is None:
            continue
        entity_key = _story_bible_identity_key(item)
        if entity_key:
            return entity_key

    raise AppError(
        code="story_bible.pending_change_identity_missing",
        message="Pending change does not contain a stable entity key.",
        status_code=400,
    )


def _extract_pending_item_from_value(
    *,
    value: dict[str, Any] | None,
    section_key: str,
    entity_key: str | None,
) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None

    nested_item = value.get("item")
    if isinstance(nested_item, dict):
        return deepcopy(nested_item)

    section_value = value.get(section_key)
    if isinstance(section_value, dict):
        if _story_bible_identity_key(section_value):
            return deepcopy(section_value)

    if isinstance(section_value, list):
        candidates = [
            item
            for item in section_value
            if isinstance(item, dict)
        ]
        selected = _select_pending_item_candidate(candidates, entity_key)
        if selected is not None:
            return selected

    if _story_bible_identity_key(value):
        return deepcopy(value)

    return None


def _select_pending_item_candidate(
    candidates: list[dict[str, Any]],
    entity_key: str | None,
) -> dict[str, Any] | None:
    if entity_key:
        for candidate in candidates:
            if _story_bible_identity_key(candidate) == entity_key:
                return deepcopy(candidate)
    if len(candidates) == 1:
        return deepcopy(candidates[0])
    return None


def _story_bible_identity_key(row: dict[str, Any]) -> str | None:
    for field in ("id", "key", "name", "title", "content"):
        value = row.get(field)
        if value:
            return f"{field}:{value}"
    return None


def _story_bible_lookup_value(item: dict[str, Any], field: str) -> Any:
    if field in item:
        return item[field]
    data = item.get("data")
    if isinstance(data, dict):
        return data.get(field)
    return None


async def _ensure_project_branch(
    session: AsyncSession,
    project_id: UUID,
    branch_id: UUID,
) -> None:
    branch_stmt = select(ProjectBranch.id).where(
        ProjectBranch.id == branch_id,
        ProjectBranch.project_id == project_id,
    )
    branch_result = await session.execute(branch_stmt)
    if branch_result.scalar_one_or_none() is None:
        raise AppError(
            code="project.branch_not_found",
            message="Project branch not found.",
            status_code=404,
        )


async def _restore_branch_story_bible_snapshot(
    session: AsyncSession,
    *,
    project_id: UUID,
    branch_id: UUID,
    branch_story_bible: ProjectBranchStoryBible | None,
    snapshot: dict[str, Any],
) -> None:
    if snapshot:
        if branch_story_bible is None:
            session.add(
                ProjectBranchStoryBible(
                    project_id=project_id,
                    branch_id=branch_id,
                    payload=snapshot,
                )
            )
            return
        branch_story_bible.payload = snapshot
        return

    if branch_story_bible is not None:
        await session.delete(branch_story_bible)


def _resolve_rollback_change_type(
    *,
    current_snapshot: dict[str, Any],
    target_snapshot: dict[str, Any],
) -> StoryBibleChangeType:
    if not current_snapshot and target_snapshot:
        return StoryBibleChangeType.ADDED
    if current_snapshot and not target_snapshot:
        return StoryBibleChangeType.REMOVED
    return StoryBibleChangeType.UPDATED
