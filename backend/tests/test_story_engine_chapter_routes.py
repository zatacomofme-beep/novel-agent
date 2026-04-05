from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from fastapi import Response

from core.errors import AppError
from schemas.chapter import (
    ChapterCheckpointCreate,
    ChapterReviewCommentCreate,
    ChapterReviewCommentRead,
    ChapterReviewWorkspaceRead,
    ChapterSelectionRewriteRequest,
    ChapterSelectionRewriteResponse,
    ChapterRead,
    ChapterUpdate,
)
from api.v1.story_engine import (
    story_engine_chapter_beta_reader,
    story_engine_chapter_comment_create,
    story_engine_chapter_create,
    story_engine_chapter_generate,
    story_engine_chapter_patch,
    story_engine_chapter_rewrite_selection,
    story_engine_chapter_review_workspace,
)
from tasks.schemas import TaskState


def _build_chapter_read(*, project_id):
    return ChapterRead(
        id=uuid4(),
        project_id=project_id,
        volume_id=None,
        branch_id=None,
        chapter_number=3,
        title="测试章节",
        content="正文",
        outline=None,
        word_count=2,
        current_version_number=1,
        status="draft",
        quality_metrics=None,
        pending_checkpoint_count=0,
        rejected_checkpoint_count=0,
        latest_checkpoint_status=None,
        latest_checkpoint_title=None,
        latest_review_verdict=None,
        latest_review_summary=None,
        review_gate_blocked=False,
        evaluation_gate_blocked=False,
        latest_evaluation_status="missing",
        latest_evaluation_stale_reason=None,
        integrity_gate_blocked=False,
        latest_story_bible_integrity_issue_count=0,
        latest_story_bible_integrity_blocking_issue_count=0,
        latest_story_bible_integrity_summary=None,
        canon_gate_blocked=False,
        latest_canon_issue_count=0,
        latest_canon_blocking_issue_count=0,
        latest_canon_summary=None,
        final_ready=True,
        final_gate_status="ready",
        final_gate_reason=None,
    )


