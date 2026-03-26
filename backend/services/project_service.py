from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import re
from typing import Any
from typing import Optional
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import and_, delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.errors import AppError
from models.chapter import Chapter
from models.chapter_version import ChapterVersion
from models.character import Character
from models.foreshadowing import Foreshadowing
from models.location import Location
from models.plot_thread import PlotThread
from models.project_faction import ProjectFaction
from models.project_item import ProjectItem
from models.project import Project
from models.project_branch import ProjectBranch
from models.project_branch_story_bible import ProjectBranchStoryBible
from models.project_collaborator import ProjectCollaborator
from models.project_volume import ProjectVolume
from models.timeline_event import TimelineEvent
from models.world_setting import WorldSetting
from models.story_bible_version import (
    StoryBibleChangeSource,
    StoryBibleChangeType,
    StoryBibleSection,
)
from schemas.project import (
    CharacterItem,
    ForeshadowingItem,
    LocationItem,
    ProjectBranchCreate,
    ProjectBranchRead,
    ProjectBranchUpdate,
    ProjectCollaborationRead,
    ProjectCollaboratorCreate,
    ProjectCollaboratorRead,
    ProjectCollaboratorUpdate,
    ProjectCreate,
    ProjectRead,
    ProjectStructureRead,
    ProjectUpdate,
    ProjectVolumeCreate,
    ProjectVolumeRead,
    ProjectVolumeUpdate,
    PlotThreadItem,
    StoryBibleFactionEntry,
    StoryBibleItemEntry,
    StoryBibleRead,
    StoryBibleBranchItemDelete,
    StoryBibleBranchItemUpsert,
    StoryBibleScopeRead,
    StoryBibleUpdate,
    TimelineEventItem,
    WorldSettingItem,
)
from services.auth_service import get_user_by_email
from services.chapter_gate_service import mark_quality_metrics_stale


DEFAULT_VOLUME_TITLE = "第一卷"
DEFAULT_BRANCH_TITLE = "主线"
DEFAULT_BRANCH_KEY = "main"
STORY_BIBLE_BRANCH_PAYLOAD_MODE_PATCH = "patch"
STORY_BIBLE_SECTION_KEYS = (
    "characters",
    "world_settings",
    "items",
    "factions",
    "locations",
    "plot_threads",
    "foreshadowing",
    "timeline_events",
)
STORY_BIBLE_PUBLIC_SECTION_KEYS = STORY_BIBLE_SECTION_KEYS
STORY_BIBLE_SECTION_ITEM_MODELS = {
    "characters": CharacterItem,
    "world_settings": WorldSettingItem,
    "items": StoryBibleItemEntry,
    "factions": StoryBibleFactionEntry,
    "locations": LocationItem,
    "plot_threads": PlotThreadItem,
    "foreshadowing": ForeshadowingItem,
    "timeline_events": TimelineEventItem,
}
STORY_BIBLE_PUBLIC_SECTION_ITEM_MODELS = STORY_BIBLE_SECTION_ITEM_MODELS
PROJECT_ROLE_OWNER = "owner"
PROJECT_ROLE_EDITOR = "editor"
PROJECT_ROLE_REVIEWER = "reviewer"
PROJECT_ROLE_VIEWER = "viewer"
PROJECT_PERMISSION_READ = "read"
PROJECT_PERMISSION_EDIT = "edit"
PROJECT_PERMISSION_EVALUATE = "evaluate"
PROJECT_PERMISSION_MANAGE_COLLABORATORS = "manage_collaborators"
PROJECT_PERMISSION_DELETE = "delete"
COLLABORATOR_ROLES = (
    PROJECT_ROLE_EDITOR,
    PROJECT_ROLE_REVIEWER,
    PROJECT_ROLE_VIEWER,
)
ROLE_PERMISSIONS = {
    PROJECT_ROLE_OWNER: {
        PROJECT_PERMISSION_READ,
        PROJECT_PERMISSION_EDIT,
        PROJECT_PERMISSION_EVALUATE,
        PROJECT_PERMISSION_MANAGE_COLLABORATORS,
        PROJECT_PERMISSION_DELETE,
    },
    PROJECT_ROLE_EDITOR: {
        PROJECT_PERMISSION_READ,
        PROJECT_PERMISSION_EDIT,
        PROJECT_PERMISSION_EVALUATE,
    },
    PROJECT_ROLE_REVIEWER: {
        PROJECT_PERMISSION_READ,
        PROJECT_PERMISSION_EVALUATE,
    },
    PROJECT_ROLE_VIEWER: {
        PROJECT_PERMISSION_READ,
    },
}


@dataclass
class ProjectAccess:
    project: Project
    role: str


@dataclass
class StoryBibleResolution:
    branch: Optional[ProjectBranch]
    branch_story_bible: Optional[ProjectBranchStoryBible]
    base_scope_kind: str
    base_branch: Optional[ProjectBranch]
    sections: dict[str, list[dict[str, Any]]]
    base_sections: dict[str, list[dict[str, Any]]]
    section_override_counts: dict[str, int]


PROJECT_RELATIONS = (
    selectinload(Project.user),
    selectinload(Project.characters),
    selectinload(Project.world_settings),
    selectinload(Project.items),
    selectinload(Project.factions),
    selectinload(Project.locations),
    selectinload(Project.plot_threads),
    selectinload(Project.foreshadowing_items),
    selectinload(Project.timeline_events),
    selectinload(Project.volumes),
    selectinload(Project.branches).selectinload(ProjectBranch.source_branch),
    selectinload(Project.collaborators).selectinload(ProjectCollaborator.user),
    selectinload(Project.collaborators).selectinload(ProjectCollaborator.added_by),
    selectinload(Project.chapters).selectinload(Chapter.volume),
    selectinload(Project.chapters).selectinload(Chapter.branch),
    selectinload(Project.chapters).selectinload(Chapter.checkpoints),
    selectinload(Project.chapters).selectinload(Chapter.review_decisions),
)


async def list_projects(session: AsyncSession, user_id: UUID) -> list[Project]:
    accesses = await list_project_accesses(session, user_id)
    return [access.project for access in accesses]


async def list_project_accesses(
    session: AsyncSession,
    user_id: UUID,
) -> list[ProjectAccess]:
    statement = (
        select(Project, ProjectCollaborator.role)
        .outerjoin(
            ProjectCollaborator,
            and_(
                ProjectCollaborator.project_id == Project.id,
                ProjectCollaborator.user_id == user_id,
            ),
        )
        .where(
            or_(
                Project.user_id == user_id,
                ProjectCollaborator.user_id == user_id,
            )
        )
        .options(
            selectinload(Project.user),
            selectinload(Project.collaborators),
        )
        .order_by(Project.updated_at.desc())
    )
    result = await session.execute(statement)
    accesses: list[ProjectAccess] = []
    seen_project_ids: set[UUID] = set()
    for project, collaborator_role in result.all():
        if project.id in seen_project_ids:
            continue
        role = (
            PROJECT_ROLE_OWNER
            if project.user_id == user_id
            else str(collaborator_role or PROJECT_ROLE_VIEWER)
        )
        _apply_project_access_metadata(project, role)
        accesses.append(ProjectAccess(project=project, role=role))
        seen_project_ids.add(project.id)
    return accesses


async def get_owned_project(
    session: AsyncSession,
    project_id: UUID,
    user_id: UUID,
    *,
    with_relations: bool = False,
    permission: str = PROJECT_PERMISSION_READ,
) -> Project:
    statement = (
        select(Project, ProjectCollaborator.role)
        .outerjoin(
            ProjectCollaborator,
            and_(
                ProjectCollaborator.project_id == Project.id,
                ProjectCollaborator.user_id == user_id,
            ),
        )
        .where(Project.id == project_id)
        .where(
            or_(
                Project.user_id == user_id,
                ProjectCollaborator.user_id == user_id,
            )
        )
    )
    if with_relations:
        statement = statement.options(*PROJECT_RELATIONS)
    else:
        statement = statement.options(
            selectinload(Project.user),
            selectinload(Project.collaborators),
        )

    result = await session.execute(statement)
    row = result.first()
    if row is None:
        raise AppError(
            code="project.not_found",
            message="Project not found.",
            status_code=404,
        )
    project, collaborator_role = row
    role = (
        PROJECT_ROLE_OWNER
        if project.user_id == user_id
        else str(collaborator_role or PROJECT_ROLE_VIEWER)
    )
    _assert_project_permission(role, permission)
    _apply_project_access_metadata(project, role)

    changed = await ensure_project_structure(session, project)
    storage_normalized = False
    if with_relations:
        storage_normalized = await _normalize_project_story_bible_storage(
            session,
            project,
        )
    if changed or storage_normalized:
        await session.commit()
        result = await session.execute(statement)
        project, collaborator_role = result.first()
        role = (
            PROJECT_ROLE_OWNER
            if project.user_id == user_id
            else str(collaborator_role or PROJECT_ROLE_VIEWER)
        )
        _assert_project_permission(role, permission)
        _apply_project_access_metadata(project, role)
    return project


async def create_project(
    session: AsyncSession,
    user_id: UUID,
    payload: ProjectCreate,
) -> Project:
    payload_data = payload.model_dump()
    story_engine_preset_key = payload_data.pop("story_engine_preset_key", None)
    if story_engine_preset_key is None:
        from services.story_engine_settings_service import build_story_engine_settings_for_preset

        story_engine_settings = build_story_engine_settings_for_preset()
    else:
        from services.story_engine_settings_service import build_story_engine_settings_for_preset

        story_engine_settings = build_story_engine_settings_for_preset(story_engine_preset_key)

    project = Project(
        user_id=user_id,
        story_engine_settings=story_engine_settings,
        **payload_data,
    )
    session.add(project)
    await session.flush()
    await ensure_project_structure(session, project)
    await session.commit()
    result = await session.execute(
        select(Project)
        .where(Project.id == project.id)
        .options(selectinload(Project.user), selectinload(Project.collaborators))
    )
    project = result.scalar_one()
    _apply_project_access_metadata(project, PROJECT_ROLE_OWNER)
    return project


async def update_project(
    session: AsyncSession,
    project: Project,
    payload: ProjectUpdate,
) -> Project:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(project, field, value)
    await session.commit()
    await session.refresh(project)
    return project


async def delete_project(session: AsyncSession, project: Project) -> None:
    await session.delete(project)
    await session.commit()


async def get_project_collaboration(
    session: AsyncSession,
    project_id: UUID,
    user_id: UUID,
) -> ProjectCollaborationRead:
    project = await get_owned_project(
        session,
        project_id,
        user_id,
        with_relations=True,
        permission=PROJECT_PERMISSION_READ,
    )
    current_role = str(getattr(project, "access_role", PROJECT_ROLE_OWNER))
    return build_project_collaboration_payload(project, current_role)


