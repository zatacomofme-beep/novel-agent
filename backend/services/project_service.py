from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import re
from typing import Any
from typing import Optional
from uuid import UUID

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
from models.project import Project
from models.project_branch import ProjectBranch
from models.project_collaborator import ProjectCollaborator
from models.project_volume import ProjectVolume
from models.timeline_event import TimelineEvent
from models.world_setting import WorldSetting
from schemas.project import (
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
    StoryBibleUpdate,
)
from services.auth_service import get_user_by_email


DEFAULT_VOLUME_TITLE = "第一卷"
DEFAULT_BRANCH_TITLE = "主线"
DEFAULT_BRANCH_KEY = "main"
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


PROJECT_RELATIONS = (
    selectinload(Project.user),
    selectinload(Project.characters),
    selectinload(Project.world_settings),
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
    if changed:
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
    project = Project(user_id=user_id, **payload.model_dump())
    session.add(project)
    await session.flush()
    await ensure_project_structure(session, project)
    await session.commit()
    await session.refresh(project)
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
) -> Project:
    if payload.project is not None:
        for field, value in payload.project.model_dump(exclude_unset=True).items():
            setattr(project, field, value)

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
                "id": item.id,
                "project_id": project.id,
                "key": item.key,
                "title": item.title,
                "data": item.data,
                "version": item.version,
            }
            for item in payload.world_settings
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

    await session.commit()
    return await get_owned_project(
        session,
        project.id,
        actor_user_id,
        with_relations=True,
    )


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
