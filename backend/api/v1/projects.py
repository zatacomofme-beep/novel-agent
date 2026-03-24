from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user, get_db_session
from canon.service import build_canon_snapshot_payload
from core.errors import AppError
from memory.story_bible import load_story_bible_context
from models.user import User
from schemas.canon import CanonSnapshotRead
from schemas.project import (
    CharacterGenerationRequest,
    CharacterGenerationResponse,
    FactionGenerationRequest,
    FactionGenerationResponse,
    ItemGenerationRequest,
    ItemGenerationResponse,
    LocationGenerationRequest,
    LocationGenerationResponse,
    PlotThreadGenerationRequest,
    PlotThreadGenerationResponse,
    ProjectBranchCreate,
    ProjectBranchUpdate,
    ProjectBlueprintGenerateRequest,
    ProjectBootstrapProfileUpdate,
    ProjectBootstrapRead,
    ProjectChapterGenerationDispatchRead,
    ProjectEntityGenerationDispatchRead,
    ProjectCollaborationRead,
    ProjectCollaboratorCreate,
    ProjectCollaboratorUpdate,
    ProjectCreate,
    ProjectRead,
    ProjectStructureRead,
    ProjectUpdate,
    ProjectVolumeCreate,
    ProjectVolumeUpdate,
    StoryBibleBranchItemDelete,
    StoryBibleBranchItemUpsert,
    StoryBibleRead,
    StoryBibleScopeRead,
    StoryBibleUpdate,
)
from schemas.story_bible_version import (
    ConflictCheckRequest,
    ConflictCheckResult,
    StoryBibleApprovalRequest,
    StoryBiblePendingChangeCreate,
    StoryBiblePendingChangeList,
    StoryBiblePendingChangeRead,
    StoryBibleRollbackRequest,
    StoryBibleVersionList,
    StoryBibleVersionRead,
)
from services.project_service import (
    create_project_branch,
    create_project,
    add_project_collaborator,
    build_project_stats_payload,
    create_project_volume,
    delete_project,
    delete_story_bible_branch_item,
    get_project_collaboration,
    get_project_structure,
    get_story_bible,
    get_owned_project,
    list_projects,
    PROJECT_PERMISSION_DELETE,
    PROJECT_PERMISSION_EDIT,
    PROJECT_PERMISSION_MANAGE_COLLABORATORS,
    PROJECT_PERMISSION_READ,
    replace_story_bible,
    remove_project_collaborator,
    upsert_story_bible_branch_item,
    update_project_collaborator,
    update_project_branch,
    update_project,
    update_project_volume,
)
from services.project_bootstrap_service import (
    generate_project_blueprint,
    get_project_bootstrap_state,
    update_project_bootstrap_profile,
)
from services.project_generation_service import dispatch_next_project_chapter_generation
from services.project_entity_generation_service import dispatch_project_entity_generation
from services.story_bible_version_service import (
    approve_pending_change,
    check_conflict,
    create_pending_change,
    get_pending_changes,
    get_story_bible_versions,
    reject_pending_change,
    rollback_story_bible,
)
from services.export_service import (
    ExportFormat,
    build_export_response,
    build_project_export_filename,
    render_project_export,
)
from services.entity_generation_service import (
    generate_characters as generate_character_candidates,
    generate_factions as generate_faction_candidates,
    generate_items as generate_item_candidates,
    generate_locations as generate_location_candidates,
    generate_plot_threads as generate_plot_thread_candidates,
)


router = APIRouter()


def _as_supporting_character_payload(
    payload: CharacterGenerationRequest,
) -> CharacterGenerationRequest:
    return payload.model_copy(update={"character_type": "supporting"})


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


