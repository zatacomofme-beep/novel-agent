from __future__ import annotations

import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

from core.errors import AppError
from schemas.chapter import ChapterUpdate
from services.chapter_gate_service import (
    CHECKPOINT_STATUS_APPROVED,
    CHECKPOINT_STATUS_PENDING,
    CHECKPOINT_STATUS_REJECTED,
    FINAL_GATE_STATUS_BLOCKED_PENDING,
    FINAL_GATE_STATUS_BLOCKED_REJECTED,
    FINAL_GATE_STATUS_BLOCKED_REVIEW,
    REVIEW_VERDICT_APPROVED,
    REVIEW_VERDICT_BLOCKED,
    REVIEW_VERDICT_CHANGES_REQUESTED,
    apply_chapter_gate_metadata,
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

    async def get(self, model, ident):  # noqa: ANN001
        return None


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
            quality_metrics=None,
            review_decisions=[
                SimpleNamespace(
                    verdict=REVIEW_VERDICT_APPROVED,
                    summary="可以进入终稿。",
                    created_at=datetime.now(timezone.utc),
                )
            ],
            checkpoints=[
                SimpleNamespace(
                    status=CHECKPOINT_STATUS_APPROVED,
                    title="质量门",
                    created_at=datetime.now(timezone.utc),
                )
            ],
        )

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
            quality_metrics=None,
            checkpoints=[],
            review_decisions=[
                SimpleNamespace(
                    verdict=REVIEW_VERDICT_BLOCKED,
                    summary="动机链还有断点。",
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


if __name__ == "__main__":
    unittest.main()
