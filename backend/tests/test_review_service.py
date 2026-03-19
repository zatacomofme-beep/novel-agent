from __future__ import annotations

import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from schemas.chapter import ChapterReviewCommentCreate, ChapterReviewDecisionCreate
from services.review_service import (
    build_chapter_review_workspace_payload,
    create_chapter_comment,
    create_chapter_review_decision,
)


class ReviewServiceTests(unittest.TestCase):
    def test_workspace_payload_exposes_reviewer_permissions_and_latest_decision(self) -> None:
        chapter_id = uuid4()
        reviewer_id = uuid4()
        other_user_id = uuid4()
        now = datetime.now(timezone.utc)
        payload = build_chapter_review_workspace_payload(
            chapter_id=chapter_id,
            project=SimpleNamespace(
                access_role="reviewer",
                owner_email="owner@example.com",
            ),
            comments=[
                SimpleNamespace(
                    id=uuid4(),
                    chapter_id=chapter_id,
                    user_id=reviewer_id,
                    chapter_version_number=4,
                    body="这段情绪切得有点急。",
                    status="open",
                    selection_start=12,
                    selection_end=36,
                    selection_text="她把杯子放下，笑意却没到眼底。",
                    resolved_by_user_id=None,
                    resolved_at=None,
                    created_at=now,
                    updated_at=now,
                    user=SimpleNamespace(email="reviewer@example.com"),
                    resolved_by=None,
                ),
                SimpleNamespace(
                    id=uuid4(),
                    chapter_id=chapter_id,
                    user_id=other_user_id,
                    chapter_version_number=3,
                    body="这里的转场还可以再清晰一点。",
                    status="resolved",
                    selection_start=None,
                    selection_end=None,
                    selection_text=None,
                    resolved_by_user_id=reviewer_id,
                    resolved_at=now,
                    created_at=now,
                    updated_at=now,
                    user=SimpleNamespace(email="editor@example.com"),
                    resolved_by=SimpleNamespace(email="reviewer@example.com"),
                ),
            ],
            decisions=[
                SimpleNamespace(
                    id=uuid4(),
                    chapter_id=chapter_id,
                    user_id=reviewer_id,
                    chapter_version_number=4,
                    verdict="changes_requested",
                    summary="情绪推进还需要再压一轮。",
                    focus_points=["情绪承接", "段落收束"],
                    created_at=now,
                    user=SimpleNamespace(email="reviewer@example.com"),
                )
            ],
            checkpoints=[
                SimpleNamespace(
                    id=uuid4(),
                    chapter_id=chapter_id,
                    requester_user_id=reviewer_id,
                    chapter_version_number=4,
                    checkpoint_type="story_turn",
                    title="主角是否暴露身份",
                    description="这一转折要人工确认再继续。",
                    status="pending",
                    decision_note=None,
                    decided_by_user_id=None,
                    decided_at=None,
                    created_at=now,
                    updated_at=now,
                    requester=SimpleNamespace(email="reviewer@example.com"),
                    decided_by=None,
                )
            ],
            current_user_id=reviewer_id,
        )

        self.assertEqual(payload.current_role, "reviewer")
        self.assertFalse(payload.can_edit_chapter)
        self.assertTrue(payload.can_run_evaluation)
        self.assertFalse(payload.can_run_generation)
        self.assertTrue(payload.can_comment)
        self.assertTrue(payload.can_decide)
        self.assertEqual(payload.open_comment_count, 1)
        self.assertEqual(payload.resolved_comment_count, 1)
        self.assertEqual(payload.pending_checkpoint_count, 1)
        self.assertEqual(payload.latest_decision.verdict, "changes_requested")
        self.assertEqual(payload.latest_pending_checkpoint.title, "主角是否暴露身份")
        self.assertEqual(payload.comments[0].author_email, "reviewer@example.com")
        self.assertTrue(payload.comments[0].can_change_status)
        self.assertFalse(payload.comments[1].can_delete)
        self.assertTrue(payload.checkpoints[0].can_decide)
        self.assertTrue(payload.checkpoints[0].can_cancel)

    def test_workspace_payload_allows_owner_to_manage_all_comments(self) -> None:
        chapter_id = uuid4()
        owner_id = uuid4()
        reviewer_id = uuid4()
        now = datetime.now(timezone.utc)
        payload = build_chapter_review_workspace_payload(
            chapter_id=chapter_id,
            project=SimpleNamespace(
                access_role="owner",
                owner_email="owner@example.com",
            ),
            comments=[
                SimpleNamespace(
                    id=uuid4(),
                    chapter_id=chapter_id,
                    user_id=reviewer_id,
                    chapter_version_number=2,
                    body="这里需要补动机。",
                    status="open",
                    selection_start=None,
                    selection_end=None,
                    selection_text=None,
                    resolved_by_user_id=None,
                    resolved_at=None,
                    created_at=now,
                    updated_at=now,
                    user=SimpleNamespace(email="reviewer@example.com"),
                    resolved_by=None,
                )
            ],
            decisions=[],
            checkpoints=[
                SimpleNamespace(
                    id=uuid4(),
                    chapter_id=chapter_id,
                    requester_user_id=reviewer_id,
                    chapter_version_number=2,
                    checkpoint_type="manual_gate",
                    title="是否保留梦境伏笔",
                    description=None,
                    status="pending",
                    decision_note=None,
                    decided_by_user_id=None,
                    decided_at=None,
                    created_at=now,
                    updated_at=now,
                    requester=SimpleNamespace(email="reviewer@example.com"),
                    decided_by=None,
                )
            ],
            current_user_id=owner_id,
        )

        self.assertTrue(payload.can_edit_chapter)
        self.assertTrue(payload.can_run_generation)
        self.assertTrue(payload.can_run_evaluation)
        self.assertTrue(payload.comments[0].can_edit)
        self.assertTrue(payload.comments[0].can_change_status)
        self.assertTrue(payload.comments[0].can_delete)
        self.assertTrue(payload.checkpoints[0].can_decide)
        self.assertTrue(payload.checkpoints[0].can_cancel)

    def test_workspace_payload_sorts_pending_checkpoint_ahead_of_closed_items(self) -> None:
        chapter_id = uuid4()
        reviewer_id = uuid4()
        now = datetime.now(timezone.utc)
        payload = build_chapter_review_workspace_payload(
            chapter_id=chapter_id,
            project=SimpleNamespace(
                access_role="reviewer",
                owner_email="owner@example.com",
            ),
            comments=[],
            decisions=[],
            checkpoints=[
                SimpleNamespace(
                    id=uuid4(),
                    chapter_id=chapter_id,
                    requester_user_id=reviewer_id,
                    chapter_version_number=2,
                    checkpoint_type="quality_gate",
                    title="质量阈值是否达标",
                    description=None,
                    status="approved",
                    decision_note="可以继续。",
                    decided_by_user_id=reviewer_id,
                    decided_at=now,
                    created_at=now,
                    updated_at=now,
                    requester=SimpleNamespace(email="reviewer@example.com"),
                    decided_by=SimpleNamespace(email="reviewer@example.com"),
                ),
                SimpleNamespace(
                    id=uuid4(),
                    chapter_id=chapter_id,
                    requester_user_id=reviewer_id,
                    chapter_version_number=3,
                    checkpoint_type="story_turn",
                    title="反转是否提前揭露",
                    description="待确认。",
                    status="pending",
                    decision_note=None,
                    decided_by_user_id=None,
                    decided_at=None,
                    created_at=now,
                    updated_at=now,
                    requester=SimpleNamespace(email="reviewer@example.com"),
                    decided_by=None,
                ),
            ],
            current_user_id=reviewer_id,
        )

        self.assertEqual(payload.pending_checkpoint_count, 1)
        self.assertEqual(payload.checkpoints[0].status, "pending")
        self.assertEqual(payload.latest_pending_checkpoint.title, "反转是否提前揭露")

    def test_workspace_payload_threads_replies_under_root_comment(self) -> None:
        chapter_id = uuid4()
        owner_id = uuid4()
        root_comment_id = uuid4()
        reply_comment_id = uuid4()
        resolved_root_id = uuid4()
        now = datetime.now(timezone.utc)
        payload = build_chapter_review_workspace_payload(
            chapter_id=chapter_id,
            project=SimpleNamespace(
                access_role="owner",
                owner_email="owner@example.com",
            ),
            comments=[
                SimpleNamespace(
                    id=resolved_root_id,
                    chapter_id=chapter_id,
                    user_id=owner_id,
                    parent_comment_id=None,
                    chapter_version_number=2,
                    body="这段已经修完。",
                    status="resolved",
                    selection_start=None,
                    selection_end=None,
                    selection_text=None,
                    resolved_by_user_id=owner_id,
                    resolved_at=now,
                    created_at=now.replace(second=1),
                    updated_at=now.replace(second=1),
                    user=SimpleNamespace(email="owner@example.com"),
                    resolved_by=SimpleNamespace(email="owner@example.com"),
                ),
                SimpleNamespace(
                    id=reply_comment_id,
                    chapter_id=chapter_id,
                    user_id=owner_id,
                    parent_comment_id=root_comment_id,
                    chapter_version_number=3,
                    body="这个点我准备在下一稿补。",
                    status="open",
                    selection_start=None,
                    selection_end=None,
                    selection_text=None,
                    resolved_by_user_id=None,
                    resolved_at=None,
                    created_at=now.replace(second=5),
                    updated_at=now.replace(second=5),
                    user=SimpleNamespace(email="owner@example.com"),
                    resolved_by=None,
                ),
                SimpleNamespace(
                    id=root_comment_id,
                    chapter_id=chapter_id,
                    user_id=owner_id,
                    parent_comment_id=None,
                    chapter_version_number=3,
                    body="这里的冲突触发还不够。",
                    status="open",
                    selection_start=10,
                    selection_end=18,
                    selection_text="他还是没开口。",
                    resolved_by_user_id=None,
                    resolved_at=None,
                    created_at=now.replace(second=3),
                    updated_at=now.replace(second=3),
                    user=SimpleNamespace(email="owner@example.com"),
                    resolved_by=None,
                ),
            ],
            decisions=[],
            checkpoints=[],
            current_user_id=owner_id,
        )

        self.assertEqual(payload.comments[0].id, root_comment_id)
        self.assertEqual(payload.comments[0].reply_count, 1)
        self.assertFalse(payload.comments[0].can_delete)
        self.assertEqual(payload.comments[1].parent_comment_id, root_comment_id)
        self.assertEqual(payload.comments[1].reply_count, 0)
        self.assertEqual(payload.comments[2].id, resolved_root_id)