@router.get("/{project_id}/bootstrap", response_model=ProjectBootstrapRead)
async def project_bootstrap_detail(
    project_id: UUID,
    branch_id: Optional[UUID] = Query(default=None),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ProjectBootstrapRead:
    project = await get_owned_project(
        session,
        project_id,
        current_user.id,
        with_relations=True,
        permission=PROJECT_PERMISSION_READ,
    )
    return await get_project_bootstrap_state(
        session,
        project,
        actor_user_id=current_user.id,
        branch_id=branch_id,
    )


@router.put("/{project_id}/bootstrap", response_model=ProjectBootstrapRead)
async def project_bootstrap_replace(
    project_id: UUID,
    payload: ProjectBootstrapProfileUpdate,
    branch_id: Optional[UUID] = Query(default=None),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ProjectBootstrapRead:
    project = await get_owned_project(
        session,
        project_id,
        current_user.id,
        with_relations=True,
        permission=PROJECT_PERMISSION_EDIT,
    )
    await update_project_bootstrap_profile(session, project, payload)
    refreshed = await get_owned_project(
        session,
        project_id,
        current_user.id,
        with_relations=True,
        permission=PROJECT_PERMISSION_EDIT,
    )
    return await get_project_bootstrap_state(
        session,
        refreshed,
        actor_user_id=current_user.id,
        branch_id=branch_id,
    )


@router.post("/{project_id}/bootstrap/generate", response_model=ProjectBootstrapRead)
async def project_bootstrap_generate(
    project_id: UUID,
    payload: ProjectBlueprintGenerateRequest,
    branch_id: Optional[UUID] = Query(default=None),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ProjectBootstrapRead:
    project = await get_owned_project(
        session,
        project_id,
        current_user.id,
        with_relations=True,
        permission=PROJECT_PERMISSION_EDIT,
    )
    return await generate_project_blueprint(
        session,
        project,
        actor_user_id=current_user.id,
        branch_id=branch_id,
        create_missing_chapters=payload.create_missing_chapters,
    )


@router.post(
    "/{project_id}/generate-next-chapter",
    response_model=ProjectChapterGenerationDispatchRead,
)
async def project_generate_next_chapter(
    project_id: UUID,
    branch_id: Optional[UUID] = Query(default=None),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ProjectChapterGenerationDispatchRead:
    project = await get_owned_project(
        session,
        project_id,
        current_user.id,
        with_relations=True,
        permission=PROJECT_PERMISSION_EDIT,
    )
    return await dispatch_next_project_chapter_generation(
        session,
        project,
        actor_user_id=current_user.id,
        branch_id=branch_id,
    )


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


class ProjectStatsResponse(BaseModel):
    total_word_count: int
    chapter_count: int
    character_count: int
    item_count: int
    faction_count: int
    location_count: int
    plot_thread_count: int
    volume_count: int
    branch_count: int


class StoryBiblePendingChangeCountResponse(BaseModel):
    pending_count: int


@router.get("/{project_id}/stats", response_model=ProjectStatsResponse)
async def project_stats(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ProjectStatsResponse:
    project = await get_owned_project(
        session,
        project_id,
        current_user.id,
        with_relations=True,
    )
    return ProjectStatsResponse(**build_project_stats_payload(project))


@router.post(
    "/{project_id}/generations/characters",
    response_model=CharacterGenerationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def generate_characters(
    project_id: UUID,
    payload: CharacterGenerationRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> CharacterGenerationResponse:
    await get_owned_project(
        session,
        project_id,
        current_user.id,
        permission=PROJECT_PERMISSION_EDIT,
    )
    return await generate_character_candidates(
        session,
        project_id,
        current_user.id,
        payload,
    )


@router.post(
    "/{project_id}/generations/supporting",
    response_model=CharacterGenerationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def generate_supporting_characters(
    project_id: UUID,
    payload: CharacterGenerationRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> CharacterGenerationResponse:
    await get_owned_project(
        session,
        project_id,
        current_user.id,
        permission=PROJECT_PERMISSION_EDIT,
    )
    return await generate_character_candidates(
        session,
        project_id,
        current_user.id,
        _as_supporting_character_payload(payload),
    )


@router.post(
    "/{project_id}/generations/characters/dispatch",
    response_model=ProjectEntityGenerationDispatchRead,
)
async def dispatch_character_generation(
    project_id: UUID,
    payload: CharacterGenerationRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ProjectEntityGenerationDispatchRead:
    project = await get_owned_project(
        session,
        project_id,
        current_user.id,
        permission=PROJECT_PERMISSION_EDIT,
    )
    return await dispatch_project_entity_generation(
        session,
        project,
        actor_user_id=current_user.id,
        generation_type="characters",
        payload=payload,
    )


@router.post(
    "/{project_id}/generations/supporting/dispatch",
    response_model=ProjectEntityGenerationDispatchRead,
)
async def dispatch_supporting_generation(
    project_id: UUID,
    payload: CharacterGenerationRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ProjectEntityGenerationDispatchRead:
    project = await get_owned_project(
        session,
        project_id,
        current_user.id,
        permission=PROJECT_PERMISSION_EDIT,
    )
    return await dispatch_project_entity_generation(
        session,
        project,
        actor_user_id=current_user.id,
        generation_type="supporting",
        payload=_as_supporting_character_payload(payload),
    )


@router.post(
    "/{project_id}/generations/items",
    response_model=ItemGenerationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def generate_items(
    project_id: UUID,
    payload: ItemGenerationRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ItemGenerationResponse:
    await get_owned_project(
        session,
        project_id,
        current_user.id,
        permission=PROJECT_PERMISSION_EDIT,
    )
    return await generate_item_candidates(
        session,
        project_id,
        current_user.id,
        payload,
    )


@router.post(
    "/{project_id}/generations/items/dispatch",
    response_model=ProjectEntityGenerationDispatchRead,
)
async def dispatch_item_generation(
    project_id: UUID,
    payload: ItemGenerationRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ProjectEntityGenerationDispatchRead:
    project = await get_owned_project(
        session,
        project_id,
        current_user.id,
        permission=PROJECT_PERMISSION_EDIT,
    )
    return await dispatch_project_entity_generation(
        session,
        project,
        actor_user_id=current_user.id,
        generation_type="items",
        payload=payload,
    )


@router.post(
    "/{project_id}/generations/locations",
    response_model=LocationGenerationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def generate_locations(
    project_id: UUID,
    payload: LocationGenerationRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> LocationGenerationResponse:
    await get_owned_project(
        session,
        project_id,
        current_user.id,
        permission=PROJECT_PERMISSION_EDIT,
    )
    return await generate_location_candidates(
        session,
        project_id,
        current_user.id,
        payload,
    )


@router.post(
    "/{project_id}/generations/locations/dispatch",
    response_model=ProjectEntityGenerationDispatchRead,
)
async def dispatch_location_generation(
    project_id: UUID,
    payload: LocationGenerationRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ProjectEntityGenerationDispatchRead:
    project = await get_owned_project(
        session,
        project_id,
        current_user.id,
        permission=PROJECT_PERMISSION_EDIT,
    )
    return await dispatch_project_entity_generation(
        session,
        project,
        actor_user_id=current_user.id,
        generation_type="locations",
        payload=payload,
    )


@router.post(
    "/{project_id}/generations/factions",
    response_model=FactionGenerationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def generate_factions(
    project_id: UUID,
    payload: FactionGenerationRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> FactionGenerationResponse:
    await get_owned_project(
        session,
        project_id,
        current_user.id,
        permission=PROJECT_PERMISSION_EDIT,
    )
    return await generate_faction_candidates(
        session,
        project_id,
        current_user.id,
        payload,
    )


@router.post(
    "/{project_id}/generations/factions/dispatch",
    response_model=ProjectEntityGenerationDispatchRead,
)
async def dispatch_faction_generation(
    project_id: UUID,
    payload: FactionGenerationRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ProjectEntityGenerationDispatchRead:
    project = await get_owned_project(
        session,
        project_id,
        current_user.id,
        permission=PROJECT_PERMISSION_EDIT,
    )
    return await dispatch_project_entity_generation(
        session,
        project,
        actor_user_id=current_user.id,
        generation_type="factions",
        payload=payload,
    )


@router.post(
    "/{project_id}/generations/plot-threads",
    response_model=PlotThreadGenerationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def generate_plot_threads(
    project_id: UUID,
    payload: PlotThreadGenerationRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> PlotThreadGenerationResponse:
    await get_owned_project(
        session,
        project_id,
        current_user.id,
        permission=PROJECT_PERMISSION_EDIT,
    )
    return await generate_plot_thread_candidates(
        session,
        project_id,
        current_user.id,
        payload,
    )


@router.post(
    "/{project_id}/generations/plot-threads/dispatch",
    response_model=ProjectEntityGenerationDispatchRead,
)
async def dispatch_plot_thread_generation(
    project_id: UUID,
    payload: PlotThreadGenerationRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ProjectEntityGenerationDispatchRead:
    project = await get_owned_project(
        session,
        project_id,
        current_user.id,
        permission=PROJECT_PERMISSION_EDIT,
    )
    return await dispatch_project_entity_generation(
        session,
        project,
        actor_user_id=current_user.id,
        generation_type="plot_threads",
        payload=payload,
    )


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
    branch_id: Optional[UUID] = Query(default=None),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> StoryBibleRead:
    return await get_story_bible(
        session,
        project_id,
        current_user.id,
        branch_id=branch_id,
    )


@router.put("/{project_id}/bible", response_model=StoryBibleRead)
async def story_bible_replace(
    project_id: UUID,
    payload: StoryBibleUpdate,
    branch_id: Optional[UUID] = Query(default=None),
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
        branch_id=branch_id,
    )
    return updated


@router.post("/{project_id}/bible/item", response_model=StoryBibleRead)
async def story_bible_item_upsert(
    project_id: UUID,
    payload: StoryBibleBranchItemUpsert,
    branch_id: UUID = Query(...),
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
    return await upsert_story_bible_branch_item(
        session,
        project,
        payload,
        actor_user_id=current_user.id,
        branch_id=branch_id,
    )


@router.post("/{project_id}/bible/item/remove", response_model=StoryBibleRead)
async def story_bible_item_remove(
    project_id: UUID,
    payload: StoryBibleBranchItemDelete,
    branch_id: UUID = Query(...),
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
    return await delete_story_bible_branch_item(
        session,
        project,
        payload,
        actor_user_id=current_user.id,
        branch_id=branch_id,
    )


@router.get("/{project_id}/canon-snapshot", response_model=CanonSnapshotRead)
async def project_canon_snapshot(
    project_id: UUID,
    branch_id: Optional[UUID] = Query(default=None),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> CanonSnapshotRead:
    story_bible = await load_story_bible_context(
        session,
        project_id,
        current_user.id,
        branch_id=branch_id,
    )
    snapshot_payload = build_canon_snapshot_payload(story_bible)
    return CanonSnapshotRead(
        project_id=story_bible.project_id,
        title=story_bible.title,
        branch_id=story_bible.branch_id,
        branch_title=story_bible.branch_title,
        branch_key=story_bible.branch_key,
        scope=StoryBibleScopeRead.model_validate(story_bible.model_dump()),
        plugin_snapshots=snapshot_payload["plugin_snapshots"],
        total_entity_count=snapshot_payload["total_entity_count"],
        integrity_report=snapshot_payload["integrity_report"],
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


@router.get("/{project_id}/bible/versions", response_model=StoryBibleVersionList)
async def story_bible_version_list(
    project_id: UUID,
    branch_id: Optional[UUID] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> StoryBibleVersionList:
    await get_owned_project(
        session,
        project_id,
        current_user.id,
        permission=PROJECT_PERMISSION_READ,
    )
    resolved_branch_id = branch_id
    if not resolved_branch_id:
        project = await get_owned_project(
            session,
            project_id,
            current_user.id,
            with_relations=True,
        )
        default_branch = next((b for b in project.branches if b.is_default), None)
        if default_branch:
            resolved_branch_id = default_branch.id

    if not resolved_branch_id:
        return StoryBibleVersionList(items=[], total=0, page=page, page_size=page_size)

    return await get_story_bible_versions(
        session,
        project_id,
        resolved_branch_id,
        page=page,
        page_size=page_size,
    )


@router.post("/{project_id}/bible/rollback", response_model=StoryBibleVersionRead)
async def story_bible_rollback(
    project_id: UUID,
    request: StoryBibleRollbackRequest,
    branch_id: Optional[UUID] = Query(default=None),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> StoryBibleVersionRead:
    project = await get_owned_project(
        session,
        project_id,
        current_user.id,
        with_relations=True,
        permission=PROJECT_PERMISSION_EDIT,
    )
    resolved_branch_id = branch_id
    if not resolved_branch_id:
        default_branch = next((b for b in project.branches if b.is_default), None)
        if default_branch:
            resolved_branch_id = default_branch.id

    if not resolved_branch_id:
        raise AppError(
            code="story_bible.branch_required",
            message="A target branch is required for Story Bible rollback.",
            status_code=400,
        )

    version = await rollback_story_bible(
        session,
        project,
        resolved_branch_id,
        request,
        current_user.id,
    )
    await session.commit()
    return StoryBibleVersionRead.model_validate(version)


@router.get(
    "/{project_id}/bible/pending-changes",
    response_model=StoryBiblePendingChangeList,
)
async def story_bible_pending_changes(
    project_id: UUID,
    branch_id: Optional[UUID] = Query(default=None),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> StoryBiblePendingChangeList:
    await get_owned_project(
        session,
        project_id,
        current_user.id,
        permission=PROJECT_PERMISSION_READ,
    )
    return await get_pending_changes(session, project_id, branch_id)


@router.get(
    "/{project_id}/bible/pending-changes/count",
    response_model=StoryBiblePendingChangeCountResponse,
)
async def story_bible_pending_change_count(
    project_id: UUID,
    branch_id: Optional[UUID] = Query(default=None),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> StoryBiblePendingChangeCountResponse:
    await get_owned_project(
        session,
        project_id,
        current_user.id,
        permission=PROJECT_PERMISSION_READ,
    )
    pending = await get_pending_changes(session, project_id, branch_id)
    return StoryBiblePendingChangeCountResponse(pending_count=pending.pending_count)


@router.post(
    "/{project_id}/bible/pending-changes",
    response_model=StoryBiblePendingChangeRead,
    status_code=status.HTTP_201_CREATED,
)
async def story_bible_pending_change_create(
    project_id: UUID,
    request: StoryBiblePendingChangeCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> StoryBiblePendingChangeRead:
    await get_owned_project(
        session,
        project_id,
        current_user.id,
        permission=PROJECT_PERMISSION_EDIT,
    )
    pending = await create_pending_change(
        session,
        project_id,
        request.branch_id,
        request,
    )
    await session.commit()
    return StoryBiblePendingChangeRead.model_validate(pending)


@router.post(
    "/{project_id}/bible/pending-changes/{change_id}/approve",
    response_model=StoryBiblePendingChangeRead,
)
async def story_bible_pending_change_approve(
    project_id: UUID,
    change_id: UUID,
    request: StoryBibleApprovalRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> StoryBiblePendingChangeRead:
    await get_owned_project(
        session,
        project_id,
        current_user.id,
        permission=PROJECT_PERMISSION_EDIT,
    )
    pending = await approve_pending_change(
        session,
        change_id,
        current_user.id,
        request.comment,
        expected_project_id=project_id,
    )
    await session.commit()
    return StoryBiblePendingChangeRead.model_validate(pending)


@router.post(
    "/{project_id}/bible/pending-changes/{change_id}/reject",
    response_model=StoryBiblePendingChangeRead,
)
async def story_bible_pending_change_reject(
    project_id: UUID,
    change_id: UUID,
    request: StoryBibleApprovalRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> StoryBiblePendingChangeRead:
    await get_owned_project(
        session,
        project_id,
        current_user.id,
        permission=PROJECT_PERMISSION_EDIT,
    )
    if not request.comment:
        raise AppError(
            code="story_bible.rejection_reason_required",
            message="Rejection reason is required.",
            status_code=400,
        )
    pending = await reject_pending_change(
        session,
        change_id,
        current_user.id,
        request.comment,
        expected_project_id=project_id,
    )
    await session.commit()
    return StoryBiblePendingChangeRead.model_validate(pending)


@router.post(
    "/{project_id}/bible/check-conflict",
    response_model=ConflictCheckResult,
)
async def story_bible_check_conflict(
    project_id: UUID,
    request: ConflictCheckRequest,
    branch_id: Optional[UUID] = Query(default=None),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ConflictCheckResult:
    project = await get_owned_project(
        session,
        project_id,
        current_user.id,
        with_relations=True,
        permission=PROJECT_PERMISSION_READ,
    )
    return await check_conflict(
        session,
        project,
        request,
        branch_id=branch_id,
    )
