from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from agents.story_agents import build_agent_report
from services.story_engine_workflow_service import run_realtime_guard


class StoryEngineRealtimeGuardServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_realtime_guard_returns_observable_workflow_timeline(self) -> None:
        project_id = uuid4()
        user_id = uuid4()
        guardian_issue = {
            "severity": "high",
            "title": "人设冲突",
            "detail": "主角前文明确怕水，这里却毫无迟疑地下海。",
            "source": "guardian",
            "suggestion": "补出恐惧、迟疑和必须下水的代价。",
        }
        fallback_result = {
            "guardian_report": build_agent_report(
                "guardian",
                summary="发现当前段落撞上人物边界。",
                issues=[guardian_issue],
                proposed_actions=["先补出主角对水的本能排斥。"],
            ),
            "commercial_report": build_agent_report(
                "commercial",
                summary="已经给出最小修法。",
                issues=[],
                proposed_actions=["先写主角迟疑，再让险情逼他下水。"],
            ),
            "alerts": [guardian_issue],
            "repair_options": ["先写主角迟疑，再让险情逼他下水。"],
            "arbitration_note": "这一处建议先修再继续写。",
            "should_pause": True,
        }

        with patch(
            "services.story_engine_workflow_service.get_story_engine_project",
            AsyncMock(return_value=SimpleNamespace()),
        ), patch(
            "services.story_engine_workflow_service._resolve_stream_outline_text",
            AsyncMock(return_value="主角被逼下海\n章末留下更大代价"),
        ), patch(
            "services.story_engine_workflow_service.resolve_story_engine_model_routing",
            return_value={},
        ), patch(
            "services.story_engine_workflow_service.LANGGRAPH_AVAILABLE",
            False,
        ), patch(
            "services.story_engine_workflow_service._run_realtime_guard_fallback",
            AsyncMock(return_value=fallback_result),
        ):
            result = await run_realtime_guard(
                SimpleNamespace(),
                project_id=project_id,
                user_id=user_id,
                chapter_number=7,
                chapter_title="海上夜奔",
                outline_id=None,
                current_outline="主角被逼下海\n章末留下更大代价",
                recent_chapters=["上一章已经交代主角怕水。"],
                draft_text="浪头贴着船舷炸开，主角却直接翻身跃入海里。",
                latest_paragraph="浪头贴着船舷炸开，主角却直接翻身跃入海里。",
            )

        self.assertTrue(result["should_pause"])
        self.assertEqual(
            [item["stage"] for item in result["workflow_timeline"]],
            [
                "guard_initialized",
                "guardian_review",
                "commercial_repair",
                "guard_arbitration",
            ],
        )
        self.assertEqual(result["workflow_timeline"][-1]["status"], "paused")
        self.assertEqual(
            result["workflow_timeline"][1]["details"]["blocking_alert_count"],
            1,
        )
