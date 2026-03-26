from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from memory.story_bible import StoryBibleContext
from schemas.project import (
    CharacterGenerationRequest,
    FactionGenerationRequest,
    ItemGenerationRequest,
    PlotThreadGenerationRequest,
)
from services.entity_generation_service import (
    generate_characters,
    generate_factions,
    generate_items,
    generate_plot_threads,
    run_entity_generation_pipeline,
)


def make_story_bible() -> StoryBibleContext:
    return StoryBibleContext(
        project_id=uuid4(),
        title="雾港回潮",
        genre="悬疑奇幻",
        theme="记忆与代价",
        tone="压抑克制",
        status="draft",
        branch_id=uuid4(),
        branch_title="主线",
        branch_key="main",
        scope_kind="branch",
        base_scope_kind="project",
        has_snapshot=True,
        changed_sections=["characters", "locations"],
        section_override_counts={"characters": 1, "locations": 1},
        total_override_count=2,
        characters=[
            {
                "id": str(uuid4()),
                "name": "林澈",
                "data": {"role": "protagonist"},
                "version": 1,
                "created_chapter": 1,
            },
            {
                "id": str(uuid4()),
                "name": "沈岚",
                "data": {"role": "supporting"},
                "version": 1,
                "created_chapter": 2,
            },
        ],
        world_settings=[
            {
                "id": str(uuid4()),
                "key": "rule-memory-tide",
                "title": "潮汐记忆法则",
                "data": {"cost": "memory"},
                "version": 1,
            },
        ],
        items=[
            {
                "key": "item:tide-lamp",
                "name": "潮灯",
                "type": "artifact",
                "rarity": "rare",
                "description": "雾港常见的记忆照明器",
                "effects": ["短时照亮潮痕"],
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
                "scale": "city",
                "description": "雾港的旧势力",
                "goals": "封存深潮",
                "leader": "林澈",
                "members": ["林澈", "沈岚"],
                "territory": "雾港",
                "resources": ["钟塔"],
                "ideology": "以遗忘换秩序",
                "version": 1,
            }
        ],
        locations=[
            {
                "id": str(uuid4()),
                "name": "雾港",
                "data": {"climate": "潮湿"},
                "version": 1,
            },
            {
                "id": str(uuid4()),
                "name": "钟塔区",
                "data": {"climate": "阴冷"},
                "version": 1,
            },
        ],
        plot_threads=[
            {
                "id": str(uuid4()),
                "title": "黑钟疑案",
                "status": "active",
                "importance": 1,
                "data": {},
            }
        ],
        foreshadowing=[],
        timeline_events=[],
        chapter_summaries=[],
    )


class EntityGenerationServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_run_entity_generation_pipeline_records_failover_trace(self) -> None:
        story_bible = make_story_bible()

        first_result = SimpleNamespace(
            content='{"characters":[{"name":"角色一","role":"supporting"}]}',
            provider="local-fallback",
            model="heuristic-v1",
            used_fallback=True,
            metadata={
                "selected_provider": "openai-compatible",
                "remote_error": {
                    "error_type": "rate_limit",
                    "message": "quota reached",
                    "status_code": 429,
                },
            },
        )
        second_result = SimpleNamespace(
            content='{"characters":[{"name":"沈遥","role":"supporting","personality":"冷静克制"}]}',
            provider="openai-compatible",
            model="claude-opus-4-6",
            used_fallback=False,
            metadata={
                "selected_provider": "openai-compatible",
            },
        )

        with patch(
            "services.entity_generation_service.load_story_bible_context",
            AsyncMock(return_value=story_bible),
        ), patch(
            "services.entity_generation_service._resolve_entity_generation_model_routing",
            AsyncMock(
                return_value={
                    "guardian": {"model": "gpt-5.4", "reasoning_effort": "high"},
                    "outline": {"model": "claude-opus-4-6", "reasoning_effort": "high"},
                    "style_guardian": {
                        "model": "gemini-3.1-pro-preview",
                        "reasoning_effort": "medium",
                    },
                }
            ),
        ), patch(
            "services.entity_generation_service.model_gateway.generate_text",
            AsyncMock(side_effect=[first_result, second_result]),
        ):
            pipeline = await run_entity_generation_pipeline(
                SimpleNamespace(),
                project_id=story_bible.project_id,
                user_id=uuid4(),
                generation_type="characters",
                payload=CharacterGenerationRequest(
                    character_type="supporting",
                    count=1,
                    genre="悬疑奇幻",
                    tone="压抑克制",
                ),
            )

        self.assertEqual(pipeline.response.characters[0].name, "沈遥")
        self.assertTrue(pipeline.trace["failover_triggered"])
        self.assertEqual(pipeline.trace["selected_role"], "outline")
        self.assertEqual(len(pipeline.trace["failover_attempts"]), 1)

    async def test_generate_characters_falls_back_to_contextual_candidates(self) -> None:
        story_bible = make_story_bible()

        with patch(
            "services.entity_generation_service.load_story_bible_context",
            AsyncMock(return_value=story_bible),
        ), patch(
            "services.entity_generation_service.model_gateway.generate_text",
            AsyncMock(return_value=SimpleNamespace(content="not valid json")),
        ):
            response = await generate_characters(
                SimpleNamespace(),
                story_bible.project_id,
                uuid4(),
                CharacterGenerationRequest(
                    character_type="supporting",
                    count=2,
                    genre="悬疑奇幻",
                    tone="压抑克制",
                    theme="记忆与代价",
                    existing_characters="林澈, 沈岚",
                ),
            )

        self.assertEqual(len(response.characters), 2)
        self.assertTrue(all(character.name not in {"角色1", "配角1"} for character in response.characters))
        self.assertTrue(all(character.name not in {"林澈", "沈岚"} for character in response.characters))
        self.assertTrue(all(character.role == "supporting" for character in response.characters))

    async def test_generate_items_accepts_json_fence_output(self) -> None:
        story_bible = make_story_bible()

        with patch(
            "services.entity_generation_service.load_story_bible_context",
            AsyncMock(return_value=story_bible),
        ), patch(
            "services.entity_generation_service.model_gateway.generate_text",
            AsyncMock(
                return_value=SimpleNamespace(
                    content="""```json
                    {
                      "items": [
                        {
                          "name": "潮纹短刃",
                          "type": "weapon",
                          "rarity": "稀有",
                          "description": "由潮汐记忆法则催化的短刃。",
                          "effects": ["切开封存记忆", "短时压制幻觉"],
                          "owner": "林澈"
                        }
                      ]
                    }
                    ```"""
                )
            ),
        ):
            response = await generate_items(
                SimpleNamespace(),
                story_bible.project_id,
                uuid4(),
                ItemGenerationRequest(item_type="weapon", count=1),
            )

        self.assertEqual(len(response.items), 1)
        self.assertEqual(response.items[0].name, "潮纹短刃")
        self.assertEqual(response.items[0].owner, "林澈")
        self.assertEqual(response.items[0].effects[0], "切开封存记忆")

    async def test_generate_plot_threads_backfills_when_remote_candidates_duplicate(self) -> None:
        story_bible = make_story_bible()

        with patch(
            "services.entity_generation_service.load_story_bible_context",
            AsyncMock(return_value=story_bible),
        ), patch(
            "services.entity_generation_service.model_gateway.generate_text",
            AsyncMock(
                return_value=SimpleNamespace(
                    content="""{
                      "plot_threads": [
                        {
                          "title": "镜海疑云",
                          "type": "mystery",
                          "description": "第一条",
                          "main_characters": ["林澈"],
                          "locations": ["雾港"],
                          "stages": ["发现异常", "深入调查"],
                          "tension_arc": "递进",
                          "resolution": "揭开旧案"
                        },
                        {
                          "title": "镜海疑云",
                          "type": "mystery",
                          "description": "重复标题",
                          "main_characters": ["沈岚"],
                          "locations": ["钟塔区"],
                          "stages": ["误判", "反转"],
                          "tension_arc": "递进",
                          "resolution": "转向"
                        }
                      ]
                    }"""
                )
            ),
        ):
            response = await generate_plot_threads(
                SimpleNamespace(),
                story_bible.project_id,
                uuid4(),
                PlotThreadGenerationRequest(plot_type="mystery", count=2),
            )

        self.assertEqual(len(response.plot_threads), 2)
        self.assertEqual(response.plot_threads[0].title, "镜海疑云")
        self.assertNotEqual(response.plot_threads[0].title, response.plot_threads[1].title)

    async def test_generate_factions_fallback_reuses_known_leaders_and_territories(self) -> None:
        story_bible = make_story_bible()

        with patch(
            "services.entity_generation_service.load_story_bible_context",
            AsyncMock(return_value=story_bible),
        ), patch(
            "services.entity_generation_service.model_gateway.generate_text",
            AsyncMock(return_value=SimpleNamespace(content="")),
        ):
            response = await generate_factions(
                SimpleNamespace(),
                story_bible.project_id,
                uuid4(),
                FactionGenerationRequest(
                    faction_type="guild",
                    count=1,
                    existing_factions="黑钟会",
                ),
            )

        self.assertEqual(len(response.factions), 1)
        self.assertNotEqual(response.factions[0].name, "黑钟会")
        self.assertIn(response.factions[0].leader, {"林澈", "沈岚"})
        self.assertIn(response.factions[0].territory, {"雾港", "钟塔区"})
