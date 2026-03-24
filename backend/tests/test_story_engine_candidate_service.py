from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from core.errors import AppError
from services.story_engine_candidate_service import accept_generated_candidate


class StoryEngineCandidateServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_accept_generated_character_candidate_creates_story_entity(self) -> None:
        project_id = uuid4()
        user_id = uuid4()
        task_run = SimpleNamespace(
            task_id="task-entity-accept-1",
            project_id=project_id,
            result={
                "generation_type": "characters",
                "characters": [
                    {
                        "name": "林雾",
                        "role": "supporting",
                        "appearance": "总穿深灰风衣",
                        "personality": "冷静警觉",
                        "background": "曾在旧档案馆工作",
                        "motivation": "查清姐姐失踪的真相",
                        "conflict": "越靠近真相越会暴露自己",
                        "relationships": ["与林澈互相试探"],
                    }
                ],
            },
        )
        created_entity = SimpleNamespace(character_id=uuid4(), name="林雾")

        with patch(
            "services.story_engine_candidate_service.get_story_engine_project",
            AsyncMock(),
        ), patch(
            "services.story_engine_candidate_service.get_task_run_by_task_id",
            AsyncMock(return_value=task_run),
        ), patch(
            "services.story_engine_candidate_service.task_state_store.get",
            return_value=None,
        ), patch(
            "services.story_engine_candidate_service._ensure_name_not_exists",
            AsyncMock(),
        ), patch(
            "services.story_engine_candidate_service.create_entity",
            AsyncMock(return_value=created_entity),
        ) as mocked_create:
            result = await accept_generated_candidate(
                SimpleNamespace(),
                project_id=project_id,
                user_id=user_id,
                task_id="task-entity-accept-1",
                candidate_index=0,
            )

        payload = mocked_create.await_args.kwargs["payload"]
        self.assertEqual(payload["name"], "林雾")
        self.assertEqual(payload["personality"], "冷静警觉")
        self.assertEqual(payload["abilities"]["seed_role"], "supporting")
        self.assertEqual(result["accepted_entity_type"], "characters")
        self.assertEqual(result["accepted_entity_label"], "林雾")

    async def test_accept_generated_item_candidate_rejects_duplicate(self) -> None:
        project_id = uuid4()
        user_id = uuid4()
        task_run = SimpleNamespace(
            task_id="task-entity-accept-2",
            project_id=project_id,
            result={
                "generation_type": "items",
                "items": [
                    {
                        "name": "潮纹短刃",
                        "type": "weapon",
                        "rarity": "稀有",
                        "description": "能切开封存的记忆层。",
                        "effects": ["切开封存记忆"],
                        "owner": "林澈",
                    }
                ],
            },
        )

        with patch(
            "services.story_engine_candidate_service.get_story_engine_project",
            AsyncMock(),
        ), patch(
            "services.story_engine_candidate_service.get_task_run_by_task_id",
            AsyncMock(return_value=task_run),
        ), patch(
            "services.story_engine_candidate_service.task_state_store.get",
            return_value=None,
        ), patch(
            "services.story_engine_candidate_service._ensure_name_not_exists",
            AsyncMock(side_effect=AppError(code="dup", message="duplicate", status_code=409)),
        ):
            with self.assertRaises(AppError) as raised:
                await accept_generated_candidate(
                    SimpleNamespace(),
                    project_id=project_id,
                    user_id=user_id,
                    task_id="task-entity-accept-2",
                    candidate_index=0,
                )

        self.assertEqual(raised.exception.status_code, 409)

    async def test_accept_generated_location_candidate_upserts_story_bible_section(self) -> None:
        project_id = uuid4()
        user_id = uuid4()
        branch_id = uuid4()
        task_run = SimpleNamespace(
            task_id="task-entity-accept-3",
            project_id=project_id,
            result={
                "generation_type": "locations",
                "locations": [
                    {
                        "name": "雾港",
                        "type": "city",
                        "climate": "终年潮湿",
                        "description": "情报与潮痕交易最密集的港城。",
                        "features": ["夜间会出现异常潮汐"],
                    }
                ],
            },
        )
        project = SimpleNamespace(id=project_id, branches=[SimpleNamespace(id=branch_id)])

        with patch(
            "services.story_engine_candidate_service.get_owned_project",
            AsyncMock(return_value=project),
        ), patch(
            "services.story_engine_candidate_service.get_task_run_by_task_id",
            AsyncMock(return_value=task_run),
        ), patch(
            "services.story_engine_candidate_service.task_state_store.get",
            return_value=None,
        ), patch(
            "services.story_engine_candidate_service.upsert_story_bible_branch_item",
            AsyncMock(),
        ):
            result = await accept_generated_candidate(
                SimpleNamespace(),
                project_id=project_id,
                user_id=user_id,
                task_id="task-entity-accept-3",
                candidate_index=0,
                branch_id=branch_id,
            )

        self.assertEqual(result["accepted_entity_type"], "locations")
        self.assertEqual(result["accepted_entity_label"], "雾港")
        self.assertEqual(result["accepted_entity_key"], "name:雾港")
        self.assertEqual(result["branch_id"], branch_id)
