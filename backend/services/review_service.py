from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.errors import AppError
from models.chapter import Chapter
from models.chapter_checkpoint import ChapterCheckpoint
from models.chapter_comment import ChapterComment
from models.chapter_review_decision import ChapterReviewDecision
from schemas.chapter import (
    ChapterCheckpointCreate,
    ChapterCheckpointRead,
    ChapterCheckpointUpdate,
    ChapterReviewAssignableMemberRead,
    ChapterReviewCommentCreate,
    ChapterReviewCommentRead,
    ChapterReviewCommentUpdate,
    ChapterReviewDecisionCreate,
    ChapterReviewDecisionRead,
    ChapterReviewWorkspaceRead,
)
from services.chapter_gate_service import (
    CHAPTER_STATUS_REVIEW,
    CHECKPOINT_STATUS_APPROVED,
    CHECKPOINT_STATUS_CANCELLED,
    CHECKPOINT_STATUS_PENDING,
    CHECKPOINT_STATUS_REJECTED,
    REVIEW_VERDICT_APPROVED,
    REVIEW_VERDICT_BLOCKED,
    REVIEW_VERDICT_CHANGES_REQUESTED,
    should_downgrade_final_chapter_for_checkpoint,
    should_downgrade_final_chapter_for_review_decision,
)
from services.chapter_service import get_owned_chapter
from services.project_service import (
    PROJECT_PERMISSION_EDIT,
    PROJECT_PERMISSION_EVALUATE,
    PROJECT_PERMISSION_READ,
    PROJECT_ROLE_OWNER,
    get_owned_project,
    project_role_has_permission,
)


COMMENT_STATUS_OPEN = "open"
COMMENT_STATUS_IN_PROGRESS = "in_progress"
COMMENT_STATUS_RESOLVED = "resolved"
VALID_CHECKPOINT_TYPES = {
    "story_turn",
    "outline_gate",
    "quality_gate",
    "branch_decision",
    "manual_gate",
}
VALID_COMMENT_STATUSES = {
    COMMENT_STATUS_OPEN,
    COMMENT_STATUS_IN_PROGRESS,
    COMMENT_STATUS_RESOLVED,
}
VALID_REVIEW_VERDICTS = {
    REVIEW_VERDICT_APPROVED,
    REVIEW_VERDICT_CHANGES_REQUESTED,
    REVIEW_VERDICT_BLOCKED,
}
VALID_CHECKPOINT_STATUSES = {
    CHECKPOINT_STATUS_PENDING,
    CHECKPOINT_STATUS_APPROVED,
    CHECKPOINT_STATUS_REJECTED,
    CHECKPOINT_STATUS_CANCELLED,
}


async def get_chapter_review_workspace(
    session: AsyncSession,
    chapter_id: UUID,
    user_id: UUID,
) -> ChapterReviewWorkspaceRead:
    chapter = await get_owned_chapter(
        session,
        chapter_id,
        user_id,
        permission=PROJECT_PERMISSION_READ,
    )
    project = await get_owned_project(
        session,
        chapter.project_id,
        user_id,
        with_relations=True,
        permission=PROJECT_PERMISSION_READ,
    )
    comments = await _list_chapter_comments(session, chapter.id)
    decisions = await _list_chapter_review_decisions(session, chapter.id)
    checkpoints = await _list_chapter_checkpoints(session, chapter.id)
    return build_chapter_review_workspace_payload(
        chapter_id=chapter.id,
        project=project,
        comments=comments,
        decisions=decisions,
        checkpoints=checkpoints,
        current_user_id=user_id,
    )


