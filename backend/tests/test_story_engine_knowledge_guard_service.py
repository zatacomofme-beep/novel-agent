from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from agents.story_agents import build_agent_report
from services.story_engine_workflow_service import run_story_knowledge_guard


def _clean_guardian_report() -> dict:
    return build_agent_report(
        "guardian",
        summary="已完成设定修改前校验。",
        issues=[],
        proposed_actions=["当前改动可以写入设定圣经。"],
    )


class StoryEngineKnowledgeGuardServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_delete_last_world_rule_is_blocked_by_fallback_guard(self) -> None:
        project_id = uuid4()
        user_id = uuid4()
        rule_id = uuid4()
        workspace = {
            "project": {
                "project_id": project_id,
                "title": "潮汐档案",
                "genre": "都市异能",
                "theme": "代价与真相",
                "tone": "冷峻悬疑",
            },
            "characters": [],
            "foreshadows": [],
            "items": [],
            "world_rules": [
                SimpleNamespace(
                    rule_id=rule_id,
                    rule_name="潮汐回响必须支付代价",
                    rule_content="每次使用能力都会损耗记忆。",
                )
            ],
            "timeline_events": [],
            "outlines": [],
            "chapter_summaries": [],
            "story_bible": {
                "locations": [],
                "factions": [],
                "plot_threads": [],
            },
        }

        with patch(
            "services.story_engine_workflow_service.get_story_engine_project",
            AsyncMock(return_value=SimpleNamespace()),
        ), patch(
            "services.story_engine_workflow_service.build_workspace",
            AsyncMock(return_value=workspace),
        ), patch(
            "services.story_engine_workflow_service.resolve_story_engine_model_routing",
            return_value={"guardian": {"model": "gpt-5.4", "reasoning_effort": "high"}},
        ), patch(
            "services.story_engine_workflow_service._run_guardian_consensus_report",
            AsyncMock(return_value=_clean_guardian_report()),
        ):
            result = await run_story_knowledge_guard(
                SimpleNamespace(),
                project_id=project_id,
                user_id=user_id,
                section_key="world_rules",
                operation="删除",
                candidate_item={},
                entity_id=str(rule_id),
            )

        self.assertTrue(result["blocked"])
        self.assertEqual(result["blocking_issue_count"], 1)
        self.assertEqual(result["alerts"][0]["title"], "至少保留一条世界规则")

    async def test_delete_last_character_is_blocked_by_fallback_guard(self) -> None:
        project_id = uuid4()
        user_id = uuid4()
        character_id = uuid4()
        workspace = {
            "project": {
                "project_id": project_id,
                "title": "潮汐档案",
                "genre": "都市异能",
                "theme": "代价与真相",
                "tone": "冷峻悬疑",
            },
            "characters": [
                SimpleNamespace(
                    character_id=character_id,
                    name="林澈",
                    personality="警惕而克制",
                    status="active",
                    arc_stage="initial",
                    relationships=[],
                )
            ],
            "foreshadows": [],
            "items": [],
            "world_rules": [
                SimpleNamespace(
                    rule_id=uuid4(),
                    rule_name="潮汐回响必须支付代价",
                    rule_content="每次使用能力都会损耗记忆。",
                )
            ],
            "timeline_events": [],
            "outlines": [],
            "chapter_summaries": [],
            "story_bible": {
                "locations": [],
                "factions": [],
                "plot_threads": [],
            },
        }

        with patch(
            "services.story_engine_workflow_service.get_story_engine_project",
            AsyncMock(return_value=SimpleNamespace()),
        ), patch(
            "services.story_engine_workflow_service.build_workspace",
            AsyncMock(return_value=workspace),
        ), patch(
            "services.story_engine_workflow_service.resolve_story_engine_model_routing",
            return_value={"guardian": {"model": "gpt-5.4", "reasoning_effort": "high"}},
        ), patch(
            "services.story_engine_workflow_service._run_guardian_consensus_report",
            AsyncMock(return_value=_clean_guardian_report()),
        ):
            result = await run_story_knowledge_guard(
                SimpleNamespace(),
                project_id=project_id,
                user_id=user_id,
                section_key="characters",
                operation="删除",
                candidate_item={},
                entity_id=str(character_id),
            )

        self.assertTrue(result["blocked"])
        self.assertEqual(result["blocking_issue_count"], 1)
        self.assertEqual(result["alerts"][0]["title"], "至少保留一个人物锚点")
