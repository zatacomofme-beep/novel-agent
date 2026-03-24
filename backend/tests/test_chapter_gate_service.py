from __future__ import annotations

import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

from core.errors import AppError
from schemas.chapter import ChapterUpdate
from schemas.quality import ChapterQualityMetricsSnapshot
from services.chapter_gate_service import (
    CHECKPOINT_STATUS_APPROVED,
    CHECKPOINT_STATUS_PENDING,
    CHECKPOINT_STATUS_REJECTED,
    FINAL_GATE_STATUS_BLOCKED_CANON,
    FINAL_GATE_STATUS_BLOCKED_CHECKPOINT,
    FINAL_GATE_STATUS_BLOCKED_EVALUATION,
    FINAL_GATE_STATUS_BLOCKED_INTEGRITY,
    FINAL_GATE_STATUS_BLOCKED_PENDING,
    FINAL_GATE_STATUS_BLOCKED_REJECTED,
    FINAL_GATE_STATUS_BLOCKED_REVIEW,
    REVIEW_VERDICT_APPROVED,
    REVIEW_VERDICT_BLOCKED,
    REVIEW_VERDICT_CHANGES_REQUESTED,
    apply_chapter_gate_metadata,
    mark_quality_metrics_stale,
    review_verdict_blocks_final,
    should_downgrade_final_chapter_for_review_decision,
    should_downgrade_final_chapter_for_checkpoint,
    summarize_chapter_gate,
)
from services.chapter_service import update_chapter


class FakeSession:
    def __init__(self) -> None:
        self.commit = AsyncMock()
        self.refresh = AsyncMock()
        self.chapter_result = None

    async def get(self, model, ident):  # noqa: ANN001
        return None

    async def execute(self, statement):  # noqa: ANN001
        return SimpleNamespace(
            scalar_one=lambda: self.chapter_result,
            scalar_one_or_none=lambda: None,
        )