async def create_chapter_comment(
    session: AsyncSession,
    chapter_id: UUID,
    user_id: UUID,
    payload: ChapterReviewCommentCreate,
) -> ChapterReviewCommentRead:
    chapter = await get_owned_chapter(
        session,
        chapter_id,
        user_id,
        permission=PROJECT_PERMISSION_EVALUATE,
    )
    project = await get_owned_project(
        session,
        chapter.project_id,
        user_id,
        with_relations=True,
        permission=PROJECT_PERMISSION_EVALUATE,
    )
    parent_comment = None
    if payload.parent_comment_id is not None:
        parent_comment = await _get_comment(
            session,
            chapter_id=chapter.id,
            comment_id=payload.parent_comment_id,
        )
        if parent_comment.parent_comment_id is not None:
            parent_comment = await _get_comment(
                session,
                chapter_id=chapter.id,
                comment_id=parent_comment.parent_comment_id,
            )
    if payload.assignee_user_id is not None:
        _validate_comment_assignee(project, payload.assignee_user_id)
    selection_start, selection_end, selection_text = _normalize_comment_anchor(payload)
    comment = ChapterComment(
        id=uuid4(),
        chapter_id=chapter.id,
        user_id=user_id,
        parent_comment_id=parent_comment.id if parent_comment is not None else None,
        chapter_version_number=await _current_chapter_version_number(session, chapter.id),
        body=payload.body.strip(),
        status=COMMENT_STATUS_OPEN,
        selection_start=selection_start,
        selection_end=selection_end,
        selection_text=selection_text,
        assignee_user_id=payload.assignee_user_id,
        assigned_by_user_id=user_id if payload.assignee_user_id else None,
        assigned_at=datetime.now(timezone.utc) if payload.assignee_user_id else None,
    )
    session.add(comment)
    await session.commit()
    hydrated = await _get_comment(
        session,
        chapter_id=chapter.id,
        comment_id=comment.id,
    )
    role = str(getattr(project, "access_role", PROJECT_ROLE_OWNER))
    return build_chapter_review_comment_payload(hydrated, role, user_id)


async def update_chapter_comment(
    session: AsyncSession,
    chapter_id: UUID,
    comment_id: UUID,
    user_id: UUID,
    payload: ChapterReviewCommentUpdate,
) -> ChapterReviewCommentRead:
    comment = await _get_comment(session, chapter_id=chapter_id, comment_id=comment_id)
    project = await get_owned_project(
        session,
        comment.chapter.project_id,
        user_id,
        with_relations=True,
        permission=PROJECT_PERMISSION_READ,
    )
    role = str(getattr(project, "access_role", PROJECT_ROLE_OWNER))
    can_manage_all = project_role_has_permission(role, PROJECT_PERMISSION_EDIT)
    is_author = comment.user_id == user_id
    if not can_manage_all and not is_author:
        raise AppError(
            code="chapter.comment_permission_denied",
            message="You do not have permission to update this comment.",
            status_code=403,
        )

    if payload.body is not None:
        comment.body = payload.body.strip()

    if payload.status is not None:
        next_status = _normalize_comment_status(payload.status)
        if next_status == COMMENT_STATUS_RESOLVED:
            comment.status = COMMENT_STATUS_RESOLVED
            comment.resolved_by_user_id = user_id
            comment.resolved_at = datetime.now(timezone.utc)
        elif next_status == COMMENT_STATUS_IN_PROGRESS:
            comment.status = COMMENT_STATUS_IN_PROGRESS
            comment.resolved_by_user_id = None
            comment.resolved_at = None
        else:
            comment.status = COMMENT_STATUS_OPEN
            comment.resolved_by_user_id = None
            comment.resolved_at = None

    if "assignee_user_id" in payload.model_fields_set:
        if payload.assignee_user_id is None:
            comment.assignee_user_id = None
            comment.assigned_by_user_id = None
            comment.assigned_at = None
        else:
            _validate_comment_assignee(project, payload.assignee_user_id)
            comment.assignee_user_id = payload.assignee_user_id
            comment.assigned_by_user_id = user_id
            comment.assigned_at = datetime.now(timezone.utc)

    await session.commit()
    hydrated = await _get_comment(
        session,
        chapter_id=chapter_id,
        comment_id=comment_id,
    )
    return build_chapter_review_comment_payload(hydrated, role, user_id)


async def delete_chapter_comment(
    session: AsyncSession,
    chapter_id: UUID,
    comment_id: UUID,
    user_id: UUID,
) -> None:
    comment = await _get_comment(session, chapter_id=chapter_id, comment_id=comment_id)
    project = await get_owned_project(
        session,
        comment.chapter.project_id,
        user_id,
        permission=PROJECT_PERMISSION_READ,
    )
    role = str(getattr(project, "access_role", PROJECT_ROLE_OWNER))
    can_manage_all = project_role_has_permission(role, PROJECT_PERMISSION_EDIT)
    is_author = comment.user_id == user_id
    if not can_manage_all and not is_author:
        raise AppError(
            code="chapter.comment_permission_denied",
            message="You do not have permission to delete this comment.",
            status_code=403,
        )
    if await _comment_has_replies(session, comment.id):
        raise AppError(
            code="chapter.comment_has_replies",
            message="Delete replies before deleting this comment.",
            status_code=409,
        )
    await session.delete(comment)
    await session.commit()


