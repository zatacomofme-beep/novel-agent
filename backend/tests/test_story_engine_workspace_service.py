from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from services.story_engine_kb_service import build_workspace


class StoryEngineWorkspaceServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_build_workspace_includes_story_bible_payload(self) -> None:
        project_id = uuid4()
        user_id = uuid4()
        story_bible_payload = {
            "scope": {"branch_id": str(uuid4())},
            "characters": [],
            "world_settings": [],
            "items": [],
            "factions": [],
            "locations": [],
            "plot_threads": [],
            "foreshadowing": [],
            "timeline_events": [],
        }

        with patch(
            "services.story_engine_kb_service.get_story_engine_project",
            AsyncMock(
                return_value=SimpleNamespace(
                    id=project_id,
                    title="潮汐档案",
                    genre="都市异能",
                    theme="代价与真相",
                    tone="冷峻悬疑",
                )
            ),
        ), patch(
            "services.story_engine_kb_service.list_entities",
            AsyncMock(side_effect=[[], [], [], [], [], [], []]),
        ), patch(
            "services.story_engine_kb_service._build_workspace_story_bible",
            AsyncMock(return_value=story_bible_payload),
        ):
            payload = await build_workspace(
                SimpleNamespace(),
                project_id=project_id,
                user_id=user_id,
            )

        self.assertEqual(payload["project"]["title"], "潮汐档案")
        self.assertEqual(payload["story_bible"], story_bible_payload)