class ChapterGateServiceTests(unittest.IsolatedAsyncioTestCase):
    def test_summarize_gate_prefers_rejected_over_pending(self) -> None:
        now = datetime.now(timezone.utc)
        summary = summarize_chapter_gate(
            [
                SimpleNamespace(
                    status=CHECKPOINT_STATUS_PENDING,
                    title="待确认转折",
                    created_at=now,
                ),
                SimpleNamespace(
                    status=CHECKPOINT_STATUS_REJECTED,
                    title="被驳回质量门",
                    created_at=now.replace(microsecond=0),
                ),
            ]
        )

        self.assertFalse(summary.final_ready)
        self.assertEqual(summary.pending_checkpoint_count, 1)
        self.assertEqual(summary.rejected_checkpoint_count, 1)
        self.assertEqual(summary.final_gate_status, FINAL_GATE_STATUS_BLOCKED_REJECTED)

    def test_apply_gate_metadata_sets_chapter_fields(self) -> None:
        chapter = SimpleNamespace(
            checkpoints=[
                SimpleNamespace(
                    status=CHECKPOINT_STATUS_PENDING,
                    title="主角身份是否公开",
                    created_at=datetime.now(timezone.utc),
                )
            ]
        )

        summary = apply_chapter_gate_metadata(chapter)

        self.assertEqual(chapter.pending_checkpoint_count, 1)
        self.assertEqual(chapter.latest_checkpoint_title, "主角身份是否公开")
        self.assertEqual(chapter.final_gate_status, FINAL_GATE_STATUS_BLOCKED_PENDING)
        self.assertEqual(summary.final_gate_reason, chapter.final_gate_reason)

    def test_summarize_gate_blocks_final_when_latest_review_requires_changes(self) -> None:
        now = datetime.now(timezone.utc)
        summary = summarize_chapter_gate(
            [],
            [
                SimpleNamespace(
                    verdict=REVIEW_VERDICT_CHANGES_REQUESTED,
                    summary="情绪收束还不够稳。",
                    created_at=now,
                )
            ],
        )

        self.assertFalse(summary.final_ready)
        self.assertTrue(summary.review_gate_blocked)
        self.assertEqual(summary.latest_review_verdict, REVIEW_VERDICT_CHANGES_REQUESTED)
        self.assertEqual(summary.final_gate_status, FINAL_GATE_STATUS_BLOCKED_REVIEW)

    def test_summarize_gate_blocks_final_when_latest_canon_has_blockers(self) -> None:
        summary = summarize_chapter_gate(
            [],
            [],
            quality_metrics={
                "evaluation_status": "fresh",
                "canon_issue_count": 3,
                "canon_blocking_issue_count": 2,
                "canon_summary": "Canon 校验发现 3 个问题，其中 2 个会阻断后续修订判断。",
            },
        )

        self.assertFalse(summary.final_ready)
        self.assertTrue(summary.canon_gate_blocked)
        self.assertEqual(summary.latest_canon_issue_count, 3)
        self.assertEqual(summary.latest_canon_blocking_issue_count, 2)
        self.assertEqual(summary.final_gate_status, FINAL_GATE_STATUS_BLOCKED_CANON)
        self.assertIn("blocking continuity issues", summary.final_gate_reason or "")

    def test_summarize_gate_blocks_final_when_story_bible_integrity_has_blockers(self) -> None:
        summary = summarize_chapter_gate(
            [],
            [],
            quality_metrics={
                "evaluation_status": "fresh",
                "story_bible_integrity_issue_count": 2,
                "story_bible_integrity_blocking_issue_count": 1,
                "story_bible_integrity_summary": (
                    "Story Bible 自校验发现 2 个问题，其中 1 个会阻断后续章节校验。"
                ),
                "canon_issue_count": 0,
                "canon_blocking_issue_count": 0,
            },
        )

        self.assertFalse(summary.final_ready)
        self.assertTrue(summary.integrity_gate_blocked)
        self.assertEqual(summary.latest_story_bible_integrity_issue_count, 2)
        self.assertEqual(summary.latest_story_bible_integrity_blocking_issue_count, 1)
        self.assertEqual(summary.final_gate_status, FINAL_GATE_STATUS_BLOCKED_INTEGRITY)
        self.assertIn("truth-layer issue", summary.final_gate_reason or "")
        self.assertIn("Story Bible 自校验发现 2 个问题", summary.final_gate_reason or "")

    def test_summarize_gate_accepts_quality_metrics_snapshot_model(self) -> None:
        summary = summarize_chapter_gate(
            [],
            [],
            quality_metrics=ChapterQualityMetricsSnapshot(
                evaluation_status="fresh",
                story_bible_integrity_issue_count=2,
                story_bible_integrity_blocking_issue_count=1,
                story_bible_integrity_summary=(
                    "Story Bible 自校验发现 2 个问题，其中 1 个会阻断后续章节校验。"
                ),
            ),
        )

        self.assertFalse(summary.final_ready)
        self.assertTrue(summary.integrity_gate_blocked)
        self.assertEqual(summary.final_gate_status, FINAL_GATE_STATUS_BLOCKED_INTEGRITY)

    def test_mark_quality_metrics_stale_preserves_existing_snapshot_fields(self) -> None:
        next_metrics = mark_quality_metrics_stale(
            ChapterQualityMetricsSnapshot(
                overall_score=0.82,
                story_bible_integrity_issue_count=2,
                story_bible_integrity_blocking_issue_count=1,
                story_bible_integrity_summary=(
                    "Story Bible 自校验发现 2 个问题，其中 1 个会阻断后续章节校验。"
                ),
                canon_issue_count=3,
                canon_blocking_issue_count=1,
                canon_summary="Canon 校验发现 3 个问题，其中 1 个会阻断后续修订判断。",
            ),
            reason="The chapter content changed.",
        )

        self.assertEqual(next_metrics["evaluation_status"], "stale")
        self.assertEqual(next_metrics["evaluation_stale_reason"], "The chapter content changed.")
        self.assertEqual(next_metrics["story_bible_integrity_blocking_issue_count"], 1)
        self.assertEqual(next_metrics["canon_blocking_issue_count"], 1)

    def test_summarize_gate_blocks_final_when_latest_review_targets_old_version(self) -> None:
        now = datetime.now(timezone.utc)
        summary = summarize_chapter_gate(
            [],
            [
                SimpleNamespace(
                    verdict=REVIEW_VERDICT_APPROVED,
                    summary="旧版本可以进入终稿。",
                    chapter_version_number=4,
                    created_at=now,
                )
            ],
            quality_metrics={"evaluation_status": "fresh"},
            current_version_number=5,
        )

        self.assertFalse(summary.final_ready)
        self.assertTrue(summary.review_gate_blocked)
        self.assertTrue(summary.review_gate_stale)
        self.assertEqual(summary.final_gate_status, FINAL_GATE_STATUS_BLOCKED_REVIEW)
        self.assertIn("version 4", summary.final_gate_reason or "")
        self.assertIn("version 5", summary.final_gate_reason or "")

    def test_summarize_gate_blocks_final_when_latest_checkpoint_targets_old_version(self) -> None:
        now = datetime.now(timezone.utc)
        summary = summarize_chapter_gate(
            [
                SimpleNamespace(
                    status=CHECKPOINT_STATUS_APPROVED,
                    title="质量门",
                    chapter_version_number=2,
                    created_at=now,
                )
            ],
            [],
            quality_metrics={"evaluation_status": "fresh"},
            current_version_number=3,
        )

        self.assertFalse(summary.final_ready)
        self.assertTrue(summary.checkpoint_gate_blocked)
        self.assertTrue(summary.checkpoint_gate_stale)
        self.assertEqual(summary.final_gate_status, FINAL_GATE_STATUS_BLOCKED_CHECKPOINT)
        self.assertIn("version 2", summary.final_gate_reason or "")
        self.assertIn("version 3", summary.final_gate_reason or "")

    def test_summarize_gate_blocks_final_when_evaluation_missing(self) -> None:
        summary = summarize_chapter_gate([], [], quality_metrics=None)

        self.assertFalse(summary.final_ready)
        self.assertTrue(summary.evaluation_gate_blocked)
        self.assertEqual(summary.latest_evaluation_status, "missing")
        self.assertEqual(summary.final_gate_status, FINAL_GATE_STATUS_BLOCKED_EVALUATION)
        self.assertIn("needs a fresh evaluation", summary.final_gate_reason or "")

    def test_summarize_gate_blocks_final_when_evaluation_is_stale(self) -> None:
        summary = summarize_chapter_gate(
            [],
            [],
            quality_metrics={
                "evaluation_status": "stale",
                "evaluation_stale_reason": "The chapter content changed.",
                "canon_issue_count": 1,
                "canon_blocking_issue_count": 0,
            },
        )

        self.assertFalse(summary.final_ready)
        self.assertTrue(summary.evaluation_gate_blocked)
        self.assertEqual(summary.latest_evaluation_status, "stale")
        self.assertEqual(summary.final_gate_status, FINAL_GATE_STATUS_BLOCKED_EVALUATION)
        self.assertIn("outdated", summary.final_gate_reason or "")

    def test_should_downgrade_final_chapter_for_blocking_checkpoint(self) -> None:
        self.assertTrue(
            should_downgrade_final_chapter_for_checkpoint(
                chapter_status="final",
                checkpoint_status=CHECKPOINT_STATUS_PENDING,
            )
        )
        self.assertTrue(
            should_downgrade_final_chapter_for_checkpoint(
                chapter_status="final",
                checkpoint_status=CHECKPOINT_STATUS_REJECTED,
            )
        )
        self.assertFalse(
            should_downgrade_final_chapter_for_checkpoint(
                chapter_status="review",
                checkpoint_status=CHECKPOINT_STATUS_PENDING,
            )
        )
        self.assertFalse(
            should_downgrade_final_chapter_for_checkpoint(
                chapter_status="final",
                checkpoint_status=CHECKPOINT_STATUS_APPROVED,
            )
        )

    def test_review_verdict_blocking_matrix(self) -> None:
        self.assertTrue(review_verdict_blocks_final(REVIEW_VERDICT_CHANGES_REQUESTED))
        self.assertTrue(review_verdict_blocks_final(REVIEW_VERDICT_BLOCKED))
        self.assertFalse(review_verdict_blocks_final(REVIEW_VERDICT_APPROVED))
        self.assertTrue(
            should_downgrade_final_chapter_for_review_decision(
                chapter_status="final",
                verdict=REVIEW_VERDICT_BLOCKED,
            )
        )
        self.assertFalse(
            should_downgrade_final_chapter_for_review_decision(
                chapter_status="review",
                verdict=REVIEW_VERDICT_BLOCKED,
            )
        )

    async def test_update_chapter_blocks_final_when_pending_checkpoint_exists(self) -> None:
        chapter = SimpleNamespace(
            id=uuid4(),
            project_id=uuid4(),
            volume_id=None,
            branch_id=None,
            chapter_number=7,
            title="雾岸",
            content="她站在门前。",
            outline=None,
            status="review",
            quality_metrics=None,
            review_decisions=[],
            checkpoints=[
                SimpleNamespace(
                    status=CHECKPOINT_STATUS_PENDING,
                    title="转折是否通过",
                    created_at=datetime.now(timezone.utc),
                )
            ],
        )

        with self.assertRaises(AppError) as ctx:
            await update_chapter(
                FakeSession(),
                chapter,
                ChapterUpdate(status="final", create_version=False),
            )

        self.assertEqual(ctx.exception.code, "chapter.final_gate_blocked")
        self.assertEqual(ctx.exception.status_code, 409)

    async def test_update_chapter_allows_final_when_gate_is_clear(self) -> None:
        session = FakeSession()
        chapter = SimpleNamespace(
            id=uuid4(),
            project_id=uuid4(),
            volume_id=None,
            branch_id=None,
            chapter_number=8,
            title="回潮",
            content="她推门而入。",
            outline=None,
            status="review",
            current_version_number=4,
            quality_metrics={
                "evaluation_status": "fresh",
                "overall_score": 0.82,
            },
            review_decisions=[
                SimpleNamespace(
                    verdict=REVIEW_VERDICT_APPROVED,
                    summary="可以进入终稿。",
                    chapter_version_number=4,
                    created_at=datetime.now(timezone.utc),
                )
            ],
            checkpoints=[
                SimpleNamespace(
                    status=CHECKPOINT_STATUS_APPROVED,
                    title="质量门",
                    chapter_version_number=4,
                    created_at=datetime.now(timezone.utc),
                )
            ],
        )
        session.chapter_result = chapter

        updated = await update_chapter(
            session,
            chapter,
            ChapterUpdate(status="final", create_version=False),
        )

        self.assertEqual(updated.status, "final")
        self.assertTrue(updated.final_ready)
        session.commit.assert_awaited_once()

    async def test_update_chapter_blocks_final_when_latest_review_is_blocking(self) -> None:
        chapter = SimpleNamespace(
            id=uuid4(),
            project_id=uuid4(),
            volume_id=None,
            branch_id=None,
            chapter_number=9,
            title="回潮",
            content="她停在门后。",
            outline=None,
            status="review",
            current_version_number=3,
            quality_metrics=None,
            checkpoints=[],
            review_decisions=[
                SimpleNamespace(
                    verdict=REVIEW_VERDICT_BLOCKED,
                    summary="动机链还有断点。",
                    chapter_version_number=3,
                    created_at=datetime.now(timezone.utc),
                )
            ],
        )

        with self.assertRaises(AppError) as ctx:
            await update_chapter(
                FakeSession(),
                chapter,
                ChapterUpdate(status="final", create_version=False),
            )

        self.assertEqual(ctx.exception.code, "chapter.final_gate_blocked")
        self.assertEqual(chapter.final_gate_status, FINAL_GATE_STATUS_BLOCKED_REVIEW)

    async def test_update_chapter_blocks_final_when_latest_canon_is_blocking(self) -> None:
        chapter = SimpleNamespace(
            id=uuid4(),
            project_id=uuid4(),
            volume_id=None,
            branch_id=None,
            chapter_number=10,
            title="雾桥",
            content="她停在桥心。",
            outline=None,
            status="review",
            current_version_number=2,
            quality_metrics={
                "evaluation_status": "fresh",
                "canon_issue_count": 2,
                "canon_blocking_issue_count": 1,
                "canon_summary": "Canon 校验发现 2 个问题，其中 1 个会阻断后续修订判断。",
            },
            checkpoints=[],
            review_decisions=[],
        )

        with self.assertRaises(AppError) as ctx:
            await update_chapter(
                FakeSession(),
                chapter,
                ChapterUpdate(status="final", create_version=False),
            )

        self.assertEqual(ctx.exception.code, "chapter.final_gate_blocked")
        self.assertEqual(chapter.final_gate_status, FINAL_GATE_STATUS_BLOCKED_CANON)
        self.assertTrue(chapter.canon_gate_blocked)
        self.assertEqual(chapter.latest_canon_blocking_issue_count, 1)

    async def test_update_chapter_blocks_final_when_story_bible_integrity_is_blocking(self) -> None:
        chapter = SimpleNamespace(
            id=uuid4(),
            project_id=uuid4(),
            volume_id=None,
            branch_id=None,
            chapter_number=10,
            title="雾桥",
            content="她停在桥心。",
            outline=None,
            status="review",
            current_version_number=2,
            quality_metrics={
                "evaluation_status": "fresh",
                "story_bible_integrity_issue_count": 2,
                "story_bible_integrity_blocking_issue_count": 1,
                "story_bible_integrity_summary": (
                    "Story Bible 自校验发现 2 个问题，其中 1 个会阻断后续章节校验。"
                ),
            },
            checkpoints=[],
            review_decisions=[],
        )

        with self.assertRaises(AppError) as ctx:
            await update_chapter(
                FakeSession(),
                chapter,
                ChapterUpdate(status="final", create_version=False),
            )

        self.assertEqual(ctx.exception.code, "chapter.final_gate_blocked")
        self.assertEqual(chapter.final_gate_status, FINAL_GATE_STATUS_BLOCKED_INTEGRITY)
        self.assertTrue(chapter.integrity_gate_blocked)
        self.assertEqual(chapter.latest_story_bible_integrity_blocking_issue_count, 1)

    async def test_update_chapter_marks_quality_metrics_stale_after_content_change(self) -> None:
        session = FakeSession()
        chapter = SimpleNamespace(
            id=uuid4(),
            project_id=uuid4(),
            volume_id=None,
            branch_id=None,
            chapter_number=11,
            title="潮夜",
            content="旧内容",
            outline=None,
            status="review",
            current_version_number=7,
            quality_metrics={
                "evaluation_status": "fresh",
                "overall_score": 0.91,
            },
            checkpoints=[],
            review_decisions=[],
            word_count=2,
        )
        session.chapter_result = chapter

        updated = await update_chapter(
            session,
            chapter,
            ChapterUpdate(content="新内容", create_version=False),
        )

        self.assertEqual(updated.quality_metrics["evaluation_status"], "stale")
        self.assertEqual(updated.current_version_number, 8)
        self.assertIn(
            "content changed",
            updated.quality_metrics["evaluation_stale_reason"],
        )

    async def test_update_chapter_downgrades_final_to_review_after_content_change(self) -> None:
        session = FakeSession()
        chapter = SimpleNamespace(
            id=uuid4(),
            project_id=uuid4(),
            volume_id=None,
            branch_id=None,
            chapter_number=12,
            title="潮夜",
            content="旧内容",
            outline=None,
            status="final",
            current_version_number=5,
            quality_metrics={
                "evaluation_status": "fresh",
                "overall_score": 0.91,
            },
            checkpoints=[],
            review_decisions=[],
            word_count=2,
        )
        session.chapter_result = chapter

        updated = await update_chapter(
            session,
            chapter,
            ChapterUpdate(content="新内容", create_version=False),
        )

        self.assertEqual(updated.status, "review")
        self.assertEqual(updated.quality_metrics["evaluation_status"], "stale")
        self.assertEqual(updated.current_version_number, 6)

    async def test_update_chapter_blocks_final_when_content_changes_before_recheck(self) -> None:
        chapter = SimpleNamespace(
            id=uuid4(),
            project_id=uuid4(),
            volume_id=None,
            branch_id=None,
            chapter_number=13,
            title="潮夜",
            content="旧内容",
            outline=None,
            status="review",
            current_version_number=2,
            quality_metrics={
                "evaluation_status": "fresh",
                "overall_score": 0.91,
            },
            checkpoints=[],
            review_decisions=[],
        )

        with self.assertRaises(AppError) as ctx:
            await update_chapter(
                FakeSession(),
                chapter,
                ChapterUpdate(
                    content="新内容",
                    status="final",
                    create_version=False,
                ),
            )

        self.assertEqual(ctx.exception.code, "chapter.final_gate_blocked")
        self.assertEqual(chapter.final_gate_status, FINAL_GATE_STATUS_BLOCKED_EVALUATION)


if __name__ == "__main__":
    unittest.main()