async def create_chapter_review_decision(
    session: AsyncSession,
    chapter_id: UUID,
    user_id: UUID,
    payload: ChapterReviewDecisionCreate,
) -> ChapterReviewDecisionRead:
    chapter = await get_owned_chapter(
        session,
        chapter_id,
        user_id,
        permission=PROJECT_PERMISSION_EVALUATE,
    )
    decision = ChapterReviewDecision(
        chapter_id=chapter.id,
        user_id=user_id,
        chapter_version_number=await _current_chapter_version_number(session, chapter.id),
        verdict=_normalize_review_verdict(payload.verdict),
        summary=payload.summary.strip(),
        focus_points=[item.strip() for item in payload.focus_points if item.strip()],
    )
    if should_downgrade_final_chapter_for_review_decision(
        chapter_status=chapter.status,
        verdict=decision.verdict,
    ):
        chapter.status = CHAPTER_STATUS_REVIEW
    session.add(decision)
    await session.commit()
    hydrated = await _get_review_decision(
        session,
        chapter_id=chapter.id,
        decision_id=decision.id,
    )
    return build_chapter_review_decision_payload(hydrated)


async def create_chapter_checkpoint(
    session: AsyncSession,
    chapter_id: UUID,
    user_id: UUID,
    payload: ChapterCheckpointCreate,
) -> ChapterCheckpointRead:
    chapter = await get_owned_chapter(
        session,
        chapter_id,
        user_id,
        permission=PROJECT_PERMISSION_EVALUATE,
    )
    checkpoint = ChapterCheckpoint(
        chapter_id=chapter.id,
        requester_user_id=user_id,
        chapter_version_number=await _current_chapter_version_number(session, chapter.id),
        checkpoint_type=_normalize_checkpoint_type(payload.checkpoint_type),
        title=payload.title.strip(),
        description=payload.description.strip() if payload.description else None,
        status=CHECKPOINT_STATUS_PENDING,
    )
    if should_downgrade_final_chapter_for_checkpoint(
        chapter_status=chapter.status,
        checkpoint_status=CHECKPOINT_STATUS_PENDING,
    ):
        chapter.status = CHAPTER_STATUS_REVIEW
    session.add(checkpoint)
    await session.commit()
    hydrated = await _get_checkpoint(
        session,
        chapter_id=chapter.id,
        checkpoint_id=checkpoint.id,
    )
    project = await get_owned_project(
        session,
        chapter.project_id,
        user_id,
        permission=PROJECT_PERMISSION_READ,
    )
    role = str(getattr(project, "access_role", PROJECT_ROLE_OWNER))
    return build_chapter_checkpoint_payload(hydrated, role, user_id)


async def update_chapter_checkpoint(
    session: AsyncSession,
    chapter_id: UUID,
    checkpoint_id: UUID,
    user_id: UUID,
    payload: ChapterCheckpointUpdate,
) -> ChapterCheckpointRead:
    checkpoint = await _get_checkpoint(
        session,
        chapter_id=chapter_id,
        checkpoint_id=checkpoint_id,
    )
    project = await get_owned_project(
        session,
        checkpoint.chapter.project_id,
        user_id,
        permission=PROJECT_PERMISSION_READ,
    )
    role = str(getattr(project, "access_role", PROJECT_ROLE_OWNER))
    can_evaluate = project_role_has_permission(role, PROJECT_PERMISSION_EVALUATE)
    can_manage_all = project_role_has_permission(role, PROJECT_PERMISSION_EDIT)
    is_requester = checkpoint.requester_user_id == user_id
    next_status = _normalize_checkpoint_status(payload.status)

    if next_status == CHECKPOINT_STATUS_CANCELLED:
        if not (is_requester or can_manage_all):
            raise AppError(
                code="chapter.checkpoint_permission_denied",
                message="You do not have permission to cancel this checkpoint.",
                status_code=403,
            )
    elif not can_evaluate:
        raise AppError(
            code="chapter.checkpoint_permission_denied",
            message="You do not have permission to decide this checkpoint.",
            status_code=403,
        )

    checkpoint.status = next_status
    checkpoint.decision_note = payload.decision_note.strip() if payload.decision_note else None
    if should_downgrade_final_chapter_for_checkpoint(
        chapter_status=checkpoint.chapter.status,
        checkpoint_status=next_status,
    ):
        checkpoint.chapter.status = CHAPTER_STATUS_REVIEW

    if next_status == CHECKPOINT_STATUS_PENDING:
        checkpoint.decided_by_user_id = None
        checkpoint.decided_at = None
    else:
        checkpoint.decided_by_user_id = user_id
        checkpoint.decided_at = datetime.now(timezone.utc)

    await session.commit()
    hydrated = await _get_checkpoint(
        session,
        chapter_id=chapter_id,
        checkpoint_id=checkpoint_id,
    )
    return build_chapter_checkpoint_payload(hydrated, role, user_id)


