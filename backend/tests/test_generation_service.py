from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from memory.story_bible import StoryBibleContext
from services.generation_service import StoryBibleIntegrityError, run_generation_pipeline


class GenerationServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_run_generation_pipeline_blocks_when_story_bible_integrity_is_broken(
        self,
    ) -> None:
        chapter = SimpleNamespace(
            id=uuid4(),
            project_id=uuid4(),
            branch_id=uuid4(),
            chapter_number=6,
            title="雾港回潮",
            volume=None,
            branch=None,
        )
        story_bible = StoryBibleContext(
            project_id=chapter.project_id,
            title="雾港",
            genre="悬疑",
            theme="代价",
            tone="压抑",
            status="draft",
            branch_id=chapter.branch_id,
            branch_title="假如线",
            branch_key="alt",
            scope_kind="branch",
            base_scope_kind="project",
            has_snapshot=True,
            changed_sections=["characters"],
            section_override_counts={"characters": 1},
            total_override_count=1,
            characters=[
                {
                    "id": str(uuid4()),
                    "name": "林舟",
                    "data": {
                        "relationships": [
                            {"target": "不存在的人", "status": "ally"},
                        ]
                    },
                    "version": 1,
                    "created_chapter": 1,
                }
            ],
            world_settings=[],
            locations=[],
            plot_threads=[],
            foreshadowing=[],
            timeline_events=[],
            chapter_summaries=[],
        )

        with patch(
            "services.generation_service.get_owned_chapter",
            AsyncMock(return_value=chapter),
        ), patch(
            "services.generation_service.load_story_bible_context",
            AsyncMock(return_value=story_bible),
        ), patch(
            "services.generation_service.build_generation_payload",
            AsyncMock(),
        ) as mocked_build_generation_payload:
            with self.assertRaises(StoryBibleIntegrityError) as raised:
                await run_generation_pipeline(
                    session=SimpleNamespace(),
                    chapter_id=chapter.id,
                    user_id=uuid4(),
                    task_id="task-integrity",
                )

        mocked_build_generation_payload.assert_not_awaited()
        self.assertEqual(raised.exception.report.issue_count, 1)
        self.assertEqual(raised.exception.report.blocking_issue_count, 1)
        self.assertEqual(
            raised.exception.report.issues[0].code,
            "relationship.unknown_character",
        )


if __name__ == "__main__":
    unittest.main()
