from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from memory.context_builder import build_context_bundle
from memory.story_bible import StoryBibleContext
from memory.vector_store import RetrievedItem


class ContextBuilderTests(unittest.IsolatedAsyncioTestCase):
    async def test_build_context_bundle_queries_item_and_faction_sections(self) -> None:
        story_bible = StoryBibleContext(
            project_id=uuid4(),
            title="雾港回潮",
            genre="悬疑奇幻",
            theme="记忆与代价",
            tone="压抑",
            status="draft",
            characters=[
                {
                    "id": "character-1",
                    "name": "林澈",
                    "data": {"role": "protagonist"},
                    "version": 1,
                }
            ],
            world_settings=[
                {
                    "key": "rule-memory-tide",
                    "title": "潮汐记忆法则",
                    "data": {"cost": "memory"},
                    "version": 1,
                }
            ],
            items=[
                {
                    "key": "item:tide-lamp",
                    "name": "潮灯",
                    "type": "artifact",
                    "description": "能照见潮痕的灯。",
                    "effects": ["照见残留记忆"],
                    "owner": "林澈",
                    "location": "雾港",
                    "status": "active",
                    "introduced_chapter": 1,
                    "forbidden_holders": [],
                    "version": 1,
                }
            ],
            factions=[
                {
                    "key": "faction:black-bell",
                    "name": "黑钟会",
                    "type": "cult",
                    "description": "盘踞雾港旧城区的组织。",
                    "leader": "沈岚",
                    "members": ["沈岚"],
                    "territory": "雾港旧城区",
                    "resources": ["钟塔"],
                    "ideology": "以遗忘换秩序",
                    "version": 1,
                }
            ],
            locations=[],
            plot_threads=[],
            foreshadowing=[],
            timeline_events=[],
            chapter_summaries=[],
        )

        search_mock = AsyncMock(
            side_effect=[
                [],
                [],
                [
                    RetrievedItem(
                        item_type="item",
                        item_id="item:tide-lamp",
                        score=0.74,
                        payload=story_bible.items[0],
                        backend="lexical",
                    )
                ],
                [
                    RetrievedItem(
                        item_type="faction",
                        item_id="faction:black-bell",
                        score=0.68,
                        payload=story_bible.factions[0],
                        backend="lexical",
                    )
                ],
                [],
                [],
                [],
                [],
            ]
        )

        with patch("memory.context_builder.vector_store.search", new=search_mock):
            bundle = await build_context_bundle(
                story_bible,
                None,
                project_id=str(story_bible.project_id),
                chapter_number=7,
                chapter_title="黑钟再鸣",
            )

        self.assertEqual(
            [call.kwargs["item_type"] for call in search_mock.await_args_list],
            [
                "character",
                "world_setting",
                "item",
                "faction",
                "location",
                "plot_thread",
                "foreshadowing",
                "timeline_event",
            ],
        )
        retrieved_types = [item["type"] for item in bundle["retrieved_items"]]
        self.assertIn("item", retrieved_types)
        self.assertIn("faction", retrieved_types)
        self.assertEqual(bundle["retrieval_backends"], ["lexical"])


if __name__ == "__main__":
    unittest.main()