class StoryEngineChapterRouteTests(unittest.IsolatedAsyncioTestCase):
    async def test_review_workspace_rejects_project_mismatch(self) -> None:
        project_id = uuid4()
        chapter_id = uuid4()
        user = SimpleNamespace(id=uuid4())
        chapter = SimpleNamespace(id=chapter_id, project_id=uuid4())

        with patch(
            "api.v1.story_engine.get_owned_chapter",
            AsyncMock(return_value=chapter),
        ):
            with self.assertRaises(AppError) as raised:
                await story_engine_chapter_review_workspace(
                    project_id=project_id,
                    chapter_id=chapter_id,
                    current_user=user,
                    session=SimpleNamespace(),
                )

        self.assertEqual(raised.exception.code, "story_engine.chapter_project_mismatch")

    async def test_review_workspace_delegates_to_review_service(self) -> None:
        project_id = uuid4()
        chapter_id = uuid4()
        user = SimpleNamespace(id=uuid4())
        chapter = SimpleNamespace(id=chapter_id, project_id=project_id)
        workspace = ChapterReviewWorkspaceRead(
            chapter_id=chapter_id,
            current_role="owner",
            owner_email="owner@example.com",
        )

        with patch(
            "api.v1.story_engine.get_owned_chapter",
            AsyncMock(return_value=chapter),
        ), patch(
            "api.v1.story_engine.get_chapter_review_workspace",
            AsyncMock(return_value=workspace),
        ) as mocked_workspace:
            result = await story_engine_chapter_review_workspace(
                project_id=project_id,
                chapter_id=chapter_id,
                current_user=user,
                session=SimpleNamespace(),
            )

        mocked_workspace.assert_awaited_once()
        self.assertEqual(result.chapter_id, chapter_id)

    async def test_comment_create_uses_story_engine_wrapper(self) -> None:
        project_id = uuid4()
        chapter_id = uuid4()
        user = SimpleNamespace(id=uuid4())
        chapter = SimpleNamespace(id=chapter_id, project_id=project_id)
        payload = ChapterReviewCommentCreate(body="需要修改这里")
        comment = ChapterReviewCommentRead(
            id=uuid4(),
            chapter_id=chapter_id,
            user_id=user.id,
            parent_comment_id=None,
            chapter_version_number=1,
            author_email="owner@example.com",
            body="需要修改这里",
            status="open",
            selection_start=None,
            selection_end=None,
            selection_text=None,
            assignee_user_id=None,
            assignee_email=None,
            assigned_by_user_id=None,
            assigned_by_email=None,
            assigned_at=None,
            resolved_by_user_id=None,
            resolved_by_email=None,
            resolved_at=None,
            created_at="2026-04-02T00:00:00Z",
            updated_at="2026-04-02T00:00:00Z",
            reply_count=0,
            can_edit=True,
            can_assign=True,
            can_change_status=True,
            can_delete=True,
        )

        with patch(
            "api.v1.story_engine.get_owned_chapter",
            AsyncMock(return_value=chapter),
        ), patch(
            "api.v1.story_engine.create_chapter_comment",
            AsyncMock(return_value=comment),
        ) as mocked_create:
            result = await story_engine_chapter_comment_create(
                project_id=project_id,
                chapter_id=chapter_id,
                payload=payload,
                current_user=user,
                session=SimpleNamespace(),
            )

        mocked_create.assert_awaited_once()
        self.assertEqual(result.body, "需要修改这里")

    async def test_rewrite_selection_delegates_to_service(self) -> None:
        project_id = uuid4()
        chapter_id = uuid4()
        user = SimpleNamespace(id=uuid4())
        chapter = SimpleNamespace(id=chapter_id, project_id=project_id)
        payload = ChapterSelectionRewriteRequest(
            selection_start=0,
            selection_end=4,
            instruction="压缩这段表述",
            create_version=True,
        )
        rewritten = ChapterSelectionRewriteResponse(
            chapter=_build_chapter_read(project_id=project_id),
            selection_start=0,
            selection_end=4,
            rewritten_selection_end=4,
            original_text="原文",
            rewritten_text="改文",
            instruction="压缩这段表述",
            change_reason="rewrite",
            related_comment_count=0,
            generation={
                "provider": "local-fallback",
                "model": "heuristic-v1",
                "used_fallback": True,
                "metadata": {},
            },
        )

        with patch(
            "api.v1.story_engine.get_owned_chapter",
            AsyncMock(return_value=chapter),
        ), patch(
            "api.v1.story_engine.rewrite_chapter_selection",
            AsyncMock(return_value=rewritten),
        ) as mocked_rewrite:
            result = await story_engine_chapter_rewrite_selection(
                project_id=project_id,
                chapter_id=chapter_id,
                payload=payload,
                current_user=user,
                session=SimpleNamespace(),
            )

        mocked_rewrite.assert_awaited_once()
        self.assertEqual(result.rewritten_text, "改文")

    async def test_chapter_patch_delegates_to_update_service(self) -> None:
        project_id = uuid4()
        chapter_id = uuid4()
        user = SimpleNamespace(id=uuid4())
        chapter = SimpleNamespace(id=chapter_id, project_id=project_id)
        payload = ChapterUpdate(content="新正文", create_version=True)
        updated = _build_chapter_read(project_id=project_id)

        with patch(
            "api.v1.story_engine.get_owned_chapter",
            AsyncMock(return_value=chapter),
        ), patch(
            "api.v1.story_engine.update_chapter",
            AsyncMock(return_value=updated),
        ) as mocked_update:
            result = await story_engine_chapter_patch(
                project_id=project_id,
                chapter_id=chapter_id,
                payload=payload,
                current_user=user,
                session=SimpleNamespace(),
            )

        mocked_update.assert_awaited_once()
        self.assertEqual(result.project_id, project_id)

    async def test_chapter_generate_delegates_to_legacy_dispatch(self) -> None:
        project_id = uuid4()
        chapter_id = uuid4()
        user = SimpleNamespace(id=uuid4())
        chapter = SimpleNamespace(id=chapter_id, project_id=project_id)
        task_state = TaskState(
            task_id="task-123",
            task_type="chapter_generation",
            status="queued",
            progress=0,
            message="queued",
            project_id=project_id,
            chapter_id=chapter_id,
        )

        with patch(
            "api.v1.story_engine.get_owned_chapter",
            AsyncMock(return_value=chapter),
        ), patch(
            "api.v1.story_engine.dispatch_legacy_generation_for_chapter",
            AsyncMock(return_value=task_state),
        ) as mocked_dispatch:
            result = await story_engine_chapter_generate(
                project_id=project_id,
                chapter_id=chapter_id,
                current_user=user,
                session=SimpleNamespace(),
            )

        self.assertEqual(result.task_id, "task-123")
        mocked_dispatch.assert_awaited_once_with(
            unittest.mock.ANY,
            chapter=chapter,
            user_id=user.id,
        )

    async def test_beta_reader_delegates_to_agent_with_project_scoped_route(self) -> None:
        project_id = uuid4()
        chapter_id = uuid4()
        user = SimpleNamespace(id=uuid4())
        chapter = SimpleNamespace(id=chapter_id, project_id=project_id)
        beta_result = SimpleNamespace(success=True, data={"summary": "ok"}, error=None)

        with patch(
            "api.v1.story_engine.get_owned_chapter",
            AsyncMock(return_value=chapter),
        ), patch(
            "agents.beta_reader.BetaReaderAgent",
        ) as mocked_beta_reader_cls, patch(
            "agents.base.AgentRunContext",
        ) as mocked_context_cls:
            mocked_beta_reader = mocked_beta_reader_cls.return_value
            mocked_beta_reader.run = AsyncMock(return_value=beta_result)
            result = await story_engine_chapter_beta_reader(
                project_id=project_id,
                chapter_id=chapter_id,
                body={"content": "片段", "genre": "悬疑", "target_audience": "adult"},
                current_user=user,
                session=SimpleNamespace(),
            )

        self.assertEqual(result, {"success": True, "beta_feedback": {"summary": "ok"}})
        mocked_context_cls.assert_called_once()
        mocked_beta_reader.run.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
