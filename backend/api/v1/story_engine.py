from __future__ import annotations

import json
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user, get_db_session, get_model_routing_admin_user
from core.errors import AppError
from models.user import User
from schemas.story_engine import (
    ChapterStreamGenerateRequest,
    FinalOptimizeRequest,
    FinalOptimizeResponse,
    OutlineStressTestRequest,
    OutlineStressTestResponse,
    RealtimeGuardRequest,
    RealtimeGuardResponse,
    StoryBulkImportRequest,
    StoryBulkImportResponse,
    StoryBulkImportPayload,
    StoryGeneratedCandidateAcceptRequest,
    StoryGeneratedCandidateAcceptResponse,
    StoryChapterSummaryCreate,
    StoryChapterSummaryRead,
    StoryChapterSummaryUpdate,
    StoryCharacterGraphRead,
    StoryCharacterRead,
    StoryCharacterCreate,
    StoryCharacterUpdate,
    StoryRoomCloudDraftRead,
    StoryRoomCloudDraftSummaryRead,
    StoryRoomCloudDraftUpsertRequest,
    StoryEnginePresetCatalogRead,
    StoryEngineModelRoutingRead,
    StoryEngineModelRoutingUpdateRequest,
    StoryKnowledgeDeleteRequest,
    StoryKnowledgeMutationResponse,
    StoryKnowledgeSuggestionResolveRequest,
    StoryKnowledgeSuggestionResolveResponse,
    StoryKnowledgeSectionKey,
    StoryEngineWorkspaceRead,
    StoryForeshadowCreate,
    StoryForeshadowRead,
    StoryForeshadowUpdate,
    StoryKnowledgeUpsertRequest,
    StoryItemCreate,
    StoryItemRead,
    StoryItemUpdate,
    StoryKnowledgeRollbackResponse,
    StoryKnowledgeVersionRead,
    StoryOutlineCreate,
    StoryOutlineRead,
    StoryOutlineUpdate,
    StoryImportTemplateRead,
    StorySearchResultRead,
    StoryTimelineMapEventCreate,
    StoryTimelineMapEventRead,
    StoryTimelineMapEventUpdate,
    StoryWorldRuleCreate,
    StoryWorldRuleRead,
    StoryWorldRuleUpdate,
)
from schemas.chapter import (
    ChapterCreate,
    ChapterRead,
    ChapterUpdate,
    ChapterCheckpointCreate,
    ChapterCheckpointRead,
    ChapterCheckpointUpdate,
    ChapterReviewCommentCreate,
    ChapterReviewCommentRead,
    ChapterReviewCommentUpdate,
    ChapterReviewDecisionCreate,
    ChapterReviewDecisionRead,
    ChapterReviewWorkspaceRead,
    ChapterSelectionRewriteRequest,
    ChapterSelectionRewriteResponse,
    ChapterVersionRead,
    RollbackResponse,
)
from services.story_engine_import_service import (
    bulk_import_story_payload,
    get_import_template,
    list_import_templates,
)
from services.story_engine_cloud_draft_service import (
    delete_story_room_cloud_draft,
    get_story_room_cloud_draft,
    list_story_room_cloud_drafts,
    upsert_story_room_cloud_draft,
)
from services.story_engine_candidate_service import accept_generated_candidate
from services.story_engine_kb_service import (
    build_character_graph,
    create_entity,
    delete_entity,
    get_story_engine_project,
    list_entities,
    list_versions,
    rollback_entity_version,
    search_knowledge,
    update_entity,
)
from services.story_engine_settings_service import (
    list_story_engine_model_preset_catalog,
    get_story_engine_model_routing,
    update_story_engine_model_routing,
)
from services.story_engine_kb_resolution_service import resolve_chapter_summary_kb_suggestion
from services.story_engine_unified_knowledge_service import (
    delete_story_knowledge,
    save_story_knowledge,
)
from services.story_engine_workflow_service import (
    list_story_engine_agent_specs,
    run_chapter_stream_generate,
    load_story_engine_workspace,
    run_final_optimize,
    run_outline_stress_test,
    run_realtime_guard,
)
from services.chapter_service import (
    create_chapter,
    get_owned_chapter,
    list_versions as list_chapter_versions,
    rollback_to_version,
    update_chapter,
)
from services.project_service import PROJECT_PERMISSION_EDIT, PROJECT_PERMISSION_READ
from services.review_service import (
    create_chapter_checkpoint,
    create_chapter_comment,
    create_chapter_review_decision,
    delete_chapter_comment,
    get_chapter_review_workspace,
    update_chapter_checkpoint,
    update_chapter_comment,
)
from services.rewrite_service import rewrite_chapter_selection
from services.export_service import (
    ExportFormat,
    build_chapter_export_filename,
    build_export_response,
    render_chapter_export,
)
from tasks.schemas import TaskState
from tasks.story_engine_workflows import (
    dispatch_bulk_import_task,
    dispatch_final_optimize_task,
    dispatch_outline_stress_task,
    enqueue_bulk_import_task,
    enqueue_final_optimize_task,
    enqueue_outline_stress_task,
)


router = APIRouter()


async def _get_story_engine_chapter_or_404(
    session: AsyncSession,
    *,
    project_id: UUID,
    chapter_id: UUID,
    user_id: UUID,
    permission: str = PROJECT_PERMISSION_READ,
):
    chapter = await get_owned_chapter(
        session,
        chapter_id,
        user_id,
        permission=permission,
    )
    if chapter.project_id != project_id:
        raise AppError(
            code="story_engine.chapter_project_mismatch",
            message="Chapter does not belong to this project.",
            status_code=404,
        )
    return chapter