def build_chapter_review_workspace_payload(
    *,
    chapter_id: UUID,
    project,
    comments: list[ChapterComment],
    decisions: list[ChapterReviewDecision],
    checkpoints: list[ChapterCheckpoint],
    current_user_id: UUID,
) -> ChapterReviewWorkspaceRead:
    role = str(getattr(project, "access_role", PROJECT_ROLE_OWNER))
    can_edit_chapter = project_role_has_permission(role, PROJECT_PERMISSION_EDIT)
    can_evaluate = project_role_has_permission(role, PROJECT_PERMISSION_EVALUATE)
    assignable_members = build_chapter_review_assignable_members_payload(project)
    open_comments = [item for item in comments if item.status == COMMENT_STATUS_OPEN]
    in_progress_comments = [item for item in comments if item.status == COMMENT_STATUS_IN_PROGRESS]
    resolved_comments = [item for item in comments if item.status == COMMENT_STATUS_RESOLVED]
    ordered_comments = _order_comments_for_workspace(
        open_comments + in_progress_comments + resolved_comments
    )
    decision_payloads = [build_chapter_review_decision_payload(item) for item in decisions]
    pending_checkpoints = [
        item for item in checkpoints if item.status == CHECKPOINT_STATUS_PENDING
    ]
    closed_checkpoints = [
        item for item in checkpoints if item.status != CHECKPOINT_STATUS_PENDING
    ]
    ordered_checkpoints = pending_checkpoints + closed_checkpoints
    checkpoint_payloads = [
        build_chapter_checkpoint_payload(item, role, current_user_id)
        for item in ordered_checkpoints
    ]
    pending_checkpoint_payloads = [
        item for item in checkpoint_payloads if item.status == CHECKPOINT_STATUS_PENDING
    ]
    reply_counts = _build_reply_counts(comments)

    return ChapterReviewWorkspaceRead(
        chapter_id=chapter_id,
        current_role=role,
        owner_email=getattr(project, "owner_email", None),
        can_edit_chapter=can_edit_chapter,
        can_run_generation=can_edit_chapter,
        can_run_evaluation=can_evaluate,
        can_comment=can_evaluate,
        can_assign_comment=can_evaluate,
        can_decide=can_evaluate,
        can_request_checkpoint=can_evaluate,
        can_decide_checkpoint=can_evaluate,
        open_comment_count=len(open_comments),
        resolved_comment_count=len(resolved_comments),
        pending_checkpoint_count=len(pending_checkpoints),
        latest_decision=decision_payloads[0] if decision_payloads else None,
        latest_pending_checkpoint=(
            pending_checkpoint_payloads[0] if pending_checkpoint_payloads else None
        ),
        assignable_members=assignable_members,
        comments=[
            build_chapter_review_comment_payload(
                item,
                role,
                current_user_id,
                reply_count=reply_counts.get(item.id, 0),
            )
            for item in ordered_comments
        ],
        decisions=decision_payloads,
        checkpoints=checkpoint_payloads,
    )


