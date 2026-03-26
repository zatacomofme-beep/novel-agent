from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from services.story_engine_kb_service import build_workspace


class _ScalarSequenceResult:
    def __init__(self, values):
        self._values = values

    def scalars(self):
        return self

    def all(self):
        return list(self._values)


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
        self.assertEqual(payload["knowledge_provenance"], [])

    async def test_build_workspace_includes_relation_and_provenance_summary(self) -> None:
        project_id = uuid4()
        user_id = uuid4()
        character_id = uuid4()
        item_id = uuid4()
        event_id = uuid4()
        location_id = uuid4()
        thread_id = uuid4()
        summary_id = uuid4()

        session = AsyncMock()
        session.execute.return_value = _ScalarSequenceResult([])
        story_bible_payload = {
            "scope": {
                "scope_kind": "branch",
                "section_override_details": [
                    {
                        "section_key": "factions",
                        "items": [{"entity_key": "key:faction:tide"}],
                    }
                ],
            },
            "characters": [],
            "world_settings": [],
            "items": [],
            "factions": [
                {
                    "key": "faction:tide",
                    "name": "潮汐会",
                    "leader": "林澈",
                    "territory": "雾港",
                    "members": ["林澈"],
                }
            ],
            "locations": [
                {
                    "id": str(location_id),
                    "name": "雾港",
                    "data": {"type": "harbor"},
                }
            ],
            "plot_threads": [
                {
                    "id": str(thread_id),
                    "title": "潮痕疑案",
                    "status": "active",
                    "importance": 1,
                    "data": {
                        "focus_characters": ["林澈"],
                        "locations": ["雾港"],
                    },
                }
            ],
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
            AsyncMock(
                side_effect=[
                    [
                        SimpleNamespace(
                            character_id=character_id,
                            name="林澈",
                            appearance=None,
                            personality="冷静",
                            micro_habits=[],
                            abilities={},
                            relationships=[],
                            status="active",
                            arc_stage="initial",
                            arc_boundaries=[],
                        )
                    ],
                    [],
                    [
                        SimpleNamespace(
                            item_id=item_id,
                            name="潮灯",
                            features="雾港常见照明器",
                            owner="林澈",
                            location="雾港",
                            special_rules=[],
                        )
                    ],
                    [],
                    [
                        SimpleNamespace(
                            event_id=event_id,
                            chapter_number=7,
                            in_universe_time=None,
                            location="雾港",
                            weather="暴雨",
                            core_event="潮灯在雨夜熄灭",
                            character_states=[{"name": "林澈"}],
                        )
                    ],
                    [],
                    [
                        SimpleNamespace(
                            summary_id=summary_id,
                            chapter_number=7,
                            kb_update_suggestions=[
                                {
                                    "suggestion_id": "sg-1",
                                    "status": "applied",
                                    "entity_type": "items",
                                    "applied_entity_id": str(item_id),
                                    "applied_entity_label": "潮灯",
                                }
                            ],
                        )
                    ],
                ]
            ),
        ), patch(
            "services.story_engine_kb_service._build_workspace_story_bible",
            AsyncMock(return_value=story_bible_payload),
        ):
            payload = await build_workspace(
                session,
                project_id=project_id,
                user_id=user_id,
            )

        provenance = payload["knowledge_provenance"]
        item_entry = next(item for item in provenance if item["section_key"] == "items")
        faction_entry = next(item for item in provenance if item["section_key"] == "factions")

        self.assertEqual(item_entry["recent_chapters"], [7])
        self.assertEqual(
            {relation["relation_type"] for relation in item_entry["outbound_relations"]},
            {"owner", "located_at"},
        )
        self.assertTrue(
            any(relation["relation_type"] == "applied_update" for relation in item_entry["inbound_relations"])
        )
        self.assertEqual(faction_entry["scope_origin"], "branch_override")
