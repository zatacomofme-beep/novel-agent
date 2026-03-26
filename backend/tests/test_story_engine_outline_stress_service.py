from __future__ import annotations

import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from agents.story_agents import build_agent_report
from schemas.story_engine import OutlineStressTestResponse
from services.story_engine_workflow_service import run_outline_stress_test


class _TaskCapableSession:
    def add(self, *_args, **_kwargs) -> None:
        return None

    async def flush(self) -> None:
        return None

    async def commit(self) -> None:
        return None


def _outline_entity(*, level: str, title: str) -> SimpleNamespace:
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        outline_id=uuid4(),
        project_id=uuid4(),
        branch_id=uuid4(),
        parent_id=None,
        level=level,
        title=title,
        content=f"{title}内容",
        status="todo",
        version=1,
        node_order=1,
        locked=level == "level_1",
        immutable_reason="主线锁定" if level == "level_1" else None,
        created_at=now,
        updated_at=now,
    )


def _character_entity() -> SimpleNamespace:
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        character_id=uuid4(),
        project_id=uuid4(),
        name="林澈",
        appearance="肩背旧伤",
        personality="克制警惕",
        micro_habits=["压怒时会摩挲指节"],
        abilities={"core": "燃命秘法"},
        relationships=[],
        status="active",
        arc_stage="initial",
        arc_boundaries=[],
        version=1,
        created_at=now,
        updated_at=now,
    )


class StoryEngineOutlineStressServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_outline_stress_test_returns_serializable_initial_kb(self) -> None:
        project_id = uuid4()
        user_id = uuid4()
        fallback_result = {
            "outline_draft": {
                "level_1": [{"level": "level_1", "title": "主线圣经", "content": "主线", "status": "todo", "node_order": 1, "locked": True}],
                "level_2": [{"level": "level_2", "title": "卷一", "content": "卷一内容", "status": "todo", "node_order": 1}],
                "level_3": [{"level": "level_3", "title": "第一章", "content": "章纲", "status": "todo", "node_order": 1}],
            },
            "initial_kb": {
                "characters": [{"name": "林澈"}],
                "foreshadows": [],
                "items": [],
                "world_rules": [],
                "timeline_events": [],
            },
            "guardian_report": build_agent_report("guardian", summary="guardian", issues=[], proposed_actions=[]),
            "commercial_report": build_agent_report("commercial", summary="commercial", issues=[], proposed_actions=[]),
            "logic_report": build_agent_report("logic_debunker", summary="logic", issues=[], proposed_actions=[]),
            "arbitrated_report": build_agent_report("arbitrator", summary="arbitrator", issues=[], proposed_actions=[]),
            "optimization_plan": ["锁定主线圣经"],
            "debate_round": 1,
        }
        persisted_result = {
            "outlines": [
                _outline_entity(level="level_1", title="主线圣经"),
                _outline_entity(level="level_2", title="卷一"),
                _outline_entity(level="level_3", title="第一章"),
            ],
            "initial_kb": {
                "characters": [_character_entity()],
                "foreshadows": [],
                "items": [],
                "world_rules": [],
                "timeline_events": [],
            },
        }

        with patch(
            "services.story_engine_workflow_service.get_story_engine_project",
            AsyncMock(return_value=SimpleNamespace()),
        ), patch(
            "services.story_engine_workflow_service.resolve_story_engine_model_routing",
            return_value={"guardian": {"model": "gpt-5.4", "reasoning_effort": "high"}},
        ), patch(
            "services.story_engine_workflow_service.LANGGRAPH_AVAILABLE",
            False,
        ), patch(
            "services.story_engine_workflow_service._run_outline_stress_fallback",
            AsyncMock(return_value=fallback_result),
        ), patch(
            "services.story_engine_workflow_service._persist_outline_stress_result",
            AsyncMock(return_value=persisted_result),
        ):
            result = await run_outline_stress_test(
                SimpleNamespace(),
                project_id=project_id,
                user_id=user_id,
                branch_id=None,
                idea="一个被宗门舍弃的少年，每次越级爆发都要失去记忆。",
                source_material=None,
                source_material_name=None,
                genre="玄幻",
                tone="热血压迫感",
                target_chapter_count=10,
                target_total_words=50000,
            )

        dumped = OutlineStressTestResponse.model_validate(result).model_dump(mode="json")
        self.assertEqual(dumped["locked_level_1_outlines"][0]["level"], "level_1")
        self.assertEqual(dumped["initial_knowledge_base"]["characters"][0]["name"], "林澈")
        self.assertIsInstance(dumped["initial_knowledge_base"]["characters"][0], dict)
        self.assertEqual(dumped["workflow_timeline"][0]["stage"], "outline_stress_started")
        self.assertEqual(dumped["workflow_timeline"][-1]["stage"], "outline_stress_completed")
        self.assertIn(
            "outline_persisted",
            [item["stage"] for item in dumped["workflow_timeline"]],
        )

    async def test_outline_stress_test_persists_task_run_and_events_when_session_supports_it(self) -> None:
        project_id = uuid4()
        user_id = uuid4()
        fallback_result = {
            "outline_draft": {
                "level_1": [{"level": "level_1", "title": "主线圣经", "content": "主线", "status": "todo", "node_order": 1, "locked": True}],
                "level_2": [{"level": "level_2", "title": "卷一", "content": "卷一内容", "status": "todo", "node_order": 1}],
                "level_3": [{"level": "level_3", "title": "第一章", "content": "章纲", "status": "todo", "node_order": 1}],
            },
            "initial_kb": {
                "characters": [{"name": "林澈"}],
                "foreshadows": [],
                "items": [],
                "world_rules": [],
                "timeline_events": [],
            },
            "guardian_report": build_agent_report("guardian", summary="guardian", issues=[], proposed_actions=[]),
            "commercial_report": build_agent_report("commercial", summary="commercial", issues=[], proposed_actions=[]),
            "logic_report": build_agent_report("logic_debunker", summary="logic", issues=[], proposed_actions=[]),
            "arbitrated_report": build_agent_report("arbitrator", summary="arbitrator", issues=[], proposed_actions=[]),
            "optimization_plan": ["锁定主线圣经"],
            "debate_round": 1,
        }
        persisted_result = {
            "outlines": [
                _outline_entity(level="level_1", title="主线圣经"),
                _outline_entity(level="level_2", title="卷一"),
                _outline_entity(level="level_3", title="第一章"),
            ],
            "initial_kb": {
                "characters": [_character_entity()],
                "foreshadows": [],
                "items": [],
                "world_rules": [],
                "timeline_events": [],
            },
        }
        create_task_run_mock = AsyncMock()
        persist_task_event_mock = AsyncMock()

        with patch(
            "services.story_engine_workflow_service.get_story_engine_project",
            AsyncMock(return_value=SimpleNamespace()),
        ), patch(
            "services.story_engine_workflow_service.resolve_story_engine_model_routing",
            return_value={"guardian": {"model": "gpt-5.4", "reasoning_effort": "high"}},
        ), patch(
            "services.story_engine_workflow_service.LANGGRAPH_AVAILABLE",
            False,
        ), patch(
            "services.story_engine_workflow_service._run_outline_stress_fallback",
            AsyncMock(return_value=fallback_result),
        ), patch(
            "services.story_engine_workflow_service._persist_outline_stress_result",
            AsyncMock(return_value=persisted_result),
        ), patch(
            "services.story_engine_workflow_service.create_task_run",
            create_task_run_mock,
        ), patch(
            "services.story_engine_workflow_service._persist_workflow_task_event",
            persist_task_event_mock,
        ):
            result = await run_outline_stress_test(
                _TaskCapableSession(),
                project_id=project_id,
                user_id=user_id,
                branch_id=None,
                idea="一个被宗门舍弃的少年，每次越级爆发都要失去记忆。",
                source_material=None,
                source_material_name=None,
                genre="玄幻",
                tone="热血压迫感",
                target_chapter_count=10,
                target_total_words=50000,
            )

        self.assertEqual(create_task_run_mock.await_count, 1)
        self.assertEqual(
            persist_task_event_mock.await_count,
            len(result["workflow_timeline"]),
        )