def build_chapter_review_comment_payload(
    comment: ChapterComment,
    role: str,
    current_user_id: UUID,
    *,
    reply_count: int = 0,
) -> ChapterReviewCommentRead:
    can_manage_all = project_role_has_permission(role, PROJECT_PERMISSION_EDIT)
    is_author = comment.user_id == current_user_id
    can_manage_own = is_author and project_role_has_permission(role, PROJECT_PERMISSION_EVALUATE)
    return ChapterReviewCommentRead(
        id=comment.id,
        chapter_id=comment.chapter_id,
        user_id=comment.user_id,
        parent_comment_id=getattr(comment, "parent_comment_id", None),
        chapter_version_number=comment.chapter_version_number,
        author_email=getattr(getattr(comment, "user", None), "email", "") or "",
        body=comment.body,
        status=comment.status,
        selection_start=comment.selection_start,
        selection_end=comment.selection_end,
        selection_text=comment.selection_text,
        assignee_user_id=getattr(comment, "assignee_user_id", None),
        assignee_email=getattr(getattr(comment, "assignee", None), "email", None),
        assigned_by_user_id=getattr(comment, "assigned_by_user_id", None),
        assigned_by_email=getattr(getattr(comment, "assigned_by", None), "email", None),
        assigned_at=getattr(comment, "assigned_at", None),
        resolved_by_user_id=comment.resolved_by_user_id,
        resolved_by_email=getattr(getattr(comment, "resolved_by", None), "email", None),
        resolved_at=comment.resolved_at,
        created_at=comment.created_at,
        updated_at=comment.updated_at,
        reply_count=reply_count,
        can_edit=can_manage_all or can_manage_own,
        can_assign=can_manage_all or can_manage_own,
        can_change_status=can_manage_all or can_manage_own,
        can_delete=(can_manage_all or can_manage_own) and reply_count == 0,
    )


def build_chapter_review_assignable_members_payload(
    project,
) -> list[ChapterReviewAssignableMemberRead]:
    members: list[ChapterReviewAssignableMemberRead] = []
    seen_user_ids: set[UUID] = set()

    owner_user_id = getattr(project, "user_id", None)
    if owner_user_id is not None:
        members.append(
            ChapterReviewAssignableMemberRead(
                user_id=owner_user_id,
                email=(
                    getattr(getattr(project, "user", None), "email", None)
                    or getattr(project, "owner_email", None)
                    or ""
                ),
                role=PROJECT_ROLE_OWNER,
                is_owner=True,
            )
        )
        seen_user_ids.add(owner_user_id)

    collaborators = sorted(
        getattr(project, "collaborators", []) or [],
        key=lambda item: (str(getattr(item, "role", "")), str(getattr(item, "user_id", ""))),
    )
    for collaborator in collaborators:
        collaborator_user_id = getattr(collaborator, "user_id", None)
        if collaborator_user_id is None or collaborator_user_id in seen_user_ids:
            continue
        members.append(
            ChapterReviewAssignableMemberRead(
                user_id=collaborator_user_id,
                email=getattr(getattr(collaborator, "user", None), "email", "") or "",
                role=str(getattr(collaborator, "role", "")),
                is_owner=False,
            )
        )
        seen_user_ids.add(collaborator_user_id)

    return members


def build_chapter_review_decision_payload(
    decision: ChapterReviewDecision,
) -> ChapterReviewDecisionRead:
    return ChapterReviewDecisionRead(
        id=decision.id,
        chapter_id=decision.chapter_id,
        user_id=decision.user_id,
        chapter_version_number=decision.chapter_version_number,
        reviewer_email=getattr(getattr(decision, "user", None), "email", "") or "",
        verdict=decision.verdict,
        summary=decision.summary,
        focus_points=list(decision.focus_points or []),
        created_at=decision.created_at,
    )


def build_chapter_checkpoint_payload(
    checkpoint: ChapterCheckpoint,
    role: str,
    current_user_id: UUID,
) -> ChapterCheckpointRead:
    can_evaluate = project_role_has_permission(role, PROJECT_PERMISSION_EVALUATE)
    can_manage_all = project_role_has_permission(role, PROJECT_PERMISSION_EDIT)
    is_requester = checkpoint.requester_user_id == current_user_id
    can_decide = can_evaluate and checkpoint.status == CHECKPOINT_STATUS_PENDING
    can_cancel = checkpoint.status == CHECKPOINT_STATUS_PENDING and (
        is_requester or can_manage_all
    )
    return ChapterCheckpointRead(
        id=checkpoint.id,
        chapter_id=checkpoint.chapter_id,
        requester_user_id=checkpoint.requester_user_id,
        chapter_version_number=checkpoint.chapter_version_number,
        checkpoint_type=checkpoint.checkpoint_type,
        title=checkpoint.title,
        description=checkpoint.description,
        status=checkpoint.status,
        decision_note=checkpoint.decision_note,
        requester_email=getattr(getattr(checkpoint, "requester", None), "email", "") or "",
        decided_by_user_id=checkpoint.decided_by_user_id,
        decided_by_email=getattr(getattr(checkpoint, "decided_by", None), "email", None),
        decided_at=checkpoint.decided_at,
        created_at=checkpoint.created_at,
        updated_at=checkpoint.updated_at,
        can_decide=can_decide,
        can_cancel=can_cancel,
    )