def build_project_collaboration_payload(
    project: Project,
    current_role: str,
) -> ProjectCollaborationRead:
    members: list[ProjectCollaboratorRead] = [
        ProjectCollaboratorRead(
            id=project.user_id,
            project_id=project.id,
            user_id=project.user_id,
            added_by_user_id=None,
            email=getattr(project.user, "email", None) or getattr(project, "owner_email", None) or "",
            role=PROJECT_ROLE_OWNER,
            is_owner=True,
        )
    ]
    for collaborator in sorted(
        project.collaborators,
        key=lambda item: (item.role, item.created_at),
    ):
        members.append(
            ProjectCollaboratorRead(
                id=collaborator.id,
                project_id=collaborator.project_id,
                user_id=collaborator.user_id,
                added_by_user_id=collaborator.added_by_user_id,
                email=getattr(collaborator.user, "email", ""),
                role=collaborator.role,
                is_owner=False,
            )
        )

    return ProjectCollaborationRead(
        project=ProjectRead.model_validate(project),
        current_role=current_role,
        members=members,
    )


async def add_project_collaborator(
    session: AsyncSession,
    project: Project,
    *,
    actor_user_id: UUID,
    payload: ProjectCollaboratorCreate,
) -> ProjectCollaborator:
    role = _normalize_collaborator_role(payload.role)
    collaborator_user = await get_user_by_email(session, payload.email)
    if collaborator_user is None:
        raise AppError(
            code="project.collaborator_user_not_found",
            message="Collaborator user not found.",
            status_code=404,
        )
    if collaborator_user.id == project.user_id:
        raise AppError(
            code="project.collaborator_is_owner",
            message="Project owner already has access.",
            status_code=409,
        )

    existing = await session.execute(
        select(ProjectCollaborator.id).where(
            ProjectCollaborator.project_id == project.id,
            ProjectCollaborator.user_id == collaborator_user.id,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise AppError(
            code="project.collaborator_exists",
            message="Collaborator already exists in this project.",
            status_code=409,
        )

    collaborator = ProjectCollaborator(
        project_id=project.id,
        user_id=collaborator_user.id,
        added_by_user_id=actor_user_id,
        role=role,
    )
    session.add(collaborator)
    await session.commit()
    await session.refresh(collaborator)
    return collaborator


async def update_project_collaborator(
    session: AsyncSession,
    project: Project,
    collaborator_id: UUID,
    payload: ProjectCollaboratorUpdate,
) -> ProjectCollaborator:
    collaborator = await _get_project_collaborator(session, project.id, collaborator_id)
    collaborator.role = _normalize_collaborator_role(payload.role)
    await session.commit()
    await session.refresh(collaborator)
    return collaborator


async def remove_project_collaborator(
    session: AsyncSession,
    project: Project,
    collaborator_id: UUID,
) -> None:
    collaborator = await _get_project_collaborator(session, project.id, collaborator_id)
    await session.delete(collaborator)
    await session.commit()


async def get_project_structure(
    session: AsyncSession,
    project_id: UUID,
    user_id: UUID,
) -> ProjectStructureRead:
    project = await get_owned_project(
        session,
        project_id,
        user_id,
        with_relations=True,
    )
    return build_project_structure_payload(project)


def build_project_structure_payload(project: Project) -> ProjectStructureRead:
    volumes = sorted(project.volumes, key=lambda item: item.volume_number)
    branches = sorted(
        project.branches,
        key=lambda item: (0 if item.is_default else 1, item.created_at),
    )
    default_volume = volumes[0] if volumes else None
    default_branch = next((item for item in branches if item.is_default), None)
    if default_branch is None and branches:
        default_branch = branches[0]

    volume_counts = {volume.id: 0 for volume in volumes}
    branch_counts = {branch.id: 0 for branch in branches}
    for chapter in project.chapters:
        if chapter.volume_id in volume_counts:
            volume_counts[chapter.volume_id] += 1
        if chapter.branch_id in branch_counts:
            branch_counts[chapter.branch_id] += 1

    volume_payload = []
    for volume in volumes:
        volume_data = ProjectVolumeRead.model_validate(volume)
        volume_payload.append(
            volume_data.model_copy(
                update={
                    "is_default": default_volume is not None and volume.id == default_volume.id,
                    "chapter_count": volume_counts.get(volume.id, 0),
                }
            )
        )

    branch_payload = []
    for branch in branches:
        branch_data = ProjectBranchRead.model_validate(branch)
        branch_payload.append(
            branch_data.model_copy(
                update={
                    "is_default": default_branch is not None and branch.id == default_branch.id,
                    "chapter_count": branch_counts.get(branch.id, 0),
                }
            )
        )

    return ProjectStructureRead(
        project=ProjectRead.model_validate(project),
        default_volume_id=default_volume.id if default_volume is not None else None,
        default_branch_id=default_branch.id if default_branch is not None else None,
        volumes=volume_payload,
        branches=branch_payload,
    )


def build_project_stats_payload(project: Project) -> dict[str, int]:
    public_sections = build_public_story_bible_sections(
        serialize_project_story_bible_sections(project)
    )
    return {
        "total_word_count": sum(ch.word_count or 0 for ch in project.chapters),
        "chapter_count": len(project.chapters),
        "character_count": len(public_sections["characters"]),
        "item_count": len(public_sections["items"]),
        "faction_count": len(public_sections["factions"]),
        "location_count": len(public_sections["locations"]),
        "plot_thread_count": len(public_sections["plot_threads"]),
        "volume_count": len(project.volumes),
        "branch_count": len(project.branches),
    }


async def get_story_bible(
    session: AsyncSession,
    project_id: UUID,
    user_id: UUID,
    *,
    branch_id: Optional[UUID] = None,
) -> StoryBibleRead:
    project = await get_owned_project(
        session,
        project_id,
        user_id,
        with_relations=True,
        permission=PROJECT_PERMISSION_READ,
    )
    return await build_story_bible_payload(
        session,
        project,
        branch_id=branch_id,
    )


async def build_story_bible_payload(
    session: AsyncSession,
    project: Project,
    *,
    branch_id: Optional[UUID] = None,
) -> StoryBibleRead:
    resolution = await resolve_story_bible_resolution(
        session,
        project,
        branch_id=branch_id,
    )
    public_sections = build_public_story_bible_sections(resolution.sections)
    return StoryBibleRead(
        project=ProjectRead.model_validate(project),
        scope=build_story_bible_scope(
            resolution,
        ),
        **public_sections,
    )


def build_story_bible_scope(
    resolution: StoryBibleResolution,
) -> StoryBibleScopeRead:
    branch = resolution.branch
    if branch is None:
        return StoryBibleScopeRead()
    public_base_sections = build_public_story_bible_sections(resolution.base_sections)
    public_sections = build_public_story_bible_sections(resolution.sections)
    public_override_counts = calculate_story_bible_override_counts(
        public_base_sections,
        public_sections,
        section_keys=STORY_BIBLE_PUBLIC_SECTION_KEYS,
    )
    section_override_details = build_story_bible_section_override_details(
        public_base_sections,
        public_sections,
        section_keys=STORY_BIBLE_PUBLIC_SECTION_KEYS,
    )
    changed_sections = sorted(
        key
        for key, count in public_override_counts.items()
        if count > 0
    )
    return StoryBibleScopeRead(
        scope_kind="branch",
        branch_id=branch.id,
        branch_title=branch.title,
        branch_key=branch.key,
        inherits_from_project=(
            resolution.branch_story_bible is None
            and resolution.base_scope_kind == "project"
        ),
        base_scope_kind=resolution.base_scope_kind,
        base_branch_id=(
            resolution.base_branch.id if resolution.base_branch is not None else None
        ),
        base_branch_title=(
            resolution.base_branch.title if resolution.base_branch is not None else None
        ),
        base_branch_key=(
            resolution.base_branch.key if resolution.base_branch is not None else None
        ),
        has_snapshot=resolution.branch_story_bible is not None,
        changed_sections=changed_sections,
        section_override_counts={
            key: count
            for key, count in public_override_counts.items()
            if count > 0
        },
        total_override_count=sum(public_override_counts.values()),
        section_override_details=section_override_details,
    )


def serialize_project_story_bible_sections(project: Project) -> dict[str, list[dict[str, Any]]]:
    return {
        "characters": [
            {
                "id": str(character.id),
                "name": character.name,
                "data": character.data,
                "version": character.version,
                "created_chapter": character.created_chapter,
            }
            for character in getattr(project, "characters", [])
        ],
        "world_settings": [
            {
                "id": str(item.id),
                "key": item.key,
                "title": item.title,
                "data": item.data,
                "version": item.version,
            }
            for item in getattr(project, "world_settings", [])
        ],
        "items": [
            {
                "id": str(item.id),
                "key": item.key,
                "name": item.name,
                "type": item.item_type,
                "rarity": item.rarity,
                "description": item.description,
                "effects": _clean_story_bible_string_list(item.effects),
                "owner": item.owner,
                "location": item.location,
                "status": item.status,
                "introduced_chapter": item.introduced_chapter,
                "forbidden_holders": _clean_story_bible_string_list(item.forbidden_holders),
                "version": item.version,
            }
            for item in getattr(project, "items", [])
        ],
        "factions": [
            {
                "id": str(item.id),
                "key": item.key,
                "name": item.name,
                "type": item.faction_type,
                "scale": item.scale,
                "description": item.description,
                "goals": item.goals,
                "leader": item.leader,
                "members": _clean_story_bible_string_list(item.members),
                "territory": item.territory,
                "resources": _clean_story_bible_string_list(item.resources),
                "ideology": item.ideology,
                "version": item.version,
            }
            for item in getattr(project, "factions", [])
        ],
        "locations": [
            {
                "id": str(item.id),
                "name": item.name,
                "data": item.data,
                "version": item.version,
            }
            for item in getattr(project, "locations", [])
        ],
        "plot_threads": [
            {
                "id": str(item.id),
                "title": item.title,
                "status": item.status,
                "importance": item.importance,
                "data": item.data,
            }
            for item in getattr(project, "plot_threads", [])
        ],
        "foreshadowing": [
            {
                "id": str(item.id),
                "content": item.content,
                "planted_chapter": item.planted_chapter,
                "payoff_chapter": item.payoff_chapter,
                "status": item.status,
                "importance": item.importance,
            }
            for item in getattr(project, "foreshadowing_items", [])
        ],
        "timeline_events": [
            {
                "id": str(item.id),
                "chapter_number": item.chapter_number,
                "title": item.title,
                "data": item.data,
            }
            for item in getattr(project, "timeline_events", [])
        ],
    }


def build_public_story_bible_sections(
    sections: dict[str, list[dict[str, Any]]],
) -> dict[str, list[dict[str, Any]]]:
    world_settings = [
        deepcopy(item)
        for item in sections.get("world_settings", [])
        if isinstance(item, dict)
    ]
    public_world_settings = [
        item
        for item in world_settings
        if not _is_story_bible_virtual_wrapper(item)
    ]
    native_items = [
        deepcopy(item)
        for item in sections.get("items", [])
        if isinstance(item, dict)
    ]
    native_factions = [
        deepcopy(item)
        for item in sections.get("factions", [])
        if isinstance(item, dict)
    ]
    legacy_items = [
        _world_setting_wrapper_to_item_entry(item)
        for item in world_settings
        if _is_story_bible_item_wrapper(item)
    ]
    legacy_factions = [
        _world_setting_wrapper_to_faction_entry(item)
        for item in world_settings
        if _is_story_bible_faction_wrapper(item)
    ]
    return {
        "characters": [
            deepcopy(item)
            for item in sections.get("characters", [])
            if isinstance(item, dict)
        ],
        "world_settings": public_world_settings,
        "items": _merge_story_bible_section_rows(native_items, legacy_items),
        "factions": _merge_story_bible_section_rows(native_factions, legacy_factions),
        "locations": [
            deepcopy(item)
            for item in sections.get("locations", [])
            if isinstance(item, dict)
        ],
        "plot_threads": [
            deepcopy(item)
            for item in sections.get("plot_threads", [])
            if isinstance(item, dict)
        ],
        "foreshadowing": [
            deepcopy(item)
            for item in sections.get("foreshadowing", [])
            if isinstance(item, dict)
        ],
        "timeline_events": [
            deepcopy(item)
            for item in sections.get("timeline_events", [])
            if isinstance(item, dict)
        ],
    }


def combine_public_story_bible_world_settings(
    world_settings: list[dict[str, Any]],
    *,
    items: list[dict[str, Any]],
    factions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    combined = [
        deepcopy(item)
        for item in world_settings
        if isinstance(item, dict)
    ]
    combined.extend(
        _story_bible_item_entry_to_world_setting(item)
        for item in items
        if isinstance(item, dict)
    )
    combined.extend(
        _story_bible_faction_entry_to_world_setting(item)
        for item in factions
        if isinstance(item, dict)
    )
    return combined


def canonicalize_story_bible_branch_payload(
    base_sections: dict[str, list[dict[str, Any]]],
    branch_story_bible_payload: Optional[dict[str, Any]],
) -> dict[str, Any]:
    if not isinstance(branch_story_bible_payload, dict):
        return {}
    merged_sections = merge_story_bible_sections(
        base_sections,
        branch_story_bible_payload=branch_story_bible_payload,
    )
    return build_story_bible_branch_delta_payload(
        base_sections,
        merged_sections,
    )


def _is_story_bible_virtual_wrapper(row: dict[str, Any]) -> bool:
    return _is_story_bible_item_wrapper(row) or _is_story_bible_faction_wrapper(row)


def _is_story_bible_item_wrapper(row: dict[str, Any]) -> bool:
    data = row.get("data")
    return isinstance(data, dict) and str(data.get("entity_type") or "").strip().lower() == "item"


def _is_story_bible_faction_wrapper(row: dict[str, Any]) -> bool:
    data = row.get("data")
    return isinstance(data, dict) and str(data.get("entity_type") or "").strip().lower() == "faction"


def _world_setting_wrapper_to_item_entry(row: dict[str, Any]) -> dict[str, Any]:
    data = row.get("data")
    normalized_data = data if isinstance(data, dict) else {}
    nested_items = normalized_data.get("items")
    nested_item = (
        nested_items[0]
        if isinstance(nested_items, list) and nested_items and isinstance(nested_items[0], dict)
        else {}
    )
    return StoryBibleItemEntry(
        key=str(row.get("key") or nested_item.get("key") or nested_item.get("name") or "").strip(),
        name=str(
            nested_item.get("name")
            or nested_item.get("title")
            or row.get("title")
            or row.get("key")
            or ""
        ).strip(),
        type=_optional_story_bible_text(
            nested_item.get("type") or normalized_data.get("item_type")
        ),
        rarity=_optional_story_bible_text(nested_item.get("rarity")),
        description=_optional_story_bible_text(
            nested_item.get("description") or normalized_data.get("description")
        ),
        effects=_clean_story_bible_string_list(nested_item.get("effects")),
        owner=_optional_story_bible_text(
            nested_item.get("owner") or normalized_data.get("owner")
        ),
        location=_optional_story_bible_text(
            nested_item.get("location") or normalized_data.get("location")
        ),
        status=_optional_story_bible_text(
            nested_item.get("status") or normalized_data.get("status")
        ),
        introduced_chapter=_optional_story_bible_int(
            nested_item.get("introduced_chapter") or normalized_data.get("introduced_chapter")
        ),
        forbidden_holders=_clean_story_bible_string_list(
            nested_item.get("forbidden_holders") or normalized_data.get("forbidden_holders")
        ),
        version=int(row.get("version") or 1),
    ).model_dump(mode="json")


def _world_setting_wrapper_to_faction_entry(row: dict[str, Any]) -> dict[str, Any]:
    data = row.get("data")
    normalized_data = data if isinstance(data, dict) else {}
    return StoryBibleFactionEntry(
        key=str(row.get("key") or normalized_data.get("key") or row.get("title") or "").strip(),
        name=str(
            normalized_data.get("name")
            or row.get("title")
            or row.get("key")
            or ""
        ).strip(),
        type=_optional_story_bible_text(
            normalized_data.get("faction_type") or normalized_data.get("type")
        ),
        scale=_optional_story_bible_text(normalized_data.get("scale")),
        description=_optional_story_bible_text(normalized_data.get("description")),
        goals=_optional_story_bible_text(normalized_data.get("goals")),
        leader=_optional_story_bible_text(normalized_data.get("leader")),
        members=_clean_story_bible_string_list(normalized_data.get("members")),
        territory=_optional_story_bible_text(normalized_data.get("territory")),
        resources=_clean_story_bible_string_list(normalized_data.get("resources")),
        ideology=_optional_story_bible_text(normalized_data.get("ideology")),
        version=int(row.get("version") or 1),
    ).model_dump(mode="json")


def _story_bible_item_entry_to_world_setting(item: dict[str, Any]) -> dict[str, Any]:
    normalized = StoryBibleItemEntry.model_validate(item).model_dump(mode="json")
    return WorldSettingItem(
        key=normalized["key"],
        title=normalized["name"],
        data={
            "entity_type": "item",
            "item_type": normalized.get("type"),
            "items": [
                {
                    "name": normalized["name"],
                    "type": normalized.get("type"),
                    "rarity": normalized.get("rarity"),
                    "description": normalized.get("description"),
                    "effects": normalized.get("effects", []),
                    "owner": normalized.get("owner"),
                    "location": normalized.get("location"),
                    "status": normalized.get("status"),
                    "introduced_chapter": normalized.get("introduced_chapter"),
                    "forbidden_holders": normalized.get("forbidden_holders", []),
                }
            ],
        },
        version=int(normalized.get("version") or 1),
    ).model_dump(mode="json")


def _story_bible_faction_entry_to_world_setting(item: dict[str, Any]) -> dict[str, Any]:
    normalized = StoryBibleFactionEntry.model_validate(item).model_dump(mode="json")
    return WorldSettingItem(
        key=normalized["key"],
        title=normalized["name"],
        data={
            "entity_type": "faction",
            "name": normalized["name"],
            "faction_type": normalized.get("type"),
            "scale": normalized.get("scale"),
            "description": normalized.get("description"),
            "goals": normalized.get("goals"),
            "leader": normalized.get("leader"),
            "members": normalized.get("members", []),
            "territory": normalized.get("territory"),
            "resources": normalized.get("resources", []),
            "ideology": normalized.get("ideology"),
        },
        version=int(normalized.get("version") or 1),
    ).model_dump(mode="json")


def _merge_story_bible_section_rows(
    primary_rows: list[dict[str, Any]],
    fallback_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen_keys: set[str] = set()

    for index, row in enumerate([*primary_rows, *fallback_rows]):
        if not isinstance(row, dict):
            continue
        row_copy = deepcopy(row)
        row_key = _story_bible_identity_key(row_copy) or f"index:{index}:{repr(sorted(row_copy.items()))}"
        if row_key in seen_keys:
            continue
        seen_keys.add(row_key)
        merged.append(row_copy)

    return merged


def _optional_story_bible_text(value: Any) -> str | None:
    if value is None:
        return None
    candidate = str(value).strip()
    return candidate or None


def _optional_story_bible_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _clean_story_bible_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    cleaned: list[str] = []
    seen: set[str] = set()
    for item in value:
        candidate = _optional_story_bible_text(item)
        if not candidate:
            continue
        normalized = candidate.lower()
        if normalized in seen:
            continue
        seen.add(normalized)
        cleaned.append(candidate)
    return cleaned


def _normalize_story_bible_branch_payload(
    base_sections: dict[str, list[dict[str, Any]]],
    branch_story_bible_payload: dict[str, Any],
) -> dict[str, Any]:
    if "items" in branch_story_bible_payload or "factions" in branch_story_bible_payload:
        return deepcopy(branch_story_bible_payload)

    world_settings_payload = branch_story_bible_payload.get("world_settings")
    legacy_base_world_settings = combine_public_story_bible_world_settings(
        base_sections.get("world_settings", []),
        items=base_sections.get("items", []),
        factions=base_sections.get("factions", []),
    )

    if isinstance(world_settings_payload, list):
        legacy_current_world_settings = [
            deepcopy(item)
            for item in world_settings_payload
            if isinstance(item, dict)
        ]
    elif isinstance(world_settings_payload, dict):
        legacy_current_world_settings = _apply_story_bible_section_payload(
            legacy_base_world_settings,
            world_settings_payload,
        )
    else:
        legacy_current_world_settings = legacy_base_world_settings

    if not any(_is_story_bible_virtual_wrapper(item) for item in legacy_current_world_settings):
        return deepcopy(branch_story_bible_payload)

    split_sections = build_public_story_bible_sections(
        {
            "characters": [],
            "world_settings": legacy_current_world_settings,
            "items": [],
            "factions": [],
            "locations": [],
            "plot_threads": [],
            "foreshadowing": [],
            "timeline_events": [],
        }
    )
    normalized_payload = deepcopy(branch_story_bible_payload)
    normalized_payload["world_settings"] = split_sections["world_settings"]
    normalized_payload["items"] = split_sections["items"]
    normalized_payload["factions"] = split_sections["factions"]
    return normalized_payload


def merge_story_bible_sections(
    base_sections: dict[str, list[dict[str, Any]]],
    *,
    branch_story_bible_payload: Optional[dict[str, Any]] = None,
) -> dict[str, list[dict[str, Any]]]:
    if not isinstance(branch_story_bible_payload, dict):
        return {
            key: deepcopy(base_sections.get(key, []))
            for key in STORY_BIBLE_SECTION_KEYS
        }

    normalized_payload = _normalize_story_bible_branch_payload(
        base_sections,
        branch_story_bible_payload,
    )
    merged_sections: dict[str, list[dict[str, Any]]] = {}
    for key in STORY_BIBLE_SECTION_KEYS:
        base_rows = base_sections.get(key, [])
        override_rows = normalized_payload.get(key)
        if isinstance(override_rows, list):
            merged_sections[key] = [
                item
                for item in override_rows
                if isinstance(item, dict)
            ]
            continue
        if isinstance(override_rows, dict):
            merged_sections[key] = _apply_story_bible_section_payload(
                base_rows,
                override_rows,
            )
            continue
        merged_sections[key] = deepcopy(base_rows)
    return merged_sections


def serialize_story_bible_sections(
    project: Project,
    *,
    branch_story_bible_payload: Optional[dict[str, Any]] = None,
) -> dict[str, list[dict[str, Any]]]:
    return merge_story_bible_sections(
        serialize_project_story_bible_sections(project),
        branch_story_bible_payload=branch_story_bible_payload,
    )


def build_story_bible_branch_delta_payload(
    base_sections: dict[str, list[dict[str, Any]]],
    current_sections: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for key in STORY_BIBLE_SECTION_KEYS:
        section_payload = _build_story_bible_section_delta(
            base_sections.get(key, []),
            current_sections.get(key, []),
        )
        if section_payload is not None:
            payload[key] = section_payload
    return payload


def serialize_story_bible_chapter_summaries(
    project: Project,
    *,
    branch: Optional[ProjectBranch] = None,
) -> list[dict[str, Any]]:
    chapters = list(project.chapters)
    if branch is not None:
        chapters = [
            chapter
            for chapter in chapters
            if chapter.branch_id == branch.id
        ]
    chapters.sort(
        key=lambda chapter: (
            getattr(getattr(chapter, "volume", None), "volume_number", 0) or 0,
            chapter.chapter_number,
            str(chapter.id),
        )
    )
    return [
        {
            "id": str(chapter.id),
            "volume_id": str(chapter.volume_id) if chapter.volume_id is not None else None,
            "volume_title": chapter.volume.title if chapter.volume is not None else None,
            "volume_number": (
                chapter.volume.volume_number if chapter.volume is not None else None
            ),
            "branch_id": str(chapter.branch_id) if chapter.branch_id is not None else None,
            "branch_title": chapter.branch.title if chapter.branch is not None else None,
            "branch_key": chapter.branch.key if chapter.branch is not None else None,
            "chapter_number": chapter.chapter_number,
            "title": chapter.title,
            "status": chapter.status,
            "word_count": chapter.word_count,
        }
        for chapter in chapters
    ]


async def resolve_story_bible_scope(
    session: AsyncSession,
    project: Project,
    *,
    branch_id: Optional[UUID] = None,
) -> tuple[Optional[ProjectBranch], Optional[ProjectBranchStoryBible]]:
    resolution = await resolve_story_bible_resolution(
        session,
        project,
        branch_id=branch_id,
    )
    return resolution.branch, resolution.branch_story_bible


async def resolve_story_bible_resolution(
    session: AsyncSession,
    project: Project,
    *,
    branch_id: Optional[UUID] = None,
    branch: Optional[ProjectBranch] = None,
    branch_story_bible_cache: Optional[dict[UUID, Optional[ProjectBranchStoryBible]]] = None,
    branch_resolution_cache: Optional[dict[UUID, StoryBibleResolution]] = None,
    visited_branch_ids: Optional[set[UUID]] = None,
) -> StoryBibleResolution:
    if branch is None and branch_id is not None:
        branch = next((item for item in project.branches if item.id == branch_id), None)
        if branch is None:
            raise AppError(
                code="project.branch_not_found",
                message="Project branch not found.",
                status_code=404,
            )
    if branch is None:
        base_sections = serialize_project_story_bible_sections(project)
        return StoryBibleResolution(
            branch=None,
            branch_story_bible=None,
            base_scope_kind="project",
            base_branch=None,
            sections=base_sections,
            base_sections=base_sections,
            section_override_counts={},
        )

    if branch_resolution_cache is None:
        branch_resolution_cache = {}
    if branch_story_bible_cache is None:
        branch_story_bible_cache = {}
    if visited_branch_ids is None:
        visited_branch_ids = set()
    if branch.id in branch_resolution_cache:
        return branch_resolution_cache[branch.id]
    if branch.id in visited_branch_ids:
        raise AppError(
            code="project.branch_cycle_detected",
            message="Project branches contain a cyclic source reference.",
            status_code=409,
        )

    next_visited = set(visited_branch_ids)
    next_visited.add(branch.id)
    branches_by_id = {item.id: item for item in project.branches}
    parent_branch = (
        branches_by_id.get(branch.source_branch_id)
        if branch.source_branch_id is not None
        else None
    )
    if parent_branch is not None:
        parent_resolution = await resolve_story_bible_resolution(
            session,
            project,
            branch=parent_branch,
            branch_story_bible_cache=branch_story_bible_cache,
            branch_resolution_cache=branch_resolution_cache,
            visited_branch_ids=next_visited,
        )
        base_scope_kind = "branch"
        base_branch = parent_branch
        base_sections = parent_resolution.sections
    else:
        base_scope_kind = "project"
        base_branch = None
        base_sections = serialize_project_story_bible_sections(project)

    if branch.id in branch_story_bible_cache:
        branch_story_bible = branch_story_bible_cache[branch.id]
    else:
        branch_story_bible = await get_project_branch_story_bible(
            session,
            project.id,
            branch.id,
        )
        branch_story_bible_cache[branch.id] = branch_story_bible

    sections = merge_story_bible_sections(
        base_sections,
        branch_story_bible_payload=(
            branch_story_bible.payload if branch_story_bible is not None else None
        ),
    )
    resolution = StoryBibleResolution(
        branch=branch,
        branch_story_bible=branch_story_bible,
        base_scope_kind=base_scope_kind,
        base_branch=base_branch,
        sections=sections,
        base_sections=base_sections,
        section_override_counts=calculate_story_bible_override_counts(
            base_sections,
            sections,
        ),
    )
    branch_resolution_cache[branch.id] = resolution
    return resolution


def calculate_story_bible_override_counts(
    base_sections: dict[str, list[dict[str, Any]]],
    current_sections: dict[str, list[dict[str, Any]]],
    *,
    section_keys: tuple[str, ...] = STORY_BIBLE_SECTION_KEYS,
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for key in section_keys:
        count = len(
            _build_story_bible_section_override_items(
                key,
                base_sections.get(key, []),
                current_sections.get(key, []),
            )
        )
        if count > 0:
            counts[key] = count
    return counts


def build_story_bible_section_override_details(
    base_sections: dict[str, list[dict[str, Any]]],
    current_sections: dict[str, list[dict[str, Any]]],
    *,
    section_keys: tuple[str, ...] = STORY_BIBLE_SECTION_KEYS,
) -> list[dict[str, Any]]:
    details: list[dict[str, Any]] = []
    for key in section_keys:
        items = _build_story_bible_section_override_items(
            key,
            base_sections.get(key, []),
            current_sections.get(key, []),
        )
        if items:
            details.append(
                {
                    "section_key": key,
                    "item_count": len(items),
                    "items": items,
                }
            )
    return details


def _build_story_bible_section_override_items(
    section_key: str,
    base_rows: list[dict[str, Any]],
    current_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    normalized_base_rows = [
        deepcopy(row)
        for row in base_rows
        if isinstance(row, dict)
    ]
    normalized_current_rows = [
        deepcopy(row)
        for row in current_rows
        if isinstance(row, dict)
    ]
    if normalized_base_rows == normalized_current_rows:
        return []

    base_entries = _story_bible_identity_entries(normalized_base_rows)
    current_entries = _story_bible_identity_entries(normalized_current_rows)
    if base_entries is None or current_entries is None:
        return [
            {
                "entity_key": f"section:{section_key}",
                "entity_label": "整段快照覆盖",
                "operation": "updated",
                "changed_fields": ["section"],
            }
        ]

    base_map = {
        key: row
        for key, row in base_entries
    }
    current_map = {
        key: row
        for key, row in current_entries
    }

    items: list[dict[str, Any]] = []
    for row_key, row in current_entries:
        if row_key not in base_map:
            items.append(
                {
                    "entity_key": row_key,
                    "entity_label": _story_bible_row_label(row, row_key=row_key),
                    "operation": "added",
                    "changed_fields": [],
                }
            )
            continue
        if base_map[row_key] != row:
            items.append(
                {
                    "entity_key": row_key,
                    "entity_label": _story_bible_row_label(row, row_key=row_key),
                    "operation": "updated",
                    "changed_fields": _collect_story_bible_changed_fields(
                        base_map[row_key],
                        row,
                    ),
                }
            )

    for row_key, row in base_entries:
        if row_key in current_map:
            continue
        items.append(
            {
                "entity_key": row_key,
                "entity_label": _story_bible_row_label(row, row_key=row_key),
                "operation": "removed",
                "changed_fields": [],
            }
        )

    base_order = [row_key for row_key, _ in base_entries]
    current_order = [row_key for row_key, _ in current_entries]
    if base_order != current_order and set(base_order) == set(current_order):
        items.append(
            {
                "entity_key": f"order:{section_key}",
                "entity_label": "顺序调整",
                "operation": "reordered",
                "changed_fields": ["order"],
            }
        )

    return items


def _story_bible_row_map(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    mapped: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(rows):
        key = _story_bible_row_key(row, index=index)
        mapped[key] = row
    return mapped


def _story_bible_row_key(row: dict[str, Any], *, index: int) -> str:
    for field in ("id", "key", "name", "title", "content"):
        value = row.get(field)
        if value:
            return f"{field}:{value}"
    return f"index:{index}:{repr(sorted(row.items()))}"


def _story_bible_row_label(row: dict[str, Any], *, row_key: str) -> str:
    for field in ("name", "title", "key"):
        value = row.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()
    content = row.get("content")
    if isinstance(content, str) and content.strip():
        normalized = re.sub(r"\s+", " ", content.strip())
        if len(normalized) > 24:
            return f"{normalized[:24]}..."
        return normalized
    return row_key


def _collect_story_bible_changed_fields(
    base_value: Any,
    current_value: Any,
    *,
    prefix: str = "",
) -> list[str]:
    if base_value == current_value:
        return []
    if isinstance(base_value, dict) and isinstance(current_value, dict):
        changed: list[str] = []
        for key in sorted(set(base_value) | set(current_value)):
            next_prefix = f"{prefix}.{key}" if prefix else str(key)
            changed.extend(
                _collect_story_bible_changed_fields(
                    base_value.get(key),
                    current_value.get(key),
                    prefix=next_prefix,
                )
            )
        return changed[:6]
    if isinstance(base_value, list) and isinstance(current_value, list):
        return [prefix or "value"]
    return [prefix or "value"]


def _apply_story_bible_section_payload(
    base_rows: list[dict[str, Any]],
    payload: dict[str, Any],
) -> list[dict[str, Any]]:
    mode = payload.get("mode")
    if mode != STORY_BIBLE_BRANCH_PAYLOAD_MODE_PATCH:
        return deepcopy(base_rows)

    base_entries = _story_bible_identity_entries(base_rows)
    if base_entries is None:
        return deepcopy(base_rows)

    current_map = {
        key: deepcopy(row)
        for key, row in base_entries
    }

    deletes = payload.get("deletes")
    if isinstance(deletes, list):
        for row_key in deletes:
            if isinstance(row_key, str):
                current_map.pop(row_key, None)

    patches = payload.get("patches")
    if isinstance(patches, list):
        for item in patches:
            if not isinstance(item, dict):
                continue
            row_key = item.get("entity_key")
            if not isinstance(row_key, str):
                continue
            current_row = current_map.get(row_key)
            if current_row is None:
                continue
            current_map[row_key] = _apply_story_bible_row_patch(
                current_row,
                changes=item.get("changes"),
                remove_fields=item.get("remove_fields"),
            )

    upserts = payload.get("upserts")
    if isinstance(upserts, list):
        for row in upserts:
            if not isinstance(row, dict):
                continue
            row_key = _story_bible_identity_key(row)
            if row_key is None:
                continue
            current_map[row_key] = deepcopy(row)

    ordered_keys: list[str] = []
    seen_keys: set[str] = set()
    order = payload.get("order")
    if isinstance(order, list):
        for row_key in order:
            if (
                isinstance(row_key, str)
                and row_key in current_map
                and row_key not in seen_keys
            ):
                ordered_keys.append(row_key)
                seen_keys.add(row_key)

    for row_key in current_map:
        if row_key not in seen_keys:
            ordered_keys.append(row_key)
            seen_keys.add(row_key)

    return [current_map[row_key] for row_key in ordered_keys]


def _build_story_bible_section_delta(
    base_rows: list[dict[str, Any]],
    current_rows: list[dict[str, Any]],
) -> Any:
    normalized_base_rows = [
        deepcopy(row)
        for row in base_rows
        if isinstance(row, dict)
    ]
    normalized_current_rows = [
        deepcopy(row)
        for row in current_rows
        if isinstance(row, dict)
    ]
    if normalized_base_rows == normalized_current_rows:
        return None

    base_entries = _story_bible_identity_entries(normalized_base_rows)
    current_entries = _story_bible_identity_entries(normalized_current_rows)
    if base_entries is None or current_entries is None:
        return normalized_current_rows

    base_map = {
        key: row
        for key, row in base_entries
    }
    current_map = {
        key: row
        for key, row in current_entries
    }

    upserts = [
        deepcopy(row)
        for key, row in current_entries
        if key not in base_map
    ]
    patches: list[dict[str, Any]] = []
    for key, row in current_entries:
        if key not in base_map:
            continue
        if base_map[key] == row:
            continue
        changes, remove_fields = _build_story_bible_row_patch(
            base_map[key],
            row,
        )
        patch_payload: dict[str, Any] = {"entity_key": key}
        if changes:
            patch_payload["changes"] = changes
        if remove_fields:
            patch_payload["remove_fields"] = remove_fields
        if len(patch_payload) > 1:
            patches.append(patch_payload)

    deletes = [
        key
        for key, _ in base_entries
        if key not in current_map
    ]

    payload: dict[str, Any] = {
        "mode": STORY_BIBLE_BRANCH_PAYLOAD_MODE_PATCH,
        "order": [key for key, _ in current_entries],
    }
    if upserts:
        payload["upserts"] = upserts
    if patches:
        payload["patches"] = patches
    if deletes:
        payload["deletes"] = deletes
    return payload


def _story_bible_identity_entries(
    rows: list[dict[str, Any]],
) -> Optional[list[tuple[str, dict[str, Any]]]]:
    entries: list[tuple[str, dict[str, Any]]] = []
    seen_keys: set[str] = set()
    for row in rows:
        row_key = _story_bible_identity_key(row)
        if row_key is None or row_key in seen_keys:
            return None
        seen_keys.add(row_key)
        entries.append((row_key, deepcopy(row)))
    return entries


def _story_bible_identity_key(row: dict[str, Any]) -> Optional[str]:
    for field in ("id", "key", "name", "title", "content"):
        value = row.get(field)
        if value:
            return f"{field}:{value}"
    return None


def _build_story_bible_row_patch(
    base_row: dict[str, Any],
    current_row: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    changes: dict[str, Any] = {}
    remove_fields: list[str] = []
    for key in sorted(set(base_row) | set(current_row)):
        if key not in current_row:
            remove_fields.append(key)
            continue
        if key not in base_row:
            changes[key] = deepcopy(current_row[key])
            continue
        if base_row[key] == current_row[key]:
            continue

        if isinstance(base_row[key], dict) and isinstance(current_row[key], dict):
            nested_changes, nested_remove_fields = _build_story_bible_row_patch(
                base_row[key],
                current_row[key],
            )
            if nested_changes:
                changes[key] = nested_changes
            remove_fields.extend(
                f"{key}.{field_path}"
                for field_path in nested_remove_fields
            )
            continue

        changes[key] = deepcopy(current_row[key])

    return changes, remove_fields


def _apply_story_bible_row_patch(
    row: dict[str, Any],
    *,
    changes: Any,
    remove_fields: Any,
) -> dict[str, Any]:
    next_row = deepcopy(row)
    if isinstance(changes, dict):
        _merge_story_bible_patch_dict(next_row, changes)
    if isinstance(remove_fields, list):
        for field_path in remove_fields:
            if isinstance(field_path, str) and field_path:
                _delete_story_bible_field_path(next_row, field_path)
    return next_row


def _merge_story_bible_patch_dict(
    target: dict[str, Any],
    changes: dict[str, Any],
) -> None:
    for key, value in changes.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _merge_story_bible_patch_dict(target[key], value)
            continue
        target[key] = deepcopy(value)


def _delete_story_bible_field_path(
    target: dict[str, Any],
    field_path: str,
) -> None:
    parts = [part for part in field_path.split(".") if part]
    if not parts:
        return
    current: Any = target
    for part in parts[:-1]:
        if not isinstance(current, dict):
            return
        current = current.get(part)
        if current is None:
            return
    if isinstance(current, dict):
        current.pop(parts[-1], None)


def _validate_story_bible_storage_section_key(section_key: str) -> str:
    if section_key not in STORY_BIBLE_SECTION_KEYS:
        raise AppError(
            code="project.story_bible_section_invalid",
            message="Story Bible section is invalid.",
            status_code=400,
        )
    return section_key


def _validate_story_bible_public_section_key(section_key: str) -> str:
    if section_key not in STORY_BIBLE_PUBLIC_SECTION_KEYS:
        raise AppError(
            code="project.story_bible_section_invalid",
            message="Story Bible section is invalid.",
            status_code=400,
        )
    return section_key


def normalize_story_bible_section_item(
    section_key: str,
    item_payload: dict[str, Any],
) -> dict[str, Any]:
    resolved_section_key = _validate_story_bible_public_section_key(section_key)
    model = STORY_BIBLE_PUBLIC_SECTION_ITEM_MODELS[resolved_section_key]
    try:
        item = model.model_validate(item_payload)
    except ValidationError as exc:
        raise AppError(
            code="project.story_bible_item_invalid",
            message=f"Story Bible item is invalid: {exc.errors()[0]['msg']}",
            status_code=400,
        ) from exc
    normalized_item = item.model_dump(mode="json")
    if _story_bible_identity_key(normalized_item) is None:
        raise AppError(
            code="project.story_bible_item_identity_missing",
            message="Story Bible item must contain a stable identity field.",
            status_code=400,
        )
    return normalized_item


def upsert_story_bible_section_item(
    rows: list[dict[str, Any]],
    *,
    section_key: str,
    item_payload: dict[str, Any],
) -> list[dict[str, Any]]:
    normalized_item = normalize_story_bible_section_item(section_key, item_payload)
    item_key = _story_bible_identity_key(normalized_item)
    if item_key is None:
        raise AppError(
            code="project.story_bible_item_identity_missing",
            message="Story Bible item must contain a stable identity field.",
            status_code=400,
        )
    next_rows = [
        deepcopy(row)
        for row in rows
        if isinstance(row, dict)
    ]
    for index, row in enumerate(next_rows):
        row_key = _story_bible_identity_key(row)
        if row_key == item_key:
            next_rows[index] = normalized_item
            return next_rows
    next_rows.append(normalized_item)
    return next_rows


def delete_story_bible_section_item(
    rows: list[dict[str, Any]],
    *,
    section_key: str,
    entity_key: str,
) -> list[dict[str, Any]]:
    _validate_story_bible_public_section_key(section_key)
    next_rows = [
        deepcopy(row)
        for row in rows
        if isinstance(row, dict)
    ]
    filtered_rows = [
        row
        for row in next_rows
        if _story_bible_identity_key(row) != entity_key
    ]
    if len(filtered_rows) == len(next_rows):
        raise AppError(
            code="project.story_bible_item_not_found",
            message="Story Bible item not found in current branch scope.",
            status_code=404,
        )
    return filtered_rows


async def _persist_branch_story_bible_sections(
    session: AsyncSession,
    *,
    project: Project,
    branch: ProjectBranch,
    branch_story_bible: Optional[ProjectBranchStoryBible],
    base_sections: dict[str, list[dict[str, Any]]],
    current_sections: dict[str, list[dict[str, Any]]],
    actor_user_id: Optional[UUID] = None,
    changed_section_override: str | None = None,
    old_value_override: dict[str, Any] | None = None,
    new_value_override: dict[str, Any] | None = None,
) -> None:
    snapshot_payload = build_story_bible_branch_delta_payload(
        base_sections,
        current_sections,
    )
    if not snapshot_payload:
        if branch_story_bible is not None:
            await session.delete(branch_story_bible)
        return

    old_payload = branch_story_bible.payload if branch_story_bible else None
    if branch_story_bible is None:
        session.add(
            ProjectBranchStoryBible(
                project_id=project.id,
                branch_id=branch.id,
                payload=snapshot_payload,
            )
        )
        change_type = StoryBibleChangeType.ADDED
    else:
        branch_story_bible.payload = snapshot_payload
        change_type = StoryBibleChangeType.UPDATED

    for section_key in STORY_BIBLE_SECTION_KEYS:
        old_section = (old_payload or {}).get(section_key, [])
        new_section = snapshot_payload.get(section_key, [])
        if old_section != new_section:
            changed_section_key = changed_section_override or section_key
            await _record_story_bible_change(
                session,
                project.id,
                branch.id,
                change_type=change_type,
                changed_section=StoryBibleSection(changed_section_key),
                old_value=old_value_override or {changed_section_key: old_section},
                new_value=new_value_override or {changed_section_key: new_section},
                snapshot=snapshot_payload,
                note=f"{change_type.value} {changed_section_key}",
                created_by=actor_user_id,
            )
            break


def _normalize_story_bible_branch_item_upsert_request(
    payload: StoryBibleBranchItemUpsert,
) -> dict[str, Any]:
    logical_section_key = _validate_story_bible_public_section_key(payload.section_key)
    return {
        "logical_section_key": logical_section_key,
        "storage_section_key": logical_section_key,
        "storage_item_payload": payload.item,
    }


def _normalize_story_bible_branch_item_delete_request(
    payload: StoryBibleBranchItemDelete,
) -> dict[str, Any]:
    logical_section_key = _validate_story_bible_public_section_key(payload.section_key)
    return {
        "logical_section_key": logical_section_key,
        "storage_section_key": logical_section_key,
        "storage_entity_key": payload.entity_key,
    }


async def upsert_story_bible_branch_item(
    session: AsyncSession,
    project: Project,
    payload: StoryBibleBranchItemUpsert,
    *,
    actor_user_id: UUID,
    branch_id: UUID,
) -> StoryBibleRead:
    normalized_request = _normalize_story_bible_branch_item_upsert_request(payload)
    branch = await _get_project_branch(session, project.id, branch_id)
    resolution = await resolve_story_bible_resolution(
        session,
        project,
        branch=branch,
    )
    public_sections_before = build_public_story_bible_sections(resolution.sections)
    current_sections = {
        key: deepcopy(resolution.sections.get(key, []))
        for key in STORY_BIBLE_SECTION_KEYS
    }
    logical_section_key = normalized_request["logical_section_key"]
    current_sections[normalized_request["storage_section_key"]] = upsert_story_bible_section_item(
        current_sections.get(normalized_request["storage_section_key"], []),
        section_key=normalized_request["storage_section_key"],
        item_payload=normalized_request["storage_item_payload"],
    )
    public_sections_after = build_public_story_bible_sections(current_sections)
    await _persist_branch_story_bible_sections(
        session,
        project=project,
        branch=branch,
        branch_story_bible=resolution.branch_story_bible,
        base_sections=resolution.base_sections,
        current_sections=current_sections,
        actor_user_id=actor_user_id,
        changed_section_override=normalized_request["logical_section_key"],
        old_value_override={
            normalized_request["logical_section_key"]: public_sections_before.get(
                normalized_request["logical_section_key"],
                [],
            )
        },
        new_value_override={
            normalized_request["logical_section_key"]: public_sections_after.get(
                normalized_request["logical_section_key"],
                [],
            )
        },
    )
    await _invalidate_story_bible_related_chapter_evaluations(
        session,
        project,
        reason=(
            f'The Story Bible snapshot for branch "{branch.title}" changed after the latest evaluation.'
        ),
        branch_ids=_branch_and_descendant_ids(project.branches, branch.id),
    )
    await session.commit()
    refreshed = await get_owned_project(
        session,
        project.id,
        actor_user_id,
        with_relations=True,
    )
    return await build_story_bible_payload(
        session,
        refreshed,
        branch_id=branch.id,
    )


async def delete_story_bible_branch_item(
    session: AsyncSession,
    project: Project,
    payload: StoryBibleBranchItemDelete,
    *,
    actor_user_id: UUID,
    branch_id: UUID,
) -> StoryBibleRead:
    normalized_request = _normalize_story_bible_branch_item_delete_request(payload)
    branch = await _get_project_branch(session, project.id, branch_id)
    resolution = await resolve_story_bible_resolution(
        session,
        project,
        branch=branch,
    )
    public_sections_before = build_public_story_bible_sections(resolution.sections)
    current_sections = {
        key: deepcopy(resolution.sections.get(key, []))
        for key in STORY_BIBLE_SECTION_KEYS
    }
    logical_section_key = normalized_request["logical_section_key"]
    current_sections[normalized_request["storage_section_key"]] = delete_story_bible_section_item(
        current_sections.get(normalized_request["storage_section_key"], []),
        section_key=normalized_request["storage_section_key"],
        entity_key=normalized_request["storage_entity_key"],
    )
    public_sections_after = build_public_story_bible_sections(current_sections)
    await _persist_branch_story_bible_sections(
        session,
        project=project,
        branch=branch,
        branch_story_bible=resolution.branch_story_bible,
        base_sections=resolution.base_sections,
        current_sections=current_sections,
        actor_user_id=actor_user_id,
        changed_section_override=normalized_request["logical_section_key"],
        old_value_override={
            normalized_request["logical_section_key"]: public_sections_before.get(
                normalized_request["logical_section_key"],
                [],
            )
        },
        new_value_override={
            normalized_request["logical_section_key"]: public_sections_after.get(
                normalized_request["logical_section_key"],
                [],
            )
        },
    )
    await _invalidate_story_bible_related_chapter_evaluations(
        session,
        project,
        reason=(
            f'The Story Bible snapshot for branch "{branch.title}" changed after the latest evaluation.'
        ),
        branch_ids=_branch_and_descendant_ids(project.branches, branch.id),
    )
    await session.commit()
    refreshed = await get_owned_project(
        session,
        project.id,
        actor_user_id,
        with_relations=True,
    )
    return await build_story_bible_payload(
        session,
        refreshed,
        branch_id=branch.id,
    )


async def create_project_volume(
    session: AsyncSession,
    project: Project,
    payload: ProjectVolumeCreate,
) -> ProjectVolume:
    await ensure_project_structure(session, project)
    volumes = await _list_project_volumes(session, project.id)
    volume_number = payload.volume_number or max(
        (item.volume_number for item in volumes),
        default=0,
    ) + 1
    if any(item.volume_number == volume_number for item in volumes):
        raise AppError(
            code="project.volume_number_conflict",
            message="Volume number already exists in this project.",
            status_code=409,
        )

    volume = ProjectVolume(
        project_id=project.id,
        volume_number=volume_number,
        title=payload.title.strip(),
        summary=payload.summary,
        status=payload.status,
    )
    session.add(volume)
    await session.commit()
    await session.refresh(volume)
    return volume


async def update_project_volume(
    session: AsyncSession,
    project: Project,
    volume_id: UUID,
    payload: ProjectVolumeUpdate,
) -> ProjectVolume:
    await ensure_project_structure(session, project)
    volume = await _get_project_volume(session, project.id, volume_id)
    data = payload.model_dump(exclude_unset=True)

    if "volume_number" in data and data["volume_number"] != volume.volume_number:
        existing = await session.execute(
            select(ProjectVolume.id).where(
                ProjectVolume.project_id == project.id,
                ProjectVolume.volume_number == data["volume_number"],
                ProjectVolume.id != volume.id,
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise AppError(
                code="project.volume_number_conflict",
                message="Volume number already exists in this project.",
                status_code=409,
            )

    for field, value in data.items():
        if field == "title" and value is not None:
            value = value.strip()
        setattr(volume, field, value)

    await session.commit()
    await session.refresh(volume)
    return volume


async def create_project_branch(
    session: AsyncSession,
    project: Project,
    payload: ProjectBranchCreate,
) -> ProjectBranch:
    await ensure_project_structure(session, project)
    branches = await _list_project_branches(session, project.id)
    existing_keys = {branch.key for branch in branches}

    if payload.key:
        branch_key = _normalize_branch_key(payload.key)
        if not branch_key:
            raise AppError(
                code="project.branch_key_invalid",
                message="Branch key is invalid.",
                status_code=400,
            )
        if branch_key in existing_keys:
            raise AppError(
                code="project.branch_key_conflict",
                message="Branch key already exists in this project.",
                status_code=409,
            )
    else:
        branch_key = _generate_unique_branch_key(payload.title, existing_keys)

    source_branch = None
    if payload.source_branch_id is not None:
        source_branch = await _get_project_branch(
            session,
            project.id,
            payload.source_branch_id,
        )
    elif payload.copy_chapters and branches:
        source_branch = _resolve_default_branch(branches)

    if payload.is_default:
        for existing_branch in branches:
            existing_branch.is_default = False

    branch = ProjectBranch(
        project_id=project.id,
        source_branch_id=source_branch.id if source_branch is not None else None,
        key=branch_key,
        title=payload.title.strip(),
        description=payload.description,
        status=payload.status,
        is_default=payload.is_default,
    )
    session.add(branch)
    await session.flush()

    if payload.copy_chapters and source_branch is not None:
        await _clone_branch_chapters(session, source_branch, branch)
    if source_branch is not None:
        await _clone_branch_story_bible_snapshot(session, source_branch, branch)

    await session.commit()
    await session.refresh(branch)
    return branch


async def update_project_branch(
    session: AsyncSession,
    project: Project,
    branch_id: UUID,
    payload: ProjectBranchUpdate,
) -> ProjectBranch:
    await ensure_project_structure(session, project)
    branch = await _get_project_branch(session, project.id, branch_id)
    branches = await _list_project_branches(session, project.id)
    data = payload.model_dump(exclude_unset=True)

    desired_default = data.pop("is_default", None) if "is_default" in data else None
    for field, value in data.items():
        if field == "title" and value is not None:
            value = value.strip()
        setattr(branch, field, value)

    if desired_default is True:
        for item in branches:
            item.is_default = item.id == branch.id
    elif desired_default is False and branch.is_default:
        branch.is_default = False
        fallback = next((item for item in branches if item.id != branch.id), None)
        if fallback is None:
            branch.is_default = True
        else:
            fallback.is_default = True

    await session.commit()
    await session.refresh(branch)
    return branch


async def replace_story_bible(
    session: AsyncSession,
    project: Project,
    payload: StoryBibleUpdate,
    *,
    actor_user_id: UUID,
    branch_id: Optional[UUID] = None,
) -> StoryBibleRead:
    if branch_id is None and payload.project is not None:
        for field, value in payload.project.model_dump(exclude_unset=True).items():
            setattr(project, field, value)

    if branch_id is not None:
        branch = await _get_project_branch(session, project.id, branch_id)
        resolution = await resolve_story_bible_resolution(
            session,
            project,
            branch=branch,
        )
        current_sections = {
            "characters": [item.model_dump(mode="json") for item in payload.characters],
            "world_settings": [item.model_dump(mode="json") for item in payload.world_settings],
            "items": [item.model_dump(mode="json") for item in payload.items],
            "factions": [item.model_dump(mode="json") for item in payload.factions],
            "locations": [item.model_dump(mode="json") for item in payload.locations],
            "plot_threads": [item.model_dump(mode="json") for item in payload.plot_threads],
            "foreshadowing": [
                item.model_dump(mode="json") for item in payload.foreshadowing
            ],
            "timeline_events": [
                item.model_dump(mode="json") for item in payload.timeline_events
            ],
        }
        await _persist_branch_story_bible_sections(
            session,
            project=project,
            branch=branch,
            branch_story_bible=resolution.branch_story_bible,
            base_sections=resolution.base_sections,
            current_sections=current_sections,
            actor_user_id=actor_user_id,
        )

        await _invalidate_story_bible_related_chapter_evaluations(
            session,
            project,
            reason=(
                f'The Story Bible snapshot for branch "{branch.title}" changed after the latest evaluation.'
            ),
            branch_ids=_branch_and_descendant_ids(project.branches, branch.id),
        )
        await session.commit()
        refreshed = await get_owned_project(
            session,
            project.id,
            actor_user_id,
            with_relations=True,
        )
        return await build_story_bible_payload(
            session,
            refreshed,
            branch_id=branch.id,
        )

    await _replace_related_items(
        session,
        project.id,
        Character,
        [
            {
                "id": item.id,
                "project_id": project.id,
                "name": item.name,
                "data": item.data,
                "version": item.version,
                "created_chapter": item.created_chapter,
            }
            for item in payload.characters
        ],
    )
    await _replace_related_items(
        session,
        project.id,
        WorldSetting,
        [
            {
                "id": item.get("id"),
                "project_id": project.id,
                "key": item["key"],
                "title": item["title"],
                "data": item["data"],
                "version": item.get("version", 1),
            }
            for item in [item.model_dump(mode="json") for item in payload.world_settings]
        ],
    )
    await _replace_related_items(
        session,
        project.id,
        ProjectItem,
        [
            {
                "project_id": project.id,
                "key": item.key,
                "name": item.name,
                "item_type": item.type,
                "rarity": item.rarity,
                "description": item.description,
                "effects": item.effects,
                "owner": item.owner,
                "location": item.location,
                "status": item.status,
                "introduced_chapter": item.introduced_chapter,
                "forbidden_holders": item.forbidden_holders,
                "version": item.version,
            }
            for item in payload.items
        ],
    )
    await _replace_related_items(
        session,
        project.id,
        ProjectFaction,
        [
            {
                "project_id": project.id,
                "key": item.key,
                "name": item.name,
                "faction_type": item.type,
                "scale": item.scale,
                "description": item.description,
                "goals": item.goals,
                "leader": item.leader,
                "members": item.members,
                "territory": item.territory,
                "resources": item.resources,
                "ideology": item.ideology,
                "version": item.version,
            }
            for item in payload.factions
        ],
    )
    await _replace_related_items(
        session,
        project.id,
        Location,
        [
            {
                "id": item.id,
                "project_id": project.id,
                "name": item.name,
                "data": item.data,
                "version": item.version,
            }
            for item in payload.locations
        ],
    )
    await _replace_related_items(
        session,
        project.id,
        PlotThread,
        [
            {
                "id": item.id,
                "project_id": project.id,
                "title": item.title,
                "status": item.status,
                "importance": item.importance,
                "data": item.data,
            }
            for item in payload.plot_threads
        ],
    )
    await _replace_related_items(
        session,
        project.id,
        Foreshadowing,
        [
            {
                "id": item.id,
                "project_id": project.id,
                "content": item.content,
                "planted_chapter": item.planted_chapter,
                "payoff_chapter": item.payoff_chapter,
                "status": item.status,
                "importance": item.importance,
            }
            for item in payload.foreshadowing
        ],
    )
    await _replace_related_items(
        session,
        project.id,
        TimelineEvent,
        [
            {
                "id": item.id,
                "project_id": project.id,
                "chapter_number": item.chapter_number,
                "title": item.title,
                "data": item.data,
            }
            for item in payload.timeline_events
        ],
    )
    await _invalidate_story_bible_related_chapter_evaluations(
        session,
        project,
        reason="The project Story Bible changed after the latest evaluation.",
    )

    await session.commit()
    refreshed = await get_owned_project(
        session,
        project.id,
        actor_user_id,
        with_relations=True,
    )
    return await build_story_bible_payload(
        session,
        refreshed,
    )


async def _invalidate_story_bible_related_chapter_evaluations(
    session: AsyncSession,
    project: Project,
    *,
    reason: str,
    branch_ids: Optional[set[UUID]] = None,
) -> None:
    statement = select(Chapter).where(Chapter.project_id == project.id)
    if branch_ids:
        statement = statement.where(Chapter.branch_id.in_(branch_ids))

    result = await session.execute(statement)
    for chapter in result.scalars().all():
        chapter.quality_metrics = mark_quality_metrics_stale(
            chapter.quality_metrics,
            reason=reason,
        )


async def _record_story_bible_change(
    session: AsyncSession,
    project_id: UUID,
    branch_id: UUID,
    *,
    change_type: StoryBibleChangeType,
    changed_section: StoryBibleSection,
    old_value: dict[str, Any] | None = None,
    new_value: dict[str, Any] | None = None,
    snapshot: dict[str, Any],
    changed_entity_id: UUID | None = None,
    changed_entity_key: str | None = None,
    note: str | None = None,
    created_by: UUID | None = None,
) -> None:
    from models.story_bible_version import StoryBibleVersion

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
        change_source=StoryBibleChangeSource.USER.value,
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


def _branch_and_descendant_ids(
    branches: list[ProjectBranch],
    branch_id: UUID,
) -> set[UUID]:
    affected_branch_ids = {branch_id}
    frontier = {branch_id}

    while frontier:
        next_frontier = {
            branch.id
            for branch in branches
            if branch.source_branch_id in frontier and branch.id not in affected_branch_ids
        }
        if not next_frontier:
            break
        affected_branch_ids.update(next_frontier)
        frontier = next_frontier

    return affected_branch_ids


async def ensure_project_structure(
    session: AsyncSession,
    project: Project,
) -> bool:
    changed = False
    volumes = await _list_project_volumes(session, project.id)
    if not volumes:
        default_volume = ProjectVolume(
            project_id=project.id,
            volume_number=1,
            title=DEFAULT_VOLUME_TITLE,
            status="planning",
        )
        session.add(default_volume)
        await session.flush()
        volumes = [default_volume]
        changed = True

    default_volume = volumes[0]
    branches = await _list_project_branches(session, project.id)
    if not branches:
        default_branch = ProjectBranch(
            project_id=project.id,
            key=DEFAULT_BRANCH_KEY,
            title=DEFAULT_BRANCH_TITLE,
            status="active",
            is_default=True,
        )
        session.add(default_branch)
        await session.flush()
        branches = [default_branch]
        changed = True

    default_branch = _resolve_default_branch(branches)
    for branch in branches:
        should_be_default = branch.id == default_branch.id
        if branch.is_default != should_be_default:
            branch.is_default = should_be_default
            changed = True

    missing_result = await session.execute(
        select(Chapter).where(
            Chapter.project_id == project.id,
            or_(
                Chapter.volume_id.is_(None),
                Chapter.branch_id.is_(None),
            ),
        )
    )
    missing_chapters = list(missing_result.scalars().all())
    for chapter in missing_chapters:
        if chapter.volume_id is None:
            chapter.volume_id = default_volume.id
            changed = True
        if chapter.branch_id is None:
            chapter.branch_id = default_branch.id
            changed = True

    if changed:
        await session.flush()
    return changed


async def _normalize_project_story_bible_storage(
    session: AsyncSession,
    project: Project,
) -> bool:
    changed = await _migrate_project_story_bible_wrappers_to_native(
        session,
        project,
    )

    branch_story_bible_result = await session.execute(
        select(ProjectBranchStoryBible).where(
            ProjectBranchStoryBible.project_id == project.id,
        )
    )
    branch_story_bibles = {
        snapshot.branch_id: snapshot
        for snapshot in branch_story_bible_result.scalars().all()
    }
    if not branch_story_bibles:
        return changed

    branch_resolution_cache: dict[UUID, StoryBibleResolution] = {}
    branch_story_bible_cache: dict[UUID, Optional[ProjectBranchStoryBible]] = {
        branch.id: branch_story_bibles.get(branch.id)
        for branch in project.branches
    }

    for branch in project.branches:
        branch_story_bible = branch_story_bible_cache.get(branch.id)
        if branch_story_bible is None or not isinstance(branch_story_bible.payload, dict):
            continue
        resolution = await resolve_story_bible_resolution(
            session,
            project,
            branch=branch,
            branch_story_bible_cache=branch_story_bible_cache,
            branch_resolution_cache=branch_resolution_cache,
        )
        canonical_payload = canonicalize_story_bible_branch_payload(
            resolution.base_sections,
            branch_story_bible.payload,
        )
        if not canonical_payload:
            await session.delete(branch_story_bible)
            branch_story_bible_cache[branch.id] = None
            changed = True
            continue
        if canonical_payload != branch_story_bible.payload:
            branch_story_bible.payload = canonical_payload
            changed = True

    if changed:
        await session.flush()
    return changed


async def _migrate_project_story_bible_wrappers_to_native(
    session: AsyncSession,
    project: Project,
) -> bool:
    changed = False
    native_item_keys = {
        str(item.key).strip().lower()
        for item in project.items
        if str(getattr(item, "key", "")).strip()
    }
    native_item_names = {
        str(item.name).strip().lower()
        for item in project.items
        if str(getattr(item, "name", "")).strip()
    }
    native_faction_keys = {
        str(item.key).strip().lower()
        for item in project.factions
        if str(getattr(item, "key", "")).strip()
    }
    native_faction_names = {
        str(item.name).strip().lower()
        for item in project.factions
        if str(getattr(item, "name", "")).strip()
    }

    next_world_settings: list[WorldSetting] = []
    for world_setting in list(project.world_settings):
        serialized_row = {
            "id": str(world_setting.id),
            "key": world_setting.key,
            "title": world_setting.title,
            "data": world_setting.data,
            "version": world_setting.version,
        }
        if _is_story_bible_item_wrapper(serialized_row):
            candidate = _build_project_item_from_legacy_world_setting(world_setting)
            if candidate is not None:
                candidate_key = str(candidate.key).strip().lower()
                candidate_name = str(candidate.name).strip().lower()
                if candidate_key not in native_item_keys and candidate_name not in native_item_names:
                    session.add(candidate)
                    project.items.append(candidate)
                    if candidate_key:
                        native_item_keys.add(candidate_key)
                    if candidate_name:
                        native_item_names.add(candidate_name)
            await session.delete(world_setting)
            changed = True
            continue
        if _is_story_bible_faction_wrapper(serialized_row):
            candidate = _build_project_faction_from_legacy_world_setting(world_setting)
            if candidate is not None:
                candidate_key = str(candidate.key).strip().lower()
                candidate_name = str(candidate.name).strip().lower()
                if (
                    candidate_key not in native_faction_keys
                    and candidate_name not in native_faction_names
                ):
                    session.add(candidate)
                    project.factions.append(candidate)
                    if candidate_key:
                        native_faction_keys.add(candidate_key)
                    if candidate_name:
                        native_faction_names.add(candidate_name)
            await session.delete(world_setting)
            changed = True
            continue
        next_world_settings.append(world_setting)

    if changed:
        project.world_settings = next_world_settings
    return changed


def _build_project_item_from_legacy_world_setting(
    world_setting: WorldSetting,
) -> ProjectItem | None:
    try:
        payload = _world_setting_wrapper_to_item_entry(
            {
                "id": str(world_setting.id),
                "key": world_setting.key,
                "title": world_setting.title,
                "data": world_setting.data,
                "version": world_setting.version,
            }
        )
    except ValidationError:
        return None
    return ProjectItem(
        id=world_setting.id,
        project_id=world_setting.project_id,
        key=payload["key"],
        name=payload["name"],
        item_type=payload.get("type"),
        rarity=payload.get("rarity"),
        description=payload.get("description"),
        effects=_clean_story_bible_string_list(payload.get("effects")),
        owner=payload.get("owner"),
        location=payload.get("location"),
        status=payload.get("status"),
        introduced_chapter=payload.get("introduced_chapter"),
        forbidden_holders=_clean_story_bible_string_list(payload.get("forbidden_holders")),
        version=int(payload.get("version") or 1),
        created_at=world_setting.created_at,
        updated_at=world_setting.updated_at,
    )


def _build_project_faction_from_legacy_world_setting(
    world_setting: WorldSetting,
) -> ProjectFaction | None:
    try:
        payload = _world_setting_wrapper_to_faction_entry(
            {
                "id": str(world_setting.id),
                "key": world_setting.key,
                "title": world_setting.title,
                "data": world_setting.data,
                "version": world_setting.version,
            }
        )
    except ValidationError:
        return None
    return ProjectFaction(
        id=world_setting.id,
        project_id=world_setting.project_id,
        key=payload["key"],
        name=payload["name"],
        faction_type=payload.get("type"),
        scale=payload.get("scale"),
        description=payload.get("description"),
        goals=payload.get("goals"),
        leader=payload.get("leader"),
        members=_clean_story_bible_string_list(payload.get("members")),
        territory=payload.get("territory"),
        resources=_clean_story_bible_string_list(payload.get("resources")),
        ideology=payload.get("ideology"),
        version=int(payload.get("version") or 1),
        created_at=world_setting.created_at,
        updated_at=world_setting.updated_at,
    )


async def resolve_project_structure_scope(
    session: AsyncSession,
    project: Project,
    *,
    volume_id: Optional[UUID] = None,
    branch_id: Optional[UUID] = None,
) -> tuple[ProjectVolume, ProjectBranch]:
    await ensure_project_structure(session, project)
    volumes = await _list_project_volumes(session, project.id)
    branches = await _list_project_branches(session, project.id)
    default_volume = volumes[0]
    default_branch = _resolve_default_branch(branches)

    volume = default_volume
    if volume_id is not None:
        volume = next((item for item in volumes if item.id == volume_id), None)
        if volume is None:
            raise AppError(
                code="project.volume_not_found",
                message="Project volume not found.",
                status_code=404,
            )

    branch = default_branch
    if branch_id is not None:
        branch = next((item for item in branches if item.id == branch_id), None)
        if branch is None:
            raise AppError(
                code="project.branch_not_found",
                message="Project branch not found.",
                status_code=404,
            )

    return volume, branch


async def _replace_related_items(
    session: AsyncSession,
    project_id: UUID,
    model: type,
    rows: list[dict[str, Any]],
) -> None:
    await session.execute(delete(model).where(model.project_id == project_id))
    for row in rows:
        clean_row = {key: value for key, value in row.items() if value is not None}
        session.add(model(**clean_row))


async def _list_project_volumes(
    session: AsyncSession,
    project_id: UUID,
) -> list[ProjectVolume]:
    result = await session.execute(
        select(ProjectVolume)
        .where(ProjectVolume.project_id == project_id)
        .order_by(ProjectVolume.volume_number.asc())
    )
    return list(result.scalars().all())


async def _list_project_branches(
    session: AsyncSession,
    project_id: UUID,
) -> list[ProjectBranch]:
    result = await session.execute(
        select(ProjectBranch)
        .where(ProjectBranch.project_id == project_id)
        .order_by(ProjectBranch.created_at.asc())
    )
    return list(result.scalars().all())


async def _get_project_volume(
    session: AsyncSession,
    project_id: UUID,
    volume_id: UUID,
) -> ProjectVolume:
    result = await session.execute(
        select(ProjectVolume).where(
            ProjectVolume.id == volume_id,
            ProjectVolume.project_id == project_id,
        )
    )
    volume = result.scalar_one_or_none()
    if volume is None:
        raise AppError(
            code="project.volume_not_found",
            message="Project volume not found.",
            status_code=404,
        )
    return volume


async def _get_project_branch(
    session: AsyncSession,
    project_id: UUID,
    branch_id: UUID,
) -> ProjectBranch:
    result = await session.execute(
        select(ProjectBranch).where(
            ProjectBranch.id == branch_id,
            ProjectBranch.project_id == project_id,
        )
    )
    branch = result.scalar_one_or_none()
    if branch is None:
        raise AppError(
            code="project.branch_not_found",
            message="Project branch not found.",
            status_code=404,
        )
    return branch


async def get_project_branch_story_bible(
    session: AsyncSession,
    project_id: UUID,
    branch_id: UUID,
) -> Optional[ProjectBranchStoryBible]:
    result = await session.execute(
        select(ProjectBranchStoryBible).where(
            ProjectBranchStoryBible.project_id == project_id,
            ProjectBranchStoryBible.branch_id == branch_id,
        )
    )
    return result.scalar_one_or_none()


async def _get_project_collaborator(
    session: AsyncSession,
    project_id: UUID,
    collaborator_id: UUID,
) -> ProjectCollaborator:
    result = await session.execute(
        select(ProjectCollaborator)
        .where(
            ProjectCollaborator.project_id == project_id,
            ProjectCollaborator.id == collaborator_id,
        )
        .options(
            selectinload(ProjectCollaborator.user),
            selectinload(ProjectCollaborator.added_by),
        )
    )
    collaborator = result.scalar_one_or_none()
    if collaborator is None:
        raise AppError(
            code="project.collaborator_not_found",
            message="Project collaborator not found.",
            status_code=404,
        )
    return collaborator


async def _clone_branch_chapters(
    session: AsyncSession,
    source_branch: ProjectBranch,
    target_branch: ProjectBranch,
) -> None:
    result = await session.execute(
        select(Chapter)
        .where(
            Chapter.project_id == source_branch.project_id,
            Chapter.branch_id == source_branch.id,
        )
        .options(selectinload(Chapter.versions))
        .order_by(Chapter.volume_id.asc(), Chapter.chapter_number.asc())
    )
    source_chapters = list(result.scalars().all())
    for source_chapter in source_chapters:
        cloned_chapter = Chapter(
            project_id=source_chapter.project_id,
            volume_id=source_chapter.volume_id,
            branch_id=target_branch.id,
            chapter_number=source_chapter.chapter_number,
            title=source_chapter.title,
            content=source_chapter.content,
            outline=deepcopy(source_chapter.outline),
            word_count=source_chapter.word_count,
            current_version_number=int(
                getattr(source_chapter, "current_version_number", 1) or 1
            ),
            status=source_chapter.status,
            quality_metrics=deepcopy(source_chapter.quality_metrics),
        )
        session.add(cloned_chapter)
        await session.flush()

        if source_chapter.versions:
            for version in source_chapter.versions:
                session.add(
                    ChapterVersion(
                        chapter_id=cloned_chapter.id,
                        version_number=version.version_number,
                        content=version.content,
                        change_reason=version.change_reason,
                    )
                )
            continue

        session.add(
            ChapterVersion(
                chapter_id=cloned_chapter.id,
                version_number=1,
                content=cloned_chapter.content,
                change_reason=f"Cloned from branch {source_branch.title}",
            )
        )


async def _clone_branch_story_bible_snapshot(
    session: AsyncSession,
    source_branch: ProjectBranch,
    target_branch: ProjectBranch,
) -> None:
    snapshot = await get_project_branch_story_bible(
        session,
        source_branch.project_id,
        source_branch.id,
    )
    if snapshot is None:
        return
    session.add(
        ProjectBranchStoryBible(
            project_id=target_branch.project_id,
            branch_id=target_branch.id,
            payload=deepcopy(snapshot.payload),
        )
    )


def _resolve_default_branch(branches: list[ProjectBranch]) -> ProjectBranch:
    default_branch = next((branch for branch in branches if branch.is_default), None)
    if default_branch is not None:
        return default_branch
    main_branch = next((branch for branch in branches if branch.key == DEFAULT_BRANCH_KEY), None)
    if main_branch is not None:
        return main_branch
    return branches[0]


def _normalize_branch_key(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.strip().lower())
    return normalized.strip("-")


def _generate_unique_branch_key(title: str, existing_keys: set[str]) -> str:
    base_key = _normalize_branch_key(title) or "branch"
    if base_key not in existing_keys:
        return base_key

    suffix = 2
    while f"{base_key}-{suffix}" in existing_keys:
        suffix += 1
    return f"{base_key}-{suffix}"


def _normalize_collaborator_role(role: str) -> str:
    normalized = role.strip().lower()
    if normalized not in COLLABORATOR_ROLES:
        raise AppError(
            code="project.collaborator_role_invalid",
            message="Collaborator role is invalid.",
            status_code=400,
        )
    return normalized


def _assert_project_permission(role: str, permission: str) -> None:
    if project_role_has_permission(role, permission):
        return
    raise AppError(
        code="project.permission_denied",
        message="You do not have permission to access this project.",
        status_code=403,
        metadata={"required_permission": permission, "current_role": role},
    )


def project_role_has_permission(role: str, permission: str) -> bool:
    return permission in ROLE_PERMISSIONS.get(role, set())


def _apply_project_access_metadata(project: Project, role: str) -> None:
    setattr(project, "access_role", role)
    setattr(project, "owner_email", getattr(project.user, "email", None))
    setattr(project, "collaborator_count", len(getattr(project, "collaborators", []) or []))
    setattr(project, "has_bootstrap_profile", bool(getattr(project, "bootstrap_profile", None)))
    setattr(project, "has_novel_blueprint", bool(getattr(project, "novel_blueprint", None)))