class ReviewServiceAsyncTests(unittest.IsolatedAsyncioTestCase):
    async def test_create_comment_reply_attaches_to_root_thread(self) -> None:
        added_items = []

        def capture_add(item) -> None:  # noqa: ANN001
            added_items.append(item)

        session = SimpleNamespace(
            add=MagicMock(side_effect=capture_add),
            commit=AsyncMock(),
        )
        chapter_id = uuid4()
        project_id = uuid4()
        user_id = uuid4()
        root_comment_id = uuid4()
        reply_comment_id = uuid4()
        chapter = SimpleNamespace(
            id=chapter_id,
            project_id=project_id,
        )
        project = SimpleNamespace(access_role="reviewer")

        async def get_comment_side_effect(session_arg, *, chapter_id, comment_id):  # noqa: ANN001
            if comment_id == reply_comment_id:
                return SimpleNamespace(
                    id=reply_comment_id,
                    chapter_id=chapter_id,
                    parent_comment_id=root_comment_id,
                )
            if comment_id == root_comment_id:
                return SimpleNamespace(
                    id=root_comment_id,
                    chapter_id=chapter_id,
                    parent_comment_id=None,
                )
            created = added_items[0]
            return SimpleNamespace(
                id=created.id,
                chapter_id=created.chapter_id,
                user_id=created.user_id,
                parent_comment_id=created.parent_comment_id,
                chapter_version_number=created.chapter_version_number,
                body=created.body,
                status=created.status,
                selection_start=created.selection_start,
                selection_end=created.selection_end,
                selection_text=created.selection_text,
                resolved_by_user_id=None,
                resolved_by_email=None,
                resolved_at=None,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
                user=SimpleNamespace(email="reviewer@example.com"),
                resolved_by=None,
            )

        with patch(
            "services.review_service.get_owned_chapter",
            new=AsyncMock(return_value=chapter),
        ), patch(
            "services.review_service.get_owned_project",
            new=AsyncMock(return_value=project),
        ), patch(
            "services.review_service._current_chapter_version_number",
            new=AsyncMock(return_value=6),
        ), patch(
            "services.review_service._get_comment",
            new=AsyncMock(side_effect=get_comment_side_effect),
        ):
            result = await create_chapter_comment(
                session,
                chapter_id,
                user_id,
                ChapterReviewCommentCreate(
                    body="我同意这个问题，下一稿一起修。",
                    parent_comment_id=reply_comment_id,
                ),
            )

        self.assertEqual(len(added_items), 1)
        self.assertEqual(added_items[0].parent_comment_id, root_comment_id)
        self.assertEqual(result.parent_comment_id, root_comment_id)

    async def test_create_review_decision_downgrades_final_chapter_when_verdict_blocks(self) -> None:
        session = SimpleNamespace(
            add=MagicMock(),
            commit=AsyncMock(),
        )
        chapter_id = uuid4()
        user_id = uuid4()
        chapter = SimpleNamespace(
            id=chapter_id,
            status="final",
        )
        hydrated = SimpleNamespace(
            id=uuid4(),
            chapter_id=chapter_id,
            user_id=user_id,
            chapter_version_number=4,
            verdict="blocked",
            summary="当前版本仍有关键逻辑断裂。",
            focus_points=["逻辑闭环"],
            created_at=datetime.now(timezone.utc),
            user=SimpleNamespace(email="reviewer@example.com"),
        )

        with patch(
            "services.review_service.get_owned_chapter",
            new=AsyncMock(return_value=chapter),
        ), patch(
            "services.review_service._current_chapter_version_number",
            new=AsyncMock(return_value=4),
        ), patch(
            "services.review_service._get_review_decision",
            new=AsyncMock(return_value=hydrated),
        ):
            result = await create_chapter_review_decision(
                session,
                chapter_id,
                user_id,
                ChapterReviewDecisionCreate(
                    verdict="blocked",
                    summary="当前版本仍有关键逻辑断裂。",
                    focus_points=["逻辑闭环"],
                ),
            )

        self.assertEqual(chapter.status, "review")
        self.assertEqual(result.verdict, "blocked")
        session.commit.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
