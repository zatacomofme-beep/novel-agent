from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from core.errors import AppError
from services.story_engine_unified_knowledge_service import (
    delete_story_knowledge,
    save_story_knowledge,
)


def _allowed_guard_result(*, warning_count: int = 0) -> dict:
    return {
        "passed": True,
        "blocked": False,
        "message": "通过",
        "alerts": [],
        "blocking_issue_count": 0,
        "warning_count": warning_count,
    }


class StoryEngineUnifiedKnowledgeServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_save_story_knowledge_routes_character_update_to_structured_kb(self) -> None:
        project_id = uuid4()
        user_id = uuid4()
        entity_id = uuid4()

        with patch(
            "services.story_engine_unified_knowledge_service.update_entity",
            AsyncMock(),
        ) as mocked_update, patch(
            "services.story_engine_unified_knowledge_service.create_entity",
            AsyncMock(),
        ) as mocked_create, patch(
            "services.story_engine_unified_knowledge_service.run_story_knowledge_guard",
            AsyncMock(return_value=_allowed_guard_result()),
        ) as mocked_guard:
            result = await save_story_knowledge(
                SimpleNamespace(),
                project_id=project_id,
                user_id=user_id,
                section_key="characters",
                entity_id=str(entity_id),
                item={
                    "name": "林澈",
                    "personality": "警惕而克制",
                    "status": "active",
                    "arc_stage": "initial",
                },
            )

        mocked_guard.assert_awaited_once()
        mocked_create.assert_not_awaited()
        payload = mocked_update.await_args.kwargs["payload"]
        self.assertEqual(mocked_update.await_args.kwargs["entity_type"], "characters")
        self.assertEqual(mocked_update.await_args.kwargs["entity_id"], entity_id)
        self.assertEqual(payload["name"], "林澈")
        self.assertEqual(payload["personality"], "警惕而克制")
        self.assertEqual(result["message"], "这条设定已保存，并通过守护校验。")

    async def test_save_story_knowledge_routes_location_update_to_story_bible(self) -> None:
        project_id = uuid4()
        user_id = uuid4()
        branch_id = uuid4()
        project = SimpleNamespace(id=project_id, branches=[SimpleNamespace(id=branch_id)])

        with patch(
            "services.story_engine_unified_knowledge_service.get_owned_project",
            AsyncMock(return_value=project),
        ), patch(
            "services.story_engine_unified_knowledge_service.upsert_story_bible_branch_item",
            AsyncMock(),
        ) as mocked_upsert, patch(
            "services.story_engine_unified_knowledge_service.delete_story_bible_branch_item",
            AsyncMock(),
        ) as mocked_delete, patch(
            "services.story_engine_unified_knowledge_service.run_story_knowledge_guard",
            AsyncMock(return_value=_allowed_guard_result(warning_count=1)),
        ) as mocked_guard:
            result = await save_story_knowledge(
                SimpleNamespace(),
                project_id=project_id,
                user_id=user_id,
                section_key="locations",
                branch_id=branch_id,
                previous_entity_key="name:旧港口",
                item={
                    "name": "新港口",
                    "data": {
                        "type": "harbor",
                        "climate": "潮湿多雾",
                    },
                    "version": 1,
                },
            )

        mocked_guard.assert_awaited_once()
        upsert_payload = mocked_upsert.await_args.args[2]
        delete_payload = mocked_delete.await_args.args[2]
        self.assertEqual(upsert_payload.section_key, "locations")
        self.assertEqual(upsert_payload.item["name"], "新港口")
        self.assertEqual(delete_payload.section_key, "locations")
        self.assertEqual(delete_payload.entity_key, "name:旧港口")
        self.assertIn("连续性提醒", result["message"])

    async def test_delete_story_knowledge_routes_structured_section_to_entity_delete(self) -> None:
        project_id = uuid4()
        user_id = uuid4()
        entity_id = uuid4()

        with patch(
            "services.story_engine_unified_knowledge_service.delete_entity",
            AsyncMock(),
        ) as mocked_delete, patch(
            "services.story_engine_unified_knowledge_service.run_story_knowledge_guard",
            AsyncMock(return_value=_allowed_guard_result()),
        ) as mocked_guard:
            result = await delete_story_knowledge(
                SimpleNamespace(),
                project_id=project_id,
                user_id=user_id,
                section_key="world_rules",
                entity_id=str(entity_id),
            )

        mocked_guard.assert_awaited_once()
        self.assertEqual(mocked_delete.await_args.kwargs["entity_type"], "world_rules")
        self.assertEqual(mocked_delete.await_args.kwargs["entity_id"], entity_id)
        self.assertEqual(result["message"], "这条设定已删除，并通过守护校验。")

    async def test_save_story_knowledge_raises_when_guard_blocks(self) -> None:
        project_id = uuid4()
        user_id = uuid4()

        with patch(
            "services.story_engine_unified_knowledge_service.run_story_knowledge_guard",
            AsyncMock(
                return_value={
                    "passed": False,
                    "blocked": True,
                    "message": "这条设定暂时不能直接保存，先修掉核心冲突再继续。",
                    "alerts": [
                        {
                            "severity": "high",
                            "title": "人物重名会冲掉设定锚点",
                            "detail": "已有重名人物。",
                            "source": "guardian",
                            "suggestion": "改名。",
                        }
                    ],
                    "blocking_issue_count": 1,
                    "warning_count": 0,
                }
            ),
        ), patch(
            "services.story_engine_unified_knowledge_service.create_entity",
            AsyncMock(),
        ) as mocked_create:
            with self.assertRaises(AppError) as raised:
                await save_story_knowledge(
                    SimpleNamespace(),
                    project_id=project_id,
                    user_id=user_id,
                    section_key="characters",
                    item={
                        "name": "林澈",
                        "personality": "警惕而克制",
                        "status": "active",
                        "arc_stage": "initial",
                    },
                )

        mocked_create.assert_not_awaited()
        self.assertEqual(raised.exception.code, "story_engine.knowledge_guard_blocked")

    async def test_delete_story_knowledge_raises_when_guard_blocks(self) -> None:
        project_id = uuid4()
        user_id = uuid4()
        entity_id = uuid4()

        with patch(
            "services.story_engine_unified_knowledge_service.run_story_knowledge_guard",
            AsyncMock(
                return_value={
                    "passed": False,
                    "blocked": True,
                    "message": "这条设定暂时不能直接删除，先处理悬空引用再继续。",
                    "alerts": [],
                    "blocking_issue_count": 1,
                    "warning_count": 0,
                }
            ),
        ), patch(
            "services.story_engine_unified_knowledge_service.delete_entity",
            AsyncMock(),
        ) as mocked_delete:
            with self.assertRaises(AppError) as raised:
                await delete_story_knowledge(
                    SimpleNamespace(),
                    project_id=project_id,
                    user_id=user_id,
                    section_key="world_rules",
                    entity_id=str(entity_id),
                )

        mocked_delete.assert_not_awaited()
        self.assertEqual(raised.exception.code, "story_engine.knowledge_guard_blocked")
