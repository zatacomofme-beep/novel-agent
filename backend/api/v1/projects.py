from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user, get_db_session
from models.user import User
from schemas.project import (
    ProjectBranchCreate,
    ProjectBranchUpdate,
    ProjectCollaborationRead,
    ProjectCollaboratorCreate,
    ProjectCollaboratorUpdate,
    ProjectCreate,
    ProjectRead,
    ProjectStructureRead,
    ProjectUpdate,
    ProjectVolumeCreate,
    ProjectVolumeUpdate,
    StoryBibleRead,
    StoryBibleUpdate,
)
from services.project_service import (
    create_project_branch,
    create_project,
    add_project_collaborator,
    create_project_volume,
    delete_project,
    get_project_collaboration,
    get_project_structure,
    get_owned_project,
    list_projects,
    PROJECT_PERMISSION_DELETE,
    PROJECT_PERMISSION_EDIT,
    PROJECT_PERMISSION_MANAGE_COLLABORATORS,
    PROJECT_PERMISSION_READ,
    replace_story_bible,
    remove_project_collaborator,
    update_project_collaborator,
    update_project_branch,
    update_project,
    update_project_volume,
)
from services.export_service import (
    ExportFormat,
    build_export_response,
    build_project_export_filename,
    render_project_export,
)


router = APIRouter()