def _resolve_story_engine_import_payload(
    payload: StoryBulkImportRequest,
) -> tuple[StoryBulkImportPayload, dict[str, Any] | None]:
    import_payload = payload.payload
    template: dict[str, Any] | None = None
    if import_payload is None and payload.template_key:
        template = get_import_template(payload.template_key)
        import_payload = template["payload"]
    if import_payload is None:
        raise AppError(
            code="story_engine.import_payload_required",
            message="请先选择一个起盘模板，或贴入完整设定包。",
            status_code=400,
        )
    return StoryBulkImportPayload.model_validate(import_payload), template


@router.get(
    "/story-engine/model-routing/preset-catalog",
    response_model=StoryEnginePresetCatalogRead,
)
async def story_engine_model_routing_preset_catalog(
    current_user: User = Depends(get_model_routing_admin_user),
) -> StoryEnginePresetCatalogRead:
    del current_user
    payload = list_story_engine_model_preset_catalog()
    return StoryEnginePresetCatalogRead.model_validate(payload)


@router.get(
    "/projects/{project_id}/story-engine/workspace",
    response_model=StoryEngineWorkspaceRead,
)
async def story_engine_workspace(
    project_id: UUID,
    branch_id: Optional[UUID] = Query(default=None),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> StoryEngineWorkspaceRead:
    payload = await load_story_engine_workspace(
        session,
        project_id=project_id,
        user_id=current_user.id,
        branch_id=branch_id,
    )
    return StoryEngineWorkspaceRead.model_validate(payload)


@router.post(
    "/projects/{project_id}/story-engine/chapters",
    response_model=ChapterRead,
    status_code=status.HTTP_201_CREATED,
)
async def story_engine_chapter_create(
    project_id: UUID,
    payload: ChapterCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ChapterRead:
    chapter = await create_chapter(session, project_id, current_user.id, payload)
    return ChapterRead.model_validate(chapter)


@router.get(
    "/projects/{project_id}/story-engine/chapters/{chapter_id}",
    response_model=ChapterRead,
)
async def story_engine_chapter_detail(
    project_id: UUID,
    chapter_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ChapterRead:
    chapter = await _get_story_engine_chapter_or_404(
        session,
        project_id=project_id,
        chapter_id=chapter_id,
        user_id=current_user.id,
        permission=PROJECT_PERMISSION_READ,
    )
    return ChapterRead.model_validate(chapter)


@router.get("/projects/{project_id}/story-engine/agents")
async def story_engine_agents(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[dict[str, Any]]:
    await get_story_engine_project(session, project_id, current_user.id)
    return list_story_engine_agent_specs()


@router.get(
    "/projects/{project_id}/story-engine/model-routing",
    response_model=StoryEngineModelRoutingRead,
)
async def story_engine_model_routing(
    project_id: UUID,
    current_user: User = Depends(get_model_routing_admin_user),
    session: AsyncSession = Depends(get_db_session),
) -> StoryEngineModelRoutingRead:
    payload = await get_story_engine_model_routing(
        session,
        project_id=project_id,
        user_id=current_user.id,
    )
    return StoryEngineModelRoutingRead.model_validate(payload)


@router.put(
    "/projects/{project_id}/story-engine/model-routing",
    response_model=StoryEngineModelRoutingRead,
)
async def story_engine_model_routing_update(
    project_id: UUID,
    payload: StoryEngineModelRoutingUpdateRequest,
    current_user: User = Depends(get_model_routing_admin_user),
    session: AsyncSession = Depends(get_db_session),
) -> StoryEngineModelRoutingRead:
    result = await update_story_engine_model_routing(
        session,
        project_id=project_id,
        user_id=current_user.id,
        active_preset_key=payload.active_preset_key,
        manual_overrides={
            role_key: route.model_dump(mode="json")
            for role_key, route in payload.manual_overrides.items()
        },
    )
    return StoryEngineModelRoutingRead.model_validate(result)


@router.get(
    "/projects/{project_id}/story-engine/search",
    response_model=list[StorySearchResultRead],
)
async def story_engine_search(
    project_id: UUID,
    query: str = Query(min_length=1),
    entity_type: Optional[str] = Query(default=None),
    limit: int = Query(default=8, ge=1, le=20),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[StorySearchResultRead]:
    results = await search_knowledge(
        session,
        project_id=project_id,
        user_id=current_user.id,
        query=query,
        entity_type=entity_type,
        limit=limit,
    )
    return [StorySearchResultRead.model_validate(item) for item in results]


@router.get(
    "/projects/{project_id}/story-engine/cloud-drafts",
    response_model=list[StoryRoomCloudDraftSummaryRead],
)
async def story_engine_cloud_drafts(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[StoryRoomCloudDraftSummaryRead]:
    payload = await list_story_room_cloud_drafts(
        session,
        project_id=project_id,
        user_id=current_user.id,
    )
    return [StoryRoomCloudDraftSummaryRead.model_validate(item) for item in payload]


@router.get(
    "/projects/{project_id}/story-engine/cloud-drafts/{draft_snapshot_id}",
    response_model=Optional[StoryRoomCloudDraftRead],
)
async def story_engine_cloud_draft_detail(
    project_id: UUID,
    draft_snapshot_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> Optional[StoryRoomCloudDraftRead]:
    payload = await get_story_room_cloud_draft(
        session,
        project_id=project_id,
        user_id=current_user.id,
        draft_snapshot_id=draft_snapshot_id,
    )
    if payload is None:
        return None
    return StoryRoomCloudDraftRead.model_validate(payload)


@router.put(
    "/projects/{project_id}/story-engine/cloud-drafts/current",
    response_model=StoryRoomCloudDraftRead,
)
async def story_engine_cloud_draft_upsert(
    project_id: UUID,
    payload: StoryRoomCloudDraftUpsertRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> StoryRoomCloudDraftRead:
    result = await upsert_story_room_cloud_draft(
        session,
        project_id=project_id,
        user_id=current_user.id,
        branch_id=payload.branch_id,
        volume_id=payload.volume_id,
        chapter_number=payload.chapter_number,
        chapter_title=payload.chapter_title,
        draft_text=payload.draft_text,
        outline_id=payload.outline_id,
        source_chapter_id=payload.source_chapter_id,
        source_version_number=payload.source_version_number,
    )
    return StoryRoomCloudDraftRead.model_validate(result)


@router.delete(
    "/projects/{project_id}/story-engine/cloud-drafts/{draft_snapshot_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def story_engine_cloud_draft_delete(
    project_id: UUID,
    draft_snapshot_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    deleted = await delete_story_room_cloud_draft(
        session,
        project_id=project_id,
        user_id=current_user.id,
        draft_snapshot_id=draft_snapshot_id,
    )
    if not deleted:
        raise AppError(
            code="story_engine.cloud_draft.not_found",
            message="Cloud draft not found.",
            status_code=404,
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/projects/{project_id}/story-engine/chapters/{chapter_id}/review-workspace",
    response_model=ChapterReviewWorkspaceRead,
)
async def story_engine_chapter_review_workspace(
    project_id: UUID,
    chapter_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ChapterReviewWorkspaceRead:
    await _get_story_engine_chapter_or_404(
        session,
        project_id=project_id,
        chapter_id=chapter_id,
        user_id=current_user.id,
        permission=PROJECT_PERMISSION_READ,
    )
    return await get_chapter_review_workspace(session, chapter_id, current_user.id)


@router.get(
    "/projects/{project_id}/story-engine/chapters/{chapter_id}/versions",
    response_model=list[ChapterVersionRead],
)
async def story_engine_chapter_versions(
    project_id: UUID,
    chapter_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[ChapterVersionRead]:
    await _get_story_engine_chapter_or_404(
        session,
        project_id=project_id,
        chapter_id=chapter_id,
        user_id=current_user.id,
        permission=PROJECT_PERMISSION_READ,
    )
    versions = await list_chapter_versions(session, chapter_id, current_user.id)
    return [ChapterVersionRead.model_validate(version) for version in versions]


@router.post(
    "/projects/{project_id}/story-engine/chapters/{chapter_id}/comments",
    response_model=ChapterReviewCommentRead,
    status_code=status.HTTP_201_CREATED,
)
async def story_engine_chapter_comment_create(
    project_id: UUID,
    chapter_id: UUID,
    payload: ChapterReviewCommentCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ChapterReviewCommentRead:
    await _get_story_engine_chapter_or_404(
        session,
        project_id=project_id,
        chapter_id=chapter_id,
        user_id=current_user.id,
        permission=PROJECT_PERMISSION_READ,
    )
    return await create_chapter_comment(session, chapter_id, current_user.id, payload)


@router.patch(
    "/projects/{project_id}/story-engine/chapters/{chapter_id}/comments/{comment_id}",
    response_model=ChapterReviewCommentRead,
)
async def story_engine_chapter_comment_update(
    project_id: UUID,
    chapter_id: UUID,
    comment_id: UUID,
    payload: ChapterReviewCommentUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ChapterReviewCommentRead:
    await _get_story_engine_chapter_or_404(
        session,
        project_id=project_id,
        chapter_id=chapter_id,
        user_id=current_user.id,
        permission=PROJECT_PERMISSION_READ,
    )
    return await update_chapter_comment(
        session,
        chapter_id,
        comment_id,
        current_user.id,
        payload,
    )


@router.delete(
    "/projects/{project_id}/story-engine/chapters/{chapter_id}/comments/{comment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def story_engine_chapter_comment_delete(
    project_id: UUID,
    chapter_id: UUID,
    comment_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    await _get_story_engine_chapter_or_404(
        session,
        project_id=project_id,
        chapter_id=chapter_id,
        user_id=current_user.id,
        permission=PROJECT_PERMISSION_READ,
    )
    await delete_chapter_comment(session, chapter_id, comment_id, current_user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/projects/{project_id}/story-engine/chapters/{chapter_id}/checkpoints",
    response_model=ChapterCheckpointRead,
    status_code=status.HTTP_201_CREATED,
)
async def story_engine_chapter_checkpoint_create(
    project_id: UUID,
    chapter_id: UUID,
    payload: ChapterCheckpointCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ChapterCheckpointRead:
    await _get_story_engine_chapter_or_404(
        session,
        project_id=project_id,
        chapter_id=chapter_id,
        user_id=current_user.id,
        permission=PROJECT_PERMISSION_READ,
    )
    return await create_chapter_checkpoint(session, chapter_id, current_user.id, payload)


@router.patch(
    "/projects/{project_id}/story-engine/chapters/{chapter_id}/checkpoints/{checkpoint_id}",
    response_model=ChapterCheckpointRead,
)
async def story_engine_chapter_checkpoint_update(
    project_id: UUID,
    chapter_id: UUID,
    checkpoint_id: UUID,
    payload: ChapterCheckpointUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ChapterCheckpointRead:
    await _get_story_engine_chapter_or_404(
        session,
        project_id=project_id,
        chapter_id=chapter_id,
        user_id=current_user.id,
        permission=PROJECT_PERMISSION_READ,
    )
    return await update_chapter_checkpoint(
        session,
        chapter_id,
        checkpoint_id,
        current_user.id,
        payload,
    )


@router.post(
    "/projects/{project_id}/story-engine/chapters/{chapter_id}/reviews",
    response_model=ChapterReviewDecisionRead,
    status_code=status.HTTP_201_CREATED,
)
async def story_engine_chapter_review_create(
    project_id: UUID,
    chapter_id: UUID,
    payload: ChapterReviewDecisionCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ChapterReviewDecisionRead:
    await _get_story_engine_chapter_or_404(
        session,
        project_id=project_id,
        chapter_id=chapter_id,
        user_id=current_user.id,
        permission=PROJECT_PERMISSION_READ,
    )
    return await create_chapter_review_decision(
        session,
        chapter_id,
        current_user.id,
        payload,
    )


@router.post(
    "/projects/{project_id}/story-engine/chapters/{chapter_id}/rewrite-selection",
    response_model=ChapterSelectionRewriteResponse,
)
async def story_engine_chapter_rewrite_selection(
    project_id: UUID,
    chapter_id: UUID,
    payload: ChapterSelectionRewriteRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ChapterSelectionRewriteResponse:
    await _get_story_engine_chapter_or_404(
        session,
        project_id=project_id,
        chapter_id=chapter_id,
        user_id=current_user.id,
        permission=PROJECT_PERMISSION_EDIT,
    )
    return await rewrite_chapter_selection(
        session,
        chapter_id,
        current_user.id,
        payload,
    )


@router.post(
    "/projects/{project_id}/story-engine/chapters/{chapter_id}/rollback/{version_id}",
    response_model=RollbackResponse,
)
async def story_engine_chapter_rollback(
    project_id: UUID,
    chapter_id: UUID,
    version_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> RollbackResponse:
    await _get_story_engine_chapter_or_404(
        session,
        project_id=project_id,
        chapter_id=chapter_id,
        user_id=current_user.id,
        permission=PROJECT_PERMISSION_EDIT,
    )
    chapter, restored_version = await rollback_to_version(
        session,
        chapter_id,
        version_id,
        current_user.id,
    )
    return RollbackResponse(
        chapter=ChapterRead.model_validate(chapter),
        restored_version=ChapterVersionRead.model_validate(restored_version),
    )


@router.patch(
    "/projects/{project_id}/story-engine/chapters/{chapter_id}",
    response_model=ChapterRead,
)
async def story_engine_chapter_patch(
    project_id: UUID,
    chapter_id: UUID,
    payload: ChapterUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ChapterRead:
    chapter = await _get_story_engine_chapter_or_404(
        session,
        project_id=project_id,
        chapter_id=chapter_id,
        user_id=current_user.id,
        permission=PROJECT_PERMISSION_EDIT,
    )
    updated = await update_chapter(
        session,
        chapter,
        payload,
        preference_learning_user_id=current_user.id,
        preference_learning_source="manual_update",
    )
    return ChapterRead.model_validate(updated)


@router.get("/projects/{project_id}/story-engine/chapters/{chapter_id}/export")
async def story_engine_chapter_export(
    project_id: UUID,
    chapter_id: UUID,
    export_format: ExportFormat = Query(default="md", alias="format"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    chapter = await _get_story_engine_chapter_or_404(
        session,
        project_id=project_id,
        chapter_id=chapter_id,
        user_id=current_user.id,
        permission=PROJECT_PERMISSION_READ,
    )
    project = await get_story_engine_project(session, project_id, current_user.id)
    return build_export_response(
        content=render_chapter_export(
            project_title=project.title,
            chapter=chapter,
            export_format=export_format,
        ),
        filename=build_chapter_export_filename(project.title, chapter, export_format),
    )


@router.get(
    "/projects/{project_id}/story-engine/graph/characters",
    response_model=StoryCharacterGraphRead,
)
async def story_engine_character_graph(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> StoryCharacterGraphRead:
    characters = await list_entities(
        session,
        project_id=project_id,
        user_id=current_user.id,
        entity_type="characters",
    )
    return StoryCharacterGraphRead.model_validate(build_character_graph(characters))


@router.get(
    "/projects/{project_id}/story-engine/versions",
    response_model=list[StoryKnowledgeVersionRead],
)
async def story_engine_versions(
    project_id: UUID,
    entity_type: Optional[str] = Query(default=None),
    entity_id: Optional[UUID] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[StoryKnowledgeVersionRead]:
    versions = await list_versions(
        session,
        project_id=project_id,
        user_id=current_user.id,
        entity_type=entity_type,
        entity_id=entity_id,
        limit=limit,
    )
    return [StoryKnowledgeVersionRead.model_validate(item) for item in versions]


@router.post(
    "/projects/{project_id}/story-engine/versions/{version_record_id}/rollback",
    response_model=StoryKnowledgeRollbackResponse,
)
async def story_engine_rollback(
    project_id: UUID,
    version_record_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> StoryKnowledgeRollbackResponse:
    payload = await rollback_entity_version(
        session,
        project_id=project_id,
        user_id=current_user.id,
        version_record_id=version_record_id,
    )
    return StoryKnowledgeRollbackResponse.model_validate(payload)


@router.get(
    "/projects/{project_id}/story-engine/import-templates",
    response_model=list[StoryImportTemplateRead],
)
async def story_engine_import_templates(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[StoryImportTemplateRead]:
    await get_story_engine_project(session, project_id, current_user.id)
    return [StoryImportTemplateRead.model_validate(item) for item in list_import_templates()]


@router.post(
    "/projects/{project_id}/story-engine/imports/bulk",
    response_model=StoryBulkImportResponse,
)
async def story_engine_bulk_import(
    project_id: UUID,
    payload: StoryBulkImportRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> StoryBulkImportResponse:
    import_payload, template = _resolve_story_engine_import_payload(payload)

    result = await bulk_import_story_payload(
        session,
        project_id=project_id,
        user_id=current_user.id,
        payload=import_payload,
        branch_id=payload.branch_id,
        replace_existing_sections=payload.replace_existing_sections,
        model_preset_key=(
            str(template.get("recommended_model_preset_key") or "").strip()
            if payload.apply_template_model_routing and template is not None
            else None
        ),
    )
    return StoryBulkImportResponse.model_validate(result)


@router.post(
    "/projects/{project_id}/story-engine/imports/bulk/start",
    response_model=TaskState,
)
async def story_engine_bulk_import_start(
    project_id: UUID,
    payload: StoryBulkImportRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> TaskState:
    await get_story_engine_project(session, project_id, current_user.id)
    import_payload, template = _resolve_story_engine_import_payload(payload)
    task_state = await enqueue_bulk_import_task(
        project_id=str(project_id),
        user_id=str(current_user.id),
        payload=import_payload.model_dump(mode="json"),
        replace_existing_sections=payload.replace_existing_sections,
        branch_id=payload.branch_id,
        model_preset_key=(
            str(template.get("recommended_model_preset_key") or "").strip()
            if payload.apply_template_model_routing and template is not None
            else None
        ),
    )
    return await dispatch_bulk_import_task(
        task_id=task_state.task_id,
        project_id=str(project_id),
        user_id=str(current_user.id),
    )


@router.post(
    "/projects/{project_id}/story-engine/generated-candidates/accept",
    response_model=StoryGeneratedCandidateAcceptResponse,
)
async def story_engine_generated_candidate_accept(
    project_id: UUID,
    payload: StoryGeneratedCandidateAcceptRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> StoryGeneratedCandidateAcceptResponse:
    result = await accept_generated_candidate(
        session,
        project_id=project_id,
        user_id=current_user.id,
        task_id=payload.task_id,
        candidate_index=payload.candidate_index,
        branch_id=payload.branch_id,
    )
    return StoryGeneratedCandidateAcceptResponse.model_validate(result)


@router.post(
    "/projects/{project_id}/story-engine/workflows/outline-stress-test",
    response_model=OutlineStressTestResponse,
)
async def story_engine_outline_stress_test(
    project_id: UUID,
    payload: OutlineStressTestRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> OutlineStressTestResponse:
    result = await run_outline_stress_test(
        session,
        project_id=project_id,
        user_id=current_user.id,
        branch_id=payload.branch_id,
        idea=payload.idea,
        source_material=payload.source_material,
        source_material_name=payload.source_material_name,
        genre=payload.genre,
        tone=payload.tone,
        target_chapter_count=payload.target_chapter_count or 120,
        target_total_words=payload.target_total_words or 1_000_000,
    )
    return OutlineStressTestResponse.model_validate(result)


@router.post(
    "/projects/{project_id}/story-engine/workflows/outline-stress-test/start",
    response_model=TaskState,
)
async def story_engine_outline_stress_test_start(
    project_id: UUID,
    payload: OutlineStressTestRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> TaskState:
    await get_story_engine_project(session, project_id, current_user.id)
    task_state = await enqueue_outline_stress_task(
        project_id=str(project_id),
        user_id=str(current_user.id),
        payload=payload.model_dump(mode="json"),
    )
    return await dispatch_outline_stress_task(
        task_id=task_state.task_id,
        project_id=str(project_id),
        user_id=str(current_user.id),
    )


@router.post(
    "/projects/{project_id}/story-engine/workflows/realtime-guard",
    response_model=RealtimeGuardResponse,
)
async def story_engine_realtime_guard(
    project_id: UUID,
    payload: RealtimeGuardRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> RealtimeGuardResponse:
    result = await run_realtime_guard(
        session,
        project_id=project_id,
        user_id=current_user.id,
        branch_id=payload.branch_id,
        chapter_id=payload.chapter_id,
        chapter_number=payload.chapter_number,
        chapter_title=payload.chapter_title,
        outline_id=payload.outline_id,
        current_outline=payload.current_outline,
        recent_chapters=payload.recent_chapters,
        draft_text=payload.draft_text,
        latest_paragraph=payload.latest_paragraph,
    )
    return RealtimeGuardResponse.model_validate(result)


@router.post("/projects/{project_id}/story-engine/workflows/chapter-stream")
async def story_engine_chapter_stream(
    project_id: UUID,
    payload: ChapterStreamGenerateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> StreamingResponse:
    async def event_stream():
        try:
            async for event in run_chapter_stream_generate(
                session,
                project_id=project_id,
                user_id=current_user.id,
                branch_id=payload.branch_id,
                chapter_id=payload.chapter_id,
                chapter_number=payload.chapter_number,
                chapter_title=payload.chapter_title,
                outline_id=payload.outline_id,
                current_outline=payload.current_outline,
                recent_chapters=payload.recent_chapters,
                existing_text=payload.existing_text,
                style_sample=payload.style_sample,
                target_word_count=payload.target_word_count,
                target_paragraph_count=payload.target_paragraph_count,
                resume_from_paragraph=payload.resume_from_paragraph,
                repair_instruction=payload.repair_instruction,
                rewrite_latest_paragraph=payload.rewrite_latest_paragraph,
            ):
                yield _ndjson_line(event)
        except Exception as exc:  # pragma: no cover - 流式异常交给前端状态栏展示
            yield _ndjson_line(
                {
                    "event": "error",
                    "message": str(exc),
                    "metadata": {"status": "failed"},
                }
            )

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")


@router.post(
    "/projects/{project_id}/story-engine/workflows/final-optimize",
    response_model=FinalOptimizeResponse,
)
async def story_engine_final_optimize(
    project_id: UUID,
    payload: FinalOptimizeRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> FinalOptimizeResponse:
    result = await run_final_optimize(
        session,
        project_id=project_id,
        user_id=current_user.id,
        branch_id=payload.branch_id,
        chapter_id=payload.chapter_id,
        chapter_number=payload.chapter_number,
        chapter_title=payload.chapter_title,
        draft_text=payload.draft_text,
        style_sample=payload.style_sample,
    )
    return FinalOptimizeResponse.model_validate(result)


@router.post(
    "/projects/{project_id}/story-engine/workflows/final-optimize/start",
    response_model=TaskState,
)
async def story_engine_final_optimize_start(
    project_id: UUID,
    payload: FinalOptimizeRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> TaskState:
    await get_story_engine_project(session, project_id, current_user.id)
    task_state = await enqueue_final_optimize_task(
        project_id=str(project_id),
        user_id=str(current_user.id),
        payload=payload.model_dump(mode="json"),
    )
    return await dispatch_final_optimize_task(
        task_id=task_state.task_id,
        project_id=str(project_id),
        user_id=str(current_user.id),
    )


@router.post(
    "/projects/{project_id}/story-engine/chapter-summaries/{summary_id}/kb-updates/{suggestion_id}",
    response_model=StoryKnowledgeSuggestionResolveResponse,
)
async def story_engine_kb_update_resolve(
    project_id: UUID,
    summary_id: UUID,
    suggestion_id: str,
    payload: StoryKnowledgeSuggestionResolveRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> StoryKnowledgeSuggestionResolveResponse:
    result = await resolve_chapter_summary_kb_suggestion(
        session,
        project_id=project_id,
        user_id=current_user.id,
        summary_id=summary_id,
        suggestion_id=suggestion_id,
        action=payload.action,
    )
    return StoryKnowledgeSuggestionResolveResponse.model_validate(result)


@router.post(
    "/projects/{project_id}/story-engine/knowledge/{section_key}",
    response_model=StoryKnowledgeMutationResponse,
)
async def story_engine_knowledge_upsert(
    project_id: UUID,
    section_key: StoryKnowledgeSectionKey,
    payload: StoryKnowledgeUpsertRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> StoryKnowledgeMutationResponse:
    result = await save_story_knowledge(
        session,
        project_id=project_id,
        user_id=current_user.id,
        section_key=section_key,
        item=payload.item,
        entity_id=payload.entity_id,
        branch_id=payload.branch_id,
        previous_entity_key=payload.previous_entity_key,
    )
    return StoryKnowledgeMutationResponse.model_validate(result)


@router.post(
    "/projects/{project_id}/story-engine/knowledge/{section_key}/remove",
    response_model=StoryKnowledgeMutationResponse,
)
async def story_engine_knowledge_delete(
    project_id: UUID,
    section_key: StoryKnowledgeSectionKey,
    payload: StoryKnowledgeDeleteRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> StoryKnowledgeMutationResponse:
    result = await delete_story_knowledge(
        session,
        project_id=project_id,
        user_id=current_user.id,
        section_key=section_key,
        entity_id=payload.entity_id,
        branch_id=payload.branch_id,
    )
    return StoryKnowledgeMutationResponse.model_validate(result)


@router.get(
    "/projects/{project_id}/story-engine/characters",
    response_model=list[StoryCharacterRead],
)
async def story_engine_character_list(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[StoryCharacterRead]:
    return await _list_entity_response(
        session,
        project_id=project_id,
        user_id=current_user.id,
        entity_type="characters",
        schema=StoryCharacterRead,
    )


@router.post(
    "/projects/{project_id}/story-engine/characters",
    response_model=StoryCharacterRead,
    status_code=status.HTTP_201_CREATED,
)
async def story_engine_character_create(
    project_id: UUID,
    payload: StoryCharacterCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> StoryCharacterRead:
    return await _create_entity_response(
        session,
        project_id=project_id,
        user_id=current_user.id,
        entity_type="characters",
        payload=payload.model_dump(),
        schema=StoryCharacterRead,
    )


@router.patch(
    "/projects/{project_id}/story-engine/characters/{entity_id}",
    response_model=StoryCharacterRead,
)
async def story_engine_character_patch(
    project_id: UUID,
    entity_id: UUID,
    payload: StoryCharacterUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> StoryCharacterRead:
    return await _update_entity_response(
        session,
        project_id=project_id,
        user_id=current_user.id,
        entity_type="characters",
        entity_id=entity_id,
        payload=payload.model_dump(exclude_unset=True),
        schema=StoryCharacterRead,
    )


@router.delete(
    "/projects/{project_id}/story-engine/characters/{entity_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def story_engine_character_delete(
    project_id: UUID,
    entity_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    await _delete_entity_response(
        session,
        project_id=project_id,
        user_id=current_user.id,
        entity_type="characters",
        entity_id=entity_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/projects/{project_id}/story-engine/foreshadows",
    response_model=list[StoryForeshadowRead],
)
async def story_engine_foreshadow_list(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[StoryForeshadowRead]:
    return await _list_entity_response(session, project_id=project_id, user_id=current_user.id, entity_type="foreshadows", schema=StoryForeshadowRead)


@router.post(
    "/projects/{project_id}/story-engine/foreshadows",
    response_model=StoryForeshadowRead,
    status_code=status.HTTP_201_CREATED,
)
async def story_engine_foreshadow_create(
    project_id: UUID,
    payload: StoryForeshadowCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> StoryForeshadowRead:
    return await _create_entity_response(session, project_id=project_id, user_id=current_user.id, entity_type="foreshadows", payload=payload.model_dump(), schema=StoryForeshadowRead)


@router.patch(
    "/projects/{project_id}/story-engine/foreshadows/{entity_id}",
    response_model=StoryForeshadowRead,
)
async def story_engine_foreshadow_patch(
    project_id: UUID,
    entity_id: UUID,
    payload: StoryForeshadowUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> StoryForeshadowRead:
    return await _update_entity_response(session, project_id=project_id, user_id=current_user.id, entity_type="foreshadows", entity_id=entity_id, payload=payload.model_dump(exclude_unset=True), schema=StoryForeshadowRead)


@router.delete(
    "/projects/{project_id}/story-engine/foreshadows/{entity_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def story_engine_foreshadow_delete(
    project_id: UUID,
    entity_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    await _delete_entity_response(session, project_id=project_id, user_id=current_user.id, entity_type="foreshadows", entity_id=entity_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/projects/{project_id}/story-engine/items",
    response_model=list[StoryItemRead],
)
async def story_engine_item_list(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[StoryItemRead]:
    return await _list_entity_response(session, project_id=project_id, user_id=current_user.id, entity_type="items", schema=StoryItemRead)


@router.post(
    "/projects/{project_id}/story-engine/items",
    response_model=StoryItemRead,
    status_code=status.HTTP_201_CREATED,
)
async def story_engine_item_create(
    project_id: UUID,
    payload: StoryItemCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> StoryItemRead:
    return await _create_entity_response(session, project_id=project_id, user_id=current_user.id, entity_type="items", payload=payload.model_dump(), schema=StoryItemRead)


@router.patch(
    "/projects/{project_id}/story-engine/items/{entity_id}",
    response_model=StoryItemRead,
)
async def story_engine_item_patch(
    project_id: UUID,
    entity_id: UUID,
    payload: StoryItemUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> StoryItemRead:
    return await _update_entity_response(session, project_id=project_id, user_id=current_user.id, entity_type="items", entity_id=entity_id, payload=payload.model_dump(exclude_unset=True), schema=StoryItemRead)


@router.delete(
    "/projects/{project_id}/story-engine/items/{entity_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def story_engine_item_delete(
    project_id: UUID,
    entity_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    await _delete_entity_response(session, project_id=project_id, user_id=current_user.id, entity_type="items", entity_id=entity_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/projects/{project_id}/story-engine/world-rules",
    response_model=list[StoryWorldRuleRead],
)
async def story_engine_world_rule_list(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[StoryWorldRuleRead]:
    return await _list_entity_response(session, project_id=project_id, user_id=current_user.id, entity_type="world_rules", schema=StoryWorldRuleRead)


@router.post(
    "/projects/{project_id}/story-engine/world-rules",
    response_model=StoryWorldRuleRead,
    status_code=status.HTTP_201_CREATED,
)
async def story_engine_world_rule_create(
    project_id: UUID,
    payload: StoryWorldRuleCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> StoryWorldRuleRead:
    return await _create_entity_response(session, project_id=project_id, user_id=current_user.id, entity_type="world_rules", payload=payload.model_dump(), schema=StoryWorldRuleRead)


@router.patch(
    "/projects/{project_id}/story-engine/world-rules/{entity_id}",
    response_model=StoryWorldRuleRead,
)
async def story_engine_world_rule_patch(
    project_id: UUID,
    entity_id: UUID,
    payload: StoryWorldRuleUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> StoryWorldRuleRead:
    return await _update_entity_response(session, project_id=project_id, user_id=current_user.id, entity_type="world_rules", entity_id=entity_id, payload=payload.model_dump(exclude_unset=True), schema=StoryWorldRuleRead)


@router.delete(
    "/projects/{project_id}/story-engine/world-rules/{entity_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def story_engine_world_rule_delete(
    project_id: UUID,
    entity_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    await _delete_entity_response(session, project_id=project_id, user_id=current_user.id, entity_type="world_rules", entity_id=entity_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/projects/{project_id}/story-engine/timeline-events",
    response_model=list[StoryTimelineMapEventRead],
)
async def story_engine_timeline_event_list(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[StoryTimelineMapEventRead]:
    return await _list_entity_response(session, project_id=project_id, user_id=current_user.id, entity_type="timeline_events", schema=StoryTimelineMapEventRead)


@router.post(
    "/projects/{project_id}/story-engine/timeline-events",
    response_model=StoryTimelineMapEventRead,
    status_code=status.HTTP_201_CREATED,
)
async def story_engine_timeline_event_create(
    project_id: UUID,
    payload: StoryTimelineMapEventCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> StoryTimelineMapEventRead:
    return await _create_entity_response(session, project_id=project_id, user_id=current_user.id, entity_type="timeline_events", payload=payload.model_dump(), schema=StoryTimelineMapEventRead)


@router.patch(
    "/projects/{project_id}/story-engine/timeline-events/{entity_id}",
    response_model=StoryTimelineMapEventRead,
)
async def story_engine_timeline_event_patch(
    project_id: UUID,
    entity_id: UUID,
    payload: StoryTimelineMapEventUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> StoryTimelineMapEventRead:
    return await _update_entity_response(session, project_id=project_id, user_id=current_user.id, entity_type="timeline_events", entity_id=entity_id, payload=payload.model_dump(exclude_unset=True), schema=StoryTimelineMapEventRead)


@router.delete(
    "/projects/{project_id}/story-engine/timeline-events/{entity_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def story_engine_timeline_event_delete(
    project_id: UUID,
    entity_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    await _delete_entity_response(session, project_id=project_id, user_id=current_user.id, entity_type="timeline_events", entity_id=entity_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/projects/{project_id}/story-engine/outlines",
    response_model=list[StoryOutlineRead],
)
async def story_engine_outline_list(
    project_id: UUID,
    branch_id: Optional[UUID] = Query(default=None),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[StoryOutlineRead]:
    return await _list_entity_response(
        session,
        project_id=project_id,
        user_id=current_user.id,
        entity_type="outlines",
        schema=StoryOutlineRead,
        branch_id=branch_id,
    )


@router.post(
    "/projects/{project_id}/story-engine/outlines",
    response_model=StoryOutlineRead,
    status_code=status.HTTP_201_CREATED,
)
async def story_engine_outline_create(
    project_id: UUID,
    payload: StoryOutlineCreate,
    branch_id: Optional[UUID] = Query(default=None),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> StoryOutlineRead:
    return await _create_entity_response(
        session,
        project_id=project_id,
        user_id=current_user.id,
        entity_type="outlines",
        payload=payload.model_dump(),
        schema=StoryOutlineRead,
        branch_id=branch_id,
    )


@router.patch(
    "/projects/{project_id}/story-engine/outlines/{entity_id}",
    response_model=StoryOutlineRead,
)
async def story_engine_outline_patch(
    project_id: UUID,
    entity_id: UUID,
    payload: StoryOutlineUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> StoryOutlineRead:
    return await _update_entity_response(session, project_id=project_id, user_id=current_user.id, entity_type="outlines", entity_id=entity_id, payload=payload.model_dump(exclude_unset=True), schema=StoryOutlineRead)


@router.delete(
    "/projects/{project_id}/story-engine/outlines/{entity_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def story_engine_outline_delete(
    project_id: UUID,
    entity_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    await _delete_entity_response(session, project_id=project_id, user_id=current_user.id, entity_type="outlines", entity_id=entity_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/projects/{project_id}/story-engine/chapter-summaries",
    response_model=list[StoryChapterSummaryRead],
)
async def story_engine_chapter_summary_list(
    project_id: UUID,
    branch_id: Optional[UUID] = Query(default=None),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[StoryChapterSummaryRead]:
    return await _list_entity_response(
        session,
        project_id=project_id,
        user_id=current_user.id,
        entity_type="chapter_summaries",
        schema=StoryChapterSummaryRead,
        branch_id=branch_id,
    )


@router.post(
    "/projects/{project_id}/story-engine/chapter-summaries",
    response_model=StoryChapterSummaryRead,
    status_code=status.HTTP_201_CREATED,
)
async def story_engine_chapter_summary_create(
    project_id: UUID,
    payload: StoryChapterSummaryCreate,
    branch_id: Optional[UUID] = Query(default=None),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> StoryChapterSummaryRead:
    return await _create_entity_response(
        session,
        project_id=project_id,
        user_id=current_user.id,
        entity_type="chapter_summaries",
        payload=payload.model_dump(),
        schema=StoryChapterSummaryRead,
        branch_id=branch_id,
    )


@router.patch(
    "/projects/{project_id}/story-engine/chapter-summaries/{entity_id}",
    response_model=StoryChapterSummaryRead,
)
async def story_engine_chapter_summary_patch(
    project_id: UUID,
    entity_id: UUID,
    payload: StoryChapterSummaryUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> StoryChapterSummaryRead:
    return await _update_entity_response(session, project_id=project_id, user_id=current_user.id, entity_type="chapter_summaries", entity_id=entity_id, payload=payload.model_dump(exclude_unset=True), schema=StoryChapterSummaryRead)


@router.delete(
    "/projects/{project_id}/story-engine/chapter-summaries/{entity_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def story_engine_chapter_summary_delete(
    project_id: UUID,
    entity_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    await _delete_entity_response(session, project_id=project_id, user_id=current_user.id, entity_type="chapter_summaries", entity_id=entity_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


async def _list_entity_response(
    session: AsyncSession,
    *,
    project_id: UUID,
    user_id: UUID,
    entity_type: str,
    schema,
    branch_id: Optional[UUID] = None,
) -> list[Any]:
    entities = await list_entities(
        session,
        project_id=project_id,
        user_id=user_id,
        entity_type=entity_type,
        branch_id=branch_id,
    )
    return [schema.model_validate(item) for item in entities]


async def _create_entity_response(
    session: AsyncSession,
    *,
    project_id: UUID,
    user_id: UUID,
    entity_type: str,
    payload: dict[str, Any],
    schema,
    branch_id: Optional[UUID] = None,
) -> Any:
    if branch_id is not None:
        payload = {**payload, "branch_id": branch_id}
    entity = await create_entity(
        session,
        project_id=project_id,
        user_id=user_id,
        entity_type=entity_type,
        payload=payload,
    )
    return schema.model_validate(entity)


async def _update_entity_response(
    session: AsyncSession,
    *,
    project_id: UUID,
    user_id: UUID,
    entity_type: str,
    entity_id: UUID,
    payload: dict[str, Any],
    schema,
) -> Any:
    entity = await update_entity(
        session,
        project_id=project_id,
        user_id=user_id,
        entity_type=entity_type,
        entity_id=entity_id,
        payload=payload,
    )
    return schema.model_validate(entity)


async def _delete_entity_response(
    session: AsyncSession,
    *,
    project_id: UUID,
    user_id: UUID,
    entity_type: str,
    entity_id: UUID,
) -> None:
    await delete_entity(
        session,
        project_id=project_id,
        user_id=user_id,
        entity_type=entity_type,
        entity_id=entity_id,
    )


def _ndjson_line(payload: dict[str, Any]) -> str:
    return json.dumps(jsonable_encoder(payload), ensure_ascii=False) + "\n"