async def _list_chapter_comments(
    session: AsyncSession,
    chapter_id: UUID,
) -> list[ChapterComment]:
    result = await session.execute(
        select(ChapterComment)
        .where(ChapterComment.chapter_id == chapter_id)
        .options(
            selectinload(ChapterComment.user),
            selectinload(ChapterComment.assignee),
            selectinload(ChapterComment.assigned_by),
            selectinload(ChapterComment.resolved_by),
        )
        .order_by(ChapterComment.created_at.asc())
    )
    return list(result.scalars().all())


async def _list_chapter_review_decisions(
    session: AsyncSession,
    chapter_id: UUID,
) -> list[ChapterReviewDecision]:
    result = await session.execute(
        select(ChapterReviewDecision)
        .where(ChapterReviewDecision.chapter_id == chapter_id)
        .options(selectinload(ChapterReviewDecision.user))
        .order_by(ChapterReviewDecision.created_at.desc())
    )
    return list(result.scalars().all())


async def _list_chapter_checkpoints(
    session: AsyncSession,
    chapter_id: UUID,
) -> list[ChapterCheckpoint]:
    result = await session.execute(
        select(ChapterCheckpoint)
        .where(ChapterCheckpoint.chapter_id == chapter_id)
        .options(
            selectinload(ChapterCheckpoint.requester),
            selectinload(ChapterCheckpoint.decided_by),
        )
        .order_by(ChapterCheckpoint.created_at.desc())
    )
    return list(result.scalars().all())


async def _get_comment(
    session: AsyncSession,
    *,
    chapter_id: UUID,
    comment_id: UUID,
) -> ChapterComment:
    result = await session.execute(
        select(ChapterComment)
        .where(
            ChapterComment.id == comment_id,
            ChapterComment.chapter_id == chapter_id,
        )
        .options(
            selectinload(ChapterComment.chapter),
            selectinload(ChapterComment.user),
            selectinload(ChapterComment.assignee),
            selectinload(ChapterComment.assigned_by),
            selectinload(ChapterComment.resolved_by),
        )
    )
    comment = result.scalar_one_or_none()
    if comment is None:
        raise AppError(
            code="chapter.comment_not_found",
            message="Chapter comment not found.",
            status_code=404,
        )
    return comment


async def _get_review_decision(
    session: AsyncSession,
    *,
    chapter_id: UUID,
    decision_id: UUID,
) -> ChapterReviewDecision:
    result = await session.execute(
        select(ChapterReviewDecision)
        .where(
            ChapterReviewDecision.id == decision_id,
            ChapterReviewDecision.chapter_id == chapter_id,
        )
        .options(selectinload(ChapterReviewDecision.user))
    )
    decision = result.scalar_one_or_none()
    if decision is None:
        raise AppError(
            code="chapter.review_decision_not_found",
            message="Chapter review decision not found.",
            status_code=404,
    )
    return decision


async def _get_checkpoint(
    session: AsyncSession,
    *,
    chapter_id: UUID,
    checkpoint_id: UUID,
) -> ChapterCheckpoint:
    result = await session.execute(
        select(ChapterCheckpoint)
        .where(
            ChapterCheckpoint.id == checkpoint_id,
            ChapterCheckpoint.chapter_id == chapter_id,
        )
        .options(
            selectinload(ChapterCheckpoint.chapter),
            selectinload(ChapterCheckpoint.requester),
            selectinload(ChapterCheckpoint.decided_by),
        )
    )
    checkpoint = result.scalar_one_or_none()
    if checkpoint is None:
        raise AppError(
            code="chapter.checkpoint_not_found",
            message="Chapter checkpoint not found.",
            status_code=404,
        )
    return checkpoint


async def _current_chapter_version_number(
    session: AsyncSession,
    chapter_id: UUID,
) -> int:
    result = await session.execute(
        select(Chapter.current_version_number).where(Chapter.id == chapter_id)
    )
    return int(result.scalar_one_or_none() or 1)


async def _comment_has_replies(
    session: AsyncSession,
    comment_id: UUID,
) -> bool:
    result = await session.execute(
        select(ChapterComment.id).where(ChapterComment.parent_comment_id == comment_id).limit(1)
    )
    return result.scalar_one_or_none() is not None


