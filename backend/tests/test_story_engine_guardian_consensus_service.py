from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from agents.story_agents import build_agent_report
from services.story_engine_workflows._shared import _run_guardian_consensus_report


class StoryEngineGuardianConsensusServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_dual_guardian_returns_consensus_when_two_models_agree(self) -> None:
        primary_report = build_agent_report(
            "guardian",
            summary="主守护已完成检查。",
            issues=[
                {
                    "severity": "high",
                    "title": "主角疑似 OOC",
                    "detail": "这一段让主角无铺垫地违背核心禁区。",
                    "source": "guardian",
                    "suggestion": "补出心理挣扎和代价。",
                }
            ],
            proposed_actions=["补出心理挣扎和代价。"],
        )
        shadow_report = build_agent_report(
            "guardian",
            summary="副守护已完成检查。",
            issues=[
                {
                    "severity": "high",
                    "title": "主角疑似 OOC",
                    "detail": "这一段让主角无铺垫地违背核心禁区。",
                    "source": "guardian",
                    "suggestion": "补出心理挣扎和代价。",
                }
            ],
            proposed_actions=["补出心理挣扎和代价。"],
        )

        with patch(
            "services.story_engine_workflow_service.get_story_engine_guardian_consensus_config",
            return_value={
                "enabled": True,
                "shadow_model": "gemini-3.1-pro-preview",
                "shadow_reasoning_effort": "high",
                "outline_enabled": True,
                "realtime_enabled": True,
                "final_enabled": True,
            },
        ), patch(
            "services.story_engine_workflow_service.generate_story_agent_report",
            AsyncMock(side_effect=[primary_report, shadow_report]),
        ) as report_mock:
            result = await _run_guardian_consensus_report(
                task_name="story_engine.realtime_guardian",
                task_goal="检查最新段落是否存在设定冲突。",
                context="正文：主角突然跳海。",
                fallback_report=build_agent_report(
                    "guardian",
                    summary="fallback",
                    issues=[],
                    proposed_actions=[],
                ),
                model_routing={"guardian": {"model": "gpt-5.4", "reasoning_effort": "high"}},
                workflow_key="realtime",
                workflow_label="实时守护",
            )

        self.assertEqual(result["summary"], "双模型设定守护已完成交叉校验，实时守护阶段结论一致。")
        self.assertEqual(len(result["issues"]), 1)
        self.assertFalse(result["raw_output"]["disagreement"])
        self.assertEqual(result["raw_output"]["guardian_primary_model"], "gpt-5.4")
        self.assertEqual(result["raw_output"]["guardian_shadow_model"], "gemini-3.1-pro-preview")
        self.assertEqual(report_mock.await_count, 2)

    async def test_guardian_disagreement_triggers_logic_tiebreak(self) -> None:
        primary_report = build_agent_report(
            "guardian",
            summary="主守护认为这里有硬冲突。",
            issues=[
                {
                    "severity": "high",
                    "title": "主角疑似 OOC",
                    "detail": "这一段让主角无铺垫地违背核心禁区。",
                    "source": "guardian",
                    "suggestion": "补出心理挣扎和代价。",
                }
            ],
            proposed_actions=["补出心理挣扎和代价。"],
        )
        shadow_report = build_agent_report(
            "guardian",
            summary="副守护认为目前还能成立。",
            issues=[],
            proposed_actions=["可以继续，但要盯住下一段。"],
        )
        tiebreak_report = build_agent_report(
            "logic_debunker",
            summary="第三方复核后认定这里确实会炸。",
            issues=[
                {
                    "severity": "high",
                    "title": "角色动机断裂",
                    "detail": "前文没有给足刺激，这里直接跳海会断掉因果链。",
                    "source": "logic_debunker",
                    "suggestion": "先补一个触发点，再让主角下水。",
                }
            ],
            proposed_actions=["先补一个触发点，再让主角下水。"],
        )

        with patch(
            "services.story_engine_workflow_service.get_story_engine_guardian_consensus_config",
            return_value={
                "enabled": True,
                "shadow_model": "gemini-3.1-pro-preview",
                "shadow_reasoning_effort": "high",
                "outline_enabled": True,
                "realtime_enabled": True,
                "final_enabled": True,
            },
        ), patch(
            "services.story_engine_workflow_service.generate_story_agent_report",
            AsyncMock(side_effect=[primary_report, shadow_report, tiebreak_report]),
        ) as report_mock:
            result = await _run_guardian_consensus_report(
                task_name="story_engine.realtime_guardian",
                task_goal="检查最新段落是否存在设定冲突。",
                context="正文：主角突然跳海。",
                fallback_report=build_agent_report(
                    "guardian",
                    summary="fallback",
                    issues=[],
                    proposed_actions=[],
                ),
                model_routing={"guardian": {"model": "gpt-5.4", "reasoning_effort": "high"}},
                workflow_key="realtime",
                workflow_label="实时守护",
            )

        self.assertTrue(result["raw_output"]["disagreement"])
        self.assertEqual(len(result["issues"]), 1)
        self.assertEqual(result["issues"][0]["title"], "角色动机断裂")
        self.assertIn("逻辑挑刺复核", result["summary"])
        self.assertEqual(report_mock.await_count, 3)