@router.get("", response_model=list[ProjectRead])
async def project_list(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[ProjectRead]:
    projects = await list_projects(session, current_user.id)
    return [ProjectRead.model_validate(project) for project in projects]


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
async def project_create(
    payload: ProjectCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ProjectRead:
    project = await create_project(session, current_user.id, payload)
    return ProjectRead.model_validate(project)


@router.get("/{project_id}", response_model=ProjectRead)
async def project_detail(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ProjectRead:
    project = await get_owned_project(
        session,
        project_id,
        current_user.id,
        permission=PROJECT_PERMISSION_READ,
    )
    return ProjectRead.model_validate(project)


@router.patch("/{project_id}", response_model=ProjectRead)
async def project_patch(
    project_id: UUID,
    payload: ProjectUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ProjectRead:
    project = await get_owned_project(
        session,
        project_id,
        current_user.id,
        permission=PROJECT_PERMISSION_EDIT,
    )
    updated = await update_project(session, project, payload)
    return ProjectRead.model_validate(updated)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def project_delete(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    project = await get_owned_project(
        session,
        project_id,
        current_user.id,
        permission=PROJECT_PERMISSION_DELETE,
    )
    await delete_project(session, project)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{project_id}/structure", response_model=ProjectStructureRead)
async def project_structure_detail(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ProjectStructureRead:
    return await get_project_structure(session, project_id, current_user.id)


@router.post(
    "/{project_id}/volumes",
    response_model=ProjectStructureRead,
    status_code=status.HTTP_201_CREATED,
)
async def project_volume_create(
    project_id: UUID,
    payload: ProjectVolumeCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ProjectStructureRead:
    project = await get_owned_project(
        session,
        project_id,
        current_user.id,
        permission=PROJECT_PERMISSION_EDIT,
    )
    await create_project_volume(session, project, payload)
    return await get_project_structure(session, project_id, current_user.id)


@router.patch("/{project_id}/volumes/{volume_id}", response_model=ProjectStructureRead)
async def project_volume_patch(
    project_id: UUID,
    volume_id: UUID,
    payload: ProjectVolumeUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ProjectStructureRead:
    project = await get_owned_project(
        session,
        project_id,
        current_user.id,
        permission=PROJECT_PERMISSION_EDIT,
    )
    await update_project_volume(session, project, volume_id, payload)
    return await get_project_structure(session, project_id, current_user.id)


@router.post(
    "/{project_id}/branches",
    response_model=ProjectStructureRead,
    status_code=status.HTTP_201_CREATED,
)
async def project_branch_create(
    project_id: UUID,
    payload: ProjectBranchCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ProjectStructureRead:
    project = await get_owned_project(
        session,
        project_id,
        current_user.id,
        permission=PROJECT_PERMISSION_EDIT,
    )
    await create_project_branch(session, project, payload)
    return await get_project_structure(session, project_id, current_user.id)


@router.patch("/{project_id}/branches/{branch_id}", response_model=ProjectStructureRead)
async def project_branch_patch(
    project_id: UUID,
    branch_id: UUID,
    payload: ProjectBranchUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ProjectStructureRead:
    project = await get_owned_project(
        session,
        project_id,
        current_user.id,
        permission=PROJECT_PERMISSION_EDIT,
    )
    await update_project_branch(session, project, branch_id, payload)
    return await get_project_structure(session, project_id, current_user.id)


@router.get("/{project_id}/collaborators", response_model=ProjectCollaborationRead)
async def project_collaboration_detail(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ProjectCollaborationRead:
    return await get_project_collaboration(session, project_id, current_user.id)


@router.post(
    "/{project_id}/collaborators",
    response_model=ProjectCollaborationRead,
    status_code=status.HTTP_201_CREATED,
)
async def project_collaborator_create(
    project_id: UUID,
    payload: ProjectCollaboratorCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ProjectCollaborationRead:
    project = await get_owned_project(
        session,
        project_id,
        current_user.id,
        with_relations=True,
        permission=PROJECT_PERMISSION_MANAGE_COLLABORATORS,
    )
    await add_project_collaborator(
        session,
        project,
        actor_user_id=current_user.id,
        payload=payload,
    )
    return await get_project_collaboration(session, project_id, current_user.id)


@router.patch(
    "/{project_id}/collaborators/{collaborator_id}",
    response_model=ProjectCollaborationRead,
)
async def project_collaborator_patch(
    project_id: UUID,
    collaborator_id: UUID,
    payload: ProjectCollaboratorUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ProjectCollaborationRead:
    project = await get_owned_project(
        session,
        project_id,
        current_user.id,
        with_relations=True,
        permission=PROJECT_PERMISSION_MANAGE_COLLABORATORS,
    )
    await update_project_collaborator(session, project, collaborator_id, payload)
    return await get_project_collaboration(session, project_id, current_user.id)


@router.delete(
    "/{project_id}/collaborators/{collaborator_id}",
    response_model=ProjectCollaborationRead,
)
async def project_collaborator_delete(
    project_id: UUID,
    collaborator_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ProjectCollaborationRead:
    project = await get_owned_project(
        session,
        project_id,
        current_user.id,
        with_relations=True,
        permission=PROJECT_PERMISSION_MANAGE_COLLABORATORS,
    )
    await remove_project_collaborator(session, project, collaborator_id)
    return await get_project_collaboration(session, project_id, current_user.id)


@router.get("/{project_id}/bible", response_model=StoryBibleRead)
async def story_bible_detail(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> StoryBibleRead:
    project = await get_owned_project(
        session,
        project_id,
        current_user.id,
        with_relations=True,
        permission=PROJECT_PERMISSION_READ,
    )
    return StoryBibleRead(
        project=ProjectRead.model_validate(project),
        characters=project.characters,
        world_settings=project.world_settings,
        locations=project.locations,
        plot_threads=project.plot_threads,
        foreshadowing=project.foreshadowing_items,
        timeline_events=project.timeline_events,
    )


@router.put("/{project_id}/bible", response_model=StoryBibleRead)
async def story_bible_replace(
    project_id: UUID,
    payload: StoryBibleUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> StoryBibleRead:
    project = await get_owned_project(
        session,
        project_id,
        current_user.id,
        with_relations=True,
        permission=PROJECT_PERMISSION_EDIT,
    )
    updated = await replace_story_bible(
        session,
        project,
        payload,
        actor_user_id=current_user.id,
    )
    return StoryBibleRead(
        project=ProjectRead.model_validate(updated),
        characters=updated.characters,
        world_settings=updated.world_settings,
        locations=updated.locations,
        plot_threads=updated.plot_threads,
        foreshadowing=updated.foreshadowing_items,
        timeline_events=updated.timeline_events,
    )


@router.get("/{project_id}/export")
async def project_export(
    project_id: UUID,
    export_format: ExportFormat = Query(default="md", alias="format"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    project = await get_owned_project(
        session,
        project_id,
        current_user.id,
        with_relations=True,
        permission=PROJECT_PERMISSION_READ,
    )
    return build_export_response(
        content=render_project_export(project=project, export_format=export_format),
        filename=build_project_export_filename(project.title, export_format),
    )