def _build_reply_counts(comments: list[ChapterComment]) -> dict[UUID, int]:
    counts: dict[UUID, int] = {}
    for item in comments:
        parent_comment_id = getattr(item, "parent_comment_id", None)
        if parent_comment_id is None:
            continue
        counts[parent_comment_id] = counts.get(parent_comment_id, 0) + 1
    return counts


def _order_comments_for_workspace(comments: list[ChapterComment]) -> list[ChapterComment]:
    roots: list[ChapterComment] = []
    replies_by_parent: dict[UUID, list[ChapterComment]] = {}
    root_ids: set[UUID] = set()

    for item in comments:
        parent_comment_id = getattr(item, "parent_comment_id", None)
        if parent_comment_id is None:
            roots.append(item)
            root_ids.add(item.id)
            continue
        replies_by_parent.setdefault(parent_comment_id, []).append(item)

    for parent_id, replies in list(replies_by_parent.items()):
        replies.sort(key=lambda item: item.created_at)
        if parent_id not in root_ids:
            roots.extend(replies)
            replies_by_parent.pop(parent_id, None)

    open_roots = [item for item in roots if item.status == COMMENT_STATUS_OPEN]
    in_progress_roots = [item for item in roots if item.status == COMMENT_STATUS_IN_PROGRESS]
    resolved_roots = [item for item in roots if item.status == COMMENT_STATUS_RESOLVED]
    ordered_roots = (
        sorted(open_roots, key=lambda item: item.created_at, reverse=True)
        + sorted(in_progress_roots, key=lambda item: item.created_at, reverse=True)
        + sorted(resolved_roots, key=lambda item: item.created_at, reverse=True)
    )

    ordered: list[ChapterComment] = []
    for root in ordered_roots:
        ordered.append(root)
        ordered.extend(replies_by_parent.get(root.id, []))
    return ordered


def _normalize_comment_anchor(
    payload: ChapterReviewCommentCreate,
) -> tuple[int | None, int | None, str | None]:
    if payload.selection_start is None and payload.selection_end is None:
        selection_text = payload.selection_text.strip() if payload.selection_text else None
        return None, None, selection_text or None

    if payload.selection_start is None or payload.selection_end is None:
        raise AppError(
            code="chapter.comment_anchor_invalid",
            message="Selection anchor is invalid.",
            status_code=400,
        )
    if payload.selection_end <= payload.selection_start:
        raise AppError(
            code="chapter.comment_anchor_invalid",
            message="Selection anchor is invalid.",
            status_code=400,
        )
    selection_text = payload.selection_text.strip() if payload.selection_text else None
    return payload.selection_start, payload.selection_end, selection_text or None


def _validate_comment_assignee(project, assignee_user_id: UUID) -> None:
    allowed_user_ids = {getattr(project, "user_id", None)}
    allowed_user_ids.update(
        getattr(collaborator, "user_id", None)
        for collaborator in getattr(project, "collaborators", []) or []
    )
    if assignee_user_id in allowed_user_ids:
        return
    raise AppError(
        code="chapter.comment_assignee_not_in_project",
        message="Comment assignee must be a project member.",
        status_code=400,
    )


def _normalize_comment_status(value: str) -> str:
    normalized = value.strip().lower()
    if normalized not in VALID_COMMENT_STATUSES:
        raise AppError(
            code="chapter.comment_status_invalid",
            message="Comment status is invalid.",
            status_code=400,
        )
    return normalized


def _normalize_review_verdict(value: str) -> str:
    normalized = value.strip().lower()
    if normalized not in VALID_REVIEW_VERDICTS:
        raise AppError(
            code="chapter.review_verdict_invalid",
            message="Review verdict is invalid.",
            status_code=400,
        )
    return normalized


def _normalize_checkpoint_type(value: str) -> str:
    normalized = value.strip().lower()
    if normalized not in VALID_CHECKPOINT_TYPES:
        raise AppError(
            code="chapter.checkpoint_type_invalid",
            message="Checkpoint type is invalid.",
            status_code=400,
        )
    return normalized


def _normalize_checkpoint_status(value: str) -> str:
    normalized = value.strip().lower()
    if normalized not in VALID_CHECKPOINT_STATUSES:
        raise AppError(
            code="chapter.checkpoint_status_invalid",
            message="Checkpoint status is invalid.",
            status_code=400,
        )
    return normalized
