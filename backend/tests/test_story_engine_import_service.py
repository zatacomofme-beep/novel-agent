from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from core.errors import AppError
from schemas.story_engine import StoryBulkImportPayload, StoryBulkImportResponse
from services.story_engine_import_service import bulk_import_story_payload


def _ok_mutation_result(*, warning_count: int = 0, alerts: list[dict] | None = None) -> dict:
    return {
        "passed": True,
        "blocked": False,
        "message": "通过",
        "alerts": alerts or [],
        "blocking_issue_count": 0,
        "warning_count": warning_count,
    }


class _TaskCapableSession:
    def add(self, *_args, **_kwargs) -> None:
        return None

    async def flush(self) -> None:
        return None

    async def commit(self) -> None:
        return None


class StoryEngineImportServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_bulk_import_routes_structured_sections_through_guarded_save(self) -> None:
        project_id = uuid4()
        user_id = uuid4()
        payload = StoryBulkImportPayload.model_validate(
            {
                "characters": [
                    {
                        "name": "林澈",
                        "appearance": None,
                        "personality": "警惕而克制",
                        "micro_habits": [],
                        "abilities": {},
                        "relationships": [],
                        "status": "active",
                        "arc_stage": "initial",
                        "arc_boundaries": [],
                    }
                ]
            }
        )

        with patch(
            "services.story_engine_import_service.get_story_engine_project",
            AsyncMock(return_value=SimpleNamespace()),
        ), patch(
            "services.story_engine_import_service._resolve_import_branch_id",
            AsyncMock(return_value=uuid4()),
        ), patch(
            "services.story_engine_import_service.run_story_bulk_import_guard",
            AsyncMock(return_value=_ok_mutation_result()),
        ), patch(
            "services.story_engine_import_service._find_by_field",
            AsyncMock(return_value=None),
        ), patch(
            "services.story_engine_import_service.save_story_knowledge",
            AsyncMock(return_value=_ok_mutation_result()),
        ) as mocked_save:
            result = await bulk_import_story_payload(
                SimpleNamespace(),
                project_id=project_id,
                user_id=user_id,
                payload=payload,
                replace_existing_sections=[],
            )

        dumped = StoryBulkImportResponse.model_validate(result).model_dump(mode="json")
        self.assertEqual(result["imported_counts"]["characters"], 1)
        self.assertEqual(dumped["workflow_timeline"][0]["stage"], "bulk_import_started")
        self.assertEqual(dumped["workflow_timeline"][-1]["stage"], "bulk_import_completed")
        save_kwargs = mocked_save.await_args.kwargs
        self.assertEqual(save_kwargs["section_key"], "characters")
        self.assertEqual(save_kwargs["source_workflow"], "bulk_import")
        self.assertEqual(save_kwargs["guard_operation"], "导入")
        self.assertTrue(save_kwargs["skip_guard"])

    async def test_bulk_import_replace_deletes_stale_entities_via_guarded_delete(self) -> None:
        project_id = uuid4()
        user_id = uuid4()
        keep_id = uuid4()
        stale_id = uuid4()
        payload = StoryBulkImportPayload.model_validate(
            {
                "characters": [
                    {
                        "name": "林澈",
                        "appearance": None,
                        "personality": "警惕而克制",
                        "micro_habits": [],
                        "abilities": {},
                        "relationships": [],
                        "status": "active",
                        "arc_stage": "initial",
                        "arc_boundaries": [],
                    }
                ]
            }
        )
        keep_character = SimpleNamespace(character_id=keep_id, name="林澈")
        stale_character = SimpleNamespace(character_id=stale_id, name="沈夜")

        with patch(
            "services.story_engine_import_service.get_story_engine_project",
            AsyncMock(return_value=SimpleNamespace()),
        ), patch(
            "services.story_engine_import_service._resolve_import_branch_id",
            AsyncMock(return_value=uuid4()),
        ), patch(
            "services.story_engine_import_service.run_story_bulk_import_guard",
            AsyncMock(return_value=_ok_mutation_result()),
        ), patch(
            "services.story_engine_import_service.list_entities",
            AsyncMock(return_value=[keep_character, stale_character]),
        ), patch(
            "services.story_engine_import_service._find_by_field",
            AsyncMock(return_value=keep_character),
        ), patch(
            "services.story_engine_import_service.save_story_knowledge",
            AsyncMock(return_value=_ok_mutation_result()),
        ) as mocked_save, patch(
            "services.story_engine_import_service.delete_story_knowledge",
            AsyncMock(return_value=_ok_mutation_result()),
        ) as mocked_delete:
            result = await bulk_import_story_payload(
                SimpleNamespace(),
                project_id=project_id,
                user_id=user_id,
                payload=payload,
                replace_existing_sections=["characters"],
            )

        self.assertEqual(result["replaced_sections"], ["characters"])
        self.assertEqual(mocked_save.await_count, 1)
        delete_kwargs = mocked_delete.await_args.kwargs
        self.assertEqual(delete_kwargs["section_key"], "characters")
        self.assertEqual(delete_kwargs["entity_id"], str(stale_id))
        self.assertEqual(delete_kwargs["source_workflow"], "bulk_import")

    async def test_bulk_import_preserves_locked_level1_outline(self) -> None:
        project_id = uuid4()
        user_id = uuid4()
        locked_outline = SimpleNamespace(
            outline_id=uuid4(),
            title="现有主线圣经",
            level="level_1",
            locked=True,
        )
        payload = StoryBulkImportPayload.model_validate(
            {
                "outlines": [
                    {
                        "level": "level_1",
                        "title": "模板主线圣经",
                        "content": "新的模板主线",
                        "status": "todo",
                        "node_order": 1,
                        "locked": True,
                        "immutable_reason": "一级大纲导入后自动锁定。",
                    }
                ]
            }
        )

        with patch(
            "services.story_engine_import_service.get_story_engine_project",
            AsyncMock(return_value=SimpleNamespace()),
        ), patch(
            "services.story_engine_import_service._resolve_import_branch_id",
            AsyncMock(return_value=uuid4()),
        ), patch(
            "services.story_engine_import_service.run_story_bulk_import_guard",
            AsyncMock(return_value=_ok_mutation_result()),
        ), patch(
            "services.story_engine_import_service._find_outline",
            AsyncMock(return_value=None),
        ), patch(
            "services.story_engine_import_service._find_any_level_1_outline",
            AsyncMock(return_value=locked_outline),
        ), patch(
            "services.story_engine_import_service.save_story_knowledge",
            AsyncMock(return_value=_ok_mutation_result()),
        ) as mocked_save:
            result = await bulk_import_story_payload(
                SimpleNamespace(),
                project_id=project_id,
                user_id=user_id,
                payload=payload,
                replace_existing_sections=[],
            )

        mocked_save.assert_not_awaited()
        self.assertEqual(result["imported_counts"]["outlines"], 1)
        self.assertTrue(any("已锁定" in item for item in result["warnings"]))

    async def test_bulk_import_stops_when_preflight_guard_blocks(self) -> None:
        project_id = uuid4()
        user_id = uuid4()
        payload = StoryBulkImportPayload.model_validate(
            {
                "characters": [
                    {
                        "name": "林澈",
                        "appearance": None,
                        "personality": "警惕而克制",
                        "micro_habits": [],
                        "abilities": {},
                        "relationships": [],
                        "status": "active",
                        "arc_stage": "initial",
                        "arc_boundaries": [],
                    }
                ]
            }
        )

        blocked_result = {
            "passed": False,
            "blocked": True,
            "message": "这批设定暂时不能导入。",
            "alerts": [{"severity": "high", "title": "缺少世界规则"}],
            "blocking_issue_count": 1,
            "warning_count": 0,
        }

        with patch(
            "services.story_engine_import_service.get_story_engine_project",
            AsyncMock(return_value=SimpleNamespace()),
        ), patch(
            "services.story_engine_import_service._resolve_import_branch_id",
            AsyncMock(return_value=uuid4()),
        ), patch(
            "services.story_engine_import_service.run_story_bulk_import_guard",
            AsyncMock(return_value=blocked_result),
        ), patch(
            "services.story_engine_import_service.save_story_knowledge",
            AsyncMock(return_value=_ok_mutation_result()),
        ) as mocked_save:
            with self.assertRaises(AppError):
                await bulk_import_story_payload(
                    SimpleNamespace(),
                    project_id=project_id,
                    user_id=user_id,
                    payload=payload,
                    replace_existing_sections=[],
                )

        mocked_save.assert_not_awaited()

    async def test_bulk_import_persists_task_run_and_events_when_session_supports_it(self) -> None:
        project_id = uuid4()
        user_id = uuid4()
        payload = StoryBulkImportPayload.model_validate(
            {
                "characters": [
                    {
                        "name": "林澈",
                        "appearance": None,
                        "personality": "警惕而克制",
                        "micro_habits": [],
                        "abilities": {},
                        "relationships": [],
                        "status": "active",
                        "arc_stage": "initial",
                        "arc_boundaries": [],
                    }
                ],
                "world_rules": [
                    {
                        "rule_name": "越级爆发必有代价",
                        "rule_content": "任何越级都要付出真实代价。",
                        "negative_list": ["无代价爆发"],
                        "scope": "battle",
                    }
                ],
            }
        )
        create_task_run_mock = AsyncMock()
        persist_task_event_mock = AsyncMock()

        with patch(
            "services.story_engine_import_service.get_story_engine_project",
            AsyncMock(return_value=SimpleNamespace()),
        ), patch(
            "services.story_engine_import_service._resolve_import_branch_id",
            AsyncMock(return_value=uuid4()),
        ), patch(
            "services.story_engine_import_service.run_story_bulk_import_guard",
            AsyncMock(return_value=_ok_mutation_result()),
        ), patch(
            "services.story_engine_import_service._find_by_field",
            AsyncMock(return_value=None),
        ), patch(
            "services.story_engine_import_service.save_story_knowledge",
            AsyncMock(return_value=_ok_mutation_result()),
        ), patch(
            "services.story_engine_workflow_service.create_task_run",
            create_task_run_mock,
        ), patch(
            "services.story_engine_import_service._persist_workflow_task_event",
            persist_task_event_mock,
        ):
            result = await bulk_import_story_payload(
                _TaskCapableSession(),
                project_id=project_id,
                user_id=user_id,
                payload=payload,
                replace_existing_sections=[],
            )

        self.assertEqual(create_task_run_mock.await_count, 1)
        self.assertEqual(
            persist_task_event_mock.await_count,
            len(result["workflow_timeline"]),
        )
        self.assertEqual(result["workflow_timeline"][-1]["stage"], "bulk_import_completed")
